import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from ...logic.calculations import perform_tank_calc
from ...logic.tank_lookup import get_store_and_preset_status, get_tank_mapping
from ...models import StoreTankMapping
from ...serializers import CalcRequestSerializer, CalcResponseSerializer
from .error_contract import drf_error_response, drf_success_response

logger = logging.getLogger("tankgauge")


class CalculateTankAPIView(APIView):
    """Execute tank volume and delivery projection calculations."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CalcRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "CALC_REQUEST_INVALID",
                extra={
                    "reason_code": "serializer_invalid",
                    "errors": serializer.errors,
                },
            )
            return drf_error_response(
                request=request,
                code="validation_error",
                message="Request payload is invalid.",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        store_id = data["store_id"]
        fuel_type = data["fuel_type"]
        tank_id = data.get("tank_id")
        tank_index = data.get("tank_index")
        current_inches = data["current_inches"]
        delivery_gallons = data["delivery_gallons"]

        virtual_meta = None
        mapping = None
        try:
            if tank_id and tank_id.isdigit():
                mapping = (
                    StoreTankMapping.objects.filter(id=int(tank_id))
                    .select_related("tank_type")
                    .first()
                )
            else:
                store, _ = get_store_and_preset_status(store_id)
                mapping = get_tank_mapping(store, fuel_type, tank_index=tank_index)

                if not mapping and store and tank_index is not None:
                    logger.info(
                        "VIRTUAL_RESOLVER_CANDIDATE",
                        extra={
                            "store_id": store.id,
                            "fuel_type": fuel_type,
                            "tank_index": tank_index,
                            "reason_code": "missing_explicit_mapping",
                        },
                    )
                    virtual_meta = {
                        "store_id": store.id,
                        "fuel_type": fuel_type,
                        "tank_index": tank_index,
                    }
        except Exception:
            logger.error(
                "DATABASE_ERROR_AJAX_CALC",
                extra={"store_id": store_id, "fuel_type": fuel_type},
                exc_info=True,
            )
            return drf_error_response(
                request=request,
                code="database_error",
                message="Database connection error.",
                details={"operation": "tank_mapping_resolution"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not mapping and not virtual_meta:
            logger.warning(
                "CALC_MISSING_MAPPING",
                extra={
                    "store_id": store_id,
                    "fuel_type": fuel_type,
                    "tank_index": tank_index,
                    "reason_code": "mapping_not_found",
                },
            )
            return drf_error_response(
                request=request,
                code="mapping_not_found",
                message="No tank mapping or type found for the requested tank.",
                details={
                    "store_id": store_id,
                    "fuel_type": fuel_type,
                    "tank_index": tank_index,
                },
                status_code=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = perform_tank_calc(
                mapping,
                current_inches,
                delivery_gallons,
                virtual_meta=virtual_meta,
            )
            final_gallons = result.get("final_gallons")
            logger.info(
                "CALC_SUCCESS",
                extra={
                    "store_id": store_id,
                    "fuel_type": fuel_type,
                    "tank_index": tank_index,
                    "final_gallons": final_gallons,
                    "data_source": result.get("data_source"),
                },
            )

            response_serializer = CalcResponseSerializer(data=result)
            if response_serializer.is_valid():
                return drf_success_response(
                    data=response_serializer.validated_data,
                    status_code=status.HTTP_200_OK,
                )

            return drf_success_response(data=result, status_code=status.HTTP_200_OK)
        except Exception as exc:
            logger.error(
                "CALCULATION_LOGIC_FAILURE",
                extra={"store_id": store_id, "fuel_type": fuel_type},
                exc_info=True,
            )
            return drf_error_response(
                request=request,
                code="calculation_failed",
                message="Calculation failed.",
                details={"exception": str(exc)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
