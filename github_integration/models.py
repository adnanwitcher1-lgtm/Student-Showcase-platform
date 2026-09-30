from django.db import models

# Create your models here.
from django.db import models
from projects.models import Project


class GitHubMeta(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='github_meta')
    stars = models.PositiveIntegerField(default=0)
    forks = models.PositiveIntegerField(default=0)
    last_commit_at = models.DateTimeField(null=True, blank=True)
    primary_language = models.CharField(max_length=50, blank=True)
    readme_cache = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GitHub meta for {self.project.title}"