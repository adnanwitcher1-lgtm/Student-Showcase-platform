from celery import shared_task
from django.utils.dateparse import parse_datetime
from .models import GitHubMeta
from .github_client import fetch_repo_meta, fetch_repo_readme


@shared_task
def sync_github_meta(project_id):
    try:
        meta = GitHubMeta.objects.get(project_id=project_id)
    except GitHubMeta.DoesNotExist:
        return f"No GitHubMeta found for project {project_id}"

    project = meta.project
    if not project.github_url:
        return f"Project {project_id} has no github_url"

    parts = project.github_url.rstrip('/').split('/')
    owner, repo = parts[-2], parts[-1]

    data = fetch_repo_meta(owner, repo)
    meta.stars = data['stars']
    meta.forks = data['forks']
    meta.primary_language = data['primary_language']
    if data['last_commit_at']:
        meta.last_commit_at = parse_datetime(data['last_commit_at'])

    meta.readme_cache = fetch_repo_readme(owner, repo)

    meta.save()

    return f"Synced GitHub meta for project {project_id}"


@shared_task
def sync_all_approved_projects():
    from projects.models import Project
    approved_projects = Project.objects.filter(status=Project.Status.APPROVED, github_url__gt='')
    for project in approved_projects:
        GitHubMeta.objects.get_or_create(project=project)
        sync_github_meta.delay(project.id)
    return f"Queued sync for {approved_projects.count()} projects"