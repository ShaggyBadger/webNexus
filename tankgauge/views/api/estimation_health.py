import logging

from atg.models import VeederReading
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from ...logic.tank_lookup import get_store_and_preset_status
from ...models import StoreTankMapping, TankEstimation, VirtualTankEstimation
from ...serializers import EstimationHealthRequestSerializer
from .error_contract import drf_error_response, drf_success_response

logger = logging.getLogger("tankgauge")


class EstimationHealthAPIView(APIView):
    """Return estimation quality and telemetry for a tank identity."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = EstimationHealthRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            logger.warning(
                "ESTIMATION_HEALTH_INVALID_REQUEST",
                extra={
                    "reason_code": "serializer_invalid",
                    "errors": serializer.errors,
                },
            )
            return drf_error_response(
                request=request,
                code="validation_error",
                message="Request parameters are invalid.",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        tank_id = data.get("tank_id")
        if tank_id and str(tank_id).isdigit():
            return self._mapped_tank_health(request=request, tank_id=int(tank_id))

        store_id = data.get("store_id")
        store, _ = get_store_and_preset_status(store_id)
        if not store:
            logger.warning(
                "ESTIMATION_HEALTH_STORE_NOT_FOUND",
                extra={"store_id": store_id, "reason_code": "store_not_found"},
            )
            return drf_error_response(
                request=request,
                code="store_not_found",
                message="Store not found.",
                details={"store_id": store_id},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return self._virtual_tank_health(
            store=store,
            fuel_type=data.get("fuel_type"),
            tank_index=data.get("tank_index"),
        )

    def _mapped_tank_health(self, request, tank_id: int):
        mapping = (
            StoreTankMapping.objects.filter(id=tank_id)
            .select_related("store", "tank_type")
            .first()
        )
        if not mapping:
            logger.warning(
                "ESTIMATION_HEALTH_MAPPING_NOT_FOUND",
                extra={"tank_id": tank_id, "reason_code": "mapping_not_found"},
            )
            return drf_error_response(
                request=request,
                code="mapping_not_found",
                message="Tank mapping not found.",
                details={"tank_id": tank_id},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        estimates = list(
            TankEstimation.objects.filter(tank_mapping=mapping).order_by("-created_at")[
                :2
            ]
        )
        active = next((item for item in estimates if item.is_active), None)

        reading_qs = VeederReading.objects.filter(
            ticket__store=mapping.store,
            tank_index=mapping.tank_index,
            fuel_type__name__iexact=mapping.fuel_type,
        ).select_related("ticket")
        latest_reading = reading_qs.order_by("-ticket__uploaded_at").first()

        return drf_success_response(
            data={
                "identity": {
                    "source": "mapped",
                    "store_num": mapping.store.store_num,
                    "fuel_type": mapping.fuel_type,
                    "tank_index": mapping.tank_index,
                    "mapping_id": mapping.id,
                },
                **self._build_health_payload(
                    active, estimates, reading_qs.count(), latest_reading
                ),
            }
        )

    def _virtual_tank_health(self, store, fuel_type, tank_index):
        estimates = list(
            VirtualTankEstimation.objects.filter(
                store=store,
                fuel_type__iexact=fuel_type,
                tank_index=tank_index,
            ).order_by("-created_at")[:2]
        )
        active = next((item for item in estimates if item.is_active), None)

        reading_qs = VeederReading.objects.filter(
            ticket__store=store,
            tank_index=tank_index,
            fuel_type__name__iexact=fuel_type,
        ).select_related("ticket")
        latest_reading = reading_qs.order_by("-ticket__uploaded_at").first()

        return drf_success_response(
            data={
                "identity": {
                    "source": "virtual",
                    "store_num": store.store_num,
                    "fuel_type": fuel_type,
                    "tank_index": tank_index,
                    "mapping_id": None,
                },
                **self._build_health_payload(
                    active, estimates, reading_qs.count(), latest_reading
                ),
            }
        )

    def _build_health_payload(self, active, estimates, reading_count, latest_reading):
        previous = estimates[1] if len(estimates) > 1 else None
        mean_error_delta = None
        trend = "insufficient_history"

        if (
            active
            and previous
            and active.mean_error is not None
            and previous.mean_error is not None
        ):
            mean_error_delta = round(active.mean_error - previous.mean_error, 4)
            if mean_error_delta < 0:
                trend = "improving"
            elif mean_error_delta > 0:
                trend = "degrading"
            else:
                trend = "flat"

        return {
            "has_active_estimation": bool(active),
            "reading_count": reading_count,
            "sample_count": active.sample_count if active else 0,
            "mean_error_gallons": active.mean_error if active else None,
            "max_error_gallons": active.max_error if active else None,
            "mean_error_delta_gallons": mean_error_delta,
            "trend": trend,
            "last_estimated_at": active.created_at.isoformat() if active else None,
            "latest_ticket_at": (
                latest_reading.ticket.uploaded_at.isoformat()
                if latest_reading
                else None
            ),
        }
