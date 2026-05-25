from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    """
    TACTICAL_AGENT_PROFILE:
    Extends the standard Django User model to store operational parameters,
    field identifiers, and UI preferences.
    """

    MAP_CHOICES = [
        ("STANDARD", "Standard OSM"),
        ("DARK", "CartoDB Dark Matter"),
    ]

    # Primary Link to Django Auth
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Field Identifiers
    callsign = models.CharField(
        max_length=50, blank=True, help_text="Tactical field identifier."
    )
    driver_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text="Primary operator ID.",
    )

    # Status Indicators
    is_verified_field_agent = models.BooleanField(
        default=False, help_text="Security clearance level."
    )

    # UI/UX Operational Preferences
    map_preference = models.CharField(
        max_length=20,
        choices=MAP_CHOICES,
        default="STANDARD",
        help_text="Preferred tactical mapping layer.",
    )

    # MissionLog Settings
    work_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Checked normal workdays (e.g., ['MON', 'TUE']).",
    )
    normal_shift_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Normal shift start time (e.g., 15:00).",
    )
    normal_shift_end = models.TimeField(
        null=True,
        blank=True,
        help_text="Normal shift end time (e.g., 03:00).",
    )
    timezone = models.CharField(
        max_length=100,
        default="America/New_York",
        help_text="Preferred timezone for display.",
    )
    hourly_pay_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Agent hourly pay rate.",
    )

    def __str__(self):
        """Returns the agent's identity record identifier."""
        return f"{self.user.username}'s Profile"
