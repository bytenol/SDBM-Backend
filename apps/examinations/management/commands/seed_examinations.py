from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academics.models import AcademicSession, AcademicTerm, SchoolSettings
from apps.examinations.models import (
    AssessmentCategory,
    AssessmentComponent,
    GradingScale,
)


class Command(BaseCommand):
    help = "Seeds default Assessment Components (CA1, CA2, Assignment, Exam) and standard Grading Scales."

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-id',
            type=str,
            help='Optional UUID of a specific AcademicSession to seed assessment components for.',
        )
        parser.add_argument(
            '--all-terms',
            action='store_true',
            help='Seed assessment components across all terms of the target session instead of just the active term.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Starting Examinations & Grading configuration seeding..."))

        # 1. Seed Global Default Grading Scales
        self._seed_grading_scales()

        # 2. Resolve Target Academic Session & Terms
        session, terms = self._resolve_session_and_terms(
            session_id=options.get('session_id'),
            all_terms=options.get('all_terms', False)
        )

        if not session or not terms:
            self.stdout.write(
                self.style.WARNING(
                    "Grading scales seeded, but no AcademicSession/AcademicTerm was found to attach AssessmentComponents. "
                    "Create an AcademicSession and AcademicTerm first, then re-run this command."
                )
            )
            return

        # 3. Seed Default Assessment Components per Term
        for term in terms:
            self._seed_assessment_components(session, term)

        self.stdout.write(self.style.SUCCESS("Examinations configuration seeding completed successfully!"))

    def _seed_grading_scales(self):
        """
        Seeds standard school-wide grading boundaries (A - F) where academic_session and education_level are null.
        """
        default_grades = [
            {
                "grade_letter": "A",
                "min_score": Decimal("70.00"),
                "max_score": Decimal("100.00"),
                "grade_point": Decimal("5.00"),
                "remark": "Excellent",
            },
            {
                "grade_letter": "B",
                "min_score": Decimal("60.00"),
                "max_score": Decimal("69.99"),
                "grade_point": Decimal("4.00"),
                "remark": "Very Good",
            },
            {
                "grade_letter": "C",
                "min_score": Decimal("50.00"),
                "max_score": Decimal("59.99"),
                "grade_point": Decimal("3.00"),
                "remark": "Good",
            },
            {
                "grade_letter": "D",
                "min_score": Decimal("45.00"),
                "max_score": Decimal("49.99"),
                "grade_point": Decimal("2.00"),
                "remark": "Fair",
            },
            {
                "grade_letter": "E",
                "min_score": Decimal("40.00"),
                "max_score": Decimal("44.99"),
                "grade_point": Decimal("1.00"),
                "remark": "Pass",
            },
            {
                "grade_letter": "F",
                "min_score": Decimal("0.00"),
                "max_score": Decimal("39.99"),
                "grade_point": Decimal("0.00"),
                "remark": "Fail",
            },
        ]

        created_count = 0
        updated_count = 0

        for item in default_grades:
            obj, created = GradingScale.objects.update_or_create(
                academic_session=None,
                education_level=None,
                grade_letter=item["grade_letter"],
                defaults={
                    "min_score": item["min_score"],
                    "max_score": item["max_score"],
                    "grade_point": item["grade_point"],
                    "remark": item["remark"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  [GradingScale] {created_count} created, {updated_count} updated (Global A-F scale)."
            )
        )

    def _resolve_session_and_terms(self, session_id=None, all_terms=False):
        if session_id:
            session = AcademicSession.objects.filter(pk=session_id).first()
        else:
            settings_obj = SchoolSettings.load()
            session = settings_obj.current_session or AcademicSession.objects.order_by('-start_date').first()

        if not session:
            return None, []

        if all_terms:
            terms = list(AcademicTerm.objects.filter(session=session).order_by('start_date'))
        else:
            settings_obj = SchoolSettings.load()
            if settings_obj.current_term and settings_obj.current_term.session_id == session.id:
                terms = [settings_obj.current_term]
            else:
                terms = list(AcademicTerm.objects.filter(session=session).order_by('start_date'))

        return session, terms

    def _seed_assessment_components(self, session, term):
        """
        Seeds the standard 4-component breakdown (10 + 10 + 10 + 70 = 100%) globally for the given session and term.
        """
        default_components = [
            {
                "code": "CA1",
                "name": "First Continuous Assessment",
                "category": AssessmentCategory.CA,
                "maximum_score": Decimal("10.00"),
                "weight_percentage": Decimal("10.00"),
                "display_order": 1,
            },
            {
                "code": "CA2",
                "name": "Second Continuous Assessment",
                "category": AssessmentCategory.CA,
                "maximum_score": Decimal("10.00"),
                "weight_percentage": Decimal("10.00"),
                "display_order": 2,
            },
            {
                "code": "ASSIGN",
                "name": "Assignment / Project",
                "category": AssessmentCategory.ASSIGNMENT,
                "maximum_score": Decimal("10.00"),
                "weight_percentage": Decimal("10.00"),
                "display_order": 3,
            },
            {
                "code": "EXAM",
                "name": "Term Examination",
                "category": AssessmentCategory.EXAMINATION,
                "maximum_score": Decimal("70.00"),
                "weight_percentage": Decimal("70.00"),
                "display_order": 4,
            },
        ]

        created_count = 0
        updated_count = 0

        for comp in default_components:
            obj, created = AssessmentComponent.objects.update_or_create(
                academic_session=session,
                academic_term=term,
                class_obj=None,
                code=comp["code"],
                defaults={
                    "name": comp["name"],
                    "category": comp["category"],
                    "maximum_score": comp["maximum_score"],
                    "weight_percentage": comp["weight_percentage"],
                    "display_order": comp["display_order"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  [AssessmentComponent] {session.name} ({term.get_name_display()}): "
                f"{created_count} created, {updated_count} updated (Total weight = 100%)."
            )
        )