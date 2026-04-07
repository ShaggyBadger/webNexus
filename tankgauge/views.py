from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Store, StoreTankMapping, TankType, TankChart
from .forms import DeliveryEstimationForm, TankDataForm
from .logic.tank_lookup import get_store_and_preset_status, get_tank_mapping
from .logic.calculations import (
    get_volume_from_depth,
    get_depth_from_volume,
    perform_tank_calc,
)
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

            store, is_preset = get_store_and_preset_status(store_number_input)

            if not store:
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"STORE_ID #{store_number_input} NOT FOUND IN DATABASE",
                    },
                )

            tanks_found = []
            for fuel in selected_fuels:
                mapping = get_tank_mapping(store, fuel)

                if mapping:
                    has_chart = TankChart.objects.filter(
                        tank_type=mapping.tank_type
                    ).exists()
                    capacity = mapping.tank_type.capacity or 0
                    tanks_found.append(
                        {
                            "fuel_type": fuel.upper(),
                            "tank_model": mapping.tank_type.name,
                            "capacity": capacity,
                            "max_depth": mapping.tank_type.max_depth,
                            "ninety_percent": int(capacity * 0.9),
                            "form": TankDataForm(
                                auto_id=f"tank_{mapping.id if not is_preset else fuel}_%s",
                                prefix=f"tank_{mapping.id if not is_preset else fuel}",
                            ),
                            "is_preset": is_preset,
                            "mapping_id": mapping.id if not is_preset else None,
                            "has_chart": has_chart,
                            "error": None if has_chart else "MISSING_CHART_DATA",
                        }
                    )
                else:
                    tanks_found.append(
                        {
                            "fuel_type": fuel.upper(),
                            "is_missing": True,
                            "error": (
                                "TANK_NOT_FOUND_IN_PRESET"
                                if is_preset
                                else "TANK_NOT_MAPPED_TO_STORE"
                            ),
                        }
                    )

            if is_preset:
                context = {
                    "store_num": "7-11_STD",
                    "tanks": tanks_found,
                    "is_preset": True,
                    "selected_fuels": ",".join(selected_fuels),
                }
                return render(
                    request, "tankgauge/delivery_results_preset.html", context
                )
            else:
                context = {"store": store, "tanks": tanks_found, "is_preset": False}
                return render(request, "tankgauge/delivery_results_db.html", context)
        else:
            return render(request, "tankgauge/delivery_form.html", {"form": form})
    return redirect("tankgauge:delivery_form")


from .logic.utils import haversine


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
        if current_inches < 0 or delivery_gallons < 0:
            return JsonResponse({"error": "Numerical values must be >= 0"}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid numerical input"}, status=400)

    # Tank lookup logic using helpers
    store, _ = get_store_and_preset_status(store_id)
    mapping = get_tank_mapping(store, fuel_type)

    if mapping:
        tank_type = mapping.tank_type

    if not tank_type:
        return JsonResponse({"error": "Tank chart not found"}, status=404)

    # Perform calculation
    result = perform_tank_calc(tank_type, fuel_type, current_inches, delivery_gallons)
    return JsonResponse(result)
