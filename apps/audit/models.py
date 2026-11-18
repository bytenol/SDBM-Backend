from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder

from apps.core.models import TimeStampedUUIDModel


class AuditAction(models.TextChoices):
    CREATE = 'CREATE', 'Create'
    UPDATE = 'UPDATE', 'Update'
    DELETE = 'DELETE', 'Delete'
    LOGIN = 'LOGIN', 'Login'
    LOGOUT = 'LOGOUT', 'Logout'
    LOGIN_FAILED = 'LOGIN_FAILED', 'Login Failed'
    PASSWORD_CHANGED = 'PASSWORD_CHANGED', 'Password Changed'
    PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
    EMAIL_VERIFIED = 'EMAIL_VERIFIED', 'Email Verified'
    ACCOUNT_ACTIVATED = 'ACCOUNT_ACTIVATED', 'Account Activated'
    ACCOUNT_DEACTIVATED = 'ACCOUNT_DEACTIVATED', 'Account Deactivated'
    APPROVE = 'APPROVE', 'Approve'
    REJECT = 'REJECT', 'Reject'
    PUBLISH = 'PUBLISH', 'Publish'
    UNPUBLISH = 'UNPUBLISH', 'Unpublish / Reopen'
    EXPORT = 'EXPORT', 'Export'
    IMPORT = 'IMPORT', 'Import'
    OTHER = 'OTHER', 'Other'


class AuditCategory(models.TextChoices):
    AUTHENTICATION = 'AUTHENTICATION', 'Authentication & Security'
    ACCOUNTS = 'ACCOUNTS', 'User Accounts & Roles'
    ACADEMICS = 'ACADEMICS', 'Academic Structure & Calendar'
    STUDENTS = 'STUDENTS', 'Student Management & Enrollment'
    STAFF = 'STAFF', 'Staff Management & Assignments'
    EXAMINATIONS = 'EXAMINATIONS', 'Examinations & Results'
    SYSTEM = 'SYSTEM', 'System & Background Operations'


class AuditLogQuerySet(models.QuerySet):
    """
    Protects audit records against accidental bulk updates or deletions via the ORM.
    """
    def update(self, **kwargs):
        raise PermissionDenied("AuditLog records are immutable and cannot be updated.")

    def delete(self):
        raise PermissionDenied(
            "Direct deletion of AuditLog records is forbidden. "
            "Use the controlled retention policy service if purging expired logs."
        )

    def _raw_purge(self):
        """
        Internal helper used strictly by the controlled retention management command.
        """
        return super().delete()


class AuditLogManager(models.Manager):
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)


class AuditLog(TimeStampedUUIDModel):
    """
    Centralized, append-only audit log recording security, administrative,
    academic, and system-generated events across the platform.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="Authenticated user who performed the action (null for system or unauthenticated events)."
    )
    actor_identifier = models.CharField(
        max_length=150,
        blank=True,
        default='',
        db_index=True,
        help_text="Snapshot of actor login_id/email or attempted identifier on failed login."
    )

    action = models.CharField(
        max_length=30,
        choices=AuditAction.choices,
        db_index=True
    )
    category = models.CharField(
        max_length=30,
        choices=AuditCategory.choices,
        db_index=True
    )

    # Generic target reference supporting UUID primary keys across all apps
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="Content type of the affected database model."
    )
    object_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Stringified UUID (or PK) of the affected record."
    )
    affected_object = GenericForeignKey('content_type', 'object_id')
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Human-readable snapshot of the affected record at event time."
    )

    description = models.TextField(
        help_text="Human-readable summary describing what occurred."
    )
    previous_values = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
        help_text="Sanitized before-state field values (for UPDATE and DELETE events)."
    )
    new_values = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
        help_text="Sanitized after-state field values (for CREATE and UPDATE events)."
    )
    metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
        help_text="Additional context (e.g. request path, method, session_id, term_id, record counts)."
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Originating client IPv4 or IPv6 address."
    )
    user_agent = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text="Client HTTP User-Agent string."
    )

    objects = AuditLogManager()

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='audit_created_at_idx'),
            models.Index(fields=['category', '-created_at'], name='audit_cat_created_idx'),
            models.Index(fields=['action', '-created_at'], name='audit_act_created_idx'),
            models.Index(fields=['actor', '-created_at'], name='audit_actor_created_idx'),
            models.Index(fields=['content_type', 'object_id', '-created_at'], name='audit_target_created_idx'),
        ]

    def __str__(self):
        actor_label = self.actor_identifier or (self.actor.login_id if self.actor else 'SYSTEM')
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {actor_label} | {self.action} ({self.category})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("AuditLog records are append-only and cannot be modified after creation.")
        if self.actor and not self.actor_identifier:
            self.actor_identifier = getattr(self.actor, 'login_id', None) or getattr(self.actor, 'email', '') or str(self.actor.pk)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AuditLog records cannot be deleted via model instance delete().")