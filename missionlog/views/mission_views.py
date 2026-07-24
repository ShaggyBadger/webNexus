import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import FuelType, Mission, OrderNumber
from .api_contract import json_error_response, json_success_response

logger = logging.getLogger("webnexus")


def serialize_mission(mission):
    """Helper to perform deep relational serialization of a single Mission log."""
    return {
        "id": mission.id,
        "entry_type": mission.entry_type,
        "total_gallons": (
            float(mission.total_gallons) if mission.total_gallons is not None else None
        ),
        "shift_start": mission.shift_start.isoformat(),
        "shift_end": mission.shift_end.isoformat() if mission.shift_end else None,
        "start_miles": mission.start_miles,
        "end_miles": mission.end_miles,
        "total_miles": mission.total_miles,
        "total_stops": mission.total_stops,
        "hours_on_duty": (
            float(mission.hours_on_duty) if mission.hours_on_duty else None
        ),
        "hours_on_duty_not_driving": (
            float(mission.hours_on_duty_not_driving)
            if mission.hours_on_duty_not_driving
            else None
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
    """GET all missions or POST a new mission."""
    if request.method == "GET":
        missions = Mission.objects.filter(user=request.user).order_by("-shift_start")
        return json_success_response(
            data={"missions": [serialize_mission(mission) for mission in missions]}
        )

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            start_time_str = data.get("shift_start")
            shift_start = (
                timezone.datetime.fromisoformat(start_time_str)
                if start_time_str
                else timezone.now()
            )

            active_shift = (
                Mission.objects.filter(user=request.user, is_completed=False)
                .order_by("-shift_start", "-id")
                .first()
            )

            if active_shift:
                logger.warning(
                    "INIT_WARN: User %s tried to start a new mission, but Mission #%s is already active.",
                    request.user.username,
                    active_shift.id,
                )
                return json_error_response(
                    request=request,
                    code="active_mission_exists",
                    message="An active mission is already in progress. Close it before initiating a new deployment.",
                    details={"mission_id": active_shift.id},
                    status_code=400,
                )

            entry_type = data.get("entry_type", "basic")
            total_gallons = data.get("total_gallons")
            if total_gallons is not None:
                try:
                    total_gallons = Decimal(str(total_gallons))
                except (ValueError, TypeError, InvalidOperation):
                    total_gallons = None

            mission = Mission.objects.create(
                user=request.user,
                shift_start=shift_start,
                start_miles=data.get("start_miles"),
                hours_on_duty_not_driving=data.get("hours_on_duty_not_driving"),
                notes=data.get("notes", ""),
                entry_type=entry_type,
                total_gallons=total_gallons,
            )
            logger.info(
                "MISSION_INIT: Mission #%s initialized by operator %s at %s.",
                mission.id,
                request.user.username,
                shift_start,
            )
            return json_success_response(
                data={"mission": serialize_mission(mission)}, status_code=201
            )
        except Exception as exc:
            logger.error("MISSION_INIT_FAIL: %s", str(exc))
            return json_error_response(
                request=request,
                code="mission_init_failed",
                message="Mission initialization failed.",
                details={"exception": str(exc)},
                status_code=400,
            )

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )


@login_required
def active_mission(request):
    """GET the latest incomplete mission for the user."""
    if request.method == "GET":
        mission = (
            Mission.objects.filter(user=request.user, is_completed=False)
            .order_by("-shift_start", "-id")
            .first()
        )
        if mission:
            return json_success_response(
                data={"active": True, "mission": serialize_mission(mission)}
            )
        return json_success_response(data={"active": False})

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )


@login_required
def mission_detail_or_update(request, pk):
    """GET mission detail, PUT updates, DELETE mission."""
    mission = get_object_or_404(Mission, pk=pk, user=request.user)

    if request.method == "GET":
        return json_success_response(data={"mission": serialize_mission(mission)})

    if request.method == "PUT":
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
            if "hours_on_duty_not_driving" in data:
                mission.hours_on_duty_not_driving = data["hours_on_duty_not_driving"]
            
            if "entry_type" in data:
                existing_entry_type = mission.entry_type
                requested_entry_type = data["entry_type"]
                if existing_entry_type == "basic" and requested_entry_type == "advanced":
                    mission.entry_type = "advanced"
                elif existing_entry_type is None:
                    pass
                else:
                    mission.entry_type = requested_entry_type

            if "total_gallons" in data:
                if mission.entry_type == "basic":
                    val = data["total_gallons"]
                    if val is not None:
                        mission.total_gallons = Decimal(str(val))
                    else:
                        mission.total_gallons = None

            mission.save()

            if mission.entry_type in ["advanced", None]:
                mission.sync_derived_totals(save_after_sync=True)
            logger.info(
                "MISSION_UPDATE: Mission #%s updated by %s.",
                mission.id,
                request.user.username,
            )
            return json_success_response(data={"mission": serialize_mission(mission)})
        except Exception as exc:
            logger.error("MISSION_UPDATE_FAIL: %s", str(exc))
            return json_error_response(
                request=request,
                code="mission_update_failed",
                message="Mission update failed.",
                details={"exception": str(exc)},
                status_code=400,
            )

    if request.method == "DELETE":
        try:
            mission_id = mission.id
            mission.delete()
            logger.info(
                "MISSION_DELETE: Mission #%s aborted/deleted by %s.",
                mission_id,
                request.user.username,
            )
            return json_success_response(
                data={"message": "Mission aborted and deleted."}
            )
        except Exception as exc:
            logger.error("MISSION_DELETE_FAIL: %s", str(exc))
            return json_error_response(
                request=request,
                code="mission_delete_failed",
                message="Mission deletion failed.",
                details={"exception": str(exc)},
                status_code=400,
            )

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )


@login_required
def complete_mission(request, pk):
    """POST finalization of mission log."""
    if request.method == "POST":
        mission = get_object_or_404(Mission, pk=pk, user=request.user)
        try:
            data = json.loads(request.body)

            end_time_str = data.get("shift_end")
            mission.shift_end = (
                timezone.datetime.fromisoformat(end_time_str)
                if end_time_str
                else timezone.now()
            )

            if "end_miles" in data:
                val = data["end_miles"]
                mission.end_miles = int(val) if val is not None else None

            val = data.get("hours_on_duty")
            if val is not None:
                mission.hours_on_duty = float(val)
            else:
                delta = mission.shift_end - mission.shift_start
                mission.hours_on_duty = round(delta.total_seconds() / 3600.0, 2)

            val_not_driving = data.get("hours_on_duty_not_driving")
            if val_not_driving is not None and str(val_not_driving).strip() != "":
                mission.hours_on_duty_not_driving = float(val_not_driving)
            else:
                mission.hours_on_duty_not_driving = None

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

            if mission.entry_type in ["advanced", None]:
                mission.sync_derived_totals(save_after_sync=True)

            logger.info(
                "MISSION_COMPLETE: Mission #%s signed off by operator %s. Odometer end: %s. stops: %s.",
                mission.id,
                request.user.username,
                mission.end_miles,
                mission.total_stops,
            )
            return json_success_response(data={"mission": serialize_mission(mission)})
        except Exception as exc:
            logger.error("MISSION_COMPLETE_FAIL: %s", str(exc))
            return json_error_response(
                request=request,
                code="mission_complete_failed",
                message="Mission completion failed.",
                details={"exception": str(exc)},
                status_code=400,
            )

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )


@login_required
def order_create(request, mission_id):
    """POST create an order number container under mission."""
    if request.method == "POST":
        mission = get_object_or_404(Mission, pk=mission_id, user=request.user)
        if mission.is_completed:
            return json_error_response(
                request=request,
                code="mission_completed",
                message="Cannot modify a completed mission.",
                status_code=400,
            )

        try:
            data = json.loads(request.body)
            order_number = data.get("order_number")

            from django.db import IntegrityError

            try:
                order = OrderNumber.objects.create(
                    mission=mission,
                    order_number=order_number,
                )
                logger.info(
                    "ORDER_CREATE: Order #%s created under Mission #%s.",
                    order.order_number,
                    mission.id,
                )
                return json_success_response(
                    data={
                        "order": {
                            "id": order.id,
                            "order_number": order.order_number,
                            "purchase_orders": [],
                        }
                    },
                    status_code=201,
                )
            except IntegrityError:
                return json_error_response(
                    request=request,
                    code="duplicate_order_number",
                    message=f"Order #{order_number} already exists in the system.",
                    status_code=400,
                )
        except Exception as exc:
            logger.error("ORDER_CREATE_FAIL: %s", str(exc))
            return json_error_response(
                request=request,
                code="order_create_failed",
                message="Order creation failed.",
                details={"exception": str(exc)},
                status_code=400,
            )

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )


@login_required
def fuel_types_list(request):
    """GET list of standardized fuel types with visual hex metadata."""
    if request.method == "GET":
        fuel_types = FuelType.objects.all()
        return json_success_response(
            data={
                "fuel_types": [
                    {
                        "id": fuel_type.id,
                        "name": fuel_type.name,
                        "color_name": fuel_type.color_name,
                        "color_hex": fuel_type.color_hex,
                    }
                    for fuel_type in fuel_types
                ]
            }
        )
    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )


@login_required
def agent_info(request):
    """GET tactical agent identity details."""
    if request.method == "GET":
        profile = getattr(request.user, "profile", None)
        return json_success_response(
            data={
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
    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )
