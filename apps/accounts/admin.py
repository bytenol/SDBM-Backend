from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, UserRole

class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom Django Admin configuration for our UUID-based User model
    supporting dual authentication (login_id & email).
    """
    inlines = [UserRoleInline]
    
    list_display = ('login_id', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_verified', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'roles')
    search_fields = ('login_id', 'email', 'first_name', 'last_name', 'username')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Authentication Identifiers', {'fields': ('login_id', 'email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'username')}),
        ('Status & Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'is_verified',
                'groups',
                'user_permissions',
            )
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_login', 'date_joined')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__login_id', 'user__email', 'role__name')
    readonly_fields = ('id', 'created_at', 'updated_at')