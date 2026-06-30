import logging

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie

logger = logging.getLogger("webnexus")


@login_required
@ensure_csrf_cookie
def spa_index(request):
    """
    MISSIONLOG_SHELL:
    Serves the server-rendered MissionLog shell (Django template + Alpine).
    Ensures a CSRF cookie is set for MissionLog API operations.
    """
    logger.info(
        "MISSIONLOG_SHELL_RENDER",
        extra={"user": request.user.username, "path": request.path},
    )
    from django.shortcuts import render

    return render(request, "missionlog/index.html")
