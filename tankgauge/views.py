from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Store, StoreTankMapping
from .forms import DeliveryEstimationForm, TankDataForm
import math


def delivery_form(request):
    """
    Renders the Fuel Delivery Estimation form.
    """
    form = DeliveryEstimationForm()
    return render(request, "tankgauge/delivery_form.html", {"form": form})


def delivery_submit(request):
    """
    Handles form submission for Fuel Delivery Estimation.
    Queries the database for specific store tanks or returns standard 7-11 defaults.
    """
    if request.method == "POST":
        form = DeliveryEstimationForm(request.POST)
        if form.is_valid():
            store_number_input = form.cleaned_data["store_number"]
            selected_fuels = form.cleaned_data["fuel_types"]
            
            tanks_found = []

            # CASE A: 7-11 STANDARD PRESET
            if store_number_input == "7-11_STD":
                # These are typical 7-11 specs for estimation
                for fuel in selected_fuels:
                    capacity = 10000 if fuel != "plus" else 4000
                    tanks_found.append({
                        "fuel_type": fuel.upper(),
                        "tank_model": "7-11_STANDARD_DOUBLE_WALL",
                        "capacity": capacity,
                        "max_depth": 92,
                        "ninety_percent": int(capacity * 0.9),
                        "form": TankDataForm(auto_id=f"tank_{fuel}_%s"),
                        "is_preset": True
                    })
                
                context = {
                    "store_num": "7-11_STD",
                    "tanks": tanks_found,
                    "is_preset": True
                }
                return render(request, "tankgauge/delivery_results_preset.html", context)
            
            # CASE B: DATABASE LOOKUP
            else:
                try:
                    store = Store.objects.get(store_num=store_number_input)
                    mappings = StoreTankMapping.objects.filter(
                        store=store, 
                        fuel_type__in=selected_fuels
                    ).select_related('tank_type')
                    
                    for m in mappings:
                        capacity = m.tank_type.capacity or 0
                        tanks_found.append({
                            "fuel_type": m.fuel_type.upper(),
                            "tank_model": m.tank_type.name,
                            "capacity": capacity,
                            "max_depth": m.tank_type.max_depth,
                            "ninety_percent": int(capacity * 0.9),
                            "form": TankDataForm(auto_id=f"tank_{m.id}_%s"),
                            "is_preset": False
                        })
                    
                    context = {
                        "store": store,
                        "tanks": tanks_found,
                        "is_preset": False
                    }
                    return render(request, "tankgauge/delivery_results_db.html", context)

                except Store.DoesNotExist:
                    # In case of manual entry failure, return to form with error
                    return render(request, "tankgauge/delivery_form.html", {
                        "form": form,
                        "error_message": f"STORE_ID #{store_number_input} NOT FOUND IN DATABASE"
                    })
        else:
            return render(request, "tankgauge/delivery_form.html", {"form": form})
    return redirect("tankgauge:delivery_form")


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
