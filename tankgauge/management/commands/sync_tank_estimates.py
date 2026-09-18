from django.core.management.base import BaseCommand
from django.db.models import F

from atg.models import VeederReading
from tankgauge.logic.estimation_service import EstimationService
from tankgauge.logic.capacity_resolution import CapacityResolutionService
from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import Store, StoreTankMapping
from atg.services.auto_mapper import AutoMapperService


class Command(BaseCommand):
    help = "Precompute and cache tank estimations for mapped and virtual tanks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--store",
            type=int,
            help="Limit sync to a single store number.",
        )
        parser.add_argument(
            "--virtual-only",
            action="store_true",
            help="Sync only virtual (unmapped) tank estimations.",
        )
        parser.add_argument(
            "--mapped-only",
            action="store_true",
            help="Sync only mapped tank estimations.",
        )
        parser.add_argument("--mapping", type=int, help="Limit sync to one mapping ID.")
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Report the mapped scope without changing estimates.",
        )

    def handle(self, *args, **options):
        if options["virtual_only"] and options["mapped_only"]:
            self.stderr.write(
                self.style.ERROR(
                    "Use either --virtual-only or --mapped-only, not both."
                )
            )
            return

        service = EstimationService()
        capacity_resolver = CapacityResolutionService()
        store_num = options.get("store")
        virtual_only = options.get("virtual_only")
        mapped_only = options.get("mapped_only")
        mapping_id = options.get("mapping")

        mapped_created = 0
        mapped_failed = 0
        virtual_created = 0
        virtual_failed = 0

        stores = Store.objects.all()
        if store_num is not None:
            stores = stores.filter(store_num=store_num)
        if mapping_id is not None:
            stores = stores.filter(tank_mappings__id=mapping_id).distinct()

        store_ids = list(stores.values_list("id", flat=True))
        if not store_ids:
            self.stdout.write(self.style.WARNING("No stores matched filter."))
            return

        if not virtual_only:
            mappings = (
                StoreTankMapping.objects.filter(store_id__in=store_ids)
                .select_related("store", "tank_type")
                .all()
            )
            if mapping_id is not None:
                mappings = mappings.filter(id=mapping_id)

            if options.get("preview"):
                count = mappings.count()
                self.stdout.write(
                    self.style.WARNING(
                        f"PREVIEW | mapped_candidates={count} virtual_candidates=0"
                    )
                )
                return

            for mapping in mappings:
                estimation = service.run_estimation_for_tank(mapping)
                if estimation:
                    mapped_created += 1
                else:
                    mapped_failed += 1

        if not mapped_only:
            virtual_groups = (
                VeederReading.objects.filter(
                    ticket__store_id__in=store_ids,
                    acceptance_status="ACCEPTED",
                )
                .values("ticket__store_id", "fuel_type__name", "tank_index")
                .distinct()
            )

            for group in virtual_groups:
                store_id = group["ticket__store_id"]
                tank_index = group["tank_index"]
                fuel_name = group["fuel_type__name"]
                fuel_key = canonicalize_fuel(fuel_name)

                if not store_id or tank_index is None or not fuel_key:
                    continue

                # AUTO_MAPPER: Attempt to bridge missing mappings
                store = Store.objects.get(pk=store_id)
                AutoMapperService.ensure_mapping(store, fuel_name, tank_index)

                is_mapped = StoreTankMapping.objects.filter(
                    store_id=store_id,
                    fuel_type=fuel_key,
                    tank_index=tank_index,
                ).exists()
                if is_mapped:
                    continue

                readings = VeederReading.objects.filter(
                    ticket__store_id=store_id,
                    tank_index=tank_index,
                    fuel_type__name__iexact=fuel_key,
                    acceptance_status="ACCEPTED",
                ).select_related("ticket")

                if not readings.exists():
                    continue

                latest = readings.order_by(
                    F("ticket__ticket_timestamp").desc(nulls_last=True),
                    F("ticket__uploaded_at").desc(nulls_last=True),
                    F("created_at").desc(nulls_last=True),
                    F("id").desc(nulls_last=True),
                ).first()
                if latest.volume is None or latest.ullage is None:
                    virtual_failed += 1
                    continue
                resolution = capacity_resolver.resolve_virtual(
                    total_capacity_gallons=latest.volume + latest.ullage,
                    evidence_ids=(str(latest.id),),
                    basis_percent_exact=latest.ullage_endpoint_percent_exact,
                )
                if not resolution.usable:
                    virtual_failed += 1
                    continue
                total_capacity = float(resolution.physical_capacity_gallons)
                observations = [(float(r.height), float(r.volume)) for r in readings]

                estimation = service.run_virtual_estimation(
                    latest.ticket.store,
                    fuel_key,
                    tank_index,
                    total_capacity,
                    observations,
                    latest_uploaded_at=latest.ticket.uploaded_at,
                )

                if estimation:
                    virtual_created += 1
                else:
                    virtual_failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                "SYNC COMPLETE | "
                f"mapped_ok={mapped_created} mapped_failed={mapped_failed} "
                f"virtual_ok={virtual_created} virtual_failed={virtual_failed}"
            )
        )
