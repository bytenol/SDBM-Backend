from datetime import date
from django.core.management.base import BaseCommand
from apps.academics.models import (
    SchoolSettings,
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject
)

class Command(BaseCommand):
    help = 'Seeds initial academic session (2026/2027), terms, standard classes, arms, and subjects.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding initial academic data..."))

        # 1. Seed Academic Session (2026/2027)
        session, created = AcademicSession.objects.get_or_create(
            name="2026/2027",
            defaults={
                'start_date': date(2026, 9, 1),
                'end_date': date(2027, 7, 31),
                'is_current': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Academic Session: {session.name}"))
        else:
            self.stdout.write(f"Academic Session already exists: {session.name}")

        # 2. Seed Academic Terms
        terms_data = [
            {
                'name': AcademicTerm.TermChoices.FIRST,
                'start_date': date(2026, 9, 1),
                'end_date': date(2026, 12, 18),
                'is_current': True
            },
            {
                'name': AcademicTerm.TermChoices.SECOND,
                'start_date': date(2027, 1, 11),
                'end_date': date(2027, 4, 9),
                'is_current': False
            },
            {
                'name': AcademicTerm.TermChoices.THIRD,
                'start_date': date(2027, 4, 26),
                'end_date': date(2027, 7, 30),
                'is_current': False
            },
        ]

        current_term_obj = None
        for term_info in terms_data:
            term, t_created = AcademicTerm.objects.get_or_create(
                session=session,
                name=term_info['name'],
                defaults={
                    'start_date': term_info['start_date'],
                    'end_date': term_info['end_date'],
                    'is_current': term_info['is_current']
                }
            )
            if term.is_current:
                current_term_obj = term
            if t_created:
                self.stdout.write(self.style.SUCCESS(f"  - Created Term: {term.get_name_display()}"))

        # 3. Initialize SchoolSettings Singleton
        settings_obj = SchoolSettings.load()
        settings_obj.current_session = session
        settings_obj.current_term = current_term_obj
        settings_obj.save()
        self.stdout.write(self.style.SUCCESS("Initialized SchoolSettings with current session and term."))

        # 4. Seed Standard School Classes & Arms
        classes_data = [
            # Nursery
            {'name': 'Nursery 1', 'code': 'NUR-1', 'level': Class.EducationLevel.NURSERY, 'order': 1, 'arms': ['Gold', 'Silver']},
            {'name': 'Nursery 2', 'code': 'NUR-2', 'level': Class.EducationLevel.NURSERY, 'order': 2, 'arms': ['Gold', 'Silver']},
            
            # Primary
            {'name': 'Primary 1', 'code': 'PRI-1', 'level': Class.EducationLevel.PRIMARY, 'order': 3, 'arms': ['A', 'B', 'C']},
            {'name': 'Primary 2', 'code': 'PRI-2', 'level': Class.EducationLevel.PRIMARY, 'order': 4, 'arms': ['A', 'B', 'C']},
            {'name': 'Primary 3', 'code': 'PRI-3', 'level': Class.EducationLevel.PRIMARY, 'order': 5, 'arms': ['A', 'B', 'C']},
            {'name': 'Primary 4', 'code': 'PRI-4', 'level': Class.EducationLevel.PRIMARY, 'order': 6, 'arms': ['A', 'B']},
            {'name': 'Primary 5', 'code': 'PRI-5', 'level': Class.EducationLevel.PRIMARY, 'order': 7, 'arms': ['A', 'B']},
            {'name': 'Primary 6', 'code': 'PRI-6', 'level': Class.EducationLevel.PRIMARY, 'order': 8, 'arms': ['A', 'B']},

            # Junior Secondary
            {'name': 'JSS 1', 'code': 'JSS-1', 'level': Class.EducationLevel.JUNIOR_SECONDARY, 'order': 9, 'arms': ['A', 'B', 'C']},
            {'name': 'JSS 2', 'code': 'JSS-2', 'level': Class.EducationLevel.JUNIOR_SECONDARY, 'order': 10, 'arms': ['A', 'B', 'C']},
            {'name': 'JSS 3', 'code': 'JSS-3', 'level': Class.EducationLevel.JUNIOR_SECONDARY, 'order': 11, 'arms': ['A', 'B', 'C']},

            # Senior Secondary
            {'name': 'SSS 1', 'code': 'SSS-1', 'level': Class.EducationLevel.SENIOR_SECONDARY, 'order': 12, 'arms': ['Science', 'Arts', 'Commercial']},
            {'name': 'SSS 2', 'code': 'SSS-2', 'level': Class.EducationLevel.SENIOR_SECONDARY, 'order': 13, 'arms': ['Science', 'Arts', 'Commercial']},
            {'name': 'SSS 3', 'code': 'SSS-3', 'level': Class.EducationLevel.SENIOR_SECONDARY, 'order': 14, 'arms': ['Science', 'Arts', 'Commercial']},
        ]

        for c_data in classes_data:
            cls_obj, c_created = Class.objects.get_or_create(
                code=c_data['code'],
                defaults={
                    'name': c_data['name'],
                    'education_level': c_data['level'],
                    'display_order': c_data['order'],
                    'is_active': True
                }
            )
            if c_created:
                self.stdout.write(self.style.SUCCESS(f"  + Created Class: {cls_obj.name}"))
            
            # Seed arms for the class
            for arm_name in c_data['arms']:
                arm, a_created = ClassArm.objects.get_or_create(
                    class_obj=cls_obj,
                    name=arm_name,
                    defaults={'capacity': 35, 'is_active': True}
                )
                if a_created:
                    self.stdout.write(f"    - Arm: {cls_obj.name} ({arm_name})")

        # 5. Seed Core Subjects
        subjects_data = [
            {'name': 'Mathematics', 'code': 'MTH', 'category': Subject.Category.GENERAL},
            {'name': 'English Language', 'code': 'ENG', 'category': Subject.Category.GENERAL},
            {'name': 'Islamic Studies', 'code': 'ISL', 'category': Subject.Category.GENERAL},
            {'name': 'Arabic Language', 'code': 'ARB', 'category': Subject.Category.GENERAL},
            {'name': 'Basic Science', 'code': 'BSC', 'category': Subject.Category.SCIENCES},
            {'name': 'Physics', 'code': 'PHY', 'category': Subject.Category.SCIENCES},
            {'name': 'Chemistry', 'code': 'CHM', 'category': Subject.Category.SCIENCES},
            {'name': 'Biology', 'code': 'BIO', 'category': Subject.Category.SCIENCES},
            {'name': 'Civic Education', 'code': 'CIV', 'category': Subject.Category.GENERAL},
            {'name': 'Economics', 'code': 'ECO', 'category': Subject.Category.COMMERCIAL},
            {'name': 'Financial Accounting', 'code': 'ACC', 'category': Subject.Category.COMMERCIAL},
            {'name': 'Commerce', 'code': 'ACC', 'category': Subject.Category.COMMERCIAL},
            {'name': 'Literature-in-English', 'code': 'LIT', 'category': Subject.Category.ARTS},
            {'name': 'Government', 'code': 'GOV', 'category': Subject.Category.ARTS},
        ]

        for s_data in subjects_data:
            subj, s_created = Subject.objects.get_or_create(
                code=s_data['code'],
                defaults={
                    'name': s_data['name'],
                    'category': s_data['category'],
                    'is_active': True
                }
            )
            if s_created:
                self.stdout.write(self.style.SUCCESS(f"  * Created Subject: {subj.name} ({subj.code})"))

        self.stdout.write(self.style.SUCCESS("\nAcademic data seeding completed successfully!"))