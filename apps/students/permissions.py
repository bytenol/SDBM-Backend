# apps/students/permissions.py
from rest_framework import permissions
from .models import StudentGuardian

class IsStudentAdminOrAuthorizedStaff(permissions.BasePermission):
    """
    Allows full access to SUPER_ADMIN, ADMIN, and authorized STAFF.
    Restricts STUDENTS and PARENTS to object-level read permissions.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN', 'STAFF']).exists() or request.user.roles.filter(name__in=['STUDENT', 'PARENT']).exists()

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN', 'STAFF']).exists():
            return True

        # Resolve student instance whether obj is Student or a related model (like Document or Enrollment)
        student = obj if hasattr(obj, 'user') else getattr(obj, 'student', None)
        if not student:
            return False

        # Student can view their own profile
        if user.roles.filter(name='STUDENT').exists():
            return hasattr(user, 'student_profile') and user.student_profile == student

        # Parent can view linked children
        if user.roles.filter(name='PARENT').exists():
            return StudentGuardian.objects.filter(student=student, guardian=user).exists()

        return False