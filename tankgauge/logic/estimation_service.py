import logging
from typing import Optional, List, Tuple
from django.db import transaction
from tankgauge.models import StoreTankMapping, TankEstimation
from atg.models import VeederReading
from .geometry import GeometryEngine

logger = logging.getLogger("tankgauge")

# CONFIDENCE GATES (Thresholds for Experimental Mode)
MIN_READINGS = 3
MIN_HEIGHT_SPREAD = 5.0  # inches
MAX_ALLOWED_MEAN_ERROR = 150.0  # gallons


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
            fuel_type__name=tank_mapping.fuel_type,  # Assuming name matches
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
                diagnostics=result["diagnostics"],
                is_active=True,
            )

        logger.info(
            f"ESTIMATION_COMPLETE: Created TankEstimation {estimation.id} (Confidence: {estimation.confidence})"
        )
        return estimation

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
