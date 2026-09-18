from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from atg.models import VeederReading
from tankgauge.models import StoreTankMapping, TankCapacityProfileHistory


class Command(BaseCommand):
    help = "Preview or apply legacy Gross + Ullage capacity profiles."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--store", type=int)

    def handle(self, *args, **options):
        mappings = StoreTankMapping.objects.select_related("store").order_by(
            "store__store_num", "tank_index", "id"
        )
        if options.get("store") is not None:
            mappings = mappings.filter(store__store_num=options["store"])

        changed = skipped = unresolved = 0
        for mapping in mappings:
            if mapping.physical_capacity_gallons is not None:
                skipped += 1
                continue

            reading = (
                VeederReading.objects.filter(
                    ticket__store_id=mapping.store_id,
                    tank_index=mapping.tank_index,
                    acceptance_status="ACCEPTED",
                )
                .filter(fuel_type__name__iexact=mapping.fuel_type)
                .order_by(
                    F("ticket__ticket_timestamp").desc(nulls_last=True),
                    F("ticket__uploaded_at").desc(nulls_last=True),
                    F("created_at").desc(nulls_last=True),
                    F("id").desc(nulls_last=True),
                )
                .first()
            )
            if reading is None:
                unresolved += 1
                self.stdout.write(
                    f"UNRESOLVED store={mapping.store.store_num} tank={mapping.tank_index}"
                )
                continue

            baseline = Decimal(reading.volume) + Decimal(reading.ullage)
            if baseline <= 0:
                unresolved += 1
                continue

            changed += 1
            self.stdout.write(
                f"{'APPLY' if options['apply'] else 'PREVIEW'} "
                f"store={mapping.store.store_num} tank={mapping.tank_index} "
                f"capacity={baseline} endpoint={reading.ullage_endpoint_gallons} "
                f"printed_capacity={reading.printed_physical_capacity_gallons} "
                f"source=LEGACY_ASSUMED"
            )
            if options["apply"]:
                with transaction.atomic():
                    mapping.profile_version += 1
                    mapping.physical_capacity_gallons = baseline
                    mapping.capacity_source = "LEGACY_ASSUMED"
                    mapping.profile_status = "LEGACY_UNVERIFIED"
                    mapping.capacity_verified = False
                    # A legacy endpoint cannot prove its 90/95/100 basis.
                    mapping.ullage_endpoint_percent_exact = None
                    mapping.save(
                        update_fields=[
                            "physical_capacity_gallons",
                            "capacity_source",
                            "profile_status",
                            "capacity_verified",
                            "ullage_endpoint_percent_exact",
                            "profile_version",
                            "capacity_updated_at",
                        ]
                    )
                    TankCapacityProfileHistory.objects.create(
                        mapping=mapping,
                        profile_version=mapping.profile_version,
                        previous_capacity_gallons=None,
                        new_capacity_gallons=baseline,
                        new_verified=False,
                        new_source="LEGACY_ASSUMED",
                        new_basis_percent=None,
                        reason="One-time legacy Gross + Ullage capacity backfill",
                        actor_type="COMMAND",
                        source_evidence_ids=[str(reading.id)],
                    )

        mode = "APPLIED" if options["apply"] else "PREVIEW"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: changed={changed} skipped={skipped} unresolved={unresolved}"
            )
        )
