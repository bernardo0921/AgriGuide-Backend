#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py makemigrations agriguide_ai 006
python manage.py migrate agriguide_ai 0006
python manage.py migrate 