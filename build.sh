#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

python manage.py seed_roles
python manage.py seed_superuser
python manage.py seed_academics
python manage.py seed_examinations --all-terms