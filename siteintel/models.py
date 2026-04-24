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

    def apply_update(self):
        """
        OPERATIONAL FLOW:
        Transitions proposed field intelligence into the canonical system of record.
        Ensures atomicity across Location, Store, and StoreTankMapping models.
        
        This method is the final 'Commit' of a field agent's verified observations.
        """
        if self.status != 'APPROVED':
            logger.warning(f"SYNC_HALTED: Attempted to apply unapproved StoreUpdate ID {self.id}")
            raise ValueError("Only approved updates can be applied to canonical data.")

        with transaction.atomic():
            # 1. SITE_CLASSIFICATION: Determine the operational role of this site.
            if self.location_type:
                location_type = self.location_type
                logger.info(f"SYNC_STEP: Using proposed LocationType '{location_type.name}' for Update {self.id}")
            else:
                loc_type_name = "Gas Station"
                location_type, created = LocationType.objects.get_or_create(
                    name=loc_type_name,
                    defaults={'description': "Retail fuel site or convenience store."}
                )
                if created:
                    logger.info(f"SYNC_STEP: Created fallback LocationType '{loc_type_name}'")

            # 2. GEOSPATIAL_FOUNDATION: Create or update the parent Location record.
            if not self.location:
                self.location = Location.objects.create(
                    name=self.store_name or f"Store #{self.store_num}",
                    location_type=location_type,
                    address=self.address,
                    city=self.city,
                    state=self.state,
                    zip_code=self.zip_code,
                    lat=self.lat,
                    lon=self.lon
                )
                logger.info(f"SYNC_STEP: Created new canonical Location for Update {self.id}")
            else:
                # Synchronize existing location with verified field data
                self.location.name = self.store_name or self.location.name
                self.location.location_type = location_type
                self.location.address = self.address or self.location.address
                self.location.city = self.city or self.location.city
                self.location.state = self.state or self.location.state
                self.location.zip_code = self.zip_code or self.location.zip_code
                self.location.lat = self.lat or self.location.lat
                self.location.lon = self.lon or self.location.lon
                self.location.save()
                logger.info(f"SYNC_STEP: Updated existing Location ID {self.location.id}")

            # 3. CANONICAL_STORE: Create or update the specialized Store record.
            if not self.store:
                # Check for existing store by physical IDs to prevent digital fragmentation
                existing_store = None
                if self.store_num:
                    existing_store = Store.objects.filter(store_num=self.store_num).first()
                if not existing_store and self.riso_num:
                    existing_store = Store.objects.filter(riso_num=self.riso_num).first()
                
                if existing_store:
                    self.store = existing_store
                    logger.info(f"SYNC_STEP: Linked Update {self.id} to existing Store #{self.store.store_num}")
                else:
                    self.store = Store.objects.create(
                        store_num=self.store_num,
                        riso_num=self.riso_num,
                        store_name=self.store_name,
                        store_type=self.store_type,
                        address=self.address,
                        city=self.city,
                        state=self.state,
                        zip_code=self.zip_code,
                        lat=self.lat,
                        lon=self.lon,
                        location=self.location
                    )
                    logger.info(f"SYNC_STEP: Created new Store record for Update {self.id}")
            else:
                # Update existing store specialized metadata
                self.store.store_num = self.store_num or self.store.store_num
                self.store.riso_num = self.riso_num or self.store.riso_num
                self.store.store_name = self.store_name or self.store.store_name
                self.store.store_type = self.store_type or self.store.store_type
                self.store.address = self.address or self.store.address
                self.store.city = self.city or self.store.city
                self.store.state = self.state or self.store.state
                self.store.zip_code = self.zip_code or self.store.zip_code
                self.store.lat = self.lat or self.store.lat
                self.store.lon = self.lon or self.store.lon
                self.store.location = self.location
                self.store.save()
                logger.info(f"SYNC_STEP: Updated Store specialized metadata for #{self.store.store_num}")

            # 4. TANK_SYNCHRONIZATION: Surgical 'Upsert' of physical tank hardware.
            tank_updates = self.tank_updates.all()
            if tank_updates.exists():
                proposed_indices = []
                
                for tu in tank_updates:
                    mapping, created = StoreTankMapping.objects.update_or_create(
                        store=self.store,
                        tank_index=tu.tank_index,
                        defaults={
                            'tank_type': tu.tank_type,
                            'fuel_type': tu.fuel_type.lower()
                        }
                    )
                    proposed_indices.append(tu.tank_index)
                    status_str = "CREATED" if created else "UPDATED"
                    logger.info(f"SYNC_STEP: {status_str} mapping for Store #{self.store.store_num} Tank {tu.tank_index}")
                
                # MIRRORING DELETIONS: Remove canonical mappings NOT present in the final proposal.
                # This ensures the database mirrors the verified physical layout.
                deleted_count, _ = StoreTankMapping.objects.filter(
                    store=self.store
                ).exclude(tank_index__in=proposed_indices).delete()
                
                if deleted_count:
                    logger.info(f"SYNC_STEP: Purged {deleted_count} stale tank mappings for Store #{self.store.store_num}")
            
            self.save() # Final linkage persistence
            logger.info(f"SYNC_COMPLETE: Successfully applied Update {self.id} to Store {self.store.store_num}")
            logger.info(f"Successfully applied StoreUpdate ID {self.id} to Store {self.store.store_num}")

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
