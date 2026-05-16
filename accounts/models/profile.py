from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    """
    TACTICAL_AGENT_PROFILE:
    Extends the standard Django User model to store operational parameters,
    field identifiers, and UI preferences.
    """
    MAP_CHOICES = [
        ('STANDARD', 'Standard OSM'),
        ('DARK', 'CartoDB Dark Matter'),
    ]

    # Primary Link to Django Auth
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Field Identifiers
    callsign = models.CharField(max_length=50, blank=True, help_text="Tactical field identifier.")
    driver_id = models.CharField(max_length=20, blank=True, null=True, unique=True, help_text="Primary operator ID.")
    
    # Status Indicators
    is_verified_field_agent = models.BooleanField(default=False, help_text="Security clearance level.")
    
    # UI/UX Operational Preferences
    map_preference = models.CharField(
        max_length=20, 
        choices=MAP_CHOICES, 
        default='STANDARD',
        help_text="Preferred tactical mapping layer."
    )

    def __str__(self):
        """Returns the agent's identity record identifier."""
        return f"{self.user.username}'s Profile"
