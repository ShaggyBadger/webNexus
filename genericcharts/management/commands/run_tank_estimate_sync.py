import re
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from genericcharts.models import TankEstimateSyncRun


class Command(BaseCommand):
    help = "Run one tracked tank estimate sync job."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, required=True)

    def handle(self, *args, **options):
        with transaction.atomic():
            run = TankEstimateSyncRun.objects.select_for_update().get(
                pk=options["run_id"]
            )
            if run.status != TankEstimateSyncRun.Status.PENDING:
                self.stdout.write(
                    self.style.WARNING(f"Run {run.id} is already {run.status}.")
                )
                return
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
        if run.preview:
            command_options["preview"] = True
        if run.store_number is not None:
            command_options["store"] = run.store_number
        if run.mapping_id is not None:
            command_options["mapping"] = run.mapping_id
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
        output_text = output.getvalue()
        failure_match = re.search(
            r"mapped_failed=(\d+) .*virtual_failed=(\d+)", output_text
        )
        partial = bool(
            not run.preview
            and failure_match
            and (int(failure_match.group(1)) or int(failure_match.group(2)))
        )
        run.status = (
            TankEstimateSyncRun.Status.PARTIAL_FAILURE
            if partial
            else TankEstimateSyncRun.Status.COMPLETED
        )
        run.completed_at = timezone.now()
        run.output = output_text
        run.result_summary = {"output": output_text, "preview": run.preview}
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "output",
                "result_summary",
            ]
        )
