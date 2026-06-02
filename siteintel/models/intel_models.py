from django.db import models
from django.contrib.auth.models import User


class SiteIntelligence(models.Model):
    """
    OPERATIONAL FLOW:
    A dedicated table for 'notes and stuff' (Field Intelligence).
    Independent of the structural StoreUpdate/TankUpdate models.
    Supports individual user records with a 'Default' fallback mechanism.
    """

    location = models.ForeignKey(
        "siteintel.Location", on_delete=models.CASCADE, related_name="intelligence"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="field_intelligence"
    )
    notes = models.TextField(
        help_text="Tactical observations, site quirks, or field intelligence."
    )
    is_default = models.BooleanField(
        default=False,
        help_text="If True, this becomes the 'Default' intel for users who have no personal notes.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Intelligence"
        verbose_name_plural = "Site Intelligence Records"
        unique_together = ("location", "author")  # One intel profile per user per site

    def __str__(self):
        status = " [DEFAULT]" if self.is_default else ""
        return f"Intel for {self.location.name} by {self.author.username}{status}"


class HandDrawnMap(models.Model):
    """
    OPERATIONAL FLOW:
    A dedicated table for hand-drawn tactical maps using Fabric.js.
    Stores both raw JSON for editing and a Base64 image for quick display.
    """

    location = models.ForeignKey(
        "siteintel.Location", on_delete=models.CASCADE, related_name="hand_drawn_maps"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hand_drawn_maps"
    )
    fabric_json = models.TextField(help_text="Fabric.js canvas data (JSON)")
    image_data = models.TextField(help_text="Base64 encoded PNG image data")
    is_default = models.BooleanField(
        default=False,
        help_text="If True, this is the default map displayed for the location.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hand-Drawn Map"
        verbose_name_plural = "Hand-Drawn Maps"

    def __str__(self):
        status = " [DEFAULT]" if self.is_default else ""
        return f"Map for {self.location.name} by {self.author.username}{status}"
