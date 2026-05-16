import logging
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from ..models import Location, LocationType
from tankgauge.models import Store

# Configure Tactical Logger for Site Intelligence
logger = logging.getLogger('webnexus')

@login_required
def initialize_location_for_store(request, store_id):
    """
    OPERATIONAL_INIT:
    Ensures a Store has a corresponding Location record so intel can be recorded.
    This enables organic growth of the site intelligence database as agents visit sites.
    """
    store = get_object_or_404(Store, id=store_id)
    
    if not store.location:
        logger.info(f"INTEL_BOOTSTRAP: Initializing Location record for Store #{store.store_num}")
        
        # Create a basic location from store data
        gas_station, created = LocationType.objects.get_or_create(
            name="Gas Station",
            defaults={'description': "Retail fuel site or convenience store."}
        )
        if created:
            logger.info("INTEL_BOOTSTRAP: Created new 'Gas Station' LocationType")
        
        loc = Location.objects.create(
            name=store.store_name or f"Store #{store.store_num}",
            location_type=gas_station,
            address=store.address,
            city=store.city,
            state=store.state,
            zip_code=store.zip_code,
            lat=store.lat,
            lon=store.lon
        )
        
        store.location = loc
        store.save()
        logger.info(f"INTEL_INIT_SUCCESS: Store #{store.store_num} linked to Location ID {loc.id} by {request.user}")
    
    return redirect('siteintel:location_detail', pk=store.location.id)
