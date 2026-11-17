from rest_framework import permissions
from apps.students.models import StudentGuardian


class IsAdminPortalUser(permissions.BasePermission):
    """
    Allows access strictly to SUPER_ADMIN, ADMIN, or Django superusers.
    """
    message = "You do not have administrator permissions to access this resource."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists()


class IsStaffPortalUser(permissions.BasePermission):
    """
    Allows access to authenticated users with the STAFF role and an attached staff_profile.
    """
    message = "A valid staff profile is required to access this endpoint."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return (
            user.roles.filter(name='STAFF').exists()
            and hasattr(user, 'staff_profile')
            and user.staff_profile is not None
        )


class IsStudentPortalUser(permissions.BasePermission):
    """
    Allows access to authenticated users with the STUDENT role and an attached student_profile.
    """
    message = "A valid student profile is required to access this endpoint."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return (
            user.roles.filter(name='STUDENT').exists()
            and hasattr(user, 'student_profile')
            and user.student_profile is not None
        )


class IsParentPortalUser(permissions.BasePermission):
    """
    Allows access to authenticated users with the PARENT role or linked children via StudentGuardian.
    """
    message = "A valid parent/guardian account is required to access this endpoint."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.roles.filter(name='PARENT').exists():
            return True
        return StudentGuardian.objects.filter(guardian=user).exists()