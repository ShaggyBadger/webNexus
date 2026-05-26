import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import Mission, TruckFuelLog

logger = logging.getLogger("webnexus")


@login_required
def fuel_log_create(request, mission_id):
    """
    FUEL_LOG_CREATE_API:
    POST: Logs a truck fuel purchase during the active mission.
    """
    if request.method == "POST":
        mission = get_object_or_404(Mission, pk=mission_id, user=request.user)
        if mission.is_completed:
            return JsonResponse(
                {"status": "error", "message": "Cannot modify a completed mission."},
                status=400,
            )

        try:
            data = json.loads(request.body)
            gallons = float(data.get("gallons"))
            price_per_gallon = float(data.get("price_per_gallon"))

            fuel = TruckFuelLog.objects.create(
                mission=mission, gallons=gallons, price_per_gallon=price_per_gallon
            )
            logger.info(
                f"FUEL_CREATE: Truck fuel log logged under Mission #{mission.id} ({gallons} gal pumped)."
            )
            return JsonResponse(
                {"status": "success", "fuel_log_id": fuel.id}, status=201
            )
        except Exception as e:
            logger.error(f"FUEL_CREATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def fuel_log_update_delete(request, pk):
    """
    FUEL_LOG_DETAIL_API:
    PUT: Modifies truck fuel log purchase parameters.
    DELETE: Deletes a fuel log entry.
    """
    fuel = get_object_or_404(TruckFuelLog, pk=pk, mission__user=request.user)
    if fuel.mission.is_completed:
        return JsonResponse(
            {"status": "error", "message": "Cannot modify a completed mission."},
            status=400,
        )

    if request.method == "PUT":
        try:
            data = json.loads(request.body)
            if "gallons" in data:
                fuel.gallons = float(data["gallons"])
            if "price_per_gallon" in data:
                fuel.price_per_gallon = float(data["price_per_gallon"])
            fuel.save()
            logger.info(
                f"FUEL_UPDATE: Truck fuel log ID {fuel.id} purchase values updated."
            )
            return JsonResponse({"status": "success"})
        except Exception as e:
            logger.error(f"FUEL_UPDATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    elif request.method == "DELETE":
        logger.info(
            f"FUEL_DELETE: Truck fuel log ID {fuel.id} removed from Mission #{fuel.mission.id}."
        )
        fuel.delete()
        return JsonResponse({"status": "success", "message": "Fuel log entry deleted."})

    return JsonResponse({"error": "Method not allowed"}, status=405)
