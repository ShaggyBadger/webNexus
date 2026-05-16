import logging
from django.shortcuts import render, redirect
from ..forms import DeliveryEstimationForm, TankDataForm
from ..models import TankChart
from ..logic.tank_lookup import get_store_and_preset_status, get_all_tank_mappings

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
