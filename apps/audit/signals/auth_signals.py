from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from ..services import log_audit_event
from ..models import AuditAction, AuditCategory


@receiver(user_logged_in)
def audit_user_logged_in(sender, request, user, **kwargs):
    log_audit_event(
        action=AuditAction.LOGIN,
        category=AuditCategory.AUTHENTICATION,
        description=f"User {user.login_id or user.email} successfully logged in.",
        actor=user,
        metadata={"login_id": getattr(user, 'login_id', None), "email": user.email},
    )


@receiver(user_logged_out)
def audit_user_logged_out(sender, request, user, **kwargs):
    if user and user.is_authenticated:
        log_audit_event(
            action=AuditAction.LOGOUT,
            category=AuditCategory.AUTHENTICATION,
            description=f"User {user.login_id or user.email} logged out.",
            actor=user,
        )


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    # Never log password from credentials! Extract only username/login identifier
    identifier = credentials.get('login_id') or credentials.get('username') or credentials.get('email') or 'Unknown'
    log_audit_event(
        action=AuditAction.LOGIN_FAILED,
        category=AuditCategory.AUTHENTICATION,
        description=f"Failed login attempt for identifier: '{identifier}'.",
        actor=None,
        actor_identifier=str(identifier),
        metadata={"attempted_identifier": str(identifier)},
    )