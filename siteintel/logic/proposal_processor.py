from django.db import transaction
import logging
from tankgauge.models import Store, StoreTankMapping

# Tactical Logger
logger = logging.getLogger('webnexus')

def apply_proposal(proposal):
    """
    OPERATIONAL_SYNC:
    Transitions proposed field intelligence into the canonical system of record.
    Ensures atomicity across Location and specialized child models (Store, FuelRack, Yard).
    
    This function is the critical 'Commit' path for verified field observations.
    """
    from siteintel.models import Location, LocationType, FuelRack, Yard # Local import to avoid circularity

    if proposal.status != 'APPROVED':
        logger.warning(f"SYNC_HALTED: Attempted to apply unapproved Update ID {proposal.id}")
        raise ValueError("Only approved updates can be applied to canonical data.")

    logger.info(f"SYNC_START: Processing Update ID {proposal.id} (Type: {proposal.location_type})")

    with transaction.atomic():
        # 1. SITE_CLASSIFICATION: Determine the operational role of this site.
        location_type = proposal.location_type
        if not location_type:
            loc_type_name = "Gas Station"
            location_type, created = LocationType.objects.get_or_create(
                name=loc_type_name,
                defaults={'description': "Retail fuel site or convenience store."}
            )
            if created:
                logger.info(f"SYNC_CLASSIFICATION: Created fallback LocationType '{loc_type_name}'")

        # 2. GEOSPATIAL_FOUNDATION: Create or update the parent Location record.
        if not proposal.location:
            # BOOTSTRAPPING: Site has no digital twin; create initial Location container.
            proposal.location = Location.objects.create(
                name=proposal.store_name or f"Site_{proposal.store_num or proposal.id}",
                location_type=location_type,
                address=proposal.address,
                city=proposal.city,
                state=proposal.state,
                zip_code=proposal.zip_code,
                lat=proposal.lat,
                lon=proposal.lon,
                metadata=proposal.proposed_metadata
            )
            logger.info(f"SYNC_GEO: Bootstrapped new Location record ID {proposal.location.id}")
        else:
            # SYNCHRONIZATION: Update existing location with verified field data.
            proposal.location.name = proposal.store_name or proposal.location.name
            proposal.location.location_type = location_type
            proposal.location.address = proposal.address or proposal.location.address
            proposal.location.city = proposal.city or proposal.location.city
            proposal.location.state = proposal.state or proposal.location.state
            proposal.location.zip_code = proposal.zip_code or proposal.location.zip_code
            proposal.location.lat = proposal.lat or proposal.location.lat
            proposal.location.lon = proposal.lon or proposal.location.lon
            
            if proposal.proposed_metadata is not None:
                proposal.location.metadata = proposal.proposed_metadata
                logger.info(f"SYNC_METADATA: Synchronized {len(proposal.proposed_metadata)} attributes for Location ID {proposal.location.id}")
            
            proposal.location.save()
            logger.info(f"SYNC_GEO: Updated geospatial foundation for Location ID {proposal.location.id}")

        # 3. SPECIALIZED_RECORD: Route to Store, FuelRack, or Yard based on type.
        type_name = location_type.name.upper()

        if "RACK" in type_name:
            _sync_fuel_rack(proposal)
        elif "YARD" in type_name:
            _sync_yard(proposal)
        else:
            # Default to Store logic for Gas Stations or other types
            _sync_store(proposal)

        proposal.save() # Final linkage persistence
        logger.info(f"SYNC_COMPLETE: Successfully applied Update {proposal.id}")

def _sync_store(proposal):
    """Internal helper to synchronize Store-specific data."""
    if not proposal.store:
        # Check for existing store by physical IDs
        existing_store = None
        if proposal.store_num:
            existing_store = Store.objects.filter(store_num=proposal.store_num).first()
        if not existing_store and proposal.riso_num:
            existing_store = Store.objects.filter(riso_num=proposal.riso_num).first()
        
        if existing_store:
            proposal.store = existing_store
            logger.info(f"SYNC_STEP: Linked Update {proposal.id} to existing Store #{proposal.store.store_num}")
        else:
            proposal.store = Store.objects.create(
                store_num=proposal.store_num,
                riso_num=proposal.riso_num,
                store_name=proposal.store_name,
                store_type=proposal.store_type,
                address=proposal.address,
                city=proposal.city,
                state=proposal.state,
                zip_code=proposal.zip_code,
                lat=proposal.lat,
                lon=proposal.lon,
                location=proposal.location
            )
            logger.info(f"SYNC_STEP: Created new Store record for Update {proposal.id}")
    else:
        # Update existing store specialized metadata
        proposal.store.store_num = proposal.store_num or proposal.store.store_num
        proposal.store.riso_num = proposal.riso_num or proposal.store.riso_num
        proposal.store.store_name = proposal.store_name or proposal.store.store_name
        proposal.store.store_type = proposal.store_type or proposal.store.store_type
        proposal.store.address = proposal.address or proposal.store.address
        proposal.store.city = proposal.city or proposal.store.city
        proposal.store.state = proposal.state or proposal.store.state
        proposal.store.zip_code = proposal.zip_code or proposal.store.zip_code
        proposal.store.lat = proposal.lat or proposal.store.lat
        proposal.store.lon = proposal.lon or proposal.store.lon
        proposal.store.location = proposal.location
        proposal.store.save()
        logger.info(f"SYNC_STEP: Updated Store specialized metadata for #{proposal.store.store_num}")

    # TANK_SYNCHRONIZATION
    tank_updates = proposal.tank_updates.all()
    if tank_updates.exists():
        logger.info(f"SYNC_STEP: Mirroring {tank_updates.count()} tank configurations for Store #{proposal.store.store_num}")
        deleted_count, _ = StoreTankMapping.objects.filter(store=proposal.store).delete()
        if deleted_count:
            logger.info(f"SYNC_STEP: Purged {deleted_count} stale/conflicting mappings.")

        for tu in tank_updates:
            StoreTankMapping.objects.create(
                store=proposal.store,
                tank_index=tu.tank_index,
                tank_type=tu.tank_type,
                fuel_type=tu.fuel_type.lower()
            )

def _sync_fuel_rack(proposal):
    """Internal helper to synchronize Fuel Rack-specific data."""
    from siteintel.models import FuelRack
    
    rack, created = FuelRack.objects.get_or_create(
        location=proposal.location,
        defaults={
            'lockout_days': proposal.rack_lockout_days or 180,
            'config_json': proposal.rack_config_json or {}
        }
    )
    
    if not created:
        if proposal.rack_lockout_days:
            rack.lockout_days = proposal.rack_lockout_days
        if proposal.rack_config_json:
            rack.config_json = proposal.rack_config_json
        rack.save()
        logger.info(f"SYNC_STEP: Updated FuelRack record for Location ID {proposal.location.id}")
    else:
        logger.info(f"SYNC_STEP: Created new FuelRack record for Location ID {proposal.location.id}")

def _sync_yard(proposal):
    """Internal helper to synchronize Yard-specific data."""
    from siteintel.models import Yard
    
    yard, created = Yard.objects.get_or_create(
        location=proposal.location,
        defaults={
            'notes': proposal.yard_notes or ""
        }
    )
    
    if not created:
        if proposal.yard_notes:
            yard.notes = proposal.yard_notes
        yard.save()
        logger.info(f"SYNC_STEP: Updated Yard record for Location ID {proposal.location.id}")
    else:
        logger.info(f"SYNC_STEP: Created new Yard record for Location ID {proposal.location.id}")
