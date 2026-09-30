from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import GitHubMeta

@admin.register(GitHubMeta)
class GitHubMetaAdmin(admin.ModelAdmin):
    list_display = ('project', 'stars', 'forks', 'primary_language', 'updated_at')