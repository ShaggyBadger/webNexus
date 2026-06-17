from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from missionlog.models import Mission
from missionlog.services.report_service import ReportService


@login_required
def report_api(request, mission_id):
    """API endpoint to generate mission reports."""
    try:
        report_data = ReportService.generate(mission_id, user=request.user)
    except Mission.DoesNotExist as exc:
        raise Http404("Mission not found.") from exc
    return JsonResponse(report_data)


@login_required
def report_view(request, mission_id):
    """Renders the tactical report template."""
    get_object_or_404(Mission, pk=mission_id, user=request.user)
    return render(request, "reports/base_tactical.html", {"mission_id": mission_id})
