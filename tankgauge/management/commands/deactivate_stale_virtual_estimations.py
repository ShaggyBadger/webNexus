import logging

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from tankgauge.models import Store, TankEstimation, VirtualTankEstimation

logger = logging.getLogger("tankgauge")


class Command(BaseCommand):
    help = (
        "Deactivate active VirtualTankEstimations that duplicate an active "
        "mapped TankEstimation for the same (store, fuel_type, tank_index)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform the deactivation (default is a dry-run report).",
        )
        parser.add_argument(
            "--store",
            type=int,
            help="Limit to a single store number.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        store_num = options.get("store")

        stale = list(self._stale_virtual_estimations(store_num=store_num))
        total = len(stale)

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No stale virtual estimations found."))
            return

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {total} stale virtual estimation(s) would be "
                    "deactivated."
                )
            )
            for ve in sorted(stale, key=lambda v: (v.store.store_num, v.tank_index)):
                self.stdout.write(
                    f"  store={ve.store.store_num} tank_index={ve.tank_index} "
                    f"fuel_type={ve.fuel_type} virtual_id={ve.id}"
                )
            return

        for ve in stale:
            logger.info(
                "STALE_VIRTUAL_SUPERSEDED",
                extra={
                    "virtual_id": ve.id,
                    "store_id": ve.store_id,
                    "store_num": ve.store.store_num,
                    "tank_index": ve.tank_index,
                    "fuel_type": ve.fuel_type,
                    "reason_code": "stale_virtual_superseded_by_mapped",
                },
            )

        VirtualTankEstimation.objects.filter(id__in=[ve.id for ve in stale]).update(
            is_active=False
        )

        self.stdout.write(
            self.style.SUCCESS(f"Deactivated {total} stale virtual estimation(s).")
        )

    def _stale_virtual_estimations(self, *, store_num=None):
        """Return active virtuals superseded by an active mapped estimation."""
        qs = VirtualTankEstimation.objects.filter(is_active=True)

        if store_num is not None:
            store_ids = Store.objects.filter(store_num=store_num).values_list(
                "id", flat=True
            )
            qs = qs.filter(store_id__in=store_ids)

        active_mapped = TankEstimation.objects.filter(
            tank_mapping__store=OuterRef("store"),
            tank_mapping__tank_index=OuterRef("tank_index"),
            tank_mapping__fuel_type__iexact=OuterRef("fuel_type"),
            is_active=True,
        )

        return (
            qs.select_related("store")
            .annotate(has_active_mapped=Exists(active_mapped))
            .filter(has_active_mapped=True)
        )
