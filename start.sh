#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate --noinput

# Site id=2 sirf pehli baar (ya database reset ke baad) chahiye.
# Zaroorat ho to Render mein RUN_SITE_FIX=1 set karo, warna har boot par ~10 second bachte hain.
if [ "$RUN_SITE_FIX" = "1" ]; then
  echo "Ensuring Site id=2 exists..."
  python manage.py shell -c "from django.contrib.sites.models import Site; Site.objects.update_or_create(id=2, defaults={'domain': '${SITE_DOMAIN:-localhost}', 'name': 'Student Showcase'})"
fi

# Superuser sirf tab banta hai jab DJANGO_SUPERUSER_USERNAME set ho.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "Creating superuser (skipped if it already exists)..."
  python manage.py createsuperuser --noinput || true
fi

# Celery 45 second baad shuru hota hai, taake pehle website jaldi jaag jaye
# (free instance par dono ek saath chalein to start bohot sust ho jata hai).
echo "Celery will start in the background after 45 seconds..."
( sleep 45 && celery -A core worker -B --pool=solo --loglevel=info ) &

echo "Starting gunicorn on port ${PORT:-8000}..."
exec gunicorn core.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${WEB_CONCURRENCY:-2} \
  --timeout 120