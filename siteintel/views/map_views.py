import json
import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction

from ..models import Location, HandDrawnMap

logger = logging.getLogger("webnexus")

class HandDrawnMapEditView(LoginRequiredMixin, DetailView):
    """
    OPERATIONAL FLOW:
    Provides a full-screen Fabric.js canvas for hand-drawing tactical maps.
    Supports basic (finger drawing) and advanced (labels/shapes) modes.
    """
    model = Location
    template_name = "siteintel/hand_map_edit.html"
    context_object_name = "location"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if the user already has a map for this location
        context["existing_map"] = HandDrawnMap.objects.filter(
            location=self.object, author=self.request.user
        ).first()
        return context

@login_required
@require_POST
def hand_drawn_map_save_api(request, location_id):
    """
    API ENDPOINT:
    Saves or updates a hand-drawn map for a specific location.
    Payload: { "fabric_json": "...", "image_data": "..." }
    """
    try:
        data = json.loads(request.body)
        fabric_json = data.get("fabric_json")
        image_data = data.get("image_data")

        if not fabric_json or not image_data:
            return JsonResponse({"status": "error", "message": "Missing map data"}, status=400)

        location = get_object_or_404(Location, id=location_id)

        with transaction.atomic():
            # Update existing map for this user or create a new one
            hand_map, created = HandDrawnMap.objects.get_or_create(
                location=location,
                author=request.user,
                defaults={
                    "fabric_json": fabric_json,
                    "image_data": image_data,
                }
            )

            if not created:
                hand_map.fabric_json = fabric_json
                hand_map.image_data = image_data
                hand_map.save()

            # Logic for default map:
            # If no map is marked as default for this location, make this one the default.
            if not HandDrawnMap.objects.filter(location=location, is_default=True).exists():
                hand_map.is_default = True
                hand_map.save()
                logger.info(f"MAP_DEFAULT_AUTO: Set initial map for Location {location.id} as default.")

        logger.info(f"MAP_SAVE_SUCCESS: Hand-drawn map saved for Location {location.id} by {request.user.username}")
        return JsonResponse({"status": "success", "message": "Map saved successfully"})

    except Exception as e:
        logger.error(f"MAP_SAVE_ERROR: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
