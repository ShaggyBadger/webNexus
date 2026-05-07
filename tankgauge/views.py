import logging
import math
import random
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Store, StoreTankMapping, TankType, TankChart
from .forms import DeliveryEstimationForm, TankDataForm
from .logic.tank_lookup import get_store_and_preset_status, get_tank_mapping, get_all_tank_mappings
from .logic.calculations import (
    get_volume_from_depth,
    get_depth_from_volume,
    perform_tank_calc,
)
from .logic.utils import haversine

# Initialize logger for this module
logger = logging.getLogger('tankgauge')


def delivery_form(request):
    """
    OPERATIONAL FLOW:
    Renders the primary Fuel Delivery Estimation interface.
    Serves as the mission-entry point for field agents.
    """
    logger.debug(f"UI_ACCESS: Delivery form accessed by {request.user}")
    form = DeliveryEstimationForm()
    return render(request, "tankgauge/delivery_form.html", {"form": form})


def delivery_submit(request):
    """
    OPERATIONAL FLOW:
    Orchestrates the transition from 'Site Identification' to 'Tank Data Entry'.
    Resolves physical store numbers into canonical tank configurations.
    """
    if request.method == "POST":
        form = DeliveryEstimationForm(request.POST)
        if form.is_valid():
            store_number_input = form.cleaned_data["store_number"]
            selected_fuels = form.cleaned_data["fuel_types"]

            try:
                # SITE_ACQUISITION: Attempt to resolve the store identifier
                store, is_preset = get_store_and_preset_status(store_number_input)
            except Exception as e:
                logger.error(f"DATABASE_CONNECTION_ERROR: Failed to resolve store {store_number_input}", exc_info=True)
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"SYSTEM_ERROR: DATABASE_OFFLINE or CONNECTION_FAILURE",
                    },
                )

            if not store:
                logger.warning(f"STORE_NOT_FOUND: Store ID #{store_number_input} not in database.")
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"STORE_ID #{store_number_input} NOT FOUND IN DATABASE",
                    },
                )

            logger.info(f"FETCHING_DATA: Store #{store.store_num} accessed. Preset={is_preset}, Fuels={selected_fuels}")
            tanks_found = []
            for fuel in selected_fuels:
                try:
                    mappings = get_all_tank_mappings(store, fuel)
                    
                    if mappings:
                        num_mappings = len(mappings)
                        for idx, mapping in enumerate(mappings):
                            if mapping.tank_type:
                                has_chart = TankChart.objects.filter(
                                    tank_type=mapping.tank_type
                                ).exists()
                                capacity = mapping.tank_type.capacity or 0
                                tanks_found.append(
                                    {
                                        "fuel_type": fuel.upper(),
                                        "tank_index": idx + 1 if num_mappings > 1 else None,
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
                                        "tank_index": idx + 1 if num_mappings > 1 else None,
                                        "is_missing": True,
                                        "error": "TANK_TYPE_NOT_DEFINED",
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
                    logger.error("TANK_MAPPING_ERROR", extra={"store_id": store_number_input, "fuel": fuel, "error": str(e)}, exc_info=True)
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
