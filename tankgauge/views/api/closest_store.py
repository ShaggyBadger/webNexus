import logging

from ...logic.utils import haversine
from ...models import Store
from .error_contract import json_error_response, json_success_response

logger = logging.getLogger("tankgauge")


def closest_store_api(request):
    """Return up to five closest stores for GPS coordinates."""
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if not lat or not lon:
        logger.warning(
            "GEO_LOOKUP_ABORTED",
            extra={"reason_code": "missing_coordinates", "lat": lat, "lon": lon},
        )
        return json_error_response(
            request=request,
            code="missing_coordinates",
            message="Missing coordinates.",
            status_code=400,
            details={"lat": lat, "lon": lon},
        )

    try:
        user_lat = float(lat)
        user_lon = float(lon)
    except (ValueError, TypeError):
        logger.warning(
            "GEO_LOOKUP_FAILED",
            extra={"reason_code": "invalid_coordinates", "lat": lat, "lon": lon},
        )
        return json_error_response(
            request=request,
            code="invalid_coordinates",
            message="Invalid coordinates.",
            status_code=400,
            details={"lat": lat, "lon": lon},
        )

    try:
        stores = (
            Store.objects.exclude(lat__isnull=True)
            .exclude(lon__isnull=True)
            .select_related("location")
        )
    except Exception:
        logger.error(
            "DATABASE_ERROR_CLOSEST_STORE",
            extra={"lat": user_lat, "lon": user_lon, "reason_code": "query_failed"},
            exc_info=True,
        )
        return json_error_response(
            request=request,
            code="database_error",
            message="Unable to query store locations.",
            status_code=500,
            details={"operation": "closest_store_lookup"},
        )

    store_distances = []
    for store in stores:
        distance_miles = haversine(user_lat, user_lon, store.lat, store.lon)
        store_distances.append((distance_miles, store))

    store_distances.sort(key=lambda item: item[0])
    top_targets = store_distances[:5]

    if not top_targets:
        logger.warning(
            "GEOLOCATION_EMPTY",
            extra={
                "reason_code": "no_candidate_stores",
                "lat": user_lat,
                "lon": user_lon,
            },
        )
        return json_error_response(
            request=request,
            code="no_stores_found",
            message="No stores found.",
            status_code=404,
            details={"lat": user_lat, "lon": user_lon},
        )

    results = []
    for distance_miles, store in top_targets:
        distance_feet = round(distance_miles * 5280)
        distance_display = (
            f"{distance_miles:.1f} MI"
            if distance_miles >= 1
            else f"{distance_feet:,} FT"
        )
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
        "GEOLOCATION_SUCCESS",
        extra={"lat": user_lat, "lon": user_lon, "result_count": len(results)},
    )
    return json_success_response(data={"results": results})
