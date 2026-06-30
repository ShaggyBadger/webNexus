import logging
from typing import Optional

from django.db import transaction

from atg.models import VeederReading
from tankgauge.logic.estimation_service import EstimationService
from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import Store, StoreTankMapping, TankType

logger = logging.getLogger("webnexus")

MIN_AUTO_MAP_READINGS = 1


class AutoMapperService:
    @staticmethod
    def ensure_mapping(store: Optional[Store], fuel_type: str, tank_index: int) -> bool:
        """
        Ensures a StoreTankMapping exists for the given store, fuel, and index.
        If not, attempts to auto-map based on historical data.

        MERGE LOGIC:
        Before creating a new AUTO_ record, checks if a mapping already exists
        for this store + fuel_type at a *different* tank_index. This catches the
        common case where a manual SiteIntel entry had the wrong index.

        - If a conflicting mapping exists and its old index has NO Veeder readings
          (meaning the manual index was simply wrong), the existing mapping's
          tank_index is corrected to the ATG ground-truth value in place. No new
          record is created.

        - If the conflicting mapping's old index DOES have Veeder readings, the
          store genuinely has two physical tanks of the same fuel type. The new
          AUTO_ record is created normally.
        """
        if store is None:
            logger.info(
                "AUTO_MAPPER: Skipping auto-map because ticket has no store assigned."
            )
            return False

        fuel_key = canonicalize_fuel(fuel_type)

        # --- Step 1: Exact match — mapping already correct, nothing to do ---
        if StoreTankMapping.objects.filter(
            store=store,
            fuel_type=fuel_key,
            tank_index=tank_index,
        ).exists():
            return False

        # --- Step 2: Conflict check — same fuel, different tank_index ---
        conflicting_mappings = StoreTankMapping.objects.filter(
            store=store,
            fuel_type=fuel_key,
        ).exclude(tank_index=tank_index)

        for conflict in conflicting_mappings:
            old_index = conflict.tank_index

            # Does the OLD index have any real Veeder-Root readings?
            old_index_has_readings = VeederReading.objects.filter(
                ticket__store=store,
                tank_index=old_index,
                fuel_type__name__iexact=fuel_key,
            ).exists()

            if not old_index_has_readings:
                # The old index has no supporting readings — it was a manual
                # entry with the wrong index. Correct it in place.
                logger.info(
                    "AUTO_MAPPER: Correcting tank_index for existing mapping %s "
                    "(Store %s, %s: index %s → %s). Old index has no ATG readings.",
                    conflict.id,
                    store.store_num,
                    fuel_key,
                    old_index,
                    tank_index,
                )
                conflict.tank_index = tank_index
                conflict.save(update_fields=["tank_index"])
                return True
            else:
                # Old index has real readings — this is a genuine second tank
                # of the same fuel type. Fall through to create an AUTO_ record.
                logger.info(
                    "AUTO_MAPPER: Store %s has confirmed readings at tank_index %s (%s). "
                    "Treating incoming index %s as a second physical tank.",
                    store.store_num,
                    old_index,
                    fuel_key,
                    tank_index,
                )

        # --- Step 3: No merge possible — proceed with standard AUTO_ creation ---
        logger.info(
            "AUTO_MAPPER: Attempting to map Store %s Fuel %s Tank %s",
            store.store_num,
            fuel_key,
            tank_index,
        )

        readings = VeederReading.objects.filter(
            ticket__store=store,
            tank_index=tank_index,
            fuel_type__name__iexact=fuel_key,
        ).select_related("ticket")

        reading_count = readings.count()
        if reading_count < MIN_AUTO_MAP_READINGS:
            logger.warning(
                "AUTO_MAPPER: Insufficient readings for Store %s Tank %s (have %s, need %s).",
                store.store_num,
                tank_index,
                reading_count,
                MIN_AUTO_MAP_READINGS,
            )
            return False

        observations = [(float(r.height), float(r.volume)) for r in readings]
        latest = readings.order_by("-ticket__uploaded_at").first()
        if latest is None or latest.volume is None or latest.ullage is None:
            logger.warning(
                "AUTO_MAPPER: Missing latest volume/ullage for Store %s Tank %s.",
                store.store_num,
                tank_index,
            )
            return False

        total_capacity = float(latest.volume + latest.ullage)
        if total_capacity <= 0:
            logger.warning(
                "AUTO_MAPPER: Non-positive capacity derived for Store %s Tank %s.",
                store.store_num,
                tank_index,
            )
            return False

        service = EstimationService()
        estimation = service.run_virtual_estimation(
            store,
            fuel_key,
            tank_index,
            total_capacity,
            observations,
            latest.ticket.uploaded_at,
        )

        if not estimation:
            logger.warning(
                "AUTO_MAPPER: Estimation failed for Store %s Tank %s. Mapping skipped.",
                store.store_num,
                tank_index,
            )
            return False

        with transaction.atomic():
            existing_mapping = StoreTankMapping.objects.filter(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
            ).first()
            if existing_mapping:
                return False

            tank_type_name = f"AUTO_{store.store_num}_T{tank_index}_{fuel_key.upper()}"
            new_tank_type, _ = TankType.objects.get_or_create(
                name=tank_type_name,
                defaults={
                    "capacity": int(total_capacity),
                    "max_depth": int(estimation.radius * 2),
                    "misc_info": f"Auto-mapped based on estimation {estimation.id}",
                },
            )

            _, created = StoreTankMapping.objects.get_or_create(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
                defaults={"tank_type": new_tank_type},
            )

            if created:
                logger.info(
                    "AUTO_MAPPER: Successfully auto-mapped Store %s Tank %s to TankType %s",
                    store.store_num,
                    tank_index,
                    new_tank_type.name,
                )
                return True

        return False

    @staticmethod
    def trigger_updates(
        store: Optional[Store], fuel_name: str, tank_index: int
    ) -> None:
        """
        Tolerant updater: ensures mapping exists, then re-runs either
        mapped or virtual estimation to incorporate the new reading.
        """
        if not store:
            return

        fuel_key = canonicalize_fuel(fuel_name)

        # 1. Try to ensure mapping exists if possible
        AutoMapperService.ensure_mapping(store, fuel_name, tank_index)

        # 2. Re-run estimation
        mapping = StoreTankMapping.objects.filter(
            store=store, fuel_type=fuel_key, tank_index=tank_index
        ).first()

        service = EstimationService()
        if mapping:
            service.run_estimation_for_tank(mapping)
        else:
            readings = VeederReading.objects.filter(
                ticket__store=store,
                tank_index=tank_index,
                fuel_type__name__iexact=fuel_key,
            ).select_related("ticket")
            if readings.exists():
                latest = readings.order_by("-ticket__uploaded_at").first()
                total_capacity = float(latest.volume + latest.ullage)
                observations = [(float(r.height), float(r.volume)) for r in readings]
                service.run_virtual_estimation(
                    store,
                    fuel_key,
                    tank_index,
                    total_capacity,
                    observations,
                    latest.ticket.uploaded_at,
                )
