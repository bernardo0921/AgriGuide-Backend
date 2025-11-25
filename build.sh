#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

# Fix the partial migration
python manage.py fix_migrations

# Run migrations
python manage.py migrate