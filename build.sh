#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate agriguide_ai 0006 --fake  # fake this specific migration
python manage.py migrate 