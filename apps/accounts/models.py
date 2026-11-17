import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import TimeStampedUUIDModel
from .managers import UserManager

class Role(TimeStampedUUIDModel):
    """
    Represents system roles: SUPER_ADMIN, ADMIN, STUDENT, STAFF, PARENT.
    Enables flexible multi-role assignments per user.
    """
    class RoleChoices(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        STUDENT = 'STUDENT', 'Student'
        STAFF = 'STAFF', 'Staff'
        PARENT = 'PARENT', 'Parent'

    name = models.CharField(max_length=50, choices=RoleChoices.choices, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['name']

    def __str__(self):
        return self.get_name_display()


class User(AbstractUser, TimeStampedUUIDModel):
    """
    Custom User model using UUID primary key and supporting dual authentication:
    - login_id for Students and Staff (e.g., STU-2026-0001)
    - email for Parents and Administrators
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID primary key"
    )
    
    # Override username to be nullable since authentication is handled via login_id or email
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    
    # Authentication identifiers
    login_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Generated ID for students and staff (e.g. STU-2026-0001)"
    )
    email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Email address for parents and administrators"
    )

    # Account status flags
    is_verified = models.BooleanField(
        default=True,
        help_text="Designates whether this user has verified their email address."
    )
    
    # Roles M2M through UserRole
    roles = models.ManyToManyField(
        Role,
        through='UserRole',
        related_name='users',
        blank=True
    )

    # Resolve reverse accessor clashes with auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_permissions_set',
        related_query_name='user',
    )

    objects = UserManager()

    USERNAME_FIELD = 'login_id'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['login_id']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.login_id or self.email or str(self.id)

    @property
    def role_names(self):
        return list(self.roles.values_list('name', flat=True))


class UserRole(TimeStampedUUIDModel):
    """
    Through model connecting User and Role with audit timestamps.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_users')

    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user} -> {self.role.name}"