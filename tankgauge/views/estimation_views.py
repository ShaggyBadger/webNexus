import logging
from django.shortcuts import render, redirect
from ..forms import DeliveryEstimationForm, TankDataForm
from ..models import TankChart, TankEstimation
from atg.models import VeederReading
from ..logic.tank_lookup import get_store_and_preset_status, get_all_tank_mappings
from ..logic.calculations import (
    determine_operating_mode,
    MODE_OFFICIAL,
    MODE_MATHEMATICAL,
    MODE_UNAVAILABLE,
)


# Initialize logger for this module
logger = logging.getLogger("tankgauge")


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
                logger.error(
                    f"DATABASE_CONNECTION_ERROR: Failed to resolve store {store_number_input}",
                    exc_info=True,
                )
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"SYSTEM_ERROR: DATABASE_OFFLINE or CONNECTION_FAILURE",
                    },
                )

            if not store:
                logger.warning(
                    f"STORE_NOT_FOUND: Store ID #{store_number_input} not in database."
                )
                return render(
                    request,
                    "tankgauge/delivery_form.html",
                    {
                        "form": form,
                        "error_message": f"STORE_ID #{store_number_input} NOT FOUND IN DATABASE",
                    },
                )

            logger.info(
                f"FETCHING_DATA: Store #{store.store_num} accessed. Preset={is_preset}, Fuels={selected_fuels}"
            )
            tanks_found = []
            for fuel in selected_fuels:
                try:
                    mappings = get_all_tank_mappings(store, fuel)

                    if not mappings and not is_preset:
                        # TACTICAL_RECOVERY: If no explicit mapping exists, check if we have
                        # historical Veeder readings that could serve as a 'Virtual Mapping'.
                        virtual_readings = (
                            VeederReading.objects.filter(
                                ticket__store=store, fuel_type__name__iexact=fuel
                            )
                            .values("tank_index", "fuel_type__name")
                            .distinct()
                        )

                        logger.info(
                            f"DEBUG_VIRTUAL_SCAN: Store={store.store_num}, Fuel={fuel}, Found={virtual_readings.count()}"
                        )

                        if virtual_readings.exists():
                            logger.info(
                                f"VIRTUAL_MAPPING_ACQUIRED: Store {store.store_num} Fuel {fuel}"
                            )
                            for vr in virtual_readings:
                                # Look for an existing estimation for this virtual tank
                                estimation = TankEstimation.objects.filter(
                                    tank_mapping__store=store,
                                    tank_mapping__fuel_type=fuel,
                                    tank_mapping__tank_index=vr["tank_index"],
                                    is_active=True,
                                ).first()

                                # Default UI values
                                est_data = {
                                    "radius": None,
                                    "length": None,
                                    "confidence": 0.5,
                                    "is_active": False,
                                    "capacity": None,
                                }
                                if estimation:
                                    est_data.update(
                                        {
                                            "radius": estimation.radius,
                                            "length": estimation.length,
                                            "confidence": estimation.confidence,
                                            "is_active": True,
                                            "capacity": estimation.diagnostics.get(
                                                "capacity"
                                            ),
                                        }
                                    )
                                # We treat this as a virtual mapping that defaults to Experimental Mode
                                # Since we don't have a TankType, we'll need to source capacity
                                # from the service during calculation.
                                tanks_found.append(
                                    {
                                        "fuel_type": fuel.upper(),
                                        "tank_index": vr["tank_index"],
                                        "tank_model": "UNMAPPED_HARDWARE (VIRTUAL)",
                                        "est_data": est_data,
                                        "form": TankDataForm(
                                            auto_id=f"virtual_{store.id}_{fuel}_{vr['tank_index']}_%s",
                                            prefix=f"virtual_{store.id}_{fuel}_{vr['tank_index']}",
                                        ),
                                        "is_preset": False,
                                        "mapping_id": None,  # Signal it's virtual
                                        "mode": MODE_MATHEMATICAL,
                                        "has_data": True,
                                        "is_missing": False,
                                        "is_virtual": True,
                                        "store_id": store.id,
                                    }
                                )

                            continue  # Skip the normal missing mapping error

                    if mappings:
                        num_mappings = len(mappings)
                        for idx, mapping in enumerate(mappings):
                            if mapping.tank_type:
                                # Determine Operating Mode (Official vs Experimental vs Unavailable)
                                mode, source_meta = determine_operating_mode(mapping)

                                has_data = mode != MODE_UNAVAILABLE
                                capacity = mapping.tank_type.capacity or 0

                                tanks_found.append(
                                    {
                                        "fuel_type": fuel.upper(),
                                        "tank_index": (
                                            idx + 1 if num_mappings > 1 else None
                                        ),
                                        "tank_model": mapping.tank_type.name,
                                        "capacity": capacity,
                                        "max_depth": mapping.tank_type.max_depth,
                                        "ninety_percent": int(capacity * 0.9),
                                        "form": TankDataForm(
                                            auto_id=f"tank_{mapping.id if not is_preset else fuel}_%s",
                                            prefix=f"tank_{mapping.id if not is_preset else fuel}",
                                        ),
                                        "is_preset": is_preset,
                                        "mapping_id": (
                                            mapping.id if not is_preset else None
                                        ),
                                        "mode": mode,
                                        "has_data": has_data,
                                        "confidence": (
                                            source_meta.get("confidence")
                                            if source_meta
                                            else 1.0
                                        ),
                                        "error": (
                                            None
                                            if has_data
                                            else "NO_CHART_OR_VEEDER_DATA"
                                        ),
                                    }
                                )
                            else:
                                tanks_found.append(
                                    {
                                        "fuel_type": fuel.upper(),
                                        "tank_index": (
                                            idx + 1 if num_mappings > 1 else None
                                        ),
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
                    logger.error(
                        "TANK_MAPPING_ERROR",
                        extra={
                            "store_id": store_number_input,
                            "fuel": fuel,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    tanks_found.append(
                        {
                            "fuel_type": fuel.upper(),
                            "is_missing": True,
                            "error": "SYSTEM_FETCH_ERROR",
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
                logger.info(
                    f"DEBUG_TEMPLATE_CONTEXT: Rendering with {len(tanks_found)} tanks found. Tank fuels: {[t['fuel_type'] for t in tanks_found]}"
                )
                context = {"store": store, "tanks": tanks_found, "is_preset": False}
                return render(request, "tankgauge/delivery_results_db.html", context)
        else:
            return render(request, "tankgauge/delivery_form.html", {"form": form})
    return redirect("tankgauge:delivery_form")
