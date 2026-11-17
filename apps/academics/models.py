from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedUUIDModel

class AcademicSession(TimeStampedUUIDModel):
    """
    Represents an academic year, e.g., '2026/2027'.
    """
    name = models.CharField(max_length=20, unique=True, help_text="e.g. 2026/2027")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text="Designates whether this is the active school session.")


    class Meta:
        verbose_name = 'Academic Session'
        verbose_name_plural = 'Academic Sessions'
        ordering = ['-start_date']


    def __str__(self):
        status = " (Current)" if self.is_current else ""
        return f"{self.name}{status}"


    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Session start date must be earlier than the end date.")


    def save(self, *args, **kwargs):
        self.full_clean()
        # Ensure only one session is marked as current
        if self.is_current:
            AcademicSession.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)



class AcademicTerm(TimeStampedUUIDModel):
    """
    Represents an academic term belonging to an academic session (First, Second, Third Term).
    """
    class TermChoices(models.TextChoices):
        FIRST = 'FIRST', 'First Term'
        SECOND = 'SECOND', 'Second Term'
        THIRD = 'THIRD', 'Third Term'

    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=20, choices=TermChoices.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text="Designates whether this is the active term.")

    class Meta:
        verbose_name = 'Academic Term'
        verbose_name_plural = 'Academic Terms'
        unique_together = ('session', 'name')
        ordering = ['session', 'name']


    def __str__(self):
        status = " (Current)" if self.is_current else ""
        return f"{self.get_name_display()} - {self.session.name}{status}"


    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("Term start date must be earlier than the end date.")
            if self.session:
                if self.start_date < self.session.start_date or self.end_date > self.session.end_date:
                    raise ValidationError("Term dates must fall strictly within the parent session's start and end dates.")


    def save(self, *args, **kwargs):
        self.full_clean()
        # Ensure only one term is marked as current across the entire school
        if self.is_current:
            AcademicTerm.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)



class SchoolSettings(TimeStampedUUIDModel):
    """
    Singleton model storing institutional metadata and current active academic context.
    """
    school_name = models.CharField(max_length=255, default="ByteNol Demo International College")
    school_code = models.CharField(max_length=50, unique=True, default="BDIC")
    logo = models.ImageField(upload_to='school/logo/', blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    current_session = models.ForeignKey(AcademicSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    current_term = models.ForeignKey(AcademicTerm, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        verbose_name = 'School Settings'
        verbose_name_plural = 'School Settings'

    def __str__(self):
        return self.school_name

    def save(self, *args, **kwargs):
        # Enforce Singleton pattern: ensure only one record ever exists
        if not self.pk and SchoolSettings.objects.exists():
            raise ValidationError("There can only be one SchoolSettings instance. Edit the existing record.")
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=cls.objects.first().pk if cls.objects.exists() else None)
        return obj



class Class(TimeStampedUUIDModel):
    """
    Represents grade levels (e.g. Nursery 1, Primary 1, JSS 1, SSS 1).
    """
    class EducationLevel(models.TextChoices):
        NURSERY = 'NURSERY', 'Nursery'
        PRIMARY = 'PRIMARY', 'Primary'
        JUNIOR_SECONDARY = 'JUNIOR_SECONDARY', 'Junior Secondary'
        SENIOR_SECONDARY = 'SENIOR_SECONDARY', 'Senior Secondary'

    name = models.CharField(max_length=50, unique=True, help_text="e.g. Primary 1, JSS 1")
    code = models.CharField(max_length=20, unique=True, help_text="e.g. PRI-1, JSS-1")
    education_level = models.CharField(max_length=30, choices=EducationLevel.choices)
    description = models.TextField(blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0, help_text="Order in which classes appear in lists.")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class ClassArm(TimeStampedUUIDModel):
    """
    Represents sub-divisions or streams of a class (e.g. Primary 1 Gold, Primary 1 Silver).
    """
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='arms')
    name = models.CharField(max_length=50, help_text="e.g. Gold, Arm A, Ruby")
    code = models.CharField(max_length=20, blank=True, null=True)
    capacity = models.PositiveIntegerField(default=35, help_text="Maximum student capacity for this arm.")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Class Arm'
        verbose_name_plural = 'Class Arms'
        unique_together = ('class_obj', 'name')
        ordering = ['class_obj', 'name']

    def __str__(self):
        return f"{self.class_obj.name} - {self.name}"


class Subject(TimeStampedUUIDModel):
    """
    Master repository of all subjects taught in the school.
    """
    class Category(models.TextChoices):
        SCIENCES = 'SCIENCES', 'Sciences'
        ARTS = 'ARTS', 'Arts & Humanities'
        COMMERCIAL = 'COMMERCIAL', 'Commercial'
        GENERAL = 'GENERAL', 'General / Compulsory'

    name = models.CharField(max_length=100, unique=True, help_text="e.g. Mathematics, Islamic Studies")
    code = models.CharField(max_length=20, unique=True, help_text="e.g. MTH-101")
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.GENERAL)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"



class ClassSubject(TimeStampedUUIDModel):
    """
    Through model defining which subjects are offered by which classes.
    """
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='subject_classes')
    is_compulsory = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Class Subject'
        verbose_name_plural = 'Class Subjects'
        unique_together = ('class_obj', 'subject')
        ordering = ['class_obj', 'display_order']

    def __str__(self):
        compulsory_str = "Compulsory" if self.is_compulsory else "Elective"
        return f"{self.class_obj.name} -> {self.subject.name} ({compulsory_str})"