from django.core.management.base import BaseCommand, CommandError

from missionlog.services.production_report_worker import process_production_report_email


class Command(BaseCommand):
    help = "Process one queued MissionLog production report email request."

    def add_arguments(self, parser):
        parser.add_argument("--audit-id", type=int, required=True)

    def handle(self, *args, **options):
        audit_id = options.get("audit_id")
        if not audit_id:
            raise CommandError("--audit-id is required")
        process_production_report_email(audit_id=audit_id)
        self.stdout.write(self.style.SUCCESS(f"Processed audit #{audit_id}"))
