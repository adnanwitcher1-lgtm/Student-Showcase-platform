import re
import markdown
import bleach
from rest_framework import serializers
from django.core.validators import FileExtensionValidator
from .models import Category, Tag, Project, ProjectScreenshot, Comment, SourceSnippet
from github_integration.models import GitHubMeta


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class ProjectListSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'title', 'slug', 'owner', 'category', 'status', 'views_count', 'likes_count', 'cover_image', 'is_featured']


class ProjectDetailSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    category = CategorySerializer(read_only=True)
    tech_stack = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'slug', 'owner', 'description', 'category', 'tech_stack',
            'github_url', 'live_demo_url', 'cover_image', 'status',
            'views_count', 'likes_count', 'created_at', 'updated_at',
        ]


class PublicProjectSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'title', 'slug', 'category', 'cover_image']


class ProjectCreateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    tech_stack = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)

    class Meta:
        model = Project
        fields = [
            'title', 'description', 'category', 'tech_stack',
            'github_url', 'live_demo_url', 'cover_image', 'demo_file', 'status',
        ]

    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long.")
        return value

    def validate_github_url(self, value):
        if not value:
            return value
        pattern = r"^https://github\.com/[\w-]+/[\w.-]+/?$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Enter a valid GitHub repository URL, e.g. https://github.com/username/repo")
        return value

    def validate_live_demo_url(self, value):
        if not value:
            return value
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Live demo URL must start with http:// or https://")
        return value


class ScreenshotSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )

    class Meta:
        model = ProjectScreenshot
        fields = ['id', 'image', 'uploaded_at']

    def validate_image(self, value):
        max_size_mb = 5
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Each image cannot exceed {max_size_mb}MB.")

        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("File content does not match an allowed image type.")

        return value


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'author', 'text', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']

    def validate_text(self, value):
        cleaned = bleach.clean(value, tags=[], strip=True)
        if not cleaned.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return cleaned


class GitHubMetaSerializer(serializers.ModelSerializer):
    readme_html = serializers.SerializerMethodField()

    class Meta:
        model = GitHubMeta
        fields = ['stars', 'forks', 'primary_language', 'last_commit_at', 'readme_cache', 'readme_html']

    def get_readme_html(self, obj):
        if not obj.readme_cache:
            return ''
        raw_html = markdown.markdown(obj.readme_cache, extensions=['fenced_code', 'tables'])
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4',
            'h5', 'h6', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 'tr',
            'th', 'td', 'hr', 'img',
        ]
        allowed_attrs = {'a': ['href', 'title'], 'img': ['src', 'alt']}
        return bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs, strip=True)


class SourceSnippetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSnippet
        fields = ['id', 'filename', 'language', 'content', 'created_at']
class StaticSiteUploadSerializer(serializers.Serializer):
    site_zip = serializers.FileField()

    def validate_site_zip(self, value):
        if not value.name.endswith('.zip'):
            raise serializers.ValidationError("File must be a .zip archive.")
        max_size_mb = 20
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Zip file cannot exceed {max_size_mb}MB.")
        return value