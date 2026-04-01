from django.http import JsonResponse
from .models import Store
import math


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    r = 3956  # Radius of earth in miles. Use 6371 for kilometers
    return c * r


def closest_store_api(request):
    """
    Tactical Intel: Returns the closest store based on GPS coordinates.
    """
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if not lat or not lon:
        return JsonResponse({"error": "Missing coordinates"}, status=400)

    try:
        user_lat = float(lat)
        user_lon = float(lon)
    except ValueError:
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    # Fetch all stores with coordinates
    stores = Store.objects.exclude(lat__isnull=True).exclude(lon__isnull=True)

    closest_store = None
    min_distance_miles = float("inf")

    for store in stores:
        dist = haversine(user_lat, user_lon, store.lat, store.lon)
        if dist < min_distance_miles:
            min_distance_miles = dist
            closest_store = store

    if closest_store:
        distance_feet = round(min_distance_miles * 5280)
        return JsonResponse(
            {
                "store_num": closest_store.store_num,
                "store_name": closest_store.store_name,
                "city": closest_store.city,
                "state": closest_store.state,
                "distance_feet": distance_feet,
                # Reverse Geocoding would ideally go here, but for now we'll
                # return the nearest store's location as a proxy or use a free API.
                "user_location_proxy": f"{closest_store.city}, {closest_store.state}",
            }
        )

    return JsonResponse({"error": "No stores found"}, status=404)
