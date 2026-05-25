from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
import os

@login_required
@ensure_csrf_cookie
def spa_index(request):
    """
    SPA_CONTAINER:
    Serves the compiled Vue index.html.
    Ensures a CSRF cookie is set so the SPA can make state-changing requests.
    """
    dist_path = os.path.join(settings.BASE_DIR, "frontend-missionlog", "dist", "index.html")
    
    if os.path.exists(dist_path):
        with open(dist_path, "r") as f:
            return HttpResponse(f.read())
    else:
        # Fallback if the build hasn't happened yet
        return HttpResponse(
            "<h1>MissionLog: Ready for Launch</h1>"
            "<p>The Vue app has not been compiled yet. Run 'npm run dev' or 'npm run build' inside 'frontend-missionlog/'.</p>",
            status=200
        )
