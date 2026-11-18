# apps/audit/apps.py
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'
    verbose_name = 'Audit Logs & System Activity Tracking'

    def ready(self):
        # import apps.audit.signals       # noqa: F401
        import apps.audit.signals.auth_signals  # noqa: F401
        import apps.audit.signals.domain_signals