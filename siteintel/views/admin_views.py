import json
import time
from django.db import connection
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from ..logic import log_parser
from ..models import StoreUpdate, FuelRack
from tankgauge.models import Store


@method_decorator(staff_member_required, name="dispatch")
class TacticalOversightView(TemplateView):
    template_name = "siteintel/admin/oversight.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 1. Fetch raw logs for the terminal
        context["terminal_logs"] = log_parser.get_terminal_logs(200)

        # 2. Parse telemetry for stats and map (Signal Depth: 5000)
        telemetry = log_parser.parse_tactical_telemetry(5000)
        context["heatmap_data"] = json.dumps(telemetry["heatmap"])
        context["active_agents"] = telemetry["agents"]
        context["app_hits"] = telemetry["app_hits"]
        context["error_count"] = len(telemetry["errors"])
        context["recent_errors"] = telemetry["errors"][:10]

        # 3. Latest Intelligence (Proposals)
        context["latest_proposals"] = StoreUpdate.objects.order_by("-submitted_at")[:5]

        # 4. Canonical Site Markers
        stores = Store.objects.exclude(lat__isnull=True).exclude(lon__isnull=True)
        racks = (
            FuelRack.objects.select_related("location")
            .exclude(location__lat__isnull=True)
            .exclude(location__lon__isnull=True)
        )

        site_markers = []
        for s in stores:
            site_markers.append(
                {
                    "type": "STORE",
                    "brand": (s.store_type or "OTHER").upper(),
                    "name": s.store_name or f"STORE #{s.store_num}",
                    "lat": s.lat,
                    "lon": s.lon,
                    "id": s.id,
                }
            )

        for r in racks:
            site_markers.append(
                {
                    "type": "RACK",
                    "brand": "FUEL_RACK",
                    "name": r.location.name,
                    "lat": r.location.lat,
                    "lon": r.location.lon,
                    "id": r.id,
                }
            )

        context["site_markers"] = json.dumps(site_markers)

        context["title"] = "TACTICAL OVERSIGHT CONSOLE"
        return context


@staff_member_required
def tactical_telemetry_api(request):
    """
    AJAX endpoint for real-time dashboard updates.
    """
    lines = int(request.GET.get("lines", 2000))
    telemetry = log_parser.parse_tactical_telemetry(lines)
    raw_logs = log_parser.get_terminal_logs(50)

    # SYSTEM_HEALTH_PULSE
    db_status = "DB_READY"
    latency_ms = 0
    try:
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency_ms = (time.time() - start_time) * 1000
    except Exception:
        db_status = "DB_ERROR"

    # Get latest proposals for the live feed
    proposals = StoreUpdate.objects.order_by("-submitted_at")[:5]
    proposal_data = []
    for p in proposals:
        proposal_data.append(
            {
                "id": p.id,
                "store_name": p.store_name or "NEW SITE",
                "submitted_by": p.submitted_by.username.upper(),
                "time_ago": "Just now",  # Simple for API
            }
        )

    return JsonResponse(
        {
            "heatmap": telemetry["heatmap"],
            "agents": telemetry["agents"],
            "app_hits": telemetry["app_hits"],
            "terminal": raw_logs,
            "error_count": len(telemetry["errors"]),
            "latest_proposals": proposal_data,
            "system_health": {
                "db_status": db_status,
                "latency_ms": f"{latency_ms:.2f}",
            },
        }
    )
