from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Store, StoreTankMapping, TankType
from .forms import DeliveryEstimationForm, TankDataForm
from .logic.store_lookup import get_store_by_any_id
from .logic.calculations import get_volume_from_depth, get_depth_from_volume
import math
import random


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
                # Use Store #6949 as the standard for 7-11
                std_store = Store.objects.filter(store_num=6949).first()
                mappings = StoreTankMapping.objects.filter(
                    store=std_store, 
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
                        "form": TankDataForm(auto_id=f"tank_{m.fuel_type}_%s", prefix=f"tank_{m.fuel_type}"),
                        "is_preset": True
                    })
                
                context = {
                    "store_num": "7-11_STD",
                    "tanks": tanks_found,
                    "is_preset": True,
                    "selected_fuels": ",".join(selected_fuels) # Pass as comma-separated for report
                }
                return render(request, "tankgauge/delivery_results_preset.html", context)
            
            # CASE B: DATABASE LOOKUP
            else:
                store = get_store_by_any_id(store_number_input)
                if store:
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
                            "form": TankDataForm(auto_id=f"tank_{m.id}_%s", prefix=f"tank_{m.id}"),
                            "is_preset": False,
                            "mapping_id": m.id
                        })
                    
                    context = {
                        "store": store,
                        "tanks": tanks_found,
                        "is_preset": False,
                        "selected_mappings": ",".join([str(m.id) for m in mappings])
                    }
                    return render(request, "tankgauge/delivery_results_db.html", context)

                else:
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


def delivery_report(request):
    """
    Processes a list of tanks for calculation. 
    Handles both database-linked tanks and the 7-11 emulator.
    """
    if request.method != "POST":
        return redirect("tankgauge:delivery_form")

    store_id = request.POST.get("store_id")
    results = []
    store_name = "7-11_STANDARD_EMULATION"

    # Identify the store
    if store_id != "7-11_STD":
        store = get_store_by_any_id(store_id)
        if store:
            store_name = store.store_name

    # Determine which tanks to process based on hidden IDs passed in POST
    if store_id == "7-11_STD":
        std_store = Store.objects.filter(store_num=6949).first()
        fuels = request.POST.get("selected_fuels", "").split(",")
        for fuel in fuels:
            if not fuel: continue
            
            prefix = f"tank_{fuel}"
            try:
                inches = float(request.POST.get(f"{prefix}-current_inches", 0))
                gallons = float(request.POST.get(f"{prefix}-delivery_gallons", 0))
            except (ValueError, TypeError):
                inches, gallons = 0.0, 0.0

            # Emulator Tank lookup
            mapping = StoreTankMapping.objects.filter(store=std_store, fuel_type=fuel.lower()).first()
            if mapping:
                results.append(perform_tank_calc(mapping.tank_type, fuel, inches, gallons))
    
    else:
        mapping_ids = request.POST.get("selected_mappings", "").split(",")
        for m_id in mapping_ids:
            if not m_id: continue
            
            prefix = f"tank_{m_id}"
            try:
                inches = float(request.POST.get(f"{prefix}-current_inches", 0))
                gallons = float(request.POST.get(f"{prefix}-delivery_gallons", 0))
            except (ValueError, TypeError):
                inches, gallons = 0.0, 0.0

            mapping = StoreTankMapping.objects.filter(id=m_id).first()
            if mapping:
                results.append(perform_tank_calc(mapping.tank_type, mapping.fuel_type, inches, gallons))

    context = {
        "report_id": f"{random.randint(1000, 9999)}-{random.randint(100, 999)}",
        "store_id": store_id,
        "store_name": store_name,
        "results": results,
    }

    return render(request, "tankgauge/delivery_report.html", context)


def calculate_tank_api(request):
    """
    AJAX API endpoint for calculating a single tank's estimation.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    store_id = request.POST.get("store_id")
    fuel_type = request.POST.get("fuel_type")
    
    try:
        current_inches = float(request.POST.get("current_inches", 0))
        delivery_gallons = float(request.POST.get("delivery_gallons", 0))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid numerical input"}, status=400)

    # Tank lookup logic (similar to delivery_report)
    tank_type = None
    if store_id == "7-11_STD":
        std_store = Store.objects.filter(store_num=6949).first()
        mapping = StoreTankMapping.objects.filter(store=std_store, fuel_type=fuel_type.lower()).first()
        if mapping:
            tank_type = mapping.tank_type
    else:
        store = get_store_by_any_id(store_id)
        if store:
            mapping = StoreTankMapping.objects.filter(store=store, fuel_type=fuel_type.lower()).first()
            if mapping:
                tank_type = mapping.tank_type

    if not tank_type:
        return JsonResponse({"error": "Tank chart not found"}, status=404)

    # Perform calculation
    result = perform_tank_calc(tank_type, fuel_type, current_inches, delivery_gallons)
    return JsonResponse(result)


def perform_tank_calc(tank_type, fuel_type, current_inches, delivery_gallons):
    """
    Helper to perform the core calculation for a single tank.
    """
    initial_gallons = get_volume_from_depth(tank_type, current_inches)
    final_gallons = initial_gallons + delivery_gallons
    final_inches = get_depth_from_volume(tank_type, final_gallons)
    
    # Calculate 90% availability
    capacity = tank_type.capacity or 0
    ninety_percent_limit = capacity * 0.9
    avail_90 = max(0, ninety_percent_limit - initial_gallons)

    # Check for No-Fit Warning
    no_fit_warning = final_gallons > ninety_percent_limit

    return {
        "fuel_type": fuel_type,
        "initial_inches": current_inches,
        "initial_gallons": int(initial_gallons),
        "delivery_gallons": int(delivery_gallons),
        "avail_90": int(avail_90),
        "final_gallons": int(final_gallons),
        "final_inches": final_inches,
        "no_fit_warning": no_fit_warning
    }
