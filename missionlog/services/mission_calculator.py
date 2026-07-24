from decimal import Decimal
from django.db import models

class MissionCalculator:
    """
    Handles derived metric calculations for Mission records.
    Separated from model to reduce coupling and improve testability.
    """
    
    @staticmethod
    def sync_totals(mission) -> None:
        """
        Calculate and assign total_gallons and total_stops from LoadDelivery records.
        
        For Advanced and legacy (NULL) missions, delivery records are the source of truth.
        For Basic missions, this method is not called (user-entered total_gallons is preserved).
        
        Args:
            mission: Mission instance to update (in-memory only, does not save).
        """
        from missionlog.models import LoadDelivery
        
        deliveries = LoadDelivery.objects.filter(
            purchase_order__order_parent__mission=mission
        )
        
        totals = deliveries.aggregate(
            total_gal=models.Sum("gross_gal"),
            total_stops=models.Count("store", distinct=True)
        )
        
        mission.total_gallons = totals["total_gal"] or Decimal("0.00")
        mission.total_stops = totals["total_stops"] or 0
