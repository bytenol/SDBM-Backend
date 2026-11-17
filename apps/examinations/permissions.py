from rest_framework import permissions
from apps.students.models import StudentGuardian
from apps.staff.models import TeacherAssignment
from .models import ResultWorkflowStatus


class IsExamAdminOrReadOnly(permissions.BasePermission):
    """
    Allows full write access to SUPER_ADMIN and ADMIN.
    Allows read-only access to authenticated users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_superuser:
            return True
        return request.user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists()


class IsTeacherOrExamAdmin(permissions.BasePermission):
    """
    Allows access to SUPER_ADMIN, ADMIN, and STAFF (with a valid staff_profile).
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists():
            return True
        return user.roles.filter(name='STAFF').exists() and hasattr(user, 'staff_profile')


class CanAccessResultRecord(permissions.BasePermission):
    """
    Object-level permission for StudentResult and StudentTermSummary:
    - SUPER_ADMIN / ADMIN: Full access.
    - STAFF: Read access to results within their assigned classes/subjects.
    - STUDENT: Read-only access to their own PUBLISHED or LOCKED results.
    - PARENT: Read-only access to PUBLISHED or LOCKED results of linked children.
    """
    PUBLISHED_STATES = [ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists():
            return True

        if request.method not in permissions.SAFE_METHODS:
            return False

        enrollment = obj.student_enrollment
        student = enrollment.student

        # Staff check: assigned to the class or subject in that session
        if user.roles.filter(name='STAFF').exists() and hasattr(user, 'staff_profile'):
            return TeacherAssignment.objects.filter(
                staff=user.staff_profile,
                academic_session=enrollment.academic_session,
                class_obj=enrollment.class_obj,
                is_active=True
            ).exists()

        # Student check: must own the profile AND result must be published
        if user.roles.filter(name='STUDENT').exists() and hasattr(user, 'student_profile'):
            return (
                user.student_profile.id == student.id
                and obj.status in self.PUBLISHED_STATES
            )

        # Parent check: must be linked via StudentGuardian AND result must be published
        if user.roles.filter(name='PARENT').exists():
            is_linked = StudentGuardian.objects.filter(
                student=student,
                guardian=user
            ).exists()
            return is_linked and obj.status in self.PUBLISHED_STATES

        return False