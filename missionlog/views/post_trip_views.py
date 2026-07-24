import json
import logging
import uuid
import random
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import (
    Mission,
    OrderNumber,
    PurchaseOrder,
    LoadDelivery,
    FuelType,
    TruckFuelLog,
)
from tankgauge.models.store_models import Store
from .mission_views import serialize_mission
from .api_contract import json_error_response, json_success_response

logger = logging.getLogger("webnexus")


def _parse_optional_int(value):
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _parse_optional_decimal(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _resolve_mileage_bounds(data):
    start_miles = _parse_optional_int(data.get("start_miles"))
    end_miles = _parse_optional_int(data.get("end_miles"))
    total_miles = _parse_optional_int(data.get("total_miles"))

    if start_miles is not None and total_miles is not None:
        end_miles = start_miles + total_miles

    return start_miles, end_miles


@login_required
@transaction.atomic
def post_trip_create(request):
    """
    POST_TRIP_CREATE_API:
    POST: Processes the entire post-trip monolithic log in a single transaction.
    Supports initializing active missions and partial progress saves.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            shift_start_str = data.get("shift_start")
            if shift_start_str:
                # Support ISO strings like 2026-05-29T12:00
                shift_start = timezone.datetime.fromisoformat(shift_start_str)
                # Assign default timezone if naive
                if timezone.is_naive(shift_start):
                    shift_start = timezone.make_aware(
                        shift_start, timezone.get_default_timezone()
                    )
            else:
                shift_start = timezone.now()

            # Operational Status: default to True (completed) for legacy post-trip,
            # but frontend can pass False for active shift initialization.
            is_completed = data.get("is_completed", True)

            hours_on_duty = data.get("hours_on_duty")
            if hours_on_duty is not None and str(hours_on_duty).strip() != "":
                hours_on_duty = float(hours_on_duty)
                shift_end = shift_start + timezone.timedelta(hours=hours_on_duty)
            else:
                hours_on_duty = None
                shift_end = None

            hours_on_duty_not_driving_raw = data.get("hours_on_duty_not_driving")
            if (
                hours_on_duty_not_driving_raw is not None
                and str(hours_on_duty_not_driving_raw).strip() != ""
            ):
                hours_on_duty_not_driving = float(hours_on_duty_not_driving_raw)
            else:
                hours_on_duty_not_driving = None

            entry_type = data.get("entry_type")
            if entry_type is None:
                entry_type = "basic"

            if entry_type not in ["basic", "advanced"]:
                return json_error_response(
                    request=request,
                    code="INVALID_ENTRY_TYPE",
                    message="Invalid entry type.",
                    details={"entry_type": "Must be 'basic' or 'advanced'."},
                    status_code=400,
                )

            total_gallons = None
            if entry_type == "basic":
                # Validate total_gallons
                total_gallons_raw = data.get("total_gallons")
                if total_gallons_raw is None or str(total_gallons_raw).strip() == "":
                    return json_error_response(
                        request=request,
                        code="INVALID_BASIC_SUBMISSION",
                        message="total_gallons is required when entry_type is 'basic'",
                        details={"field_errors": {"total_gallons": ["This field may not be null or negative in basic mode."]}},
                        status_code=400,
                    )
                try:
                    total_gallons = Decimal(str(total_gallons_raw))
                    if total_gallons < 0:
                        raise ValueError()
                except (ValueError, TypeError, InvalidOperation):
                    return json_error_response(
                        request=request,
                        code="INVALID_BASIC_SUBMISSION",
                        message="total_gallons is required when entry_type is 'basic'",
                        details={"field_errors": {"total_gallons": ["This field may not be null or negative in basic mode."]}},
                        status_code=400,
                    )

                # Validate hours_on_duty_not_driving
                if hours_on_duty_not_driving is None or hours_on_duty_not_driving < 0:
                    return json_error_response(
                        request=request,
                        code="INVALID_BASIC_SUBMISSION",
                        message="hours_on_duty_not_driving is required when entry_type is 'basic'",
                        details={"field_errors": {"hours_on_duty_not_driving": ["This field may not be null or negative in basic mode."]}},
                        status_code=400,
                    )

            start_miles, end_miles = _resolve_mileage_bounds(data)

            notes = data.get("notes", "")
            deliveries_data = data.get("deliveries", [])
            truck_fuel = data.get("truck_fuel")  # Expecting {gallons, price_per_gallon}

            # SAFEGUARD: Check if an active mission already exists to prevent
            # duplication when this is a partial save. No time-window cutoff is
            # used so operators can resume work after multiple days.
            if not is_completed:
                existing_active = (
                    Mission.objects.filter(
                        user=request.user,
                        is_completed=False,
                    )
                    .order_by("-shift_start", "-id")
                    .first()
                )
                if existing_active:
                    logger.info(
                        f"POST_TRIP_SAFEGUARD: Redirecting partial save to existing Active Mission #{existing_active.id}"
                    )
                    # Reuse update logic by manually calling post_trip_update (conceptually)
                    # For simplicity here, we'll just return a message asking to update or we can handle it.
                    # Actually, better to redirect the frontend or just handle it here.
                    # Let's let the frontend handle the ID resolution, but this check ensures DB integrity.
                    return json_error_response(
                        request=request,
                        code="active_mission_exists",
                        message="An active mission already exists. Your session will refresh to sync with it.",
                        details={"mission_id": existing_active.id},
                        status_code=409,
                    )

            # 1. Create Mission
            mission = Mission.objects.create(
                user=request.user,
                shift_start=shift_start,
                shift_end=shift_end,
                start_miles=start_miles,
                end_miles=end_miles,
                hours_on_duty=hours_on_duty,
                hours_on_duty_not_driving=hours_on_duty_not_driving,
                is_completed=is_completed,
                notes=notes,
                entry_type=entry_type,
                total_gallons=total_gallons,
            )

            # 2. Handle Truck Fuel (Single Entry for now)
            if truck_fuel:
                gallons = _parse_optional_decimal(truck_fuel.get("gallons"))
                price = _parse_optional_decimal(truck_fuel.get("price_per_gallon"))
                if gallons is not None and price is not None:
                    TruckFuelLog.objects.create(
                        mission=mission,
                        gallons=gallons,
                        price_per_gallon=price,
                    )

            # 3. Create Overarching OrderNumber container with 007-AUTO prefix
            # Only create if there are deliveries to log
            if deliveries_data:
                order_number_str = f"007-AUTO-{uuid.uuid4().hex[:12].upper()}"
                order = OrderNumber.objects.create(
                    mission=mission, order_number=order_number_str
                )

                # 4. Create Overarching PurchaseOrder container with 707 prefix
                def generate_unique_po():
                    for _ in range(50):
                        po_number = 707000000 + random.randint(100000, 999999)
                        if not PurchaseOrder.objects.filter(
                            po_number=po_number
                        ).exists():
                            return po_number
                    raise Exception(
                        "Failed to generate a unique PO number after 50 attempts."
                    )

                po_num = generate_unique_po()
                po = PurchaseOrder.objects.create(order_parent=order, po_number=po_num)

                # 5. Create LoadDeliveries for each store delivery
                distinct_stores = set()
                for deliv in deliveries_data:
                    store_number_or_riso = deliv.get("store_number_or_riso")
                    if (
                        store_number_or_riso is None
                        or str(store_number_or_riso).strip() == ""
                    ):
                        continue

                    try:
                        s_val = int(store_number_or_riso)
                    except ValueError:
                        continue

                    from django.db.models import Q

                    store = Store.objects.filter(
                        Q(store_num=s_val) | Q(riso_num=s_val)
                    ).first()
                    if not store:
                        logger.warning(
                            f"POST_TRIP: Store with number/RISO '{store_number_or_riso}' not found in database. Skipping loads."
                        )
                        continue

                    distinct_stores.add(store.id)
                    fuel_entries = deliv.get("fuel_entries", [])
                    for entry in fuel_entries:
                        fuel_type_id = entry.get("fuel_type_id")
                        gallons = entry.get("gallons")

                        if (
                            not fuel_type_id
                            or gallons is None
                            or str(gallons).strip() == ""
                        ):
                            continue

                        fuel_type = FuelType.objects.filter(pk=fuel_type_id).first()
                        if not fuel_type:
                            continue

                        try:
                            g_val = int(gallons)
                        except ValueError:
                            g_val = 0

                        LoadDelivery.objects.create(
                            purchase_order=po,
                            fuel_type=fuel_type,
                            store=store,
                            gross_gal=g_val,
                        )

                # Update distinct store stops count
                mission.total_stops = len(distinct_stores)
                mission.save()

            if mission.entry_type == "advanced":
                mission.sync_derived_totals(save_after_sync=True)

            logger.info(
                f"POST_TRIP_SUCCESS: Mission #{mission.id} ingested successfully. status: {'COMPLETED' if is_completed else 'ACTIVE'}."
            )
            return json_success_response(
                data={"mission": serialize_mission(mission)},
                status_code=201,
            )

        except Exception as e:
            logger.error(f"POST_TRIP_FAIL: {str(e)}")
            return json_error_response(
                request=request,
                code="post_trip_create_failed",
                message="Post-trip creation failed.",
                details={"exception": str(e)},
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
@transaction.atomic
def post_trip_update(request, pk):
    """
    POST_TRIP_UPDATE_API:
    PUT: Updates an existing post-trip mission log. Rebuilds related Order, PO, and Loads.
    Supports partial progress saves and completion toggling.
    """
    if request.method == "PUT":
        mission = get_object_or_404(Mission, pk=pk, user=request.user)
        try:
            data = json.loads(request.body)

            shift_start_str = data.get("shift_start")
            if shift_start_str:
                shift_start = timezone.datetime.fromisoformat(shift_start_str)
                if timezone.is_naive(shift_start):
                    shift_start = timezone.make_aware(
                        shift_start, timezone.get_default_timezone()
                    )
            else:
                shift_start = mission.shift_start

            is_completed = data.get("is_completed", mission.is_completed)

            hours_on_duty = data.get("hours_on_duty")
            if hours_on_duty is not None and str(hours_on_duty).strip() != "":
                hours_on_duty = float(hours_on_duty)
                shift_end = shift_start + timezone.timedelta(hours=hours_on_duty)
            else:
                hours_on_duty = None
                shift_end = None

            hours_on_duty_not_driving_raw = data.get("hours_on_duty_not_driving")
            if (
                hours_on_duty_not_driving_raw is not None
                and str(hours_on_duty_not_driving_raw).strip() != ""
            ):
                hours_on_duty_not_driving = float(hours_on_duty_not_driving_raw)
            else:
                hours_on_duty_not_driving = None

            existing_entry_type = mission.entry_type
            requested_entry_type = data.get("entry_type")
            if requested_entry_type is None:
                if existing_entry_type == "advanced":
                    requested_entry_type = "advanced"
                elif existing_entry_type is None:
                    requested_entry_type = None
                else:
                    requested_entry_type = "basic"

            if requested_entry_type not in ["basic", "advanced", None]:
                return json_error_response(
                    request=request,
                    code="INVALID_ENTRY_TYPE",
                    message="Invalid entry type.",
                    details={"entry_type": "Must be 'basic' or 'advanced'."},
                    status_code=400,
                )

            # Prevent Advanced/Legacy -> Basic downgrade
            if existing_entry_type in ["advanced", None] and requested_entry_type == "basic":
                return json_error_response(
                    request=request,
                    code="ILLEGAL_DOWNGRADE",
                    message="Cannot downgrade an advanced or legacy mission to basic mode.",
                    details={"entry_type": "Reverting to basic would orphan existing delivery records."},
                    status_code=400,
                )

            total_gallons = None
            if requested_entry_type == "basic":
                # Validate total_gallons
                total_gallons_raw = data.get("total_gallons")
                if total_gallons_raw is None or str(total_gallons_raw).strip() == "":
                    return json_error_response(
                        request=request,
                        code="INVALID_BASIC_SUBMISSION",
                        message="total_gallons is required when entry_type is 'basic'",
                        details={"field_errors": {"total_gallons": ["This field may not be null or negative in basic mode."]}},
                        status_code=400,
                    )
                try:
                    total_gallons = Decimal(str(total_gallons_raw))
                    if total_gallons < 0:
                        raise ValueError()
                except (ValueError, TypeError, InvalidOperation):
                    return json_error_response(
                        request=request,
                        code="INVALID_BASIC_SUBMISSION",
                        message="total_gallons is required when entry_type is 'basic'",
                        details={"field_errors": {"total_gallons": ["This field may not be null or negative in basic mode."]}},
                        status_code=400,
                    )

                # Validate hours_on_duty_not_driving
                if hours_on_duty_not_driving is None or hours_on_duty_not_driving < 0:
                    return json_error_response(
                        request=request,
                        code="INVALID_BASIC_SUBMISSION",
                        message="hours_on_duty_not_driving is required when entry_type is 'basic'",
                        details={"field_errors": {"hours_on_duty_not_driving": ["This field may not be null or negative in basic mode."]}},
                        status_code=400,
                    )

            start_miles, end_miles = _resolve_mileage_bounds(data)

            notes = data.get("notes", "")
            deliveries_data = data.get("deliveries", [])
            truck_fuel = data.get("truck_fuel")

            # Force empty deliveries in basic mode
            if requested_entry_type == "basic":
                deliveries_data = []

            # Update Mission core parameters
            mission.shift_start = shift_start
            mission.shift_end = shift_end
            mission.start_miles = start_miles
            mission.end_miles = end_miles
            mission.hours_on_duty = hours_on_duty
            mission.hours_on_duty_not_driving = hours_on_duty_not_driving
            mission.is_completed = is_completed
            mission.notes = notes

            # Handle entry_type upgrade and value assignment
            if existing_entry_type == "basic" and requested_entry_type == "advanced":
                mission.entry_type = "advanced"
            elif existing_entry_type is None:
                pass
            else:
                mission.entry_type = requested_entry_type

            if mission.entry_type == "basic":
                mission.total_gallons = total_gallons

            mission.save()

            # Handle Truck Fuel (Single Entry logic: clear and recreate)
            mission.fuel_logs.all().delete()
            if truck_fuel:
                gallons = _parse_optional_decimal(truck_fuel.get("gallons"))
                price = _parse_optional_decimal(truck_fuel.get("price_per_gallon"))
                if gallons is not None and price is not None:
                    TruckFuelLog.objects.create(
                        mission=mission,
                        gallons=gallons,
                        price_per_gallon=price,
                    )

            # Delete existing related OrderNumber containers to clear children cascadingly
            mission.order_numbers.all().delete()

            # Recreate OrderNumber and children only if there are deliveries
            if deliveries_data:
                # Recreate OrderNumber with 007 prefix
                order_number_str = f"007-AUTO-{uuid.uuid4().hex[:12].upper()}"
                order = OrderNumber.objects.create(
                    mission=mission, order_number=order_number_str
                )

                # Recreate PO with 707 prefix
                def generate_unique_po():
                    for _ in range(50):
                        po_number = 707000000 + random.randint(100000, 999999)
                        if not PurchaseOrder.objects.filter(
                            po_number=po_number
                        ).exists():
                            return po_number
                    raise Exception(
                        "Failed to generate a unique PO number after 50 attempts."
                    )

                po_num = generate_unique_po()
                po = PurchaseOrder.objects.create(order_parent=order, po_number=po_num)

                # Recreate load deliveries
                distinct_stores = set()
                for deliv in deliveries_data:
                    store_number_or_riso = deliv.get("store_number_or_riso")
                    if (
                        store_number_or_riso is None
                        or str(store_number_or_riso).strip() == ""
                    ):
                        continue

                    try:
                        s_val = int(store_number_or_riso)
                    except ValueError:
                        continue

                    from django.db.models import Q

                    store = Store.objects.filter(
                        Q(store_num=s_val) | Q(riso_num=s_val)
                    ).first()
                    if not store:
                        continue

                    distinct_stores.add(store.id)
                    fuel_entries = deliv.get("fuel_entries", [])
                    for entry in fuel_entries:
                        fuel_type_id = entry.get("fuel_type_id")
                        gallons = entry.get("gallons")

                        if (
                            not fuel_type_id
                            or gallons is None
                            or str(gallons).strip() == ""
                        ):
                            continue

                        fuel_type = FuelType.objects.filter(pk=fuel_type_id).first()
                        if not fuel_type:
                            continue

                        try:
                            g_val = int(gallons)
                        except ValueError:
                            g_val = 0

                        LoadDelivery.objects.create(
                            purchase_order=po,
                            fuel_type=fuel_type,
                            store=store,
                            gross_gal=g_val,
                        )

                mission.total_stops = len(distinct_stores)
                mission.save()
            else:
                mission.total_stops = 0
                mission.save()

            if mission.entry_type in ["advanced", None]:
                mission.sync_derived_totals(save_after_sync=True)

            logger.info(
                f"POST_TRIP_UPDATE_SUCCESS: Mission #{mission.id} updated. status: {'COMPLETED' if is_completed else 'ACTIVE'}."
            )
            return json_success_response(data={"mission": serialize_mission(mission)})

        except Exception as e:
            logger.error(f"POST_TRIP_UPDATE_FAIL: {str(e)}")
            return json_error_response(
                request=request,
                code="post_trip_update_failed",
                message="Post-trip update failed.",
                details={"exception": str(e)},
                status_code=400,
            )

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )
