import logging
import math
import random
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
from .logic.utils import haversine

# Initialize logger for this module
logger = logging.getLogger(__name__)


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

            try:
                store, is_preset = get_store_and_preset_status(store_number_input)
            except Exception as e:
                logger.error(f"DATABASE_CONNECTION_ERROR during store lookup: {e}", exc_info=True)
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"SYSTEM_ERROR: DATABASE_OFFLINE or CONNECTION_FAILURE",
                    },
                )

            if not store:
                logger.warning(f"STORE_NOT_FOUND: User entered ID #{store_number_input}")
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"STORE_ID #{store_number_input} NOT FOUND IN DATABASE",
                    },
                )

            logger.info(f"FETCHING_DATA for Store #{store_number_input} (Preset: {is_preset})")
            tanks_found = []
            for fuel in selected_fuels:
                try:
                    mapping = get_tank_mapping(store, fuel)
                    
                    if mapping and mapping.tank_type:
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
                except Exception as e:
                    logger.error(f"TANK_MAPPING_ERROR for Store #{store_number_input}, Fuel {fuel}: {e}", exc_info=True)
                    tanks_found.append({
                        "fuel_type": fuel.upper(),
                        "is_missing": True,
                        "error": "SYSTEM_FETCH_ERROR"
                    })

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
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    # Fetch all stores with coordinates
    try:
        stores = Store.objects.exclude(lat__isnull=True).exclude(lon__isnull=True)
    except Exception as e:
        logger.error(f"DATABASE_ERROR during closest_store lookup: {e}", exc_info=True)
        return JsonResponse({"error": "Database error"}, status=500)

    closest_store = None
    min_distance_miles = float("inf")

    for store in stores:
        dist = haversine(user_lat, user_lon, store.lat, store.lon)
        if dist < min_distance_miles:
            min_distance_miles = dist
            closest_store = store

    if closest_store:
        distance_feet = round(min_distance_miles * 5280)
        
        # Tactical Distance Formatting
        if min_distance_miles >= 1:
            distance_display = f"{min_distance_miles:.1f} MI"
        else:
            distance_display = f"{distance_feet:,} FT"

        logger.info(f"GEOLOCATION_SUCCESS: Lat {user_lat}, Lon {user_lon} -> Store #{closest_store.store_num} ({distance_display})")

        return JsonResponse(
            {
                "store_num": closest_store.store_num,
                "store_name": closest_store.store_name,
                "city": closest_store.city,
                "state": closest_store.state,
                "distance_feet": distance_feet,
                "distance_display": distance_display,
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
    try:
        store, _ = get_store_and_preset_status(store_id)
        mapping = get_tank_mapping(store, fuel_type)
    except Exception as e:
        logger.error(f"DATABASE_ERROR during AJAX calculation: {e}", exc_info=True)
        return JsonResponse({"error": "Database connection error"}, status=500)

    if not mapping or not mapping.tank_type:
        logger.warning(f"CALC_MISSING_MAPPING: Store #{store_id}, Fuel {fuel_type}")
        return JsonResponse({"error": "Tank mapping or type not found"}, status=404)

    tank_type = mapping.tank_type

    # Perform calculation
    try:
        result = perform_tank_calc(tank_type, fuel_type, current_inches, delivery_gallons)
        logger.info(f"CALC_SUCCESS: Store #{store_id}, Fuel {fuel_type}, Inches {current_inches}, Gallons {delivery_gallons}")
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"CALCULATION_LOGIC_FAILURE: {e}", exc_info=True)
        return JsonResponse({"error": f"Calculation failed: {str(e)}"}, status=500)
