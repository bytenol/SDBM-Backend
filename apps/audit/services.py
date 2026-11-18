import datetime
import decimal
import uuid
from typing import Any, Dict, Optional, Union
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction

from .models import AuditLog, AuditAction, AuditCategory
from .middleware import get_current_user, get_current_ip, get_current_user_agent

# Strict list of sensitive keywords and field names that must NEVER be logged in audit payloads
SENSITIVE_FIELD_PATTERNS = {
    'password',
    'password_hash',
    'raw_password',
    'token',
    'refresh',
    'access',
    'secret',
    'key',
    'auth',
    'otp',
    'credit',
    'card',
    'cvv',
    'api_key',
    'signature',
    'verification_token',
    'administrative_notes',
}


def sanitize_value(value: Any) -> Any:
    """
    Recursively normalizes Decimals, UUIDs, dates, and querysets into JSON-safe representations.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, models.Model):
        return str(value.pk)
    if isinstance(value, dict):
        return {str(k): sanitize_value(v) for k, v in value.items() if not any(pat in str(k).lower() for pat in SENSITIVE_FIELD_PATTERNS)}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(item) for item in value]
    return value


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrubs sensitive fields and normalizes data types in a dictionary.
    """
    if not data or not isinstance(data, dict):
        return {}
    sanitized = {}
    for key, val in data.items():
        key_lower = str(key).lower()
        if any(pat in key_lower for pat in SENSITIVE_FIELD_PATTERNS):
            sanitized[key] = "[SCRUBBED]"
        else:
            sanitized[key] = sanitize_value(val)
    return sanitized


def capture_model_state(instance: models.Model, include_fields: Optional[list] = None) -> Dict[str, Any]:
    """
    Extracts field values from a Django model instance safely.
    """
    if not instance or not hasattr(instance, '_meta'):
        return {}
    state = {}
    for field in instance._meta.fields:
        field_name = field.name
        if include_fields and field_name not in include_fields:
            continue
        if any(pat in field_name.lower() for pat in SENSITIVE_FIELD_PATTERNS):
            continue
        try:
            val = getattr(instance, field_name)
            state[field_name] = sanitize_value(val)
        except Exception:
            pass
    return state


def compute_field_diff(before: Dict[str, Any], after: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Compares two model state dictionaries and returns only changed (previous, new) pairs.
    """
    prev_diff = {}
    new_diff = {}
    all_keys = set(before.keys()).union(set(after.keys()))
    for key in all_keys:
        b_val = before.get(key)
        a_val = after.get(key)
        if b_val != a_val:
            prev_diff[key] = b_val
            new_diff[key] = a_val
    return sanitize_dict(prev_diff), sanitize_dict(new_diff)



@transaction.atomic
def log_audit_event(
    action: Union[AuditAction, str],
    category: Union[AuditCategory, str],
    description: str,
    actor: Optional[any] = None,
    actor_identifier: Optional[str] = None,  # <--- Added parameter
    affected_object: Optional[models.Model] = None,
    previous_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    Core atomic service function to create an immutable AuditLog entry.
    Falls back to active contextvars middleware if actor, IP, or user_agent are omitted.
    """
    resolved_actor = actor if actor is not None else get_current_user()
    resolved_ip = ip_address or get_current_ip()
    resolved_agent = user_agent or get_current_user_agent()

    content_type = None
    object_id = None
    object_repr = ""

    if affected_object is not None and hasattr(affected_object, '_meta'):
        try:
            content_type = ContentType.objects.get_for_model(affected_object)
            object_id = str(affected_object.pk)
            object_repr = str(affected_object)[:255]
        except Exception:
            pass

    resolved_actor_identifier = actor_identifier
    if not resolved_actor_identifier:
        if resolved_actor and getattr(resolved_actor, 'is_authenticated', False):
            resolved_actor_identifier = getattr(resolved_actor, 'login_id', None) or getattr(resolved_actor, 'email', '') or str(resolved_actor.pk)
        else:
            resolved_actor_identifier = "SYSTEM"

    audit_log = AuditLog.objects.create(
        actor=resolved_actor if (resolved_actor and getattr(resolved_actor, 'is_authenticated', False)) else None,
        actor_identifier=resolved_actor_identifier,
        action=str(action),
        category=str(category),
        content_type=content_type,
        object_id=object_id,
        object_repr=object_repr,
        description=description,
        previous_values=sanitize_dict(previous_values or {}),
        new_values=sanitize_dict(new_values or {}),
        metadata=sanitize_dict(metadata or {}),
        ip_address=resolved_ip,
        user_agent=resolved_agent,
    )
    return audit_log



def log_account_lifecycle_event(
    action: AuditAction,
    target_user: any,
    description: str,
    metadata: Optional[dict] = None,
) -> None:
    """
    Helper to log account lifecycle events (activation, deactivation, password change, email verification).
    """
    log_audit_event(
        action=action,
        category=AuditCategory.ACCOUNTS,
        description=description,
        affected_object=target_user,
        metadata=metadata or {"target_user_id": str(target_user.pk), "login_id": getattr(target_user, 'login_id', None)},
    )