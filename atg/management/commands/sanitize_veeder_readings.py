from django.core.management.base import BaseCommand

from atg.models import VeederReading
from atg.services.reading_quality import (
    get_hard_errors_for_payload,
    get_mapping_sanity_issues,
)


class Command(BaseCommand):
    help = "Dry-run and optionally clean invalid Veeder readings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            default=False,
            help="Apply destructive changes (deletes hard-invalid readings).",
        )
        parser.add_argument(
            "--store",
            type=int,
            default=None,
            help="Limit to a single store number.",
        )
        parser.add_argument(
            "--delete-suspicious",
            action="store_true",
            default=False,
            help="Also delete suspicious readings (not recommended).",
        )

    def _payload_for_reading(self, reading):
        return {
            "tank_index": reading.tank_index,
            "fuel_type": reading.fuel_type,
            "volume": reading.volume,
            "ullage": reading.ullage,
            "height": reading.height,
            "temp": reading.temp,
            "water": reading.water,
            "confidence_score": reading.confidence_score,
        }

    def handle(self, *args, **options):
        commit = options["commit"]
        store_num = options.get("store")
        delete_suspicious = options.get("delete_suspicious")

        mode = "COMMIT" if commit else "DRY-RUN"
        self.stdout.write(
            self.style.WARNING(f"\n[{mode}] Sanitizing Veeder Readings\n")
        )
        if not commit:
            self.stdout.write("  Run with --commit to delete hard-invalid rows.\n")

        qs = VeederReading.objects.select_related("ticket__store", "fuel_type").all()
        if store_num is not None:
            qs = qs.filter(ticket__store__store_num=store_num)

        total_scanned = 0
        hard_invalid = []
        suspicious = []

        for reading in qs.iterator():
            total_scanned += 1
            payload = self._payload_for_reading(reading)
            hard_errors = get_hard_errors_for_payload(payload)
            if hard_errors:
                hard_invalid.append((reading, hard_errors))
                continue

            soft_issues = get_mapping_sanity_issues(reading.ticket.store, payload)
            if soft_issues:
                suspicious.append((reading, soft_issues))

        self.stdout.write(f"Scanned: {total_scanned}")
        self.stdout.write(f"Hard invalid: {len(hard_invalid)}")
        self.stdout.write(f"Suspicious: {len(suspicious)}")

        for reading, issues in hard_invalid[:25]:
            self.stdout.write(
                self.style.ERROR(
                    "  HARD_INVALID "
                    f"id={reading.id} store={reading.ticket.store.store_num if reading.ticket and reading.ticket.store else None} "
                    f"fuel={reading.fuel_type.name} idx={reading.tank_index} reasons={'; '.join(issues)}"
                )
            )

        for reading, issues in suspicious[:25]:
            self.stdout.write(
                self.style.WARNING(
                    "  SUSPICIOUS "
                    f"id={reading.id} store={reading.ticket.store.store_num if reading.ticket and reading.ticket.store else None} "
                    f"fuel={reading.fuel_type.name} idx={reading.tank_index} reasons={'; '.join(issues)}"
                )
            )

        deleted_hard = 0
        deleted_suspicious = 0
        if commit:
            hard_ids = [reading.id for reading, _ in hard_invalid]
            if hard_ids:
                deleted_hard, _ = VeederReading.objects.filter(id__in=hard_ids).delete()

            if delete_suspicious:
                suspicious_ids = [reading.id for reading, _ in suspicious]
                if suspicious_ids:
                    deleted_suspicious, _ = VeederReading.objects.filter(
                        id__in=suspicious_ids
                    ).delete()

        self.stdout.write("\n" + "-" * 50)
        self.stdout.write(f"Deleted hard invalid: {deleted_hard}")
        self.stdout.write(f"Deleted suspicious:  {deleted_suspicious}")
        if not commit:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY-RUN] No rows were deleted. Use --commit to apply.\n"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("\n[COMMIT] Sanitization complete.\n"))
