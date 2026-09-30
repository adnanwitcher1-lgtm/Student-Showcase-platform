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
from django.conf import settings
from django.shortcuts import get_object_or_404

from github_integration.models import GitHubMeta
from .models import Project, ProjectScreenshot, Like, Comment, SourceSnippet, ProjectView
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

@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True), name='create')
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    lookup_field = 'slug'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProjectFilter
    ordering_fields = ['likes_count', 'views_count', 'created_at']

    def get_queryset(self):
        queryset = Project.objects.all().order_by('-created_at')
        search = self.request.query_params.get('search')

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(tech_stack__name__icontains=search) |
                Q(owner__username__icontains=search)
            ).distinct()

        return queryset

    def list(self, request, *args, **kwargs):
        cache_key = f"project_list:{request.query_params.urlencode()}"
        cached_response = cache.get(cache_key)

        if cached_response is not None:
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)
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

        if project.status != Project.Status.DRAFT:
            return Response(
                {"detail": "Only draft projects can be submitted."},
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


class ProjectGitHubMetaView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        project = get_object_or_404(Project, slug=slug)

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
        project = get_object_or_404(Project, slug=slug)

        if not project.demo_file:
            return Response(
                {"detail": "No demo available for this project."},
                status=status.HTTP_404_NOT_FOUND
            )

        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
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
        project = get_object_or_404(Project, slug=slug)
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
        return Comment.objects.filter(
            project__slug=self.kwargs['slug']
        )

    def perform_create(self, serializer):
        project = get_object_or_404(
            Project,
            slug=self.kwargs['slug']
        )

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
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        snippets = SourceSnippet.objects.filter(project=project)
        serializer = SourceSnippetSerializer(snippets, many=True)

        response = Response(serializer.data)
        response['Content-Disposition'] = 'inline'
        return response
class SentryTestView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        1 / 0
        return Response({"detail": "This should never be reached."})