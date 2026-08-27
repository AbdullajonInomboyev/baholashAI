#!/usr/bin/env bash
set -o errexit

python manage.py migrate
python manage.py seed_demo
python manage.py seed_faculty || echo "seed_faculty o'tkazib yuborildi"

gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 3 --timeout 120
