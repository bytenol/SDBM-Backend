from rest_framework.permissions import BasePermission


class IsAdminOrSuperAdmin(BasePermission):
    """
    Allows access only to users with ADMIN or SUPER_ADMIN roles.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.roles.filter(
            name__in=['ADMIN', 'SUPER_ADMIN']
        ).exists()