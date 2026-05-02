import logging
from datetime import datetime, timezone
from siteintel.models import FuelRack, RackCheckIn
from tankgauge.logic.utils import haversine

logger = logging.getLogger('webnexus')

def get_rack_status(user, rack):
    """
    OPERATIONAL FLOW:
    Calculates the lockout status for a specific user and rack.
    Returns remaining days and a status color code.
    """
    last_checkin = RackCheckIn.objects.filter(user=user, rack=rack).order_by('-timestamp').first()
    
    if not last_checkin:
        return {
            'days_remaining': 0,
            'status_code': 'GREY',
            'last_checkin': None,
            'label': 'Expired (No Check-in)'
        }

    delta = datetime.now(timezone.utc) - last_checkin.timestamp
    days_remaining = max(0, rack.lockout_days - delta.days)
    
    if days_remaining > 60:
        status_code = 'GREEN'
    elif days_remaining > 30:
        status_code = 'YELLOW'
    elif days_remaining > 0:
        status_code = 'RED'
    else:
        status_code = 'GREY'

    return {
        'days_remaining': days_remaining,
        'status_code': status_code,
        'last_checkin': last_checkin.timestamp,
        'label': f"{days_remaining} Days Remaining" if days_remaining > 0 else "Expired"
    }

def record_checkin(user, rack, lat=None, lon=None, accuracy=None):
    """
    OPERATIONAL FLOW:
    Records a check-in event. If GPS data is provided, it calculates 
    proximity to set the 'is_verified' flag.
    """
    is_verified = False
    
    if lat is not None and lon is not None:
        # Check proximity to rack location
        if rack.location.lat and rack.location.lon:
            distance_miles = haversine(lat, lon, rack.location.lat, rack.location.lon)
            # 500 meters threshold (~0.31 miles)
            if distance_miles <= 0.31:
                is_verified = True
                logger.info(f"RACK_CHECKIN: Verified proximity for {user.username} @ {rack.location.name}")
            else:
                logger.warning(f"RACK_CHECKIN: Distance check failed ({distance_miles:.2f} miles) for {user.username}")

    checkin = RackCheckIn.objects.create(
        user=user,
        rack=rack,
        lat=lat,
        lon=lon,
        accuracy=accuracy,
        is_verified=is_verified
    )
    
    logger.info(f"RACK_CHECKIN: Recorded {'VERIFIED' if is_verified else 'MANUAL'} check-in for {user.username} @ {rack.location.name}")
    return checkin
