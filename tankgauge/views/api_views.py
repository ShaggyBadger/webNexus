import logging
from django.http import JsonResponse
from ..models import Store, StoreTankMapping
from ..logic.tank_lookup import get_store_and_preset_status, get_tank_mapping
from ..logic.calculations import perform_tank_calc
from ..logic.utils import haversine

# Initialize logger for this module
logger = logging.getLogger('tankgauge')

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
        stores = Store.objects.exclude(lat__isnull=True).exclude(lon__isnull=True).select_related('location')
    except Exception as e:
        logger.error(f"DATABASE_ERROR_CLOSEST_STORE: Lat {user_lat}, Lon {user_lon}", exc_info=True)
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

            results.append({
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
            })

        logger.info(f"GEOLOCATION_SUCCESS: Identified {len(results)} proximal targets for Agent GPS.")
        return JsonResponse({"results": results})

    logger.warning("GEOLOCATION_EMPTY: No stores found in database.")
    return JsonResponse({"error": "No stores found"}, status=404)


def calculate_tank_api(request):
    """
    TACTICAL INTEL:
    Asynchronous computation engine for real-time tank estimations.
    Takes physical stick readings and delivery amounts to project final volumes.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    store_id = request.POST.get("store_id")
    fuel_type = request.POST.get("fuel_type")
    tank_id = request.POST.get("tank_id")

    try:
        current_inches = float(request.POST.get("current_inches", 0))
        delivery_gallons = float(request.POST.get("delivery_gallons", 0))
        if current_inches < 0 or delivery_gallons < 0:
            return JsonResponse({"error": "Numerical values must be >= 0"}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid numerical input"}, status=400)

    # TANK_RESOLUTION: Determine which physical tank chart to use.
    try:
        if tank_id and tank_id.isdigit():
            mapping = StoreTankMapping.objects.filter(id=int(tank_id)).select_related("tank_type").first()
        else:
            store, _ = get_store_and_preset_status(store_id)
            mapping = get_tank_mapping(store, fuel_type)
    except Exception as e:
        logger.error(f"DATABASE_ERROR_AJAX_CALC: Store {store_id}, Fuel {fuel_type}", exc_info=True)
        return JsonResponse({"error": "Database connection error"}, status=500)

    if not mapping or not mapping.tank_type:
        logger.warning(f"CALC_MISSING_MAPPING: No hardware definition for Store {store_id} {fuel_type}")
        return JsonResponse({"error": "Tank mapping or type not found"}, status=404)

    tank_type = mapping.tank_type

    # COMPUTATION_PHASE: Execute the core math
    try:
        result = perform_tank_calc(tank_type, fuel_type, current_inches, delivery_gallons)
        logger.info(f"CALC_SUCCESS: Store {store_id} {fuel_type} -> Final Volume {result['final_gallons']}G")
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"CALCULATION_LOGIC_FAILURE: Store {store_id} {fuel_type}", exc_info=True)
        return JsonResponse({"error": f"Calculation failed: {str(e)}"}, status=500)
