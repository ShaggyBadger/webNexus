import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import PurchaseOrder, LoadDelivery, FuelType
from tankgauge.models.store_models import Store
from ..logic.tank_calculations import calculate_gallons, calculate_inches

logger = logging.getLogger("webnexus")


@login_required
def load_create(request, po_id):
    """
    LOAD_CREATE_API:
    POST: Adds a physical delivery log to the designated PO.
    """
    if request.method == "POST":
        po = get_object_or_404(
            PurchaseOrder, pk=po_id, order_parent__mission__user=request.user
        )
        if po.order_parent.mission.is_completed:
            return JsonResponse(
                {"status": "error", "message": "Cannot modify a completed mission."},
                status=400,
            )

        try:
            data = json.loads(request.body)
            fuel_type = get_object_or_404(FuelType, pk=data["fuel_type_id"])

            store_id = data.get("store_id")
            store = None
            if store_id:
                store = get_object_or_404(Store, pk=store_id)

            load = LoadDelivery.objects.create(
                purchase_order=po,
                fuel_type=fuel_type,
                store=store,
                price_at_store=data.get("price_at_store"),
                gross_gal=data.get("gross_gal"),
                net_gal=data.get("net_gal"),
                temp=data.get("temp"),
                grav=data.get("grav"),
                start_inches=data.get("start_inches"),
                start_gallons=data.get("start_gallons"),
                end_inches=data.get("end_inches"),
                end_gallons=data.get("end_gallons"),
            )

            logger.info(
                f"LOAD_CREATE: Load {fuel_type.name} to Store {store.store_num if store else 'Unlisted'} logged under PO #{po.po_number}."
            )
            return JsonResponse({"status": "success", "load_id": load.id}, status=201)
        except Exception as e:
            logger.error(f"LOAD_CREATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def load_update_delete(request, pk):
    """
    LOAD_DETAIL_API:
    PUT: Modifies precise delivery metrics.
    DELETE: Deletes a load delivery record.
    """
    load = get_object_or_404(
        LoadDelivery, pk=pk, purchase_order__order_parent__mission__user=request.user
    )
    if load.purchase_order.order_parent.mission.is_completed:
        return JsonResponse(
            {"status": "error", "message": "Cannot modify a completed mission."},
            status=400,
        )

    if request.method == "PUT":
        try:
            data = json.loads(request.body)
            if "fuel_type_id" in data:
                load.fuel_type = get_object_or_404(FuelType, pk=data["fuel_type_id"])
            if "store_id" in data:
                store_id = data["store_id"]
                load.store = get_object_or_404(Store, pk=store_id) if store_id else None
            if "price_at_store" in data:
                load.price_at_store = data["price_at_store"]
            if "gross_gal" in data:
                val = data["gross_gal"]
                load.gross_gal = int(val) if val is not None else None
            if "net_gal" in data:
                val = data["net_gal"]
                load.net_gal = int(val) if val is not None else None
            if "temp" in data:
                val = data["temp"]
                load.temp = float(val) if val is not None else None
            if "grav" in data:
                val = data["grav"]
                load.grav = float(val) if val is not None else None
            if "start_inches" in data:
                val = data["start_inches"]
                load.start_inches = float(val) if val is not None else None
            if "start_gallons" in data:
                val = data["start_gallons"]
                load.start_gallons = float(val) if val is not None else None
            if "end_inches" in data:
                val = data["end_inches"]
                load.end_inches = float(val) if val is not None else None
            if "end_gallons" in data:
                val = data["end_gallons"]
                load.end_gallons = float(val) if val is not None else None

            load.save()
            logger.info(f"LOAD_UPDATE: Load ID {load.id} delivery metrics updated.")
            return JsonResponse({"status": "success"})
        except Exception as e:
            logger.error(f"LOAD_UPDATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    elif request.method == "DELETE":
        logger.info(f"LOAD_DELETE: Load ID {load.id} delivery record deleted.")
        load.delete()
        return JsonResponse({"status": "success", "message": "Load deleted."})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def stores_list(request):
    """
    STORES_LIST_API:
    GET: Returns a quick list of all physical retail stores to support reactive autocomplete lookups.
    """
    if request.method == "GET":
        stores = Store.objects.all().order_by("store_num")
        return JsonResponse(
            [
                {
                    "id": s.id,
                    "store_num": s.store_num,
                    "store_name": s.store_name,
                    "address": s.address,
                    "city": s.city,
                }
                for s in stores
            ],
            safe=False,
        )
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def tank_chart_lookup(request):
    """
    TANK_CHART_LOOKUP_API:
    GET: Looks up the exact gallons volume based on store ID, fuel type name,
    and optional inches for start/end, or inches based on gallons.
    """
    if request.method == "GET":
        store_id = request.GET.get("store_id")
        fuel_type = request.GET.get("fuel_type")
        start_inches = request.GET.get("start_inches")
        end_inches = request.GET.get("end_inches")
        end_gallons = request.GET.get("end_gallons")

        if not all([store_id, fuel_type]):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Parameters 'store_id' and 'fuel_type' are required.",
                },
                status=400,
            )

        try:
            results = {"status": "success"}
            if start_inches:
                results["start_gallons"] = calculate_gallons(
                    store_id, fuel_type, start_inches
                )
            if end_inches:
                results["end_gallons"] = calculate_gallons(
                    store_id, fuel_type, end_inches
                )
            if end_gallons:
                results["end_inches"] = calculate_inches(
                    store_id, fuel_type, end_gallons
                )

            return JsonResponse(results)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)
