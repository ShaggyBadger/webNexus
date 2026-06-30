import logging
import math

from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..logic.calculations import perform_tank_calc
from ..models import Store, StoreTankMapping, TankChart
from ..logic.tank_lookup import get_store_and_preset_status, get_tank_mapping
from ..logic.utils import haversine
from ..serializers import (
    CalcRequestSerializer,
    CalcResponseSerializer,
    EstimationHealthRequestSerializer,
)
from ..models import TankEstimation, VirtualTankEstimation
from atg.models import VeederReading

# Initialize logger for this module
logger = logging.getLogger("tankgauge")


def closest_store_api(request):
    """
    TACTICAL INTEL:
    Determines the nearest operational site based on user-reported GPS coordinates.
    Used for the 'Near Me' feature to reduce manual store number entry.
    """
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if not lat or not lon:
        logger.warning("GEO_LOOKUP_ABORTED: Missing coordinates in request.")
        return JsonResponse({"error": "Missing coordinates"}, status=400)

    try:
        user_lat = float(lat)
        user_lon = float(lon)
    except (ValueError, TypeError):
        logger.warning(f"GEO_LOOKUP_FAILED: Invalid coordinates provided: {lat}, {lon}")
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    # SITE_SCAN: Search all stores with valid geospatial data
    try:
        stores = (
            Store.objects.exclude(lat__isnull=True)
            .exclude(lon__isnull=True)
            .select_related("location")
        )
    except Exception as e:
        logger.error(
            f"DATABASE_ERROR_CLOSEST_STORE: Lat {user_lat}, Lon {user_lon}",
            exc_info=True,
        )
        return JsonResponse({"error": "Database error"}, status=500)

    # TACTICAL: Calculate distances and sort to find top 5 targets
    store_distances = []
    for store in stores:
        dist = haversine(user_lat, user_lon, store.lat, store.lon)
        store_distances.append((dist, store))

    # Sort by distance (first element of tuple)
    store_distances.sort(key=lambda x: x[0])

    # Take top 5
    top_targets = store_distances[:5]

    if top_targets:
        results = []
        for dist_miles, store in top_targets:
            distance_feet = round(dist_miles * 5280)

            # Tactical Distance Formatting
            if dist_miles >= 1:
                distance_display = f"{dist_miles:.1f} MI"
            else:
                distance_display = f"{distance_feet:,} FT"

            results.append(
                {
                    "store_num": store.store_num,
                    "store_name": store.store_name or f"Store #{store.store_num}",
                    "store_pk": store.id,
                    "city": store.city or "UNKNOWN",
                    "state": store.state or "--",
                    "distance_feet": distance_feet,
                    "distance_display": distance_display,
                    "has_location": store.location is not None,
                    "location_id": store.location.id if store.location else None,
                    "user_location_proxy": f"{store.city}, {store.state}",
                }
            )

        logger.info(
            f"GEOLOCATION_SUCCESS: Identified {len(results)} proximal targets for Agent GPS.",
            extra={"lat": lat, "lon": lon},
        )
        return JsonResponse({"results": results})

    logger.warning("GEOLOCATION_EMPTY: No stores found in database.")
    return JsonResponse({"error": "No stores found"}, status=404)


class CalculateTankAPIView(APIView):
    """
    TACTICAL INTEL:
    Asynchronous computation engine for real-time tank estimations.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CalcRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": self._format_errors(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        store_id = data["store_id"]
        fuel_type = data["fuel_type"]
        tank_id = data.get("tank_id")
        tank_index = data.get("tank_index")
        current_inches = data["current_inches"]
        delivery_gallons = data["delivery_gallons"]

        # TANK_RESOLUTION: Determine which physical tank chart to use.
        virtual_meta = None
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

                if not mapping and store:
                    # VIRTUAL_RESOLVER: No explicit mapping, check if it's a virtual card from the frontend
                    logger.info(
                        f"VIRTUAL_RESOLVER_DEBUG: StoreID={store.id}, Fuel={fuel_type}, TankIndex={tank_index}, POST_DATA={data}"
                    )
                    if tank_index is not None:
                        virtual_meta = {
                            "store_id": store.id,
                            "fuel_type": fuel_type,
                            "tank_index": tank_index,
                        }

        except Exception:
            logger.error(
                f"DATABASE_ERROR_AJAX_CALC: Store {store_id}, Fuel {fuel_type}",
                exc_info=True,
            )
            return Response(
                {"error": "Database connection error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not mapping and not virtual_meta:
            logger.warning(
                f"CALC_MISSING_MAPPING: No hardware definition for Store {store_id} {fuel_type} (TankIndex: {tank_index})"
            )
            return Response(
                {
                    "error": f"No tank mapping or type found for Store {store_id}, {fuel_type} (TankIndex: {tank_index}). Please define this tank in Admin -> Store Tank Mappings."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # COMPUTATION_PHASE: Execute the core math
        try:
            result = perform_tank_calc(
                mapping,
                current_inches,
                delivery_gallons,
                virtual_meta=virtual_meta,
            )
            final_gallons = result.get("final_gallons")
            logger.info(
                f"CALC_SUCCESS: Store {store_id} {fuel_type} -> Final Volume {final_gallons if final_gallons is not None else 'UNAVAILABLE'} (Source={result.get('data_source')})"
            )

            response_serializer = CalcResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(
                    response_serializer.validated_data,
                    status=status.HTTP_200_OK,
                )

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"CALCULATION_LOGIC_FAILURE: Store {store_id} {fuel_type}",
                exc_info=True,
            )
            return Response(
                {"error": f"Calculation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _format_errors(self, errors):
        if isinstance(errors, dict):
            parts = []
            for field, value in errors.items():
                if isinstance(value, (list, tuple)):
                    rendered = ", ".join(str(item) for item in value)
                else:
                    rendered = str(value)
                parts.append(f"{field}: {rendered}")
            return " | ".join(parts)
        return str(errors)


class EstimationHealthAPIView(APIView):
    """
    Returns estimation quality and progress telemetry for a tank card.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = EstimationHealthRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                {"error": self._format_errors(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        tank_id = data.get("tank_id")

        if tank_id and str(tank_id).isdigit():
            return self._mapped_tank_health(int(tank_id))

        store, _ = get_store_and_preset_status(data.get("store_id"))
        if not store:
            return Response(
                {"error": f"Store {data.get('store_id')} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return self._virtual_tank_health(
            store=store,
            fuel_type=data.get("fuel_type"),
            tank_index=data.get("tank_index"),
        )

    def _mapped_tank_health(self, tank_id):
        mapping = (
            StoreTankMapping.objects.filter(id=tank_id)
            .select_related("store", "tank_type")
            .first()
        )
        if not mapping:
            return Response(
                {"error": f"Tank mapping {tank_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
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

        return Response(
            {
                "status": "success",
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

        return Response(
            {
                "status": "success",
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
            "confidence": active.confidence if active else 0.0,
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

    def _format_errors(self, errors):
        if isinstance(errors, dict):
            parts = []
            for field, value in errors.items():
                if isinstance(value, (list, tuple)):
                    rendered = ", ".join(str(item) for item in value)
                else:
                    rendered = str(value)
                parts.append(f"{field}: {rendered}")
            return " | ".join(parts)
        return str(errors)


class StoreTanksAPIView(APIView):
    """
    Returns the list of tank hardware mappings for a given store number.
    """

    permission_classes = [AllowAny]

    def _serialize_mapping(self, mapping):
        return {
            "id": mapping.id,
            "tank_index": mapping.tank_index,
            "fuel_type": mapping.fuel_type,
            "tank_type_name": mapping.tank_type.name if mapping.tank_type else None,
            "capacity": mapping.tank_type.capacity if mapping.tank_type else None,
            "max_depth": mapping.tank_type.max_depth if mapping.tank_type else None,
        }

    def get(self, request, store_num):
        try:
            store = Store.objects.get(store_num=store_num)
        except Store.DoesNotExist:
            return Response(
                {"error": "Store not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mappings = (
            StoreTankMapping.objects.filter(store=store)
            .select_related("tank_type")
            .order_by("tank_index", "id")
        )

        tanks = [self._serialize_mapping(mapping) for mapping in mappings]

        return Response(
            {
                "store": {
                    "store_num": store.store_num,
                    "store_name": store.store_name,
                    "address": store.address,
                    "city": store.city,
                    "state": store.state,
                },
                "tanks": tanks,
            },
        )


class TankChartDataAPIView(APIView):
    """
    Returns chart data for a specific tank mapping (Section 5 Chart.js).
    """

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
        generated_curve = []
        estimation = TankEstimation.objects.filter(
            tank_mapping=mapping,
            is_active=True,
        ).first()
        if not estimation or not estimation.radius or not estimation.length:
            return generated_curve

        radius = estimation.radius
        length = estimation.length

        for inch in range(1, int(max_depth) + 1):
            height = float(inch)
            if height > 2 * radius:
                height = 2 * radius

            try:
                area = (radius**2) * math.acos((radius - height) / radius) - (
                    radius - height
                ) * math.sqrt(max(0, 2 * radius * height - height**2))
                volume_gallons = (area * length) / 231.0
                generated_curve.append(
                    {
                        "inches": inch,
                        "gallons": round(volume_gallons, 1),
                    }
                )
            except Exception:
                continue

        return generated_curve

    def _get_scatter_points(self, mapping):
        readings = VeederReading.objects.filter(
            ticket__store=mapping.store,
            tank_index=mapping.tank_index,
            fuel_type__name__iexact=mapping.fuel_type,
        ).order_by("-ticket__uploaded_at")[:100]

        scatter_points = []
        for reading in readings:
            if reading.height is None or reading.volume is None:
                continue
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
            return Response(
                {"error": "Tank not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        max_depth = (
            mapping.tank_type.max_depth
            if mapping.tank_type and mapping.tank_type.max_depth
            else 120
        )

        official_chart = self._get_official_chart(mapping)
        generated_curve = self._get_generated_curve(mapping, max_depth)
        scatter_points = self._get_scatter_points(mapping)

        return Response(
            {
                "tank": {
                    "id": mapping.id,
                    "fuel_type": mapping.fuel_type,
                    "capacity": (
                        mapping.tank_type.capacity if mapping.tank_type else None
                    ),
                    "tank_index": mapping.tank_index,
                },
                "series": {
                    "official_chart": official_chart,
                    "generated_curve": generated_curve,
                    "scatter_points": scatter_points,
                },
            },
        )
