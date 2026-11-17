from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedUUIDModel
from apps.academics.models import AcademicSession, AcademicTerm, Class, ClassArm

class Student(TimeStampedUUIDModel):
    """
    Student profile model maintaining 1:1 relationship with accounts.User.
    Note: The admission number is stored in user.login_id and is NOT duplicated here.
    """
    class GenderChoices(models.TextChoices):
        MALE = 'MALE', 'Male'
        FEMALE = 'FEMALE', 'Female'

    class StatusChoices(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        GRADUATED = 'GRADUATED', 'Graduated'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'
        TRANSFERRED = 'TRANSFERRED', 'Transferred'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile',
        help_text="Linked authentication user account"
    )
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GenderChoices.choices)
    passport_photograph = models.ImageField(upload_to='students/passports/', blank=True, null=True)
    
    nationality = models.CharField(max_length=100, default='Nigerian')
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    lga = models.CharField(max_length=100, blank=True, null=True, verbose_name="Local Government Area")
    residential_address = models.TextField(blank=True, null=True)
    
    admission_date = models.DateField()
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.ACTIVE)
    
    medical_info = models.TextField(blank=True, null=True, help_text="Allergies, chronic conditions, or special medical needs")
    administrative_notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        admission_no = self.user.login_id if self.user else "No ID"
        return f"{self.last_name}, {self.first_name} ({admission_no})"


class StudentGuardian(TimeStampedUUIDModel):
    """
    Through model connecting Students to Parent/Guardian User accounts,
    supporting multiple children per guardian and multiple guardians per student.
    """
    class RelationshipChoices(models.TextChoices):
        FATHER = 'FATHER', 'Father'
        MOTHER = 'MOTHER', 'Mother'
        GUARDIAN = 'GUARDIAN', 'Guardian'
        SPONSOR = 'SPONSOR', 'Sponsor'
        OTHER = 'OTHER', 'Other'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wards',
        help_text="User account possessing the PARENT role"
    )
    relationship_type = models.CharField(max_length=20, choices=RelationshipChoices.choices, default=RelationshipChoices.PARENT if hasattr(RelationshipChoices, 'PARENT') else RelationshipChoices.FATHER)
    is_primary = models.BooleanField(default=False, help_text="Designates the primary contact guardian")
    is_emergency_contact = models.BooleanField(default=False)
    can_collect_student = models.BooleanField(default=True)
    receives_notifications = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Student Guardian'
        verbose_name_plural = 'Student Guardians'
        unique_together = ('student', 'guardian')

    def __str__(self):
        return f"{self.guardian} -> {self.student} ({self.get_relationship_type_display()})"


class StudentEnrollment(TimeStampedUUIDModel):
    """
    Session-bound enrollment history. Stores which class and arm a student belongs to
    for a given academic session, preserving historical records across promotions.
    """
    class EnrollmentStatus(models.TextChoices):
        ENROLLED = 'ENROLLED', 'Enrolled'
        COMPLETED = 'COMPLETED', 'Completed'
        REPEATING = 'REPEATING', 'Repeating'
        TRANSFERRED = 'TRANSFERRED', 'Transferred'

    class EnrollmentType(models.TextChoices):
        NEW_ADMISSION = 'NEW_ADMISSION', 'New Admission'
        PROMOTION = 'PROMOTION', 'Promotion'
        TRANSFER = 'TRANSFER', 'Transfer'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='session_enrollments')
    academic_term = models.ForeignKey(AcademicTerm, on_delete=models.SET_NULL, null=True, blank=True, related_name='term_enrollments')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_enrollments')
    class_arm = models.ForeignKey(ClassArm, on_delete=models.SET_NULL, null=True, blank=True, related_name='arm_enrollments')
    
    enrollment_date = models.DateField()
    status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ENROLLED)
    enrollment_type = models.CharField(max_length=30, choices=EnrollmentType.choices, default=EnrollmentType.NEW_ADMISSION)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Student Enrollment'
        verbose_name_plural = 'Student Enrollments'
        unique_together = ('student', 'academic_session')
        ordering = ['-academic_session__start_date', 'class_obj__display_order']

    def __str__(self):
        arm_name = f" - {self.class_arm.name}" if self.class_arm else ""
        return f"{self.student} | {self.class_obj.name}{arm_name} ({self.academic_session.name})"



class StudentDocument(TimeStampedUUIDModel):
    """
    Stores official documentation associated with a student record.
    """
    class DocumentType(models.TextChoices):
        BIRTH_CERTIFICATE = 'BIRTH_CERTIFICATE', 'Birth Certificate'
        PREVIOUS_REPORT = 'PREVIOUS_REPORT', 'Previous Report Card'
        TRANSFER_CERTIFICATE = 'TRANSFER_CERTIFICATE', 'Transfer Certificate'
        MEDICAL_REPORT = 'MEDICAL_REPORT', 'Medical Report'
        OTHER = 'OTHER', 'Other Document'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file = models.FileField(upload_to='students/documents/')
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Student Document'
        verbose_name_plural = 'Student Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.student}"



class StudentPromotionLog(TimeStampedUUIDModel):
    """
    Audit log tracking bulk or individual student promotions between academic sessions.
    """
    source_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='promotions_from')
    destination_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='promotions_to')
    destination_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='+')
    destination_class_arm = models.ForeignKey(ClassArm, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    promoted_students_count = models.PositiveIntegerField(default=0)
    promoted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Student Promotion Log'
        verbose_name_plural = 'Student Promotion Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Promotion: {self.source_session.name} -> {self.destination_session.name} ({self.promoted_students_count} students)"