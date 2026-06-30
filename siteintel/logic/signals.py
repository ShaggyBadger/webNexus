from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from siteintel.models import Location, FuelRack
from .location_utils import get_timezone_from_coords
import logging

logger = logging.getLogger("webnexus")


@receiver(pre_save, sender=Location)
def populate_location_timezone(sender, instance, **kwargs):
    """
    OPERATIONAL SIGNAL:
    Automatically resolves and persists the IANA timezone for a location.
    Required for accurate runtime calculations of UST permit status.
    """
    # Only attempt lookup if coordinates are present
    if instance.lat and instance.lon:
        # Avoid redundant lookups if coordinates haven't changed and timezone is already set
        if instance.pk:
            try:
                old_instance = Location.objects.get(pk=instance.pk)
                if (
                    old_instance.lat == instance.lat
                    and old_instance.lon == instance.lon
                    and instance.timezone
                ):
                    return
            except Location.DoesNotExist:
                pass

        resolved_tz = get_timezone_from_coords(instance.lat, instance.lon)
        if resolved_tz:
            instance.timezone = resolved_tz
            logger.info(
                f"SIGNAL_ACTION: Updated timezone for Site {instance.id or 'NEW'}: {resolved_tz}"
            )


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
    if instance.location_type.name == "Fuel Rack":
        # Check for existing digital twin to prevent duplicate key errors
        if not hasattr(instance, "fuel_rack"):
            try:
                FuelRack.objects.create(location=instance)
                logger.info(
                    f"SIGNAL_ACTION: Initialized new FuelRack tracker for Location ID {instance.id} ({instance.name})"
                )
            except Exception as e:
                logger.error(
                    f"SIGNAL_FAILURE: Failed to initialize FuelRack for Site {instance.id}: {str(e)}"
                )
