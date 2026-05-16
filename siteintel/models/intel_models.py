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
        'siteintel.Location', 
        on_delete=models.CASCADE, 
        related_name='intelligence'
    )
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='field_intelligence'
    )
    notes = models.TextField(help_text="Tactical observations, site quirks, or field intelligence.")
    is_default = models.BooleanField(
        default=False, 
        help_text="If True, this becomes the 'Default' intel for users who have no personal notes."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Intelligence"
        verbose_name_plural = "Site Intelligence Records"
        unique_together = ('location', 'author') # One intel profile per user per site

    def __str__(self):
        status = " [DEFAULT]" if self.is_default else ""
        return f"Intel for {self.location.name} by {self.author.username}{status}"
