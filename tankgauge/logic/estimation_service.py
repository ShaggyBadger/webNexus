import math
import logging
from typing import Optional, List, Tuple
from django.conf import settings
from django.db import transaction
from tankgauge.models import (
    StoreTankMapping,
    TankEstimation,
    VirtualTankEstimation,
    TankChart,
)
from atg.models import VeederReading
from .geometry import GeometryEngine
from .utils import canonicalize_fuel

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

    def run_estimation_for_tank(
        self, tank_mapping: StoreTankMapping
    ) -> Optional[TankEstimation]:
        """
        Executes the full estimation workflow for a single physical tank.
        Returns the created TankEstimation record if successful, else None.
        """
        logger.info(
            f"ESTIMATION_START: Tank {tank_mapping.id} (Store {tank_mapping.store.store_num})"
        )

        # 1. ACQUIRE RAW DATA
        readings = VeederReading.objects.filter(
            ticket__store=tank_mapping.store,
            tank_index=tank_mapping.tank_index,
            fuel_type__name__iexact=canonicalize_fuel(tank_mapping.fuel_type),
        ).select_related("ticket")

        if not readings.exists():
            logger.warning(
                f"ESTIMATION_FAILED: No Veeder readings found for Tank {tank_mapping.id}"
            )
            return None

        # 2. SOURCE TOTAL CAPACITY
        # We try to get capacity from the most recent reading (vol + ullage)
        latest_reading = readings.order_by("-ticket__uploaded_at").first()
        total_capacity = float(latest_reading.volume + latest_reading.ullage)

        if total_capacity <= 0:
            # Fallback to TankType capacity if available
            total_capacity = float(tank_mapping.tank_type.capacity or 0)

        if total_capacity <= 0:
            logger.error(
                f"ESTIMATION_FAILED: Could not determine total capacity for Tank {tank_mapping.id}"
            )
            return None

        # 3. EXTRACT (HEIGHT, VOLUME) OBSERVATIONS
        observations = [(float(r.height), float(r.volume)) for r in readings]

        # 4. EVALUATE CONFIDENCE GATES (Thresholds)
        if not self._passes_confidence_gates(observations):
            logger.warning(
                f"ESTIMATION_FAILED: Tank {tank_mapping.id} failed confidence gates."
            )
            return None

        # 5. EXECUTE PURE MATH ENGINE
        result = self.engine.calculate_best_fit(total_capacity, observations)

        if result.get("status") != "SUCCESS":
            logger.error(
                f"ESTIMATION_FAILED: GeometryEngine failed: {result.get('message')}"
            )
            return None

        # 6. PERSIST IMMUTABLE RESULT
        with transaction.atomic():
            # Deactivate previous estimates for this tank
            TankEstimation.objects.filter(tank_mapping=tank_mapping).update(
                is_active=False
            )

            # Create new versioned estimate
            estimation = TankEstimation.objects.create(
                tank_mapping=tank_mapping,
                radius=result["radius"],
                length=result["length"],
                confidence=result["confidence"],
                mean_error=result["diagnostics"].get("mean_error"),
                max_error=result["diagnostics"].get("max_error"),
                sample_count=result["diagnostics"].get("sample_count"),
                algorithm_version=result["algorithm_version"],
                diagnostics={**result["diagnostics"], "capacity": total_capacity},
                is_active=True,
            )

            # 7. Optional generated chart materialization (legacy compatibility)
            self.generate_tank_chart_from_estimation(
                estimation,
                tank_mapping.store,
                tank_mapping.fuel_type,
                tank_mapping.tank_index,
            )

        logger.info(
            f"ESTIMATION_COMPLETE: Created TankEstimation {estimation.id} (Confidence: {estimation.confidence})"
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

        # 1. Check for existing active estimation
        existing = VirtualTankEstimation.objects.filter(
            store=store, fuel_type=fuel_key, tank_index=tank_index, is_active=True
        ).first()

        if existing and self._virtual_signature_matches(existing, signature):
            return existing

        # 2. EVALUATE CONFIDENCE GATES
        if not self._passes_confidence_gates(observations):
            logger.warning(
                f"ESTIMATION_FAILED: Virtual Tank (Store {store.store_num}, Tank {tank_index}) failed confidence gates."
            )
            return None

        # 3. EXECUTE PURE MATH ENGINE
        result = self.engine.calculate_best_fit(total_capacity, observations)

        if result.get("status") != "SUCCESS":
            logger.error(
                f"ESTIMATION_FAILED: GeometryEngine failed: {result.get('message')}"
            )
            return None

        # 4. PERSIST IMMUTABLE RESULT
        with transaction.atomic():
            VirtualTankEstimation.objects.filter(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
                is_active=True,
            ).update(is_active=False)

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
                diagnostics={
                    **result["diagnostics"],
                    "capacity": total_capacity,
                    **signature,
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
            f"ESTIMATION_COMPLETE: Created VirtualTankEstimation {estimation.id} (Confidence: {estimation.confidence})"
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
            logger.debug(f"GATE_FAILED: Only {count} readings (Min: {MIN_READINGS})")
            return False

        heights = [o[0] for o in observations]
        spread = max(heights) - min(heights)
        if spread < MIN_HEIGHT_SPREAD:
            logger.debug(
                f"GATE_FAILED: Height spread {spread}in (Min: {MIN_HEIGHT_SPREAD}in)"
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
                "CHART_GENERATION_SKIPPED: Generated chart materialization is disabled."
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
            f"CHART_GENERATED: Created {len(chart_entries)} entries for {tank_name}"
        )
