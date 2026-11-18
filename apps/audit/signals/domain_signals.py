# apps/audit/domain_signals.py
import threading
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from apps.academics.models import AcademicSession, AcademicTerm, Class, ClassArm, Subject
from apps.audit.models import AuditAction, AuditCategory
from apps.audit.services import capture_model_state, compute_field_diff, log_audit_event
from apps.students.models import Student, StudentEnrollment, StudentGuardian
from apps.staff.models import Staff, Department, Designation, StaffEmployment, TeacherAssignment

# Thread-local storage to hold 'before' states during pre_save -> post_save cycles
_thread_locals = threading.local()

TRACKED_DOMAIN_MODELS = (
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject,
    Student,
    StudentEnrollment,
    StudentGuardian,
    Staff,
    Department,
    Designation,
    StaffEmployment,
    TeacherAssignment,
)


def get_model_category(model_cls) -> AuditCategory:
    """Maps a model class to its corresponding AuditCategory."""
    if model_cls in (AcademicSession, AcademicTerm, Class, ClassArm, Subject):
        return AuditCategory.ACADEMICS
    if model_cls in (Student, StudentEnrollment, StudentGuardian):
        return AuditCategory.STUDENTS
    if model_cls in (Staff, Department, Designation, StaffEmployment, TeacherAssignment):
        return AuditCategory.STAFF
    return AuditCategory.SYSTEM


@receiver(pre_save)
def capture_pre_save_state(sender, instance, **kwargs):
    if sender not in TRACKED_DOMAIN_MODELS:
        return
    if not instance.pk:
        return  # New instance, no previous state

    try:
        old_instance = sender.objects.get(pk=instance.pk)
        if not hasattr(_thread_locals, 'pre_save_states'):
            _thread_locals.pre_save_states = {}
        _thread_locals.pre_save_states[instance.pk] = capture_model_state(old_instance)
    except sender.DoesNotExist:
        pass


@receiver(post_save)
def audit_domain_post_save(sender, instance, created, **kwargs):
    if sender not in TRACKED_DOMAIN_MODELS:
        return

    category = get_model_category(sender)
    model_name = sender._meta.verbose_name.title()

    if created:
        new_vals = capture_model_state(instance)
        log_audit_event(
            action=AuditAction.CREATE,
            category=category,
            description=f"Created {model_name}: {str(instance)}",
            affected_object=instance,
            new_values=new_vals,
        )
    else:
        pre_states = getattr(_thread_locals, 'pre_save_states', {})
        old_vals = pre_states.pop(instance.pk, {})
        new_vals = capture_model_state(instance)
        prev_diff, new_diff = compute_field_diff(old_vals, new_vals)

        if prev_diff:  # Only log if actual fields changed
            log_audit_event(
                action=AuditAction.UPDATE,
                category=category,
                description=f"Updated {model_name}: {str(instance)}",
                affected_object=instance,
                previous_values=prev_diff,
                new_values=new_diff,
            )


@receiver(post_delete)
def audit_domain_post_delete(sender, instance, **kwargs):
    if sender not in TRACKED_DOMAIN_MODELS:
        return

    category = get_model_category(sender)
    model_name = sender._meta.verbose_name.title()
    deleted_vals = capture_model_state(instance)

    log_audit_event(
        action=AuditAction.DELETE,
        category=category,
        description=f"Deleted {model_name}: {str(instance)}",
        affected_object=instance,
        previous_values=deleted_vals,
    )