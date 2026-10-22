from django.db import models
from django.db.models import Q
from django.core.cache import cache
from rest_framework import viewsets, generics, permissions, status
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.core.files.storage import default_storage
import boto3
from botocore.config import Config
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import Http404

from github_integration.models import GitHubMeta
from .models import Project, ProjectScreenshot, Like, Comment, SourceSnippet, ProjectView, Bookmark, Category, Tag
from .serializers import (
    ProjectListSerializer,
    ProjectDetailSerializer,
    ProjectCreateSerializer,
    ScreenshotSerializer,
    CommentSerializer,
    GitHubMetaSerializer,
    PublicProjectSerializer,
    SourceSnippetSerializer,
    StaticSiteUploadSerializer,
)
from .permissions import IsOwnerOrReadOnly, IsInstructorOrAdmin
from .filters import ProjectFilter
from .tasks import watermark_screenshot, deploy_static_site
from .redis_utils import redis_client
from github_integration.github_client import fetch_repo_source


def visible_project_or_404(request, slug):
    """Approved project sab ko; baaki sirf owner aur instructor/admin ko. Warna 404."""
    project = get_object_or_404(Project, slug=slug)
    if project.status == Project.Status.APPROVED:
        return project
    user = request.user
    if user.is_authenticated and (project.owner_id == user.id or user.role in ('instructor', 'admin')):
        return project
    raise Http404


@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True), name='create')
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    lookup_field = 'slug'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProjectFilter
    ordering_fields = ['likes_count', 'views_count', 'created_at', 'is_featured']

    def _is_staff_role(self):
        user = self.request.user
        return user.is_authenticated and user.role in ('instructor', 'admin')

    def get_queryset(self):
        """
        Visibility rules (Day 10 workflow):
        - Explore/list: sirf APPROVED projects (pehle draft/submitted bhi sab ko nazar aate thay)
        - ?mine=true: user ke apne saare projects (draft/submitted/rejected sab)
        - ?bookmarked=true: user ke bookmarks
        - Instructor/admin: ?status=submitted wagera se kuch bhi dekh sakte hain
        - Detail/actions: approved ya apna project; instructor/admin ko sab
        """
        user = self.request.user
        params = self.request.query_params
        queryset = (
            Project.objects
            .select_related('owner', 'category')
            .prefetch_related('tech_stack', 'screenshots')
            .order_by('-created_at')
        )

        if self.action == 'list':
            if params.get('mine') == 'true' and user.is_authenticated:
                queryset = queryset.filter(owner=user)
            elif params.get('bookmarked') == 'true' and user.is_authenticated:
                queryset = queryset.filter(bookmarks__user=user).filter(
                    Q(status=Project.Status.APPROVED) | Q(owner=user)
                )
            elif not (self._is_staff_role() and params.get('status')):
                queryset = queryset.filter(status=Project.Status.APPROVED)
        elif not self._is_staff_role():
            if user.is_authenticated:
                queryset = queryset.filter(Q(status=Project.Status.APPROVED) | Q(owner=user))
            else:
                queryset = queryset.filter(status=Project.Status.APPROVED)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(tech_stack__name__icontains=search) |
                Q(owner__username__icontains=search)
            ).distinct()

        return queryset

    def list(self, request, *args, **kwargs):
        params = request.query_params
        # User-specific lists (mine/bookmarked/status) kabhi cache nahi hoti, warna ek user ka data dusre ko mil jata
        cacheable = not any(k in params for k in ('mine', 'bookmarked', 'status'))
        cache_key = f"project_list:{params.urlencode()}"

        if cacheable:
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return Response(cached_response)

        response = super().list(request, *args, **kwargs)
        if cacheable:
            cache.set(cache_key, response.data, timeout=60)

        return response

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer

        elif self.action in ['create', 'update', 'partial_update']:
            return ProjectCreateSerializer

        elif self.action == 'retrieve':
            if self.request.user and self.request.user.is_authenticated:
                return ProjectDetailSerializer

            return PublicProjectSerializer

        return ProjectDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        ProjectView.objects.create(project=instance)

        key = f'project:{instance.pk}:views_delta'
        pending = redis_client.incr(key)

        serializer = self.get_serializer(instance)
        data = serializer.data
        data['views_count'] = instance.views_count + pending

        # Likes ka pending delta (Redis) bhi jodo, taake refresh par ginti na ghate
        likes_pending = int(redis_client.get(f'project:{instance.pk}:likes_delta') or 0)
        data['likes_count'] = instance.likes_count + likes_pending
        data['liked'] = bool(
            request.user.is_authenticated
            and Like.objects.filter(project=instance, user=request.user).exists()
        )
        data['bookmarked'] = bool(
            request.user.is_authenticated
            and Bookmark.objects.filter(project=instance, user=request.user).exists()
        )
        return Response(data)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, slug=None):
        project = self.get_object()

        if project.owner != request.user:
            return Response(
                {"detail": "You do not own this project."},
                status=status.HTTP_403_FORBIDDEN
            )

        if project.status not in (Project.Status.DRAFT, Project.Status.REJECTED):
            return Response(
                {"detail": "Only draft or rejected projects can be submitted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        project.status = Project.Status.SUBMITTED
        project.save()

        return Response({
            "detail": "Project submitted for review.",
            "status": project.status
        })

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsInstructorOrAdmin]
    )
    def approve(self, request, slug=None):
        project = self.get_object()

        if project.status != Project.Status.SUBMITTED:
            return Response(
                {"detail": "Only submitted projects can be approved."},
                status=status.HTTP_400_BAD_REQUEST
            )

        project.status = Project.Status.APPROVED
        project.rejection_reason = ''
        project.save()

        cache.clear()

        return Response({
            "detail": "Project approved.",
            "status": project.status
        })

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsInstructorOrAdmin]
    )
    def reject(self, request, slug=None):
        project = self.get_object()
        reason = request.data.get('reason', '')

        if not reason:
            return Response(
                {"detail": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if project.status != Project.Status.SUBMITTED:
            return Response(
                {"detail": "Only submitted projects can be rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )

        project.status = Project.Status.REJECTED
        project.rejection_reason = reason
        project.save()

        return Response({
            "detail": "Project rejected.",
            "status": project.status
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, slug=None):
        project = self.get_object()
        like, created = Like.objects.get_or_create(project=project, user=request.user)

        key = f'project:{project.pk}:likes_delta'

        if created:
            pending = redis_client.incr(key)
            liked = True
            detail = "Project liked."
        else:
            like.delete()
            pending = redis_client.decr(key)
            liked = False
            detail = "Project unliked."

        return Response({
            "detail": detail,
            "liked": liked,
            "likes_count": project.likes_count + pending,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsInstructorOrAdmin])
    def feature(self, request, slug=None):
        project = self.get_object()
        project.is_featured = not project.is_featured
        project.save(update_fields=['is_featured'])
        cache.clear()
        return Response({"detail": "Feature status updated.", "is_featured": project.is_featured})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bookmark(self, request, slug=None):
        project = self.get_object()
        _, created = Bookmark.objects.get_or_create(project=project, user=request.user)
        if not created:
            Bookmark.objects.filter(project=project, user=request.user).delete()
        return Response({
            "detail": "Project bookmarked." if created else "Bookmark removed.",
            "bookmarked": created,
        })


class ProjectGitHubMetaView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        project = visible_project_or_404(request, slug)

        try:
            meta = project.github_meta

        except GitHubMeta.DoesNotExist:
            return Response(
                {"detail": "No GitHub metadata available for this project."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = GitHubMetaSerializer(meta)

        return Response(serializer.data)


@method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True), name='get')
class ProjectDemoUrlView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        project = visible_project_or_404(request, slug)

        if not project.demo_file:
            return Response(
                {"detail": "No demo available for this project."},
                status=status.HTTP_404_NOT_FOUND
            )

        # R2 ke liye region aur SigV4 signature zaroori hai.
        # Local MinIO par region_name khali ho to 'us-east-1' use hota hai.
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME or 'us-east-1',
            config=Config(signature_version='s3v4'),
        )

        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': project.demo_file.name
            },
            ExpiresIn=300,
        )

        return Response({
            "demo_url": signed_url,
            "expires_in_seconds": 300
        })


class StaticSiteUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        if project.owner != request.user:
            return Response({"detail": "You do not own this project."}, status=status.HTTP_403_FORBIDDEN)

        serializer = StaticSiteUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        zip_file = serializer.validated_data['site_zip']
        staging_key = f"static_site_staging/{project.id}_{zip_file.name}"
        default_storage.save(staging_key, zip_file)

        deploy_static_site.delay(project.id, staging_key)

        return Response({"detail": "Static site deployment started."}, status=status.HTTP_202_ACCEPTED)


class StaticSiteStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        project = visible_project_or_404(request, slug)
        if not project.static_site_url:
            return Response({"detail": "No static site deployed yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"site_url": project.static_site_url})


class ProjectScreenshotUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug):
        project = get_object_or_404(Project, slug=slug)

        if project.owner != request.user:
            return Response(
                {"detail": "You do not own this project."},
                status=status.HTTP_403_FORBIDDEN
            )

        images = request.FILES.getlist('images')

        if not images:
            return Response(
                {"detail": "No images provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = []
        errors = []

        for img in images:
            serializer = ScreenshotSerializer(
                data={'image': img}
            )

            if serializer.is_valid():
                screenshot = serializer.save(project=project)
                watermark_screenshot.delay(screenshot.id)

                created.append(serializer.data)

            else:
                errors.append({
                    img.name: serializer.errors
                })

        return Response({
            "uploaded": created,
            "errors": errors,
        }, status=(
            status.HTTP_201_CREATED
            if created
            else status.HTTP_400_BAD_REQUEST
        ))


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        project = visible_project_or_404(self.request, self.kwargs['slug'])
        return Comment.objects.filter(project=project)

    def perform_create(self, serializer):
        project = visible_project_or_404(self.request, self.kwargs['slug'])

        serializer.save(
            project=project,
            author=self.request.user
        )


class CommentDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, slug, comment_id):
        comment = get_object_or_404(
            Comment,
            id=comment_id,
            project__slug=slug
        )

        if (
            comment.author != request.user
            and request.user.role not in ['admin', 'instructor']
        ):
            return Response(
                {"detail": "You cannot delete this comment."},
                status=status.HTTP_403_FORBIDDEN
            )

        comment.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class ProjectSourcePreviewView(APIView):
    """GET: source snippets (approved ya owner/staff). POST: owner naya snippet jodta hai."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, slug):
        project = visible_project_or_404(request, slug)
        snippets = SourceSnippet.objects.filter(project=project).order_by('id')
        return Response(SourceSnippetSerializer(snippets, many=True).data)

    def post(self, request, slug):
        project = visible_project_or_404(request, slug)
        if project.owner_id != request.user.id:
            return Response({"detail": "You do not own this project."}, status=status.HTTP_403_FORBIDDEN)
        if SourceSnippet.objects.filter(project=project).count() >= 30:
            return Response({"detail": "A project can have at most 30 source files."},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = SourceSnippetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectSourceSnippetDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, slug, snippet_id):
        project = visible_project_or_404(request, slug)
        if project.owner_id != request.user.id and request.user.role not in ('instructor', 'admin'):
            return Response({"detail": "You do not own this project."}, status=status.HTTP_403_FORBIDDEN)
        get_object_or_404(SourceSnippet, id=snippet_id, project=project).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ratelimit(key='user_or_ip', rate='6/m', method='POST', block=True), name='post')
class ProjectSourceImportView(APIView):
    """Owner ke GitHub repo se chhoti source files import karta hai (purani snippets replace)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        project = visible_project_or_404(request, slug)
        if project.owner_id != request.user.id:
            return Response({"detail": "You do not own this project."}, status=status.HTTP_403_FORBIDDEN)
        if not project.github_url:
            return Response({"detail": "Add a GitHub repository link to this project first."},
                            status=status.HTTP_400_BAD_REQUEST)

        parts = project.github_url.rstrip('/').split('/')
        try:
            files = fetch_repo_source(parts[-2], parts[-1])
        except Exception:
            return Response(
                {"detail": "Could not read the GitHub repository. Make sure it is public and the link is correct."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if not files:
            return Response({"detail": "No suitable source files were found in the repository."},
                            status=status.HTTP_400_BAD_REQUEST)

        SourceSnippet.objects.filter(project=project).delete()
        SourceSnippet.objects.bulk_create([
            SourceSnippet(project=project, filename=path[:255], language=lang, content=text)
            for path, lang, text in files
        ])
        snippets = SourceSnippet.objects.filter(project=project).order_by('id')
        return Response(SourceSnippetSerializer(snippets, many=True).data, status=status.HTTP_201_CREATED)


class SentryTestView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        1 / 0
        return Response({"detail": "This should never be reached."})


class FilterOptionsView(APIView):
    """Explore filters aur upload wizard ke dropdowns ke liye options."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        batches = (
            Project.objects.filter(status=Project.Status.APPROVED)
            .exclude(owner__batch='')
            .values_list('owner__batch', flat=True)
            .distinct()
            .order_by('owner__batch')
        )
        return Response({
            "categories": list(Category.objects.order_by('name').values('id', 'name', 'slug')),
            "tech_stack": list(Tag.objects.order_by('name').values('id', 'name', 'slug')),
            "batches": list(batches),
        })


class MyStatsView(APIView):
    """Logged-in user ke apne projects ke numbers (My Space / sidebar ke liye)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mine = Project.objects.filter(owner=request.user)
        by_status = {s: 0 for s in ('draft', 'submitted', 'approved', 'rejected')}
        for row in mine.values('status').annotate(n=models.Count('id')):
            by_status[row['status']] = row['n']
        totals = mine.aggregate(views=models.Sum('views_count'), likes=models.Sum('likes_count'))
        return Response({
            "projects": mine.count(),
            "by_status": by_status,
            "total_views": totals['views'] or 0,
            "total_likes": totals['likes'] or 0,
            "bookmarks_saved": Bookmark.objects.filter(user=request.user).count(),
            "bookmarks_received": Bookmark.objects.filter(project__owner=request.user).count(),
        })


class LeaderboardView(APIView):
    """Top creators: sirf approved projects ginte hain."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        rows = (
            Project.objects.filter(status=Project.Status.APPROVED)
            .values('owner')
            .annotate(
                projects=models.Count('id'),
                likes=models.Sum('likes_count'),
                views=models.Sum('views_count'),
            )
            .order_by('-likes', '-views', '-projects')[:20]
        )
        from django.contrib.auth import get_user_model
        users = {u.id: u for u in get_user_model().objects.filter(id__in=[r['owner'] for r in rows])}
        data = []
        for rank, r in enumerate(rows, start=1):
            u = users.get(r['owner'])
            if not u:
                continue
            avatar = None
            if u.avatar:
                try:
                    avatar = u.avatar.url
                except Exception:
                    avatar = None
            data.append({
                "rank": rank, "username": u.username, "avatar": avatar, "batch": u.batch,
                "projects": r['projects'], "likes": r['likes'] or 0, "views": r['views'] or 0,
            })
        return Response(data)
