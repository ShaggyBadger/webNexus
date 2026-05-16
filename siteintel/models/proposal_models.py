from django.db import models, transaction
from django.contrib.auth.models import User
import logging

# Tactical Logger
logger = logging.getLogger('webnexus')

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
        'siteintel.Location', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="updates"
    )
    store = models.ForeignKey(
        'tankgauge.Store', 
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
        'siteintel.LocationType',
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
        from ..logic import proposal_processor
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
        'tankgauge.TankType', 
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
        'siteintel.Location', 
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
