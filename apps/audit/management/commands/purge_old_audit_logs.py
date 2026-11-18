import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Purges audit logs older than a specified number of days (for data retention compliance)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Retention period in days (default: 365 days). Logs older than this will be purged.',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Required flag to confirm deletion of old audit logs.',
        )

    def handle(self, *args, **options):
        days = options['days']
        confirm = options['confirm']

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: You are about to permanently purge audit logs older than {days} days. "
                    "Pass --confirm to execute this deletion."
                )
            )
            return

        cutoff_date = timezone.now() - datetime.timedelta(days=days)
        old_logs_qs = AuditLog.objects.filter(created_at__lt=cutoff_date)
        count = old_logs_qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"No audit logs older than {days} days found."))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f"Purging {count} audit log(s) older than {cutoff_date}..."))
        old_logs_qs._raw_purge()
        self.stdout.write(self.style.SUCCESS(f"Successfully purged {count} old audit log record(s)."))