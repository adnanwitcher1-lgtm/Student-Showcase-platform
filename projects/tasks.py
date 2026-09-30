import io
from datetime import datetime
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw
from .models import ProjectScreenshot
import zipfile
import mimetypes
from django.db import models
from .redis_utils import redis_client
import boto3
from django.conf import settings
from .models import Project


@shared_task
def deploy_static_site(project_id, staging_key):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return f"No project found with id {project_id}"

    with default_storage.open(staging_key, 'rb') as f:
        zip_bytes = f.read()

    s3_client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    uploaded_count = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith('/'):
                continue
            file_data = zf.read(name)
            content_type, _ = mimetypes.guess_type(name)
            key = f"demos/{project.slug}/{name}"
            s3_client.put_object(
                Bucket=settings.AWS_DEMOS_BUCKET_NAME,
                Key=key,
                Body=file_data,
                ContentType=content_type or 'application/octet-stream',
            )
            uploaded_count += 1

    default_storage.delete(staging_key)

    site_url = f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_DEMOS_BUCKET_NAME}/demos/{project.slug}/index.html"
    project.static_site_url = site_url
    project.save(update_fields=['static_site_url'])

    return f"Deployed {uploaded_count} files for project {project_id} at {site_url}"

@shared_task
def watermark_screenshot(screenshot_id):
    try:
        screenshot = ProjectScreenshot.objects.get(id=screenshot_id)
    except ProjectScreenshot.DoesNotExist:
        return f"No screenshot found with id {screenshot_id}"

    file_field = screenshot.image
    file_path = file_field.name

    with default_storage.open(file_path, 'rb') as f:
        img = Image.open(f)
        img = img.convert('RGB')

        draw = ImageDraw.Draw(img)
        student_name = screenshot.project.owner.username
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        watermark_text = f"{student_name} - {timestamp}"
        draw.text((10, 10), watermark_text, fill='white')

        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)

    default_storage.delete(file_path)
    file_field.save(file_path.split('/')[-1], ContentFile(buffer.read()), save=True)

    return f"Watermarked screenshot {screenshot_id}"

@shared_task
def sync_engagement_counters():
    updated = 0

    for key in redis_client.scan_iter('project:*:views_delta'):
        project_id = key.split(':')[1]
        delta = int(redis_client.getset(key, 0))
        if delta:
            Project.objects.filter(pk=project_id).update(views_count=models.F('views_count') + delta)
            updated += 1

    for key in redis_client.scan_iter('project:*:likes_delta'):
        project_id = key.split(':')[1]
        delta = int(redis_client.getset(key, 0))
        if delta:
            Project.objects.filter(pk=project_id).update(likes_count=models.F('likes_count') + delta)
            updated += 1

    return f"Synced {updated} counters"