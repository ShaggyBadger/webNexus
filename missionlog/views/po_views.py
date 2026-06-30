import json
import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import Mission, PurchaseOrder, OrderNumber
from .api_contract import json_error_response, json_success_response

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
            return json_error_response(
                request=request,
                code="mission_completed",
                message="Cannot modify a completed mission.",
                status_code=400,
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
                return json_success_response(
                    data={"po": {"id": po.id, "po_number": po.po_number, "loads": []}},
                    status_code=201,
                )
            except IntegrityError:
                return json_error_response(
                    request=request,
                    code="duplicate_po_number",
                    message=f"PO #{po_number} already exists in the system.",
                    status_code=400,
                )
        except Exception as e:
            logger.error(f"PO_CREATE_FAIL: {str(e)}")
            return json_error_response(
                request=request,
                code="po_create_failed",
                message="Purchase order creation failed.",
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
        return json_error_response(
            request=request,
            code="mission_completed",
            message="Cannot modify a completed mission.",
            status_code=400,
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
            return json_success_response(data={"po_number": po.po_number})
        except Exception as e:
            logger.error(f"PO_UPDATE_FAIL: {str(e)}")
            return json_error_response(
                request=request,
                code="po_update_failed",
                message="Purchase order update failed.",
                details={"exception": str(e)},
                status_code=400,
            )

    elif request.method == "DELETE":
        logger.info(
            f"PO_DELETE: PO #{po.po_number} removed from Order #{po.order_parent.order_number}."
        )
        po.delete()
        return json_success_response(data={"message": "Purchase Order deleted."})

    return json_error_response(
        request=request,
        code="method_not_allowed",
        message="Method not allowed.",
        details={"method": request.method},
        status_code=405,
    )
