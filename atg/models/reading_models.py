from django.db import models
from atg.utils.storage import generate_ulid

class VeederReading(models.Model):
    """
    DATA ACQUISITION:
    Represents ONE tank on ONE ticket.
    This is the core dataset for future Machine Learning and analysis.
    """
    id = models.CharField(
        primary_key=True,
        max_length=26,
        default=generate_ulid,
        editable=False,
        help_text="Globally unique ULID."
    )
    ticket = models.ForeignKey(
        'atg.VeederTicket',
        on_delete=models.CASCADE,
        related_name="readings",
        help_text="Parent ticket evidence."
    )
    
    # Mapping Data
    tank_index = models.IntegerField(
        help_text="The physical tank ID from the ATG printout (e.g., TANK 1, 2...)."
    )
    fuel_type = models.ForeignKey(
        'missionlog.FuelType',
        on_delete=models.PROTECT,
        related_name="atg_readings",
        help_text="Standardized product type link."
    )
    
    # Core Metrics
    volume = models.IntegerField(help_text="Current gallons (VOL).")
    ullage = models.IntegerField(help_text="Remaining empty space (ULLAGE).")
    height = models.FloatField(help_text="Physical fuel depth in inches (HEIGHT).")
    temp = models.FloatField(
        null=True,
        blank=True,
        help_text="Product temperature (TEMP)."
    )
    water = models.FloatField(
        null=True,
        blank=True,
        help_text="Detected water level in inches."
    )
    
    # ML & Audit Intelligence
    raw_line_text = models.TextField(
        blank=True,
        null=True,
        help_text="The original OCR extracted string for this specific tank line."
    )
    confidence_score = models.FloatField(
        default=1.0,
        help_text="OCR confidence rating for this line (1.0 = Manual/Confirmed)."
    )
    is_user_corrected = models.BooleanField(
        default=False,
        help_text="True if a human field agent corrected or verified this entry."
    )

    class Meta:
        verbose_name = "Veeder Reading"
        verbose_name_plural = "Veeder Readings"
        ordering = ['ticket', 'tank_index']

    def __str__(self):
        return f"{self.ticket.id} | Tank {self.tank_index} ({self.fuel_type.name})"
