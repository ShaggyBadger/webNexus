from django.db import models, transaction
from django.contrib.auth.models import User
from tankgauge.models import TankType, Store, StoreTankMapping
import logging

# Tactical Logger
logger = logging.getLogger('webnexus')

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

class StoreUpdate(models.Model):
    """
    OPERATIONAL FLOW:
    The 'Proposal' container for field-submitted store intelligence.
    Ensures data integrity by requiring administrative approval before
    affecting canonical records in the tankgauge app.
    
    This acts as a 'Draft' or 'Re-index' request from the field.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved & Applied'),
        ('REJECTED', 'Rejected'),
    ]

    # Linkage to Canonical Data (if updating existing records)
    location = models.ForeignKey(
        Location, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="updates"
    )
    store = models.ForeignKey(
        Store, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="proposed_updates"
    )

    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING'
    )

    location_type = models.ForeignKey(
        LocationType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposed_updates"
    )
    
    # Audit Trail (Who and When)
    submitted_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='submitted_updates'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_updates'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Proposed Metadata (Captured from the field form)
    store_num = models.IntegerField(null=True, blank=True, help_text="Physical Store #")
    riso_num = models.IntegerField(null=True, blank=True, help_text="RISO Identifier")
    store_name = models.CharField(max_length=255, null=True, blank=True)
    store_type = models.CharField(max_length=255, null=True, blank=True, help_text="Brand/Type (e.g., 7-Eleven, Speedway)")
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    # Hybrid Metadata Proposal
    proposed_metadata = models.JSONField(default=dict, blank=True, help_text="Proposed changes to site quirks")

    # Specialized Data Proposals
    rack_lockout_days = models.IntegerField(null=True, blank=True, help_text="Proposed lockout period for Fuel Rack")
    rack_config_json = models.JSONField(default=dict, blank=True, help_text="Proposed Lane/Arm configuration for Fuel Rack")
    yard_notes = models.TextField(null=True, blank=True, help_text="Proposed yard-specific operational details")

    def apply_update(self):
        """
        OPERATIONAL_SYNC:
        Transitions proposed field intelligence into the canonical system of record.
        Delegates to siteintel.logic.proposal_processor for specialized handling.
        """
        from .logic import proposal_processor
        proposal_processor.apply_proposal(self)

    def save(self, *args, **kwargs):
        """
        Log status changes for tactical auditing.
        """
        if self.pk:
            old_status = StoreUpdate.objects.get(pk=self.pk).status
            if old_status != self.status:
                logger.info(f"StoreUpdate ID {self.id} status changed from {old_status} to {self.status} by {self.approved_by or 'System'}")
        super().save(*args, **kwargs)

    def __str__(self):
        type_str = "Update" if self.store else "New Entry"
        return f"{type_str} for {self.store_name or 'Unidentified Site'} (Status: {self.status})"

class TankUpdate(models.Model):
    """
    OPERATIONAL FLOW:
    Captures proposed tank configurations for a StoreUpdate.
    Includes the critical Physical Tank Number (Tank Index) to align
    with on-site ATG (Veeder-Root) hardware.
    """
    class FuelType(models.TextChoices):
        REGULAR = 'regular', 'Regular'
        PLUS = 'plus', 'Plus'
        PREMIUM = 'premium', 'Premium'
        DIESEL = 'diesel', 'Diesel'
        KEROSENE = 'kerosene', 'Kerosene'

    store_update = models.ForeignKey(
        StoreUpdate, 
        on_delete=models.CASCADE, 
        related_name='tank_updates'
    )
    
    # Physical hardware indexing (e.g., 1, 2, 3...)
    tank_index = models.IntegerField(
        null=True,
        blank=True,
        help_text="The physical tank number from the ATG printout (1, 2, 3...)."
    )
    
    fuel_type = models.CharField(
        max_length=20, 
        choices=FuelType.choices,
        help_text="Product type (Regular, Diesel, etc.)"
    )
    reported_capacity = models.IntegerField(help_text="Capacity as reported by the field agent.")
    
    # Linked TankType if a match was found in the +/- 10% search
    tank_type = models.ForeignKey(
        TankType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Selected matching chart from database"
    )
    
    # Flag for "Chart Not Found" scenario
    is_unverified = models.BooleanField(
        default=False, 
        help_text="True if no matching chart exists in the database. Requires research."
    )

    def __str__(self):
        return f"Tank {self.tank_index}: {self.fuel_type} ({self.reported_capacity} gal)"

class Yard(models.Model):
    """
    OPERATIONAL FLOW:
    Represents a specialized yard or depot facility.
    Links to a Location for geospatial data.
    """
    location = models.OneToOneField(
        Location,
        on_delete=models.CASCADE,
        related_name="yard",
        help_text="Geospatial parent for this yard"
    )
    
    notes = models.TextField(blank=True, null=True, help_text="Yard-specific operational details")

    class Meta:
        verbose_name = "Yard"
        verbose_name_plural = "Yards"

    def __str__(self):
        return f"Yard: {self.location.name}"

class SiteIntelligence(models.Model):
    """
    OPERATIONAL FLOW:
    A dedicated table for 'notes and stuff' (Field Intelligence).
    Independent of the structural StoreUpdate/TankUpdate models.
    Supports individual user records with a 'Default' fallback mechanism.
    """
    location = models.ForeignKey(
        Location, 
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

class MapOverlayUpdate(models.Model):
    """
    OPERATIONAL FLOW:
    A proposal for tactical map drawings (GeoJSON).
    Requires administrative approval before affecting the canonical Location record.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved & Applied'),
        ('REJECTED', 'Rejected'),
    ]

    location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE, 
        related_name='overlay_updates'
    )
    geojson_data = models.TextField(help_text="Proposed tactical drawings (GeoJSON)")
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING'
    )
    
    submitted_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='submitted_overlays'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_overlays'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def apply_overlay(self):
        """
        Syncs the proposed GeoJSON to the canonical Location record.
        """
        if self.status != 'APPROVED':
            raise ValueError("Only approved overlays can be applied.")
            
        with transaction.atomic():
            self.location.tactical_overlay = self.geojson_data
            self.location.save()
            logger.info(f"OVERLAY_SYNC: Applied GeoJSON for Location {self.location.id}")

    def __str__(self):
        return f"Overlay Proposal for {self.location.name} (Status: {self.status})"

class FuelRack(models.Model):
    """
    OPERATIONAL FLOW:
    Represents a specialized fuel loading facility.
    Links to a Location for geospatial data and provides structured 
    configuration for lanes and arms.
    """
    location = models.OneToOneField(
        Location,
        on_delete=models.CASCADE,
        related_name="fuel_rack",
        help_text="Geospatial parent for this rack"
    )
    
    # Configuration (JSON)
    # Example: {"lanes": [{"id": 1, "arms": ["Reg", "Prem", "Diesel"]}]}
    config_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured Lane/Arm configuration"
    )
    
    # Expiration Policy
    lockout_days = models.IntegerField(
        default=180,
        help_text="Standard period (days) before access is locked out without check-in"
    )

    class Meta:
        verbose_name = "Fuel Rack"
        verbose_name_plural = "Fuel Racks"

    def __str__(self):
        return f"Rack: {self.location.name}"

class RackCheckIn(models.Model):
    """
    OPERATIONAL FLOW:
    Records a field agent's physical presence at a fuel rack.
    This event 'resets the clock' for the agent's rack access.
    """
    rack = models.ForeignKey(
        FuelRack,
        on_delete=models.CASCADE,
        related_name="check_ins"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rack_check_ins"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Proximity Audit (Captured from client at time of check-in)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True, help_text="GPS accuracy in meters")
    
    is_verified = models.BooleanField(
        default=False, 
        help_text="True if captured within proximity of the rack."
    )

    class Meta:
        verbose_name = "Rack Check-In"
        verbose_name_plural = "Rack Check-Ins"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} @ {self.rack.location.name} ({self.timestamp.date()})"
