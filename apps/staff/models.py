from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedUUIDModel
from apps.academics.models import AcademicSession, Class, ClassArm, Subject


class Department(TimeStampedUUIDModel):
    """
    Represents organizational departments within the institution (e.g. Science, Administration, ICT).
    """
    name = models.CharField(max_length=150, unique=True, help_text="e.g. Science Department")
    code = models.CharField(max_length=50, unique=True, help_text="e.g. SCI")
    description = models.TextField(blank=True, null=True)
    head = models.ForeignKey(
        'Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
        help_text="Staff member heading this department"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['name']

    def __str__(self):
        return self.name


class Designation(TimeStampedUUIDModel):
    """
    Represents professional job titles or designations (e.g. Principal, Classroom Teacher, Accountant).
    Note: Designations are job titles, distinct from application permission Roles.
    """
    class Category(models.TextChoices):
        ACADEMIC = 'ACADEMIC', 'Academic Staff'
        ADMINISTRATIVE = 'ADMINISTRATIVE', 'Administrative Staff'
        TECHNICAL = 'TECHNICAL', 'Technical Staff'
        SUPPORT = 'SUPPORT', 'Support Staff'

    name = models.CharField(max_length=150, unique=True, help_text="e.g. Classroom Teacher")
    code = models.CharField(max_length=50, unique=True, help_text="e.g. TCH")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.ACADEMIC)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Designation'
        verbose_name_plural = 'Designations'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Staff(TimeStampedUUIDModel):
    """
    Staff profile model maintaining 1:1 relationship with accounts.User.
    Note: Staff IDs are stored in user.login_id (e.g., STF-2026-0001).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile',
        help_text="Linked authentication user account"
    )
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[('MALE', 'Male'), ('FEMALE', 'Female')])
    passport_photograph = models.ImageField(upload_to='staff/passports/', blank=True, null=True)
    
    nationality = models.CharField(max_length=100, default='Nigerian')
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    lga = models.CharField(max_length=100, blank=True, null=True, verbose_name="Local Government Area")
    residential_address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    emergency_contact_name = models.CharField(max_length=255, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True, null=True)
    
    bio = models.TextField(blank=True, null=True, help_text="Professional biography or profile description")
    administrative_notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Staff'
        verbose_name_plural = 'Staff'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        staff_id = self.user.login_id if self.user else "No ID"
        return f"{self.last_name}, {self.first_name} ({staff_id})"


class StaffEmployment(TimeStampedUUIDModel):
    """
    Employment history and current contract details for staff members.
    """
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full-Time'
        PART_TIME = 'PART_TIME', 'Part-Time'
        CONTRACT = 'CONTRACT', 'Contract'
        TEMPORARY = 'TEMPORARY', 'Temporary'
        INTERN = 'INTERN', 'Intern'

    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ON_LEAVE = 'ON_LEAVE', 'On Leave'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        RESIGNED = 'RESIGNED', 'Resigned'
        TERMINATED = 'TERMINATED', 'Terminated'
        RETIRED = 'RETIRED', 'Retired'

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='employment_records')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='staff_members')
    designation = models.ForeignKey(Designation, on_delete=models.PROTECT, related_name='staff_members')
    employment_type = models.CharField(max_length=30, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Staff Employment'
        verbose_name_plural = 'Staff Employment Records'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.staff} - {self.designation.name} ({self.department.name}) [{self.get_status_display()}]"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Employment start date cannot be later than the end date.")


class TeacherAssignment(TimeStampedUUIDModel):
    """
    Manages pedagogical assignments connecting staff to academic sessions, classes, arms, and subjects.
    """
    class AssignmentType(models.TextChoices):
        SUBJECT_TEACHER = 'SUBJECT_TEACHER', 'Subject Teacher'
        CLASS_TEACHER = 'CLASS_TEACHER', 'Class Teacher (Form Master)'
        CLASS_SUPERVISOR = 'CLASS_SUPERVISOR', 'Class Supervisor'

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='teaching_assignments')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='session_teaching_assignments')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='assigned_teachers')
    class_arm = models.ForeignKey(ClassArm, on_delete=models.SET_NULL, null=True, blank=True, related_name='arm_teachers')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True, related_name='subject_teachers')
    
    assignment_type = models.CharField(max_length=30, choices=AssignmentType.choices, default=AssignmentType.SUBJECT_TEACHER)
    is_class_teacher = models.BooleanField(default=False, help_text="Designates if this staff member is the Form Master / Class Teacher")
    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Teacher Assignment'
        verbose_name_plural = 'Teacher Assignments'
        ordering = ['academic_session', 'class_obj', 'class_arm']

    def __str__(self):
        subj_str = f" teaching {self.subject.name}" if self.subject else ""
        arm_str = f" - {self.class_arm.name}" if self.class_arm else ""
        return f"{self.staff}{subj_str} in {self.class_obj.name}{arm_str} ({self.academic_session.name})"

    def clean(self):
        super().clean()
        # Validate that class_arm belongs to class_obj if specified
        if self.class_arm and self.class_arm.class_obj != self.class_obj:
            raise ValidationError("The selected class arm does not belong to the specified class.")

        # If subject teacher, validate that subject is offered by the class
        if self.assignment_type == self.AssignmentType.SUBJECT_TEACHER and self.subject:
            if not self.class_obj.class_subjects.filter(subject=self.subject, is_active=True).exists():
                raise ValidationError(f"Subject '{self.subject.name}' is not assigned as active for class '{self.class_obj.name}'.")


class StaffQualification(TimeStampedUUIDModel):
    """
    Stores academic and professional qualifications for staff members.
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='qualifications')
    qualification_name = models.CharField(max_length=255, help_text="e.g. B.Sc. Computer Science, PGDE")
    institution = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255, blank=True, null=True)
    qualification_level = models.CharField(max_length=100, help_text="e.g. Bachelor's Degree, Master's, NCE")
    start_year = models.PositiveIntegerField(blank=True, null=True)
    completion_year = models.PositiveIntegerField()
    certificate_document = models.FileField(upload_to='staff/certificates/', blank=True, null=True)

    class Meta:
        verbose_name = 'Staff Qualification'
        verbose_name_plural = 'Staff Qualifications'
        ordering = ['-completion_year']

    def __str__(self):
        return f"{self.qualification_name} - {self.staff} ({self.completion_year})"


class StaffDocument(TimeStampedUUIDModel):
    """
    Stores official documentation associated with a staff member's employment.
    """
    class DocumentType(models.TextChoices):
        CV = 'CV', 'Curriculum Vitae'
        CERTIFICATE = 'CERTIFICATE', 'Academic/Professional Certificate'
        ID_CARD = 'ID_CARD', 'Means of Identification'
        EMPLOYMENT_LETTER = 'EMPLOYMENT_LETTER', 'Employment Offer Letter'
        OTHER = 'OTHER', 'Other Document'

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file = models.FileField(upload_to='staff/documents/')
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Staff Document'
        verbose_name_plural = 'Staff Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.staff}"