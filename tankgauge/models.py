from django.db import models


class Store(models.Model):
    store_num = models.IntegerField(unique=True, null=True, blank=True)
    riso_num = models.IntegerField(unique=True, null=True, blank=True)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    store_type = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(
        max_length=50, null=True, blank=True
    )  # Increased from 2 to 50
    zip_code = models.CharField(
        max_length=10, null=True, blank=True
    )  # Added max_length
    county = models.CharField(max_length=255, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    install_date = models.DateField(null=True, blank=True)
    overfill_protection = models.CharField(max_length=255, null=True, blank=True)

    # Tactical linkage to the site intelligence system
    location = models.OneToOneField(
        'siteintel.Location', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='store_canonical',
        help_text="Canonical link to Site Intelligence"
    )

    def __str__(self):
        return f"{self.store_num} - {self.store_name}"


class TankType(models.Model):
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


class StoreTankMapping(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="tank_mappings"
    )
    tank_type = models.ForeignKey(
        TankType, on_delete=models.CASCADE, related_name="store_mappings"
    )
    fuel_type = models.CharField(max_length=20, null=True, blank=True)
    tank_index = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="The physical tank number (1, 2, 3...) from on-site ATG."
    )

    def __str__(self):
        return f"{self.store} - {self.tank_type} ({self.fuel_type})"


class TankChart(models.Model):
    tank_type = models.ForeignKey(
        TankType, on_delete=models.CASCADE, related_name="charts"
    )
    inches = models.IntegerField()
    gallons = models.IntegerField()
    tank_name = models.CharField(max_length=255)
    misc_info = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.tank_name} - {self.inches}"'
