import logging
from datetime import date, timedelta
import pytz
from django.db import transaction
from django.utils import timezone
from siteintel.models import USTPermit, USTVerification

logger = logging.getLogger("webnexus")

def get_store_local_today(store):
    """
    Returns 'today' as a date object in the store's local timezone.
    """
    location = getattr(store, "location", None)
    if location and location.timezone:
        try:
            tz = pytz.timezone(location.timezone)
            return timezone.now().astimezone(tz).date()
        except Exception as e:
            logger.error(f"UST_SERVICE_TZ_ERROR: Failed to get local time for store {store.store_num}: {str(e)}")
    
    # Fallback to UTC if timezone is missing or invalid
    return timezone.now().date()

def calculate_permit_status(permit):
    """
    RUNTIME_LOGIC:
    Calculates the RED/ORANGE/GREEN status for a permit based on its expiration date.
    Strictly follows store-local timezone boundaries.
    """
    if not permit or not permit.is_active:
        return "RED" # No active permit is a warning state
    
    exp_date = permit.expiration_date
    if isinstance(exp_date, str):
        from datetime import date
        exp_date = date.fromisoformat(exp_date)
        
    today = get_store_local_today(permit.store)
    
    if exp_date < today:
        return "RED"
    elif exp_date <= today + timedelta(days=30):
        return "ORANGE"
    else:
        return "GREEN"

def confirm_permit(store, user, notes=None):
    """
    OPERATIONAL_ACTION:
    Records a physical verification that the existing permit is still valid.
    """
    return USTVerification.objects.create(
        store=store,
        user=user,
        verification_type='confirmed',
        notes=notes
    )

@transaction.atomic
def update_permit(store, user, permit_data, notes=None):
    """
    OPERATIONAL_ACTION:
    Atomic operation to update permit details and log the verification event.
    Deactivates old permit and creates a new one to preserve history.
    """
    # 1. Deactivate current active permit(s) for this store
    USTPermit.objects.filter(store=store, is_active=True).update(is_active=False)
    
    # 2. Create new active permit
    new_permit = USTPermit.objects.create(
        store=store,
        is_active=True,
        **permit_data
    )
    
    # 3. Create verification record
    verification = USTVerification.objects.create(
        store=store,
        user=user,
        verification_type='updated',
        notes=notes
    )
    
    logger.info(f"UST_SERVICE: Updated permit for store {store.store_num} by {user.username}")
    return new_permit, verification
