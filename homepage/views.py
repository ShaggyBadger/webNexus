import logging
from django.shortcuts import render

# Tactical Logger
logger = logging.getLogger('django')

def index(request):
    """
    TACTICAL_COMMAND_CENTER:
    Renders the primary mission dashboard.
    Central hub for accessing site intel and fuel estimation tools.
    """
    logger.debug(f"DASHBOARD_ACCESS: Homepage accessed by {request.user}")
    return render(request, "homepage/index.html")


def about(request):
    """
    MISSION_OVERVIEW:
    Provides context and operational philosophy behind the webNexus system.
    """
    return render(request, "homepage/about.html")


def contact(request):
    """
    COMMS_CHANNEL:
    Operational support and feedback portal.
    """
    return render(request, "homepage/contact.html")
