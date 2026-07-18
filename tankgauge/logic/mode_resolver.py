import math
from typing import Optional

from django.conf import settings

from tankgauge.models import TankChart, TankEstimation

from .estimation_service import EstimationService
from .types import CalculationMode, ConfidenceLevel, ModeAvailability, TankLimits

OFFICIAL_UNAVAILABLE_REASON = (
    "Official tank chart unavailable. Using Veeder-derived geometry estimate."
)
MATHEMATICAL_UNAVAILABLE_REASON = "No Veeder estimation available"

_CONFIDENCE_SCORE = {
    ConfidenceLevel.NONE: 0,
    ConfidenceLevel.LOW: 1,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.HIGH: 3,
}


class ModeResolver:
    """Resolve mode availability, defaults, and mode-scoped tank limits."""

    def _generated_chart_fallback_enabled(self) -> bool:
        return bool(
            getattr(settings, "TANKGAUGE_ENABLE_GENERATED_CHART_FALLBACK", False)
        )

    def parse_display_mode(self, value: Optional[str]) -> CalculationMode:
        if not value:
            return CalculationMode.AUTO
        normalized = str(value).strip().upper()
        if normalized == CalculationMode.OFFICIAL.value:
            return CalculationMode.OFFICIAL
        if normalized == CalculationMode.MATHEMATICAL.value:
            return CalculationMode.MATHEMATICAL
        return CalculationMode.AUTO

    def confidence_level_from_numeric(
        self,
        confidence_score: Optional[float],
    ) -> ConfidenceLevel:
        if confidence_score is None:
            return ConfidenceLevel.NONE
        if confidence_score >= 0.9:
            return ConfidenceLevel.HIGH
        if confidence_score >= 0.65:
            return ConfidenceLevel.MEDIUM
        if confidence_score > 0:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.NONE

    def resolve_available_modes_for_mapping(
        self,
        mapping,
        *,
        allow_estimation_run: bool,
    ) -> tuple[list[ModeAvailability], dict[CalculationMode, dict]]:
        mode_meta: dict[CalculationMode, dict] = {}

        official_mode, official_meta = self._resolve_official_mode(mapping)
        if official_mode.available:
            mode_meta[CalculationMode.OFFICIAL] = official_meta

        mathematical_mode, mathematical_meta = self._resolve_mathematical_mode(
            mapping,
            allow_estimation_run=allow_estimation_run,
        )
        if mathematical_mode.available:
            mode_meta[CalculationMode.MATHEMATICAL] = mathematical_meta

        return [official_mode, mathematical_mode], mode_meta

    def select_default_mode(
        self, available_modes: list[ModeAvailability]
    ) -> CalculationMode:
        available = [mode for mode in available_modes if mode.available]
        if not available:
            return CalculationMode.MATHEMATICAL

        ordered = sorted(
            available,
            key=lambda item: (
                _CONFIDENCE_SCORE[item.confidence],
                1 if item.mode == CalculationMode.MATHEMATICAL else 0,
            ),
            reverse=True,
        )
        return ordered[0].mode

    def resolve_active_mode(
        self,
        requested_mode: CalculationMode,
        available_modes: list[ModeAvailability],
    ) -> CalculationMode:
        available_by_mode = {
            availability.mode: availability for availability in available_modes
        }
        default_mode = self.select_default_mode(available_modes)

        if requested_mode == CalculationMode.AUTO:
            return default_mode

        availability = available_by_mode.get(requested_mode)
        if availability and availability.available:
            return requested_mode
        return default_mode

    def build_limits_for_mode(
        self,
        mapping,
        *,
        mode: CalculationMode,
        source_meta: Optional[dict],
    ) -> TankLimits:
        warnings: list[str] = []

        if mode == CalculationMode.OFFICIAL:
            capacity_gallons = (
                int(mapping.tank_type.capacity)
                if mapping
                and mapping.tank_type
                and mapping.tank_type.capacity is not None
                else None
            )
            max_depth_inches = (
                float(mapping.tank_type.max_depth)
                if mapping
                and mapping.tank_type
                and mapping.tank_type.max_depth is not None
                else None
            )
            confidence = ConfidenceLevel.HIGH
            source = "OFFICIAL"

            if source_meta and source_meta.get("name") == "GENERATED_CHART":
                confidence = ConfidenceLevel.MEDIUM
                source = "GENERATED"
                if capacity_gallons is None and source_meta.get("capacity") is not None:
                    capacity_gallons = int(source_meta["capacity"])
                if (
                    max_depth_inches is None
                    and source_meta.get("max_depth_inches") is not None
                ):
                    max_depth_inches = float(source_meta["max_depth_inches"])

            if (
                capacity_gallons is None
                and source_meta
                and source_meta.get("capacity") is not None
            ):
                capacity_gallons = int(source_meta["capacity"])
            if (
                max_depth_inches is None
                and source_meta
                and source_meta.get("max_depth_inches") is not None
            ):
                max_depth_inches = float(source_meta["max_depth_inches"])

            ninety_percent = (
                int(capacity_gallons * 0.9) if capacity_gallons is not None else None
            )

            if capacity_gallons is None or max_depth_inches is None:
                warnings.append(OFFICIAL_UNAVAILABLE_REASON)

            return TankLimits(
                capacity_gallons=capacity_gallons,
                max_depth_inches=max_depth_inches,
                ninety_percent_gallons=ninety_percent,
                source=source,
                confidence=confidence,
                mode=CalculationMode.OFFICIAL,
                warnings=warnings,
            )

        estimation = source_meta.get("estimation") if source_meta else None
        if estimation and estimation.radius and estimation.length:
            radius_inches = float(estimation.radius)
            length_inches = float(estimation.length)
            capacity = (math.pi * radius_inches * radius_inches * length_inches) / 231.0
            capacity_gallons = int(round(capacity))
            max_depth_inches = round(radius_inches * 2.0, 2)
        else:
            capacity_gallons = None
            max_depth_inches = None
            warnings.append(MATHEMATICAL_UNAVAILABLE_REASON)

        ninety_percent = (
            int(capacity_gallons * 0.9) if capacity_gallons is not None else None
        )
        confidence = self.confidence_level_from_numeric(
            source_meta.get("confidence") if source_meta else None
        )

        return TankLimits(
            capacity_gallons=capacity_gallons,
            max_depth_inches=max_depth_inches,
            ninety_percent_gallons=ninety_percent,
            source="VEEDER",
            confidence=confidence,
            mode=CalculationMode.MATHEMATICAL,
            warnings=warnings,
        )

    def _resolve_official_mode(self, mapping) -> tuple[ModeAvailability, dict]:
        official_exists = False
        source_name = "OFFICIAL_CHART"

        if mapping.tank_type:
            official_exists = TankChart.objects.filter(
                tank_type=mapping.tank_type,
                is_official=True,
            ).exists()

        generated_exists = False
        if not official_exists and self._generated_chart_fallback_enabled():
            generated_exists = TankChart.objects.filter(
                store=mapping.store,
                tank_index=mapping.tank_index,
                is_official=False,
            ).exists()
            if generated_exists:
                source_name = "GENERATED_CHART"

        if official_exists or generated_exists:
            confidence = (
                ConfidenceLevel.HIGH
                if source_name == "OFFICIAL_CHART"
                else ConfidenceLevel.MEDIUM
            )
            source_meta = {
                "name": source_name,
                "confidence": 1.0,
            }
            return (
                ModeAvailability(
                    mode=CalculationMode.OFFICIAL,
                    available=True,
                    reason=None,
                    confidence=confidence,
                ),
                source_meta,
            )

        return (
            ModeAvailability(
                mode=CalculationMode.OFFICIAL,
                available=False,
                reason=OFFICIAL_UNAVAILABLE_REASON,
                confidence=ConfidenceLevel.NONE,
            ),
            {},
        )

    def _resolve_mathematical_mode(
        self,
        mapping,
        *,
        allow_estimation_run: bool,
    ) -> tuple[ModeAvailability, dict]:
        estimation = TankEstimation.objects.filter(
            tank_mapping=mapping,
            is_active=True,
        ).first()

        if not estimation and allow_estimation_run:
            estimation = EstimationService().run_estimation_for_tank(mapping)

        if estimation:
            confidence = self.confidence_level_from_numeric(estimation.confidence)
            source_meta = {
                "name": "MATHEMATICAL_ESTIMATE",
                "confidence": estimation.confidence,
                "estimation": estimation,
            }
            return (
                ModeAvailability(
                    mode=CalculationMode.MATHEMATICAL,
                    available=True,
                    reason=None,
                    confidence=confidence,
                ),
                source_meta,
            )

        return (
            ModeAvailability(
                mode=CalculationMode.MATHEMATICAL,
                available=False,
                reason=MATHEMATICAL_UNAVAILABLE_REASON,
                confidence=ConfidenceLevel.NONE,
            ),
            {},
        )
