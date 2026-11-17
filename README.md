Create postgressdb named schooldb

seed_accounts
seed_academics
seed_examinations

# Seed grading scales + active term components
python manage.py seed_examinations

# Or seed components across all terms (First, Second, Third) in the current session
python manage.py seed_examinations --all-terms