from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'actor_identifier',
        'action',
        'category',
        'content_type',
        'object_repr',
        'ip_address',
    )
    list_filter = ('category', 'action', 'content_type', 'created_at')
    search_fields = (
        'actor_identifier',
        'actor__login_id',
        'actor__email',
        'object_id',
        'object_repr',
        'description',
        'ip_address',
    )
    readonly_fields = (
        'id',
        'actor',
        'actor_identifier',
        'action',
        'category',
        'content_type',
        'object_id',
        'object_repr',
        'description',
        'previous_values',
        'new_values',
        'metadata',
        'ip_address',
        'user_agent',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False