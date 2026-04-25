from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    MAP_CHOICES = [
        ('STANDARD', 'Standard OSM'),
        ('DARK', 'CartoDB Dark Matter'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    callsign = models.CharField(max_length=50, blank=True)
    driver_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    is_verified_field_agent = models.BooleanField(default=False)
    map_preference = models.CharField(max_length=20, choices=MAP_CHOICES, default='STANDARD')

    def __str__(self):
        return f"{self.user.username}'s Profile"
