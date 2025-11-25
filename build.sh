#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

# Fix the database
python manage.py fix_db

# Run migrations fresh
python manage.py migrate

# Create superuser if needed
# python manage.py createsuperuser --noinput || true