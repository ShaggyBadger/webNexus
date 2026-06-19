import logging

from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..logic.calculations import perform_tank_calc
from ..models import Store, StoreTankMapping
from ..logic.tank_lookup import get_store_and_preset_status, get_tank_mapping
from ..logic.utils import haversine
from ..serializers import CalcRequestSerializer, CalcResponseSerializer

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
                {"error": f"No tank mapping or type found for Store {store_id}, {fuel_type} (TankIndex: {tank_index}). Please define this tank in Admin -> Store Tank Mappings."},
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
