import json
import os
from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Mission

@login_required
def mission_api(request):
    """
    MISSION_API:
    Handles GET (listing missions) and POST (creating a mission) for the SPA.
    """
    if request.method == "GET":
        missions = Mission.objects.filter(user=request.user).values()
        return JsonResponse(list(missions), safe=False)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            mission = Mission.objects.create(
                user=request.user,
                miles_started=data.get("miles_started", 0),
                miles_ended=data.get("miles_ended", 0),
                truck_fuel_gallons=data.get("truck_fuel_gallons", 0),
                truck_fuel_price=data.get("truck_fuel_price", 0),
                purchase_orders_json=data.get("purchase_orders", []),
                stores_visited_json=data.get("stores_visited", []),
                fuel_delivered_gallons=data.get("fuel_delivered_gallons", 0),
                notes=data.get("notes", "")
            )
            return JsonResponse({"status": "success", "id": mission.id}, status=201)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
@ensure_csrf_cookie
def spa_index(request):
    """
    SPA_CONTAINER:
    Serves the compiled Vue index.html.
    Ensures a CSRF cookie is set so the SPA can make state-changing requests.
    """
    # In development, you might point this to where Vite builds.
    # In production, this will be in the STATIC_ROOT or similar.
    dist_path = os.path.join(settings.BASE_DIR, "frontend-missionlog", "dist", "index.html")
    
    if os.path.exists(dist_path):
        with open(dist_path, "r") as f:
            return HttpResponse(f.read())
    else:
        # Fallback if the build hasn't happened yet
        return HttpResponse(
            "<h1>MissionLog: Ready for Launch</h1>"
            "<p>The Vue app has not been compiled yet. Run 'npm run build' inside 'frontend-missionlog/'.</p>",
            status=200
        )
