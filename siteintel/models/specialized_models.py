from django.db import models
from django.contrib.auth.models import User

class Yard(models.Model):
    """
    OPERATIONAL FLOW:
    Represents a specialized yard or depot facility.
    Links to a Location for geospatial data.
    """
    location = models.OneToOneField(
        'siteintel.Location',
        on_delete=models.CASCADE,
        related_name="yard",
        help_text="Geospatial parent for this yard"
    )
    
    notes = models.TextField(blank=True, null=True, help_text="Yard-specific operational details")

    class Meta:
        verbose_name = "Yard"
        verbose_name_plural = "Yards"

    def __str__(self):
        return f"Yard: {self.location.name}"

class FuelRack(models.Model):
    """
    OPERATIONAL FLOW:
    Represents a specialized fuel loading facility.
    Links to a Location for geospatial data and provides structured 
    configuration for lanes and arms.
    """
    location = models.OneToOneField(
        'siteintel.Location',
        on_delete=models.CASCADE,
        related_name="fuel_rack",
        help_text="Geospatial parent for this rack"
    )
    
    # Configuration (JSON)
    # Example: {"lanes": [{"id": 1, "arms": ["Reg", "Prem", "Diesel"]}]}
    config_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured Lane/Arm configuration"
    )
    
    # Expiration Policy
    lockout_days = models.IntegerField(
        default=180,
        help_text="Standard period (days) before access is locked out without check-in"
    )

    class Meta:
        verbose_name = "Fuel Rack"
        verbose_name_plural = "Fuel Racks"

    def __str__(self):
        return f"Rack: {self.location.name}"

class RackCheckIn(models.Model):
    """
    OPERATIONAL FLOW:
    Records a field agent's physical presence at a fuel rack.
    This event 'resets the clock' for the agent's rack access.
    """
    rack = models.ForeignKey(
        FuelRack,
        on_delete=models.CASCADE,
        related_name="check_ins"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rack_check_ins"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Proximity Audit (Captured from client at time of check-in)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True, help_text="GPS accuracy in meters")
    
    is_verified = models.BooleanField(
        default=False, 
        help_text="True if captured within proximity of the rack."
    )

    class Meta:
        verbose_name = "Rack Check-In"
        verbose_name_plural = "Rack Check-Ins"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} @ {self.rack.location.name} ({self.timestamp.date()})"
