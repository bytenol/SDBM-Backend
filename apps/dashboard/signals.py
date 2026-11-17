from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.academics.models import SchoolSettings, AcademicSession, AcademicTerm, Class, ClassArm, Subject
from apps.students.models import Student, StudentEnrollment
from apps.staff.models import Staff, Department, Designation, StaffEmployment, TeacherAssignment
from apps.examinations.models import Examination, StudentResult, StudentTermSummary, ResultWorkflowAudit
from .cache import bump_dashboard_cache_version

TRACKED_MODELS = (
    SchoolSettings,
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject,
    Student,
    StudentEnrollment,
    Staff,
    Department,
    Designation,
    StaffEmployment,
    TeacherAssignment,
    Examination,
    StudentResult,
    StudentTermSummary,
    ResultWorkflowAudit,
)


@receiver([post_save, post_delete])
def invalidate_dashboard_aggregates_on_change(sender, **kwargs):
    if sender in TRACKED_MODELS:
        bump_dashboard_cache_version()