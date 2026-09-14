from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from genericcharts.models import TankEstimateSyncRun


class Command(BaseCommand):
    help = "Run one tracked tank estimate sync job."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, required=True)

    def handle(self, *args, **options):
        run = TankEstimateSyncRun.objects.get(pk=options["run_id"])
        run.status = TankEstimateSyncRun.Status.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])
        output = StringIO()
        command_options = {
            "stdout": output,
            "stderr": output,
            "mapped_only": run.mapped_only,
            "virtual_only": False,
        }
        if run.store_number is not None:
            command_options["store"] = run.store_number
        try:
            call_command("sync_tank_estimates", **command_options)
        except Exception as exc:
            run.status = TankEstimateSyncRun.Status.FAILED
            run.completed_at = timezone.now()
            run.output = output.getvalue()
            run.failure_reason = str(exc)
            run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "output",
                    "failure_reason",
                ]
            )
            raise
        run.status = TankEstimateSyncRun.Status.COMPLETED
        run.completed_at = timezone.now()
        run.output = output.getvalue()
        run.save(update_fields=["status", "completed_at", "output"])
