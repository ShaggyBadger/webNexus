import json
import logging
import uuid
import random
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import Mission, OrderNumber, PurchaseOrder, LoadDelivery, FuelType, TruckFuelLog
from tankgauge.models.store_models import Store
from .mission_views import serialize_mission

logger = logging.getLogger("webnexus")

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
                    shift_start = timezone.make_aware(shift_start, timezone.get_default_timezone())
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
                
            start_miles = data.get("start_miles")
            total_miles = data.get("total_miles")
            
            if start_miles is not None and str(start_miles).strip() != "":
                start_miles = int(start_miles)
            else:
                start_miles = 0
                
            if total_miles is not None and str(total_miles).strip() != "":
                total_miles = int(total_miles)
                end_miles = start_miles + total_miles
            else:
                total_miles = 0
                end_miles = start_miles
                
            notes = data.get("notes", "")
            deliveries_data = data.get("deliveries", [])
            truck_fuel = data.get("truck_fuel") # Expecting {gallons, price_per_gallon}
            
            # 1. Create Mission
            mission = Mission.objects.create(
                user=request.user,
                shift_start=shift_start,
                shift_end=shift_end,
                start_miles=start_miles,
                end_miles=end_miles,
                hours_on_duty=hours_on_duty,
                is_completed=is_completed,
                notes=notes
            )

            # 2. Handle Truck Fuel (Single Entry for now)
            if truck_fuel:
                gallons = truck_fuel.get("gallons")
                price = truck_fuel.get("price_per_gallon")
                if gallons and price:
                    TruckFuelLog.objects.create(
                        mission=mission,
                        gallons=float(gallons),
                        price_per_gallon=float(price)
                    )
            
            # 3. Create Overarching OrderNumber container with 007-AUTO prefix
            # Only create if there are deliveries to log
            if deliveries_data:
                order_number_str = f"007-AUTO-{uuid.uuid4().hex[:12].upper()}"
                order = OrderNumber.objects.create(
                    mission=mission,
                    order_number=order_number_str
                )
                
                # 4. Create Overarching PurchaseOrder container with 707 prefix
                def generate_unique_po():
                    for _ in range(50):
                        po_number = 707000000 + random.randint(100000, 999999)
                        if not PurchaseOrder.objects.filter(po_number=po_number).exists():
                            return po_number
                    raise Exception("Failed to generate a unique PO number after 50 attempts.")
                    
                po_num = generate_unique_po()
                po = PurchaseOrder.objects.create(
                    order_parent=order,
                    po_number=po_num
                )
                
                # 5. Create LoadDeliveries for each store delivery
                distinct_stores = set()
                for deliv in deliveries_data:
                    store_number_or_riso = deliv.get("store_number_or_riso")
                    if store_number_or_riso is None or str(store_number_or_riso).strip() == "":
                        continue
                    
                    try:
                        s_val = int(store_number_or_riso)
                    except ValueError:
                        continue
                        
                    from django.db.models import Q
                    store = Store.objects.filter(Q(store_num=s_val) | Q(riso_num=s_val)).first()
                    if not store:
                        logger.warning(f"POST_TRIP: Store with number/RISO '{store_number_or_riso}' not found in database. Skipping loads.")
                        continue
                        
                    distinct_stores.add(store.id)
                    fuel_entries = deliv.get("fuel_entries", [])
                    for entry in fuel_entries:
                        fuel_type_id = entry.get("fuel_type_id")
                        gallons = entry.get("gallons")
                        
                        if not fuel_type_id or gallons is None or str(gallons).strip() == "":
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
                            gross_gal=g_val
                        )
                
                # Update distinct store stops count
                mission.total_stops = len(distinct_stores)
                mission.save()
            
            logger.info(f"POST_TRIP_SUCCESS: Mission #{mission.id} ingested successfully. status: {'COMPLETED' if is_completed else 'ACTIVE'}.")
            return JsonResponse({"status": "success", "mission": serialize_mission(mission)}, status=201)
            
        except Exception as e:
            logger.error(f"POST_TRIP_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)


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
                    shift_start = timezone.make_aware(shift_start, timezone.get_default_timezone())
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
                
            start_miles = data.get("start_miles")
            total_miles = data.get("total_miles")
            
            if start_miles is not None and str(start_miles).strip() != "":
                start_miles = int(start_miles)
            else:
                start_miles = 0
                
            if total_miles is not None and str(total_miles).strip() != "":
                total_miles = int(total_miles)
                end_miles = start_miles + total_miles
            else:
                total_miles = 0
                end_miles = start_miles
                
            notes = data.get("notes", "")
            deliveries_data = data.get("deliveries", [])
            truck_fuel = data.get("truck_fuel")
            
            # Update Mission core parameters
            mission.shift_start = shift_start
            mission.shift_end = shift_end
            mission.start_miles = start_miles
            mission.end_miles = end_miles
            mission.hours_on_duty = hours_on_duty
            mission.is_completed = is_completed
            mission.notes = notes
            mission.save()
            
            # Handle Truck Fuel (Single Entry logic: clear and recreate)
            mission.fuel_logs.all().delete()
            if truck_fuel:
                gallons = truck_fuel.get("gallons")
                price = truck_fuel.get("price_per_gallon")
                if gallons and price:
                    TruckFuelLog.objects.create(
                        mission=mission,
                        gallons=float(gallons),
                        price_per_gallon=float(price)
                    )

            # Delete existing related OrderNumber containers to clear children cascadingly
            mission.order_numbers.all().delete()
            
            # Recreate OrderNumber and children only if there are deliveries
            if deliveries_data:
                # Recreate OrderNumber with 007 prefix
                order_number_str = f"007-AUTO-{uuid.uuid4().hex[:12].upper()}"
                order = OrderNumber.objects.create(
                    mission=mission,
                    order_number=order_number_str
                )
                
                # Recreate PO with 707 prefix
                def generate_unique_po():
                    for _ in range(50):
                        po_number = 707000000 + random.randint(100000, 999999)
                        if not PurchaseOrder.objects.filter(po_number=po_number).exists():
                            return po_number
                    raise Exception("Failed to generate a unique PO number after 50 attempts.")
                    
                po_num = generate_unique_po()
                po = PurchaseOrder.objects.create(
                    order_parent=order,
                    po_number=po_num
                )
                
                # Recreate load deliveries
                distinct_stores = set()
                for deliv in deliveries_data:
                    store_number_or_riso = deliv.get("store_number_or_riso")
                    if store_number_or_riso is None or str(store_number_or_riso).strip() == "":
                        continue
                    
                    try:
                        s_val = int(store_number_or_riso)
                    except ValueError:
                        continue
                        
                    from django.db.models import Q
                    store = Store.objects.filter(Q(store_num=s_val) | Q(riso_num=s_val)).first()
                    if not store:
                        continue
                        
                    distinct_stores.add(store.id)
                    fuel_entries = deliv.get("fuel_entries", [])
                    for entry in fuel_entries:
                        fuel_type_id = entry.get("fuel_type_id")
                        gallons = entry.get("gallons")
                        
                        if not fuel_type_id or gallons is None or str(gallons).strip() == "":
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
                            gross_gal=g_val
                        )
                
                mission.total_stops = len(distinct_stores)
                mission.save()
            else:
                mission.total_stops = 0
                mission.save()
            
            logger.info(f"POST_TRIP_UPDATE_SUCCESS: Mission #{mission.id} updated. status: {'COMPLETED' if is_completed else 'ACTIVE'}.")
            return JsonResponse({"status": "success", "mission": serialize_mission(mission)})
            
        except Exception as e:
            logger.error(f"POST_TRIP_UPDATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)
