#!/bin/sh
# Docker (VPS) deployment ke liye startup script.
# Render wali start.sh alag hai aur bilkul waisi hi rahegi.
set -e

echo "Running migrations..."
python manage.py migrate --noinput

# SITE_ID=2 chahiye (allauth/GitHub login ke liye). Idempotent hai, har boot par safe.
echo "Ensuring Site id=2 exists..."
python manage.py shell -c "from django.contrib.sites.models import Site; Site.objects.update_or_create(id=2, defaults={'domain': '${SITE_DOMAIN:-localhost}', 'name': 'Student Showcase'})"

# Superuser sirf tab banta hai jab DJANGO_SUPERUSER_USERNAME set ho (pehle se ho to skip).
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "Creating superuser (skipped if it already exists)..."
  python manage.py createsuperuser --noinput || true
fi

echo "Starting gunicorn..."
exec gunicorn core.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers ${WEB_CONCURRENCY:-3} \
  --timeout 120 \
  --access-logfile -
