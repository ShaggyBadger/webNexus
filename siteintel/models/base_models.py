from django.db import models

class LocationType(models.Model):
    """
    OPERATIONAL FLOW:
    Defines the category of a site (e.g., Store, Fuel Rack, Yard).
    Used to drive conditional UI logic and site-specific features.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Primary classification (e.g., Store, Rack, Yard)")
    description = models.TextField(blank=True, null=True, help_text="Details regarding site characteristics")

    class Meta:
        verbose_name = "Location Type"
        verbose_name_plural = "Location Types"

    def __str__(self):
        return self.name

class SiteAttributeDefinition(models.Model):
    """
    OPERATIONAL SCHEMA:
    Defines global metadata keys that should appear for all sites.
    Managed only by administrators to maintain data consistency.
    """
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('boolean', 'Boolean (Yes/No)'),
        ('number', 'Number'),
    ]

    label = models.CharField(max_length=100, help_text="Human-readable label (e.g., 'Vapor Manifold')")
    field_key = models.SlugField(max_length=100, unique=True, help_text="Internal key for JSON storage (e.g., 'vapor_manifold')")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    sort_weight = models.IntegerField(default=100, help_text="Lower values appear first")
    is_required = models.BooleanField(default=False, help_text="If true, this field is mandatory in proposal forms")

    class Meta:
        verbose_name = "Site Attribute Definition"
        verbose_name_plural = "Site Attribute Definitions"
        ordering = ['sort_weight', 'label']

    def __str__(self):
        return f"{self.label} ({self.field_type})"

class Location(models.Model):
    """
    OPERATIONAL FLOW:
    The base physical entity representing any operational site.
    Contains shared geospatial and identification data. 
    Serves as the parent container for specialized site intelligence.
    """
    name = models.CharField(max_length=255, help_text="Common name for the site")
    location_type = models.ForeignKey(
        LocationType, 
        on_delete=models.PROTECT, 
        related_name="locations",
        help_text="Drives site-specific logic"
    )
    
    # Geospatial Data (The digital twin foundation)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    lat = models.FloatField(blank=True, null=True, help_text="High-precision Latitude")
    lon = models.FloatField(blank=True, null=True, help_text="High-precision Longitude")
    
    # Tactical Overlay Data (GeoJSON)
    tactical_overlay = models.TextField(blank=True, null=True, help_text="Canonical tactical drawings (GeoJSON)")
    
    # Hybrid Metadata (JSON Storage)
    # Stores both Global (SiteAttributeDefinition) and Custom field values.
    metadata = models.JSONField(default=dict, blank=True, help_text="Structured site quirks and manifold data")
    
    # Intel & Metadata
    notes = models.TextField(blank=True, null=True, help_text="General field observations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.location_type})"
