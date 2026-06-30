import logging
from timezonefinder import TimezoneFinder

logger = logging.getLogger("webnexus")
tf = TimezoneFinder()


def get_timezone_from_coords(lat, lon):
    """
    OPERATIONAL_UTILS:
    Determines the IANA timezone string for a given set of GPS coordinates.
    Used to ensure local-time accuracy for operational calculations (e.g., UST permit expiration).
    """
    if lat is None or lon is None:
        return None

    try:
        timezone_str = tf.timezone_at(lng=lon, lat=lat)
        if timezone_str:
            logger.info(f"GEO_TZ: Resolved {timezone_str} for coords ({lat}, {lon})")
        else:
            logger.warning(
                f"GEO_TZ: Could not resolve timezone for coords ({lat}, {lon})"
            )
        return timezone_str
    except Exception as e:
        logger.error(f"GEO_TZ_ERROR: Failed to resolve timezone: {str(e)}")
        return None
