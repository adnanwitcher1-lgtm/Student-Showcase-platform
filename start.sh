#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Ensuring Site id=2 exists..."
python manage.py shell -c "from django.contrib.sites.models import Site; Site.objects.update_or_create(id=2, defaults={'domain': '${SITE_DOMAIN:-localhost}', 'name': 'Student Showcase'})"

if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "Creating superuser (skipped if it already exists)..."
  python manage.py createsuperuser --noinput || true
fi

echo "Starting gunicorn on port ${PORT:-8000}..."
exec gunicorn core.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${WEB_CONCURRENCY:-2} \
  --timeout 120