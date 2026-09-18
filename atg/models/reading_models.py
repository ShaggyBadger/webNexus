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
        help_text="Globally unique ULID.",
    )
    ticket = models.ForeignKey(
        "atg.VeederTicket",
        on_delete=models.CASCADE,
        related_name="readings",
        help_text="Parent ticket evidence.",
    )

    # Mapping Data
    tank_index = models.IntegerField(
        help_text="The physical tank ID from the ATG printout (e.g., TANK 1, 2...)."
    )
    fuel_type = models.ForeignKey(
        "missionlog.FuelType",
        on_delete=models.PROTECT,
        related_name="atg_readings",
        help_text="Standardized product type link.",
    )

    # Core Metrics
    volume = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Gross product volume in gallons (VOL). NET is not stored.",
    )
    ullage = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Remaining empty space in gallons (ULLAGE).",
    )
    height = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        help_text="Physical fuel depth in inches (LEVEL/HEIGHT).",
    )
    printed_physical_capacity_gallons = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Printed Capacity/Tank Max when identified as physical 100% capacity.",
    )
    printed_capacity_text = models.TextField(
        blank=True,
        null=True,
        help_text="Original printed capacity text before normalization.",
    )
    ullage_endpoint_gallons = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Gross plus ullage endpoint in gallons.",
    )
    ullage_endpoint_percent_exact = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Exact endpoint percentage of printed physical capacity.",
    )
    basis_status = models.CharField(
        max_length=20,
        choices=(
            ("UNKNOWN", "Unknown"),
            ("SUGGESTED", "Suggested"),
            ("CONFIRMED", "Confirmed"),
            ("AMBIGUOUS", "Ambiguous"),
            ("CONFLICTING", "Conflicting"),
        ),
        default="UNKNOWN",
    )
    temp = models.FloatField(
        null=True, blank=True, help_text="Product temperature (TEMP)."
    )
    water = models.FloatField(
        null=True, blank=True, help_text="Detected water level in inches."
    )

    # ML & Audit Intelligence
    raw_line_text = models.TextField(
        blank=True,
        null=True,
        help_text="The original OCR extracted string for this specific tank line.",
    )
    confidence_score = models.FloatField(
        default=1.0,
        help_text="OCR confidence rating for this line (1.0 = Manual/Confirmed).",
    )
    is_user_corrected = models.BooleanField(
        default=False,
        help_text="True if a human field agent corrected or verified this entry.",
    )
    acceptance_status = models.CharField(
        max_length=20,
        choices=(
            ("ACCEPTED", "Accepted"),
            ("PENDING_REVIEW", "Pending review"),
            ("REJECTED", "Rejected"),
        ),
        default="ACCEPTED",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_veeder_readings",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Veeder Reading"
        verbose_name_plural = "Veeder Readings"
        ordering = ["ticket", "tank_index"]

    def __str__(self):
        return f"{self.ticket.id} | Tank {self.tank_index} ({self.fuel_type.name})"
