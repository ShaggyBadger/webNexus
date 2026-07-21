from django.db import models


class TankType(models.Model):
    """
    OPERATIONAL FLOW:
    Defines a specific hardware model of fuel tank (e.g., Highland 10k, Xerxes 12k).
    Contains structural dimensions and link to calibration charts.
    """

    name = models.CharField(max_length=255, null=True, blank=True)
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    model = models.CharField(max_length=255, null=True, blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    max_depth = models.IntegerField(null=True, blank=True)
    misc_info = models.TextField(null=True, blank=True)
    chart_source = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name or f"Tank Type {self.id}"


class TankChart(models.Model):
    """
    OPERATIONAL FLOW:
    High-precision calibration data (The 'Stick Chart').
    Maps physical depth (inches) to volume (gallons) for a specific TankType.
    """

    tank_type = models.ForeignKey(
        TankType,
        on_delete=models.CASCADE,
        related_name="charts",
        null=True,
        blank=True,
    )
    store = models.ForeignKey(
        "tankgauge.Store",
        on_delete=models.CASCADE,
        related_name="custom_charts",
        null=True,
        blank=True,
    )
    tank_index = models.IntegerField(null=True, blank=True)
    is_official = models.BooleanField(
        default=True,
        help_text="True if this is a manufacturer-provided chart. False if generated from telemetry.",
    )

    inches = models.IntegerField()
    gallons = models.IntegerField()
    tank_name = models.CharField(max_length=255)
    misc_info = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f'{self.tank_name} - {self.inches}"'
