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
        TankType, on_delete=models.CASCADE, related_name="charts"
    )
    inches = models.IntegerField()
    gallons = models.IntegerField()
    tank_name = models.CharField(max_length=255)
    misc_info = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.tank_name} - {self.inches}"'
