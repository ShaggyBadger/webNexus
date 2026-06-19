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
        """
        if store is None:
            logger.info(
                "AUTO_MAPPER: Skipping auto-map because ticket has no store assigned."
            )
            return False

        fuel_key = canonicalize_fuel(fuel_type)

        if StoreTankMapping.objects.filter(
            store=store,
            fuel_type=fuel_key,
            tank_index=tank_index,
        ).exists():
            return False

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
    def trigger_updates(store: Optional[Store], fuel_name: str, tank_index: int) -> None:
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

