import math
import logging
import hashlib
import json
from django.utils import timezone
from typing import Optional, List, Tuple
from django.conf import settings
from django.db import transaction
from django.db.models import F
from tankgauge.models import (
    StoreTankMapping,
    TankEstimation,
    VirtualTankEstimation,
    TankChart,
)
from atg.models import VeederReading
from .geometry import GeometryEngine
from .utils import canonicalize_fuel
from .capacity_resolution import CapacityResolutionService

logger = logging.getLogger("tankgauge")

# CONFIDENCE GATES (Thresholds for Mathematical Mode)
MIN_READINGS = 1
MIN_HEIGHT_SPREAD = 0.0  # inches

MAX_ALLOWED_MEAN_ERROR = 500.0  # gallons (relaxed for development)


def _generated_chart_materialization_enabled():
    return getattr(settings, "TANKGAUGE_ENABLE_GENERATED_CHART_MATERIALIZATION", False)


class EstimationService:
    """
    ORCHESTRATION SERVICE:
    Bridges the Django ORM and the Pure GeometryEngine.
    Handles data acquisition, threshold validation, and result persistence.
    """

    def __init__(self):
        self.engine = GeometryEngine()
        self.capacity_resolver = CapacityResolutionService()

    def run_estimation_for_tank(
        self, tank_mapping: StoreTankMapping
    ) -> Optional[TankEstimation]:
        """
        Executes the full estimation workflow for a single physical tank.
        Returns the created TankEstimation record if successful, else None.
        """
        logger.info(
            "ESTIMATION_START",
            extra={
                "tank_mapping_id": tank_mapping.id,
                "store_num": tank_mapping.store.store_num,
                "fuel_type": tank_mapping.fuel_type,
                "tank_index": tank_mapping.tank_index,
                "reason_code": "mapped_estimation_start",
            },
        )

        # 1. ACQUIRE RAW DATA
        readings = (
            VeederReading.objects.filter(
                ticket__store=tank_mapping.store,
                tank_index=tank_mapping.tank_index,
                fuel_type__name__iexact=canonicalize_fuel(tank_mapping.fuel_type),
            )
            .select_related("ticket")
            .order_by(
                F("ticket__ticket_timestamp").asc(nulls_last=True),
                "ticket__uploaded_at",
                "created_at",
                "id",
            )
        )

        observation_cutoff = timezone.now()
        all_readings = list(readings)
        eligible = [
            reading
            for reading in all_readings
            if reading.acceptance_status == "ACCEPTED"
            and reading.volume is not None
            and reading.height is not None
            and reading.volume >= 0
            and reading.height >= 0
            and reading.created_at <= observation_cutoff
        ]
        excluded = [
            {
                "id": str(reading.id),
                "reason_code": (
                    "not_accepted"
                    if reading.acceptance_status != "ACCEPTED"
                    else "invalid_observation"
                ),
            }
            for reading in all_readings
            if reading not in eligible
        ]

        if not eligible:
            logger.warning(
                "ESTIMATION_FAILED",
                extra={
                    "tank_mapping_id": tank_mapping.id,
                    "reason_code": "no_veeder_readings",
                },
            )
            return None

        # 2. Resolve physical capacity through the canonical profile boundary.
        resolution = self.capacity_resolver.resolve_mapping(tank_mapping)
        if not resolution.usable:
            logger.error(
                "ESTIMATION_FAILED",
                extra={
                    "tank_mapping_id": tank_mapping.id,
                    "reason_code": "capacity_unresolved",
                },
            )
            return None
        total_capacity = float(resolution.physical_capacity_gallons)

        # 3. EXTRACT (HEIGHT, VOLUME) OBSERVATIONS
        observations = [(float(r.height), float(r.volume)) for r in eligible]
        observation_rows = [
            {
                "id": str(reading.id),
                "volume_gallons": str(reading.volume),
                "height_inches": str(reading.height),
            }
            for reading in eligible
        ]
        observation_hash = hashlib.sha256(
            json.dumps(observation_rows, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 4. EVALUATE CONFIDENCE GATES (Thresholds)
        if not self._passes_confidence_gates(observations):
            logger.warning(
                "ESTIMATION_FAILED",
                extra={
                    "tank_mapping_id": tank_mapping.id,
                    "reason_code": "confidence_gates_failed",
                },
            )
            return None

        # 5. EXECUTE PURE MATH ENGINE
        result = self.engine.calculate_best_fit(total_capacity, observations)

        if result.get("status") != "SUCCESS":
            logger.error(
                "ESTIMATION_FAILED",
                extra={
                    "tank_mapping_id": tank_mapping.id,
                    "reason_code": "geometry_engine_failure",
                    "message": result.get("message"),
                },
            )
            return None

        # 6. PERSIST IMMUTABLE RESULT
        with transaction.atomic():
            locked_mapping = StoreTankMapping.objects.select_for_update().get(
                pk=tank_mapping.pk
            )
            if locked_mapping.profile_version != resolution.profile_version:
                logger.warning(
                    "ESTIMATION_STALE_PROFILE",
                    extra={
                        "tank_mapping_id": tank_mapping.id,
                        "reason_code": "stale_profile_version",
                    },
                )
                return None
            # Deactivate previous estimates for this tank
            TankEstimation.objects.filter(tank_mapping=locked_mapping).update(
                is_active=False, active_slot=None
            )

            # Create new versioned estimate
            estimation = TankEstimation.objects.create(
                tank_mapping=locked_mapping,
                radius=result["radius"],
                length=result["length"],
                confidence=result["confidence"],
                mean_error=result["diagnostics"].get("mean_error"),
                max_error=result["diagnostics"].get("max_error"),
                sample_count=result["diagnostics"].get("sample_count"),
                algorithm_version=result["algorithm_version"],
                active_slot="ACTIVE",
                physical_capacity_gallons=resolution.physical_capacity_gallons,
                capacity_source=resolution.authority,
                capacity_verified=locked_mapping.capacity_verified,
                profile_version=resolution.profile_version,
                estimate_status=(
                    "VALID" if resolution.status == "READY" else "LEGACY_UNVERIFIED"
                ),
                diagnostics={
                    **result["diagnostics"],
                    "capacity": total_capacity,
                    "capacity_source": resolution.authority,
                    "capacity_status": resolution.status,
                    "capacity_verified": locked_mapping.capacity_verified,
                    "profile_version": resolution.profile_version,
                    "warning_codes": list(resolution.warning_codes),
                    "snapshot_schema_version": 1,
                    "observation_cutoff": observation_cutoff.isoformat(),
                    "observation_set_hash": observation_hash,
                    "included_readings": observation_rows,
                    "excluded_readings": excluded,
                    "source_evidence_ids": list(resolution.evidence_ids),
                    "calculated_at": timezone.now().isoformat(),
                },
                is_active=True,
            )

            # Supersede any active virtual estimation for the same physical tank.
            # The mapped estimation is authoritative; the virtual was written
            # earlier while this tank was still unmapped (see auto_mapper).
            fuel_key = canonicalize_fuel(locked_mapping.fuel_type)
            stale_virtual_ids = list(
                VirtualTankEstimation.objects.filter(
                    store=locked_mapping.store,
                    fuel_type=fuel_key,
                    tank_index=locked_mapping.tank_index,
                    is_active=True,
                ).values_list("id", flat=True)
            )
            if stale_virtual_ids:
                VirtualTankEstimation.objects.filter(id__in=stale_virtual_ids).update(
                    is_active=False, active_slot=None
                )
                logger.info(
                    "STALE_VIRTUAL_SUPERSEDED",
                    extra={
                        "store_id": locked_mapping.store_id,
                        "store_num": locked_mapping.store.store_num,
                        "tank_index": locked_mapping.tank_index,
                        "fuel_type": fuel_key,
                        "virtual_ids": stale_virtual_ids,
                        "estimation_id": estimation.id,
                        "reason_code": "stale_virtual_superseded_by_mapped",
                    },
                )

            # 7. Optional generated chart materialization (legacy compatibility)
            self.generate_tank_chart_from_estimation(
                estimation,
                locked_mapping.store,
                locked_mapping.fuel_type,
                locked_mapping.tank_index,
            )

        logger.info(
            "ESTIMATION_COMPLETE",
            extra={
                "tank_mapping_id": tank_mapping.id,
                "estimation_id": estimation.id,
                "confidence": estimation.confidence,
                "reason_code": "mapped_estimation_complete",
            },
        )
        return estimation

    def run_virtual_estimation(
        self,
        store,
        fuel_type,
        tank_index,
        total_capacity,
        observations,
        latest_uploaded_at=None,
    ) -> Optional[VirtualTankEstimation]:
        """
        Executes estimation for a virtual tank and persists the result.
        Returns the existing active estimation if available, otherwise recalculates.
        """
        fuel_key = canonicalize_fuel(fuel_type)
        signature = self._build_virtual_signature(
            observations, total_capacity, latest_uploaded_at
        )
        observation_rows = [
            {
                "id": None,
                "volume_gallons": str(volume),
                "height_inches": str(height),
            }
            for height, volume in observations
        ]
        observation_hash = hashlib.sha256(
            json.dumps(observation_rows, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 1. Check for existing active estimation
        existing = VirtualTankEstimation.objects.filter(
            store=store, fuel_type=fuel_key, tank_index=tank_index, is_active=True
        ).first()

        if existing and self._virtual_signature_matches(existing, signature):
            return existing

        # 1a. If the tank already has an active mapped estimation, the mapped
        # geometry is authoritative. Deactivate any lingering active virtual for
        # the same key so exports never double-count a physical tank.
        if TankEstimation.objects.filter(
            tank_mapping__store=store,
            tank_mapping__tank_index=tank_index,
            tank_mapping__fuel_type__iexact=fuel_key,
            is_active=True,
        ).exists():
            superseded_ids = list(
                VirtualTankEstimation.objects.filter(
                    store=store,
                    fuel_type=fuel_key,
                    tank_index=tank_index,
                    is_active=True,
                ).values_list("id", flat=True)
            )
            if superseded_ids:
                VirtualTankEstimation.objects.filter(id__in=superseded_ids).update(
                    is_active=False, active_slot=None
                )
                logger.info(
                    "STALE_VIRTUAL_SUPERSEDED",
                    extra={
                        "store_id": store.id,
                        "store_num": store.store_num if store.store_num else None,
                        "tank_index": tank_index,
                        "fuel_type": fuel_key,
                        "virtual_ids": superseded_ids,
                        "reason_code": "virtual_superseded_by_mapped",
                    },
                )
            return None

        # 2. EVALUATE CONFIDENCE GATES
        if not self._passes_confidence_gates(observations):
            logger.warning(
                "ESTIMATION_FAILED",
                extra={
                    "store_num": store.store_num,
                    "tank_index": tank_index,
                    "fuel_type": fuel_key,
                    "reason_code": "virtual_confidence_gates_failed",
                },
            )
            return None

        # 3. EXECUTE PURE MATH ENGINE
        result = self.engine.calculate_best_fit(total_capacity, observations)

        if result.get("status") != "SUCCESS":
            logger.error(
                "ESTIMATION_FAILED",
                extra={
                    "store_num": store.store_num,
                    "tank_index": tank_index,
                    "fuel_type": fuel_key,
                    "reason_code": "geometry_engine_failure",
                    "message": result.get("message"),
                },
            )
            return None

        # 4. PERSIST IMMUTABLE RESULT
        resolution = self.capacity_resolver.resolve_virtual(
            total_capacity_gallons=total_capacity,
        )
        with transaction.atomic():
            VirtualTankEstimation.objects.filter(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
                is_active=True,
            ).update(is_active=False, active_slot=None)

            # Create new versioned estimate
            estimation = VirtualTankEstimation.objects.create(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
                radius=result["radius"],
                length=result["length"],
                confidence=result["confidence"],
                mean_error=result["diagnostics"].get("mean_error"),
                max_error=result["diagnostics"].get("max_error"),
                sample_count=result["diagnostics"].get("sample_count"),
                algorithm_version=result["algorithm_version"],
                active_slot="ACTIVE",
                physical_capacity_gallons=resolution.physical_capacity_gallons,
                capacity_source=resolution.authority,
                capacity_verified=False,
                estimate_status="LEGACY_UNVERIFIED",
                diagnostics={
                    **result["diagnostics"],
                    "capacity": total_capacity,
                    "capacity_source": resolution.authority,
                    "capacity_status": resolution.status,
                    "warning_codes": list(resolution.warning_codes),
                    **signature,
                    "snapshot_schema_version": 1,
                    "observation_set_hash": observation_hash,
                    "included_readings": observation_rows,
                    "excluded_readings": [],
                    "calculated_at": timezone.now().isoformat(),
                },
                is_active=True,
            )

            # 5. Optional generated chart materialization (legacy compatibility)
            self.generate_tank_chart_from_estimation(
                estimation,
                store,
                fuel_key,
                tank_index,
            )

        logger.info(
            "ESTIMATION_COMPLETE",
            extra={
                "store_num": store.store_num,
                "tank_index": tank_index,
                "fuel_type": fuel_key,
                "estimation_id": estimation.id,
                "confidence": estimation.confidence,
                "reason_code": "virtual_estimation_complete",
            },
        )
        return estimation

    def _build_virtual_signature(
        self,
        observations: List[Tuple[float, float]],
        total_capacity: float,
        latest_uploaded_at,
    ) -> dict:
        timestamp = latest_uploaded_at.isoformat() if latest_uploaded_at else None
        return {
            "reading_count": len(observations),
            "capacity": float(total_capacity),
            "latest_uploaded_at": timestamp,
        }

    def _virtual_signature_matches(
        self, estimation: VirtualTankEstimation, signature: dict
    ) -> bool:
        diagnostics = estimation.diagnostics or {}
        return (
            diagnostics.get("reading_count") == signature["reading_count"]
            and diagnostics.get("capacity") == signature["capacity"]
            and diagnostics.get("latest_uploaded_at") == signature["latest_uploaded_at"]
        )

    def _passes_confidence_gates(self, observations: List[Tuple[float, float]]) -> bool:
        """Checks if the data quantity and quality meet the minimum thresholds."""
        count = len(observations)
        if count < MIN_READINGS:
            logger.debug(
                "ESTIMATION_GATE_FAILED",
                extra={
                    "reason_code": "insufficient_readings",
                    "reading_count": count,
                    "min_required": MIN_READINGS,
                },
            )
            return False

        heights = [o[0] for o in observations]
        spread = max(heights) - min(heights)
        if spread < MIN_HEIGHT_SPREAD:
            logger.debug(
                "ESTIMATION_GATE_FAILED",
                extra={
                    "reason_code": "insufficient_height_spread",
                    "height_spread_inches": spread,
                    "min_required_inches": MIN_HEIGHT_SPREAD,
                },
            )
            return False

        return True

    def generate_tank_chart_from_estimation(
        self, estimation_obj, store, fuel_type, tank_index
    ):
        """
        Materializes a mathematical estimation into a series of TankChart entries.
        Generates 1-inch increments from 0 to the calculated max depth.
        """
        if not _generated_chart_materialization_enabled():
            logger.info(
                "CHART_GENERATION_SKIPPED",
                extra={"reason_code": "materialization_disabled"},
            )
            return

        # 1. Determine Tank Name Pattern (f"{store.store_num}_{fuel_type}_T{tank_index}")
        # fuel_type may need canonicalization if not already
        from .utils import canonicalize_fuel

        fuel_key = canonicalize_fuel(fuel_type).upper()
        tank_name = f"{store.store_num}_{fuel_key}_T{tank_index}"

        # 2. Determine Max Depth (2 * Radius)
        max_depth = float(estimation_obj.radius) * 2.0

        # 3. Use Atomic Transaction for cleanup and replacement
        with transaction.atomic():
            # Remove existing generated chart for this specific tank
            TankChart.objects.filter(
                store=store,
                tank_index=tank_index,
                is_official=False,
            ).delete()

            # 4. Generate 1-inch increments
            chart_entries = []
            # We use ceil + 1 to ensure we cover the full depth
            for inch in range(int(math.ceil(max_depth)) + 1):
                volume = self.engine.volume_from_depth(
                    float(estimation_obj.radius),
                    float(estimation_obj.length),
                    float(inch),
                )
                chart_entries.append(
                    TankChart(
                        store=store,
                        tank_index=tank_index,
                        is_official=False,
                        inches=inch,
                        gallons=int(round(volume)),
                        tank_name=tank_name,
                        misc_info=f"Generated from Estimation {estimation_obj.id} (v{estimation_obj.algorithm_version})",
                    )
                )

            # 5. Bulk Create for efficiency
            TankChart.objects.bulk_create(chart_entries)

        logger.info(
            "CHART_GENERATED",
            extra={
                "tank_name": tank_name,
                "entry_count": len(chart_entries),
                "reason_code": "materialized_from_estimation",
            },
        )
