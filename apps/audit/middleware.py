import contextvars
from typing import Optional
from django.http import HttpRequest

_current_request: contextvars.ContextVar[Optional[HttpRequest]] = contextvars.ContextVar('_current_request', default=None)


class AuditRequestContextMiddleware:
    """
    Captures the current HTTP request in a thread/async-safe context variable
    so services and signal handlers can extract acting user context, IP address,
    and User-Agent headers without explicit parameter threading.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        token = _current_request.set(request)
        try:
            response = self.get_response(request)
            return response
        finally:
            _current_request.reset(token)


def get_current_request() -> Optional[HttpRequest]:
    """Returns the currently active HttpRequest object, if any."""
    return _current_request.get()


def get_current_user() -> Optional[any]:
    """Returns the currently authenticated user from the active request, if any."""
    req = get_current_request()
    if req and hasattr(req, 'user') and req.user.is_authenticated:
        return req.user
    return None


def get_current_ip() -> Optional[str]:
    """Safely extracts client IP address from request headers or remote address."""
    req = get_current_request()
    if not req:
        return None
    x_forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return req.META.get('REMOTE_ADDR')


def get_current_user_agent() -> str:
    """Extracts and truncates the client User-Agent header."""
    req = get_current_request()
    if not req:
        return ''
    return req.META.get('HTTP_USER_AGENT', '')[:512]