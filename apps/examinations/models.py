from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from apps.core.models import TimeStampedUUIDModel
from apps.academics.models import AcademicSession, AcademicTerm, Class, ClassArm, Subject
from apps.students.models import StudentEnrollment


class AssessmentCategory(models.TextChoices):
    CA = 'CA', 'Continuous Assessment'
    ASSIGNMENT = 'ASSIGNMENT', 'Assignment'
    TEST = 'TEST', 'Test / Quiz'
    PROJECT = 'PROJECT', 'Project / Practical'
    EXAMINATION = 'EXAMINATION', 'Examination'


class ResultWorkflowStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SCORES_SUBMITTED = 'SCORES_SUBMITTED', 'Scores Submitted'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    APPROVED = 'APPROVED', 'Approved'
    PUBLISHED = 'PUBLISHED', 'Published'
    LOCKED = 'LOCKED', 'Locked'


class Examination(TimeStampedUUIDModel):
    """
    Represents formal examination windows within an academic session and term.
    Can apply globally across all classes in the term or to a specific subset of classes.
    """
    class ExamType(models.TextChoices):
        FIRST_TERM = 'FIRST_TERM', 'First Term Examination'
        SECOND_TERM = 'SECOND_TERM', 'Second Term Examination'
        THIRD_TERM = 'THIRD_TERM', 'Third Term Examination'
        MOCK = 'MOCK', 'Mock Examination'
        PROMOTIONAL = 'PROMOTIONAL', 'Promotional Examination'

    class ExamStatus(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        ONGOING = 'ONGOING', 'Ongoing'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    name = models.CharField(max_length=150, help_text="e.g. 2026/2027 First Term Examination")
    examination_type = models.CharField(max_length=30, choices=ExamType.choices, default=ExamType.FIRST_TERM)
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='examinations'
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name='examinations'
    )
    applicable_classes = models.ManyToManyField(
        Class,
        blank=True,
        related_name='examinations',
        help_text="Leave empty if the examination applies to all classes in the session/term."
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=ExamStatus.choices, default=ExamStatus.SCHEDULED)
    is_active = models.BooleanField(default=True)
    instructions = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Examination'
        verbose_name_plural = 'Examinations'
        ordering = ['-academic_session__start_date', 'start_date']
        unique_together = ('academic_session', 'academic_term', 'name')

    def __str__(self):
        return f"{self.name} ({self.academic_session.name} - {self.academic_term.get_name_display()})"

    def clean(self):
        super().clean()
        if self.academic_term_id and self.academic_session_id:
            if self.academic_term.session_id != self.academic_session_id:
                raise ValidationError({"academic_term": "Selected term does not belong to the selected academic session."})

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "Examination start date cannot be later than the end date."})


class AssessmentComponent(TimeStampedUUIDModel):
    """
    Configurable assessment components contributing to the 100% subject total.
    Example:
      - First CA: Max 10, Weight 10%
      - Second CA: Max 10, Weight 10%
      - Assignment: Max 10, Weight 10%
      - Examination: Max 70, Weight 70%
    """
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='assessment_components'
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name='assessment_components'
    )
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assessment_components',
        help_text="Optional: Leave blank if this component applies school-wide for the session/term."
    )
    category = models.CharField(
        max_length=20,
        choices=AssessmentCategory.choices,
        default=AssessmentCategory.CA
    )
    name = models.CharField(max_length=100, help_text="e.g. First Continuous Assessment, Examination")
    code = models.CharField(max_length=30, help_text="e.g. CA1, CA2, ASSIGN, EXAM")
    maximum_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        default=Decimal('10.00'),
        help_text="Maximum raw score obtainable (e.g. 10.00, 70.00, or 100.00)"
    )
    weight_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Percentage contribution to the final 100% subject score (e.g. 10.00 for 10%)"
    )
    display_order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Assessment Component'
        verbose_name_plural = 'Assessment Components'
        unique_together = ('academic_session', 'academic_term', 'class_obj', 'code')
        ordering = ['academic_session', 'academic_term', 'display_order', 'code']

    def __str__(self):
        scope = f"[{self.class_obj.name}]" if self.class_obj else "[All Classes]"
        return f"{self.name} ({self.code}: Max {self.maximum_score}, Weight {self.weight_percentage}%) {scope}"

    def clean(self):
        super().clean()
        if self.academic_term_id and self.academic_session_id:
            if self.academic_term.session_id != self.academic_session_id:
                raise ValidationError({"academic_term": "Selected term does not belong to the selected academic session."})

        # Ensure active component weights within the same scope do not exceed 100%
        if self.is_active and self.academic_session_id and self.academic_term_id and self.weight_percentage:
            qs = AssessmentComponent.objects.filter(
                academic_session_id=self.academic_session_id,
                academic_term_id=self.academic_term_id,
                class_obj=self.class_obj,
                is_active=True
            ).exclude(pk=self.pk)
            existing_weight = qs.aggregate(total=models.Sum('weight_percentage'))['total'] or Decimal('0.00')
            if existing_weight + self.weight_percentage > Decimal('100.00'):
                raise ValidationError({
                    "weight_percentage": (
                        f"Total active component weights for this scope cannot exceed 100.00%. "
                        f"Current active weight sum is {existing_weight}%."
                    )
                })


class GradingScale(TimeStampedUUIDModel):
    """
    Configurable grading policy mapping percentage score ranges to letter grades, points, and remarks.
    Can be global or scoped to a specific academic session and/or education level.
    """
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='grading_scales',
        help_text="Optional: Leave blank for the default school-wide grading policy."
    )
    education_level = models.CharField(
        max_length=30,
        choices=Class.EducationLevel.choices,
        null=True,
        blank=True,
        help_text="Optional: Scope this grading scale to a specific education level (e.g. SENIOR_SECONDARY)."
    )
    grade_letter = models.CharField(max_length=5, help_text="e.g. A, B, C, D, E, F")
    min_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    grade_point = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Grade point equivalent (e.g. 5.00, 4.00)"
    )
    remark = models.CharField(max_length=100, help_text="e.g. Excellent, Very Good, Credit, Pass, Fail")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Grading Scale'
        verbose_name_plural = 'Grading Scales'
        ordering = ['-min_score']

    def __str__(self):
        level = f" [{self.education_level}]" if self.education_level else ""
        return f"{self.grade_letter} ({self.min_score} - {self.max_score}) -> {self.remark}{level}"

    def clean(self):
        super().clean()
        if self.min_score is not None and self.max_score is not None:
            if self.min_score > self.max_score:
                raise ValidationError({"min_score": "Minimum score cannot be greater than maximum score."})

            # Prevent overlapping active grade ranges in the same scope
            if self.is_active:
                overlapping = GradingScale.objects.filter(
                    academic_session=self.academic_session,
                    education_level=self.education_level,
                    is_active=True,
                    min_score__lte=self.max_score,
                    max_score__gte=self.min_score
                ).exclude(pk=self.pk)
                if overlapping.exists():
                    conflict = overlapping.first()
                    raise ValidationError(
                        f"Score range ({self.min_score} - {self.max_score}) overlaps with existing grade "
                        f"'{conflict.grade_letter}' ({conflict.min_score} - {conflict.max_score})."
                    )


class StudentScore(TimeStampedUUIDModel):
    """
    Stores raw marks obtained by a student for a specific subject and assessment component in a term.
    Snapshots max_score_snapshot and weight_snapshot on save so historical records never corrupt
    if AssessmentComponent configuration changes later.
    """
    class ScoreSubmissionStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'

    student_enrollment = models.ForeignKey(
        StudentEnrollment,
        on_delete=models.PROTECT,
        related_name='assessment_scores',
        help_text="Establishes student, session, class, and class arm context."
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.PROTECT,
        related_name='student_scores'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='student_scores'
    )
    assessment_component = models.ForeignKey(
        AssessmentComponent,
        on_delete=models.PROTECT,
        related_name='student_scores'
    )
    examination = models.ForeignKey(
        Examination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_scores',
        help_text="Optional link to a formal Examination record if this component is an exam."
    )

    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Raw mark obtained by the student. Null if absent or exempted."
    )
    is_absent = models.BooleanField(default=False, help_text="True if the student was absent for this assessment.")
    is_exempted = models.BooleanField(default=False, help_text="True if the student is officially exempted from this component.")

    # Historical snapshots preserved at entry time
    max_score_snapshot = models.DecimalField(max_digits=5, decimal_places=2, editable=False)
    weight_snapshot = models.DecimalField(max_digits=5, decimal_places=2, editable=False)

    status = models.CharField(
        max_length=20,
        choices=ScoreSubmissionStatus.choices,
        default=ScoreSubmissionStatus.DRAFT
    )
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entered_scores'
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_scores'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Student Assessment Score'
        verbose_name_plural = 'Student Assessment Scores'
        unique_together = ('student_enrollment', 'academic_term', 'subject', 'assessment_component')
        ordering = ['student_enrollment__student__last_name', 'subject__name', 'assessment_component__display_order']

    def __str__(self):
        val = "ABS" if self.is_absent else ("EXM" if self.is_exempted else f"{self.score}/{self.max_score_snapshot}")
        return f"{self.student_enrollment.student} | {self.subject.code} | {self.assessment_component.code}: {val}"

    @property
    def weighted_score(self) -> Decimal:
        """
        Normalizes raw score against max_score_snapshot and weight_snapshot.
        Formula: (raw_score / max_score) * weight_percentage
        """
        if self.score is None or self.is_absent or self.is_exempted or not self.max_score_snapshot:
            return Decimal('0.00')
        return ((self.score / self.max_score_snapshot) * self.weight_snapshot).quantize(Decimal('0.01'))

    def clean(self):
        super().clean()
        if self.academic_term_id and self.student_enrollment_id:
            if self.academic_term.session_id != self.student_enrollment.academic_session_id:
                raise ValidationError({"academic_term": "Term does not match the student enrollment's academic session."})

        if self.assessment_component_id:
            if self.academic_term_id and self.assessment_component.academic_term_id != self.academic_term_id:
                raise ValidationError({"assessment_component": "Assessment component does not belong to the selected term."})

            if (
                self.assessment_component.class_obj_id
                and self.student_enrollment_id
                and self.assessment_component.class_obj_id != self.student_enrollment.class_obj_id
            ):
                raise ValidationError({"assessment_component": "Assessment component is restricted to a different class."})

            max_allowed = self.max_score_snapshot or self.assessment_component.maximum_score
            if self.score is not None and self.score > max_allowed:
                raise ValidationError({
                    "score": f"Entered score ({self.score}) cannot exceed the component maximum score ({max_allowed})."
                })

        if not self.is_absent and not self.is_exempted and self.score is None:
            raise ValidationError({"score": "A numeric score is required unless the student is marked absent or exempted."})

    def save(self, *args, **kwargs):
        if self.assessment_component_id and (not self.max_score_snapshot or not self.weight_snapshot):
            self.max_score_snapshot = self.assessment_component.maximum_score
            self.weight_snapshot = self.assessment_component.weight_percentage
        if self.is_absent or self.is_exempted:
            self.score = None
        super().save(*args, **kwargs)


class StudentResult(TimeStampedUUIDModel):
    """
    Stores computed subject-level results for a student enrollment in a specific term.
    """
    student_enrollment = models.ForeignKey(
        StudentEnrollment,
        on_delete=models.PROTECT,
        related_name='subject_results'
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.PROTECT,
        related_name='subject_results'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='student_results'
    )

    ca_total = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    grade = models.CharField(max_length=5, blank=True, null=True)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'))
    remark = models.CharField(max_length=100, blank=True, null=True)

    subject_position = models.PositiveIntegerField(null=True, blank=True)
    class_highest = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    class_lowest = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    class_average = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    is_incomplete = models.BooleanField(default=False, help_text="True if one or more required assessment components were missing.")
    status = models.CharField(
        max_length=25,
        choices=ResultWorkflowStatus.choices,
        default=ResultWorkflowStatus.DRAFT
    )
    computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Student Subject Result'
        verbose_name_plural = 'Student Subject Results'
        unique_together = ('student_enrollment', 'academic_term', 'subject')
        ordering = ['student_enrollment__student__last_name', 'subject__name']

    def __str__(self):
        return f"{self.student_enrollment.student} | {self.subject.code} | {self.total_score}% ({self.grade})"


class StudentTermSummary(TimeStampedUUIDModel):
    """
    Stores overall student performance for an academic term (report card master record),
    along with workflow approval/publication metadata.
    """
    student_enrollment = models.ForeignKey(
        StudentEnrollment,
        on_delete=models.PROTECT,
        related_name='term_summaries'
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.PROTECT,
        related_name='term_summaries'
    )

    subjects_offered = models.PositiveSmallIntegerField(default=0)
    subjects_passed = models.PositiveSmallIntegerField(default=0)
    total_score = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'))
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    gpa = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'))

    class_position = models.PositiveIntegerField(null=True, blank=True)
    arm_position = models.PositiveIntegerField(null=True, blank=True)
    total_students_in_class = models.PositiveIntegerField(default=0)

    teacher_remarks = models.TextField(blank=True, null=True)
    principal_remarks = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=25,
        choices=ResultWorkflowStatus.choices,
        default=ResultWorkflowStatus.DRAFT
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_term_results'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_term_results'
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Student Term Result Summary'
        verbose_name_plural = 'Student Term Result Summaries'
        unique_together = ('student_enrollment', 'academic_term')
        ordering = ['-academic_term__start_date', '-average_score']

    def __str__(self):
        return (
            f"{self.student_enrollment.student} | {self.academic_term} | "
            f"Avg: {self.average_score}% [{self.get_status_display()}]"
        )


class ResultWorkflowAudit(TimeStampedUUIDModel):
    """
    Immutable audit log recording every workflow transition (Submit, Review, Approve, Publish, Reopen)
    for traceability and security compliance.
    """
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='result_audits')
    academic_term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name='result_audits')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='result_audits')
    class_arm = models.ForeignKey(ClassArm, on_delete=models.SET_NULL, null=True, blank=True, related_name='result_audits')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name='result_audits')

    previous_status = models.CharField(max_length=25, choices=ResultWorkflowStatus.choices)
    new_status = models.CharField(max_length=25, choices=ResultWorkflowStatus.choices)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='result_audit_actions')
    reason = models.TextField(blank=True, null=True, help_text="Mandatory reason when reopening published or locked results.")

    class Meta:
        verbose_name = 'Result Workflow Audit'
        verbose_name_plural = 'Result Workflow Audits'
        ordering = ['-created_at']

    def __str__(self):
        subj = f" ({self.subject.code})" if self.subject else ""
        return f"{self.class_obj.name}{subj}: {self.previous_status} -> {self.new_status} by {self.performed_by}"