import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import Mission, PurchaseOrder, OrderNumber

logger = logging.getLogger("webnexus")


@login_required
def po_create(request, order_id):
    """
    PO_CREATE_API:
    POST: Adds a new Purchase Order to the designated OrderNumber container.
    """
    if request.method == "POST":
        order = get_object_or_404(OrderNumber, pk=order_id, mission__user=request.user)
        if order.mission.is_completed:
            return JsonResponse(
                {"status": "error", "message": "Cannot modify a completed mission."},
                status=400,
            )

        try:
            data = json.loads(request.body)
            po_number = int(data.get("po_number"))

            from django.db import IntegrityError

            try:
                po = PurchaseOrder.objects.create(
                    order_parent=order, po_number=po_number
                )
                logger.info(
                    f"PO_CREATE: PO #{po.po_number} created under Order #{order.order_number}."
                )
                return JsonResponse(
                    {
                        "status": "success",
                        "po": {"id": po.id, "po_number": po.po_number, "loads": []},
                    },
                    status=201,
                )
            except IntegrityError:
                return JsonResponse(
                    {
                        "status": "error",
                        "code": "DUPLICATE",
                        "message": f"PO #{po_number} already exists in the system.",
                    },
                    status=400,
                )
        except Exception as e:
            logger.error(f"PO_CREATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def po_detail_update_delete(request, pk):
    """
    PO_DETAIL_API:
    PUT: Updates a PO number.
    DELETE: Removes a PO and all cascaded loads.
    """
    po = get_object_or_404(
        PurchaseOrder, pk=pk, order_parent__mission__user=request.user
    )
    if po.order_parent.mission.is_completed:
        return JsonResponse(
            {"status": "error", "message": "Cannot modify a completed mission."},
            status=400,
        )

    if request.method == "PUT":
        try:
            data = json.loads(request.body)
            old_num = po.po_number
            po.po_number = int(data["po_number"])
            po.save()
            logger.info(
                f"PO_UPDATE: PO ID {po.id} changed from #{old_num} to #{po.po_number}."
            )
            return JsonResponse({"status": "success", "po_number": po.po_number})
        except Exception as e:
            logger.error(f"PO_UPDATE_FAIL: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    elif request.method == "DELETE":
        logger.info(
            f"PO_DELETE: PO #{po.po_number} removed from Order #{po.order_parent.order_number}."
        )
        po.delete()
        return JsonResponse({"status": "success", "message": "Purchase Order deleted."})

    return JsonResponse({"error": "Method not allowed"}, status=405)
