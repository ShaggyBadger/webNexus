import logging

from django.shortcuts import render

logger = logging.getLogger("tankgauge")


def delivery_form(request):
    """Render the TankGauge Alpine single-page workflow."""
    user_label = request.user.username if request.user.is_authenticated else "anonymous"
    logger.info(
        "TANKGAUGE_UI_RENDER",
        extra={
            "reason_code": "tankgauge_spa_entry",
            "user": user_label,
            "path": request.path,
        },
    )
    return render(request, "tankgauge/index.html")
