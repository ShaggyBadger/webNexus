import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.conf import settings
from ..models import Mission, FuelType, OrderNumber

logger = logging.getLogger("webnexus")


def serialize_mission(mission):
    """Helper to perform deep relational serialization of a single Mission log."""
    return {
        "id": mission.id,
        "shift_start": mission.shift_start.isoformat(),
        "shift_end": mission.shift_end.isoformat() if mission.shift_end else None,
        "start_miles": mission.start_miles,
        "end_miles": mission.end_miles,
        "total_miles": mission.total_miles,
        "total_stops": mission.total_stops,
        "hours_on_duty": (
            float(mission.hours_on_duty) if mission.hours_on_duty else None
        ),
        "is_completed": mission.is_completed,
        "notes": mission.notes,
        "order_numbers": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "purchase_orders": [
                    {
                        "id": po.id,
                        "po_number": po.po_number,
                        "loads": [
                            {
                                "id": load.id,
                                "fuel_type_id": load.fuel_type.id,
                                "fuel_type_name": load.fuel_type.name,
                                "fuel_type_color": load.fuel_type.color_hex,
                                "store_id": load.store.id if load.store else None,
                                "store_num": (
                                    load.store.store_num if load.store else None
                                ),
                                "store_name": (
                                    load.store.store_name if load.store else None
                                ),
                                "price_at_store": (
                                    float(load.price_at_store)
                                    if load.price_at_store is not None
                                    else None
                                ),
                                "gross_gal": load.gross_gal,
                                "net_gal": load.net_gal,
                                "temp": load.temp,
                                "grav": load.grav,
                                "start_inches": load.start_inches,
                                "start_gallons": load.start_gallons,
                                "end_inches": load.end_inches,
                                "end_gallons": load.end_gallons,
                            }
                            for load in po.loads.all()
                        ],
                    }
                    for po in order.purchase_orders.all()
                ],
            }
            for order in mission.order_numbers.all()
        ],
        "fuel_logs": [
            {
                "id": fuel.id,
                "gallons": float(fuel.gallons) if fuel.gallons is not None else None,
                "price_per_gallon": (
                    float(fuel.price_per_gallon)
                    if fuel.price_per_gallon is not None
                    else None
                ),
                "timestamp": fuel.timestamp.isoformat(),
            }
            for fuel in mission.fuel_logs.all()
        ],
    }


@login_required
def mission_list_or_create(request):
    """
    MISSION_CONTROL_API:
    GET: Lists historical completed missions.
    POST: Triggers initialization protocol for a new shift/mission.
    """
    if request.method == "GET":
        missions = Mission.objects.filter(user=request.user).order_by("-shift_start")
        return JsonResponse([serialize_mission(m) for m in missions], safe=False)

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            # Support time adjustments if they did not log in exactly at start of shift
            start_time_str = data.get("shift_start")
            if start_time_str:
                shift_start = timezone.datetime.fromisoformat(start_time_str)
            else:
                shift_start = timezone.now()

            # Ensure there is no existing uncompleted active shift
            active_shift = Mission.objects.filter(
                user=request.user,
                is_completed=False,
                shift_start__gte=timezone.now() - timedelta(hours=48),
            ).first()

            if active_shift:
                logger.warning(
                    f"INIT_WARN: User {request.user.username} tried to start a new mission, but Mission #{active_shift.id} is already active."
                )
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "An active mission is already in progress. Close it before initiating a new deployment.",
                    },
                    status=400,
                )

            mission = Mission.objects.create(
                user=request.user,
                shift_start=shift_start,
                start_miles=data.get("start_miles"),
                notes=data.get("notes", ""),
            )
            logger.info(
                f"MISSION_INIT: Mission #{mission.id} initialized by operator {request.user.username} at {shift_start}."
            )
            return JsonResponse(
                {"status": "success", "mission": serialize_mission(mission)}, status=201
            )
        except Exception as e:
            logger.error(f"MISSION_INIT_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def active_mission(request):
    """
    ACTIVE_MISSION_API:
    GET: Resolves and returns the currently running mission (if active and within 14h window).
    """
    if request.method == "GET":
        cutoff = timezone.now() - timedelta(hours=14)
        mission = Mission.objects.filter(
            user=request.user, is_completed=False, shift_start__gte=cutoff
        ).first()

        if mission:
            return JsonResponse({"active": True, "mission": serialize_mission(mission)})
        return JsonResponse({"active": False})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def mission_detail_or_update(request, pk):
    """
    MISSION_DETAIL_API:
    GET: Details of a specific historical mission.
    PUT: Updates primary metrics (miles, notes).
    DELETE: Aborts/Deletes the mission and all associated data.
    """
    mission = get_object_or_404(Mission, pk=pk, user=request.user)

    if request.method == "GET":
        return JsonResponse(serialize_mission(mission))

    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            if "start_miles" in data:
                mission.start_miles = data["start_miles"]
            if "end_miles" in data:
                mission.end_miles = data["end_miles"]
            if "notes" in data:
                mission.notes = data["notes"]
            if "hours_on_duty" in data:
                mission.hours_on_duty = data["hours_on_duty"]
            mission.save()
            logger.info(
                f"MISSION_UPDATE: Mission #{mission.id} updated by {request.user.username}."
            )
            return JsonResponse(
                {"status": "success", "mission": serialize_mission(mission)}
            )
        except Exception as e:
            logger.error(f"MISSION_UPDATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    elif request.method == "DELETE":
        try:
            mission_id = mission.id
            mission.delete()
            logger.info(
                f"MISSION_DELETE: Mission #{mission_id} aborted/deleted by {request.user.username}."
            )
            return JsonResponse(
                {"status": "success", "message": "Mission aborted and deleted."}
            )
        except Exception as e:
            logger.error(f"MISSION_DELETE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def complete_mission(request, pk):
    """
    MISSION_COMPLETE_API:
    POST: Finalizes the mission log. Counts stops, records ending odometer, logs completed state.
    """
    if request.method == "POST":
        mission = get_object_or_404(Mission, pk=pk, user=request.user)
        try:
            data = json.loads(request.body)

            end_time_str = data.get("shift_end")
            if end_time_str:
                mission.shift_end = timezone.datetime.fromisoformat(end_time_str)
            else:
                mission.shift_end = timezone.now()

            # Record final odometer
            if "end_miles" in data:
                val = data["end_miles"]
                mission.end_miles = int(val) if val is not None else None

            # Hours on duty
            val = data.get("hours_on_duty")
            if val is not None:
                mission.hours_on_duty = float(val)
            else:
                # Calculate elapsed time automatically
                delta = mission.shift_end - mission.shift_start
                mission.hours_on_duty = round(delta.total_seconds() / 3600.0, 2)

            # Auto calculate total stops based on distinct stores visited across the entire mission
            from ..models import LoadDelivery

            mission.total_stops = (
                LoadDelivery.objects.filter(
                    purchase_order__order_parent__mission=mission
                )
                .exclude(store__isnull=True)
                .values("store")
                .distinct()
                .count()
            )

            mission.is_completed = True
            mission.save()

            logger.info(
                f"MISSION_COMPLETE: Mission #{mission.id} signed off by operator {request.user.username}. Odometer end: {mission.end_miles}. stops: {mission.total_stops}."
            )
            return JsonResponse(
                {"status": "success", "mission": serialize_mission(mission)}
            )
        except Exception as e:
            logger.error(f"MISSION_COMPLETE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def order_create(request, mission_id):
    """
    ORDER_CREATE_API:
    POST: Adds a new OrderNumber container to the mission.
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
            order_number = data.get("order_number")

            # Check if this order number already exists in this mission
            # Note: The database constraint now enforces global uniqueness,
            # but we keep this check for better API feedback.
            from django.db import IntegrityError

            try:
                order = OrderNumber.objects.create(
                    mission=mission, order_number=order_number
                )
                logger.info(
                    f"ORDER_CREATE: Order #{order.order_number} created under Mission #{mission.id}."
                )
                return JsonResponse(
                    {
                        "status": "success",
                        "order": {
                            "id": order.id,
                            "order_number": order.order_number,
                            "purchase_orders": [],
                        },
                    },
                    status=201,
                )
            except IntegrityError:
                return JsonResponse(
                    {
                        "status": "error",
                        "code": "DUPLICATE",
                        "message": f"Order #{order_number} already exists in the system.",
                    },
                    status=400,
                )
        except Exception as e:
            logger.error(f"ORDER_CREATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def fuel_types_list(request):
    """API endpoint to get list of standardized fuel types with visual hex metadata."""
    if request.method == "GET":
        types = FuelType.objects.all()
        return JsonResponse(
            [
                {
                    "id": t.id,
                    "name": t.name,
                    "color_name": t.color_name,
                    "color_hex": t.color_hex,
                }
                for t in types
            ],
            safe=False,
        )
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def agent_info(request):
    """API endpoint to get tactical agent identity details."""
    if request.method == "GET":
        profile = getattr(request.user, "profile", None)
        return JsonResponse(
            {
                "username": request.user.username,
                "callsign": (
                    profile.callsign
                    if profile and profile.callsign
                    else request.user.username.upper()
                ),
                "is_verified": profile.is_verified_field_agent if profile else False,
                "version": settings.APP_VERSION,
            }
        )
    return JsonResponse({"error": "Method not allowed"}, status=405)
