from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    callsign = models.CharField(max_length=50, blank=True)
    driver_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    is_verified_field_agent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"
