from django.core.management.base import BaseCommand
from apps.accounts.models import Role


class Command(BaseCommand):
    help = 'Seeds default system roles (SUPER_ADMIN, ADMIN, STUDENT, STAFF, PARENT).'

    def handle(self, *args, **options):
        
        role_data = [
            {
                'name': Role.RoleChoices.SUPER_ADMIN,
                'description': 'Full system administrator with unrestrictive permissions across all modules.'
            },
            {
                'name': Role.RoleChoices.ADMIN,
                'description': 'School administrator managing routine operations, staff records, and admissions.'
            },
            {
                'name': Role.RoleChoices.STAFF,
                'description': 'Teaching and non-teaching staff members, handling grading, attendance, and coursework.'
            },
            {
                'name': Role.RoleChoices.STUDENT,
                'description': 'Enrolled students accessing learning materials, assignments, and personal results.'
            },
            {
                'name': Role.RoleChoices.PARENT,
                'description': 'Parents or guardians monitoring student attendance, fee payments, and academic reports.'
            },
        ]

        created_count = 0
        updated_count = 0

        for item in role_data:
            role, created = Role.objects.get_or_create(
                name=item['name'],
                defaults={'description': item['description']}
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Successfully created role: {role.get_name_display()}"))
            else:
                # Update description if it changed
                if role.description != item['description']:
                    role.description = item['description']
                    role.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"Updated description for role: {role.get_name_display()}"))
                else:
                    self.stdout.write(f"Role already exists: {role.get_name_display()}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRole seeding complete. Created: {created_count}, Updated: {updated_count}."
            )
        )