# apps/accounts/management/commands/seed_superuser.py
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Role

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the initial Super Administrator user.'

    def handle(self, *args, **options):
        email = os.environ.get('ADMIN_EMAIL')
        login_id = 'ADMIN-2026-0001'
        password = os.environ.get('ADMIN_PASSWORD')

        # Check if user already exists
        if User.objects.filter(email=email).exists() or User.objects.filter(login_id=login_id).exists():
            self.stdout.write(
                self.style.WARNING(f"Superuser with email '{email}' or login ID '{login_id}' already exists.")
            )
            return

        # Create the superuser using our custom manager
        user = User.objects.create_superuser(
            login_id=login_id,
            email=email,
            password=password,
            first_name='System',
            last_name='Administrator'
        )

        # Ensure the SUPER_ADMIN role exists and assign it
        super_admin_role, _ = Role.objects.get_or_create(
            name=Role.RoleChoices.SUPER_ADMIN,
            defaults={'description': 'Full system administrator with unrestrictive permissions across all modules.'}
        )
        user.roles.add(super_admin_role)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created initial superuser:\n"
                f"  - Login ID: {login_id}\n"
                f"  - Email: {email}\n"
                f"  - Role: SUPER_ADMIN"
            )
        )