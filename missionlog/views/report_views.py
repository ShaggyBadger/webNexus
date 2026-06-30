import logging

from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from missionlog.models import Mission
from missionlog.services.report_service import ReportService
from .api_contract import json_success_response

logger = logging.getLogger("webnexus")


@login_required
def report_api(request, mission_id):
    """API endpoint to generate mission reports."""
    try:
        report_data = ReportService.generate(mission_id, user=request.user)
        logger.info(
            "MISSION_REPORT_GENERATED",
            extra={"mission_id": mission_id, "user": request.user.username},
        )
    except Mission.DoesNotExist as exc:
        logger.warning(
            "MISSION_REPORT_NOT_FOUND",
            extra={"mission_id": mission_id, "user": request.user.username},
        )
        raise Http404("Mission not found.") from exc
    return json_success_response(data=report_data)


@login_required
def report_view(request, mission_id):
    """Renders the tactical report template."""
    get_object_or_404(Mission, pk=mission_id, user=request.user)
    logger.info(
        "MISSION_REPORT_VIEW_RENDER",
        extra={"mission_id": mission_id, "user": request.user.username},
    )
    return render(request, "reports/base_tactical.html", {"mission_id": mission_id})
