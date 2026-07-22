import logging
import random

from atg.models import VeederReading
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from ...logic.mode_resolver import ModeResolver
from ...logic.curve_generator import generate_inch_gallon_curve
from ...logic.store_lookup import get_store_by_any_id
from ...logic.tank_limits import resolve_tank_limits
from ...models import StoreTankMapping, TankChart, TankEstimation
from .error_contract import drf_error_response, drf_success_response

logger = logging.getLogger("tankgauge")


class StoreTanksAPIView(APIView):
    """Return tank mapping records for a store number."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode_resolver = ModeResolver()

    def _unavailable_limits(self, mode_value: str, reason: str) -> dict:
        return {
            "capacity_gallons": None,
            "max_depth_inches": None,
            "ninety_percent_gallons": None,
            "source": "UNAVAILABLE",
            "mode": mode_value,
            "warnings": [reason] if reason else [],
        }

    def _serialize_mapping(self, mapping):
        available_modes, mode_meta = (
            self.mode_resolver.resolve_available_modes_for_mapping(
                mapping,
                allow_estimation_run=True,
            )
        )
        default_mode = self.mode_resolver.select_default_mode(available_modes)

        limits_by_mode = {}
        for mode_availability in available_modes:
            if mode_availability.available:
                mode_limits = self.mode_resolver.build_limits_for_mode(
                    mapping,
                    mode=mode_availability.mode,
                    source_meta=mode_meta.get(mode_availability.mode),
                ).to_dict()
            else:
                mode_limits = self._unavailable_limits(
                    mode_availability.mode.value,
                    mode_availability.reason,
                )
            limits_by_mode[mode_availability.mode.value] = mode_limits

        limits = limits_by_mode.get(default_mode.value) or self._unavailable_limits(
            default_mode.value,
            "No data available for selected calculation mode.",
        )
        legacy_limits = resolve_tank_limits(mapping)

        return {
            "id": mapping.id,
            "tank_index": mapping.tank_index,
            "fuel_type": mapping.fuel_type,
            "tank_type_name": mapping.tank_type.name if mapping.tank_type else None,
            "capacity": legacy_limits["capacity_gallons"],
            "max_depth": legacy_limits["max_depth_inches"],
            "limits_source": legacy_limits["source"],
            "available_modes": [mode.to_dict() for mode in available_modes],
            "default_mode": default_mode.value,
            "limits": limits,
            "limits_by_mode": limits_by_mode,
        }

    def get(self, request, store_num):
        store = get_store_by_any_id(store_num)
        if not store:
            logger.warning(
                "STORE_TANKS_NOT_FOUND",
                extra={"store_num": store_num, "reason_code": "store_not_found"},
            )
            return drf_error_response(
                request=request,
                code="store_not_found",
                message="Store not found.",
                details={"store_num": store_num},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        mappings = (
            StoreTankMapping.objects.filter(store=store)
            .select_related("tank_type")
            .order_by("tank_index", "id")
        )
        tanks = [self._serialize_mapping(mapping) for mapping in mappings]

        logger.info(
            "STORE_TANKS_FETCHED",
            extra={"store_num": store_num, "tank_count": len(tanks)},
        )
        return drf_success_response(
            data={
                "store": {
                    "store_num": store.store_num,
                    "riso_num": store.riso_num,
                    "store_name": store.store_name,
                    "address": store.address,
                    "city": store.city,
                    "state": store.state,
                },
                "tanks": tanks,
            }
        )


class TankChartDataAPIView(APIView):
    """Return official, generated, and scatter chart series for a tank."""

    permission_classes = [AllowAny]

    def _get_official_chart(self, mapping):
        official_chart = list(
            TankChart.objects.filter(
                store=mapping.store,
                tank_index=mapping.tank_index,
                is_official=True,
            )
            .order_by("inches")
            .values("inches", "gallons")
        )
        if official_chart or not mapping.tank_type:
            return official_chart

        return list(
            TankChart.objects.filter(
                tank_type=mapping.tank_type,
                is_official=True,
            )
            .order_by("inches")
            .values("inches", "gallons")
        )

    def _get_generated_curve(self, mapping, max_depth):
        estimation = TankEstimation.objects.filter(
            tank_mapping=mapping,
            is_active=True,
        ).first()
        if not estimation or not estimation.radius or not estimation.length:
            return []

        try:
            return generate_inch_gallon_curve(
                radius_inches=float(estimation.radius),
                length_inches=float(estimation.length),
                max_depth=int(max_depth),
            )
        except ValueError:
            logger.warning(
                "TANK_CHART_GENERATED_CURVE_INVALID_PARAMS",
                extra={
                    "tank_mapping_id": mapping.id,
                    "radius_inches": float(estimation.radius),
                    "length_inches": float(estimation.length),
                    "reason_code": "curve_math_invalid_params",
                },
            )
            return []

    def _get_scatter_points(self, mapping):
        readings = VeederReading.objects.filter(
            ticket__store=mapping.store,
            tank_index=mapping.tank_index,
            fuel_type__name__iexact=mapping.fuel_type,
            height__isnull=False,
            volume__isnull=False,
        ).select_related("ticket")

        recent_readings = list(readings.order_by("-ticket__uploaded_at", "-id")[:5])
        if len(recent_readings) < 5:
            selected_readings = recent_readings
        else:
            remaining_ids = list(
                readings.exclude(
                    id__in=[reading.id for reading in recent_readings]
                ).values_list("id", flat=True)
            )
            random_ids = random.sample(remaining_ids, k=min(5, len(remaining_ids)))
            random_readings_by_id = {
                reading.id: reading
                for reading in VeederReading.objects.filter(
                    id__in=random_ids
                ).select_related("ticket")
            }
            random_readings = [
                random_readings_by_id[reading_id]
                for reading_id in random_ids
                if reading_id in random_readings_by_id
            ]
            selected_readings = recent_readings + random_readings

        scatter_points = []
        for reading in selected_readings:
            scatter_points.append(
                {
                    "inches": float(reading.height),
                    "gallons": float(reading.volume),
                    "date": (
                        reading.ticket.uploaded_at.isoformat()
                        if reading.ticket and reading.ticket.uploaded_at
                        else None
                    ),
                }
            )
        return scatter_points

    def get(self, request, tank_id):
        try:
            mapping = StoreTankMapping.objects.select_related("tank_type", "store").get(
                id=tank_id
            )
        except StoreTankMapping.DoesNotExist:
            logger.warning(
                "TANK_CHART_DATA_NOT_FOUND",
                extra={"tank_id": tank_id, "reason_code": "mapping_not_found"},
            )
            return drf_error_response(
                request=request,
                code="tank_not_found",
                message="Tank not found.",
                details={"tank_id": tank_id},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        limits = resolve_tank_limits(mapping)
        max_depth = limits["max_depth_inches"] or 120
        official_chart = self._get_official_chart(mapping)
        generated_curve = self._get_generated_curve(mapping, max_depth)
        scatter_points = self._get_scatter_points(mapping)

        logger.info(
            "TANK_CHART_DATA_FETCHED",
            extra={
                "tank_id": mapping.id,
                "store_num": mapping.store.store_num,
                "official_points": len(official_chart),
                "generated_points": len(generated_curve),
                "scatter_points": len(scatter_points),
            },
        )

        return drf_success_response(
            data={
                "tank": {
                    "id": mapping.id,
                    "fuel_type": mapping.fuel_type,
                    "capacity": limits["capacity_gallons"],
                    "max_depth": limits["max_depth_inches"],
                    "limits_source": limits["source"],
                    "tank_index": mapping.tank_index,
                },
                "series": {
                    "official_chart": official_chart,
                    "generated_curve": generated_curve,
                    "scatter_points": scatter_points,
                },
            }
        )
