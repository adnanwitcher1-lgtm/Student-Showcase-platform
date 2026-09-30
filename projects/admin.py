from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Category, Tag, Project
from .models import ProjectScreenshot
from .models import Like
from .models import Comment
from .models import SourceSnippet

@admin.register(SourceSnippet)
class SourceSnippetAdmin(admin.ModelAdmin):
    list_display = ('filename', 'project', 'language', 'created_at')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'status', 'views_count', 'likes_count', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'owner__username')
    prepopulated_fields = {'slug': ('title',)}
    @admin.register(ProjectScreenshot)
    class ProjectScreenshotAdmin(admin.ModelAdmin):
     list_display = ('project', 'uploaded_at')
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'created_at')
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('project', 'author', 'created_at')
    list_filter = ('created_at',)