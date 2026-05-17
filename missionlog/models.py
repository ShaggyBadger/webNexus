from django.db import models
from django.conf import settings

class Mission(models.Model):
    """
    TACTICAL MISSION LOG:
    Tracks daily operational metrics for field agents.
    Includes logistics data like fuel consumption, mileage, and delivery details.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="missions"
    )
    date = models.DateField(auto_now_add=True)
    
    # Logistics Data
    miles_started = models.IntegerField(default=0)
    miles_ended = models.IntegerField(default=0)
    truck_fuel_gallons = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    truck_fuel_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    # Mission Deliverables (Simplified for initial version)
    purchase_orders_json = models.JSONField(default=list, help_text="List of PO numbers for the day")
    stores_visited_json = models.JSONField(default=list, help_text="List of Store IDs visited")
    fuel_delivered_gallons = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "Mission"
        verbose_name_plural = "Missions"

    def __str__(self):
        return f"Mission Log: {self.date} - {self.user.username}"

    @property
    def total_miles(self):
        return self.miles_ended - self.miles_started
