#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_demo
python manage.py seed_faculty || echo "seed_faculty o'tkazib yuborildi"