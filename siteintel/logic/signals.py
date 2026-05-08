from django.db.models.signals import post_save
from django.dispatch import receiver
from siteintel.models import Location, FuelRack
import logging

logger = logging.getLogger('webnexus')

@receiver(post_save, sender=Location)
def ensure_fuel_rack_exists(sender, instance, created, **kwargs):
    """
    OPERATIONAL SIGNAL:
    Automatic digital twin synchronization for Fuel Racks.
    
    This trigger ensures that any physical site classified as a 'Fuel Rack' 
    is automatically initialized in the tracking system. This prevents 
    'orphaned' locations and ensures immediate availability for check-ins.
    
    Trigger: After any 'Location' record is saved.
    Action: Upsert into the specialized FuelRack table.
    """
    if instance.location_type.name == 'Fuel Rack':
        # Check for existing digital twin to prevent duplicate key errors
        if not hasattr(instance, 'fuel_rack'):
            try:
                FuelRack.objects.create(location=instance)
                logger.info(f"SIGNAL_ACTION: Initialized new FuelRack tracker for Location ID {instance.id} ({instance.name})")
            except Exception as e:
                logger.error(f"SIGNAL_FAILURE: Failed to initialize FuelRack for Site {instance.id}: {str(e)}")
