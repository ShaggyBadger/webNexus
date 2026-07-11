import logging
import math

from django.conf import settings

from tankgauge.models import TankEstimation

logger = logging.getLogger("tankgauge")

SOURCE_OFFICIAL_FIRST = "OFFICIAL_FIRST"
SOURCE_VEEDER_FIRST = "VEEDER_FIRST"
DEFAULT_LIMITS_SOURCE_PRIORITY = SOURCE_OFFICIAL_FIRST
VALID_LIMITS_SOURCE_PRIORITIES = {
    SOURCE_OFFICIAL_FIRST,
    SOURCE_VEEDER_FIRST,
}


def _tank_limits_priority() -> str:
    """Return configured tank limits source priority with safe fallback."""
    configured = getattr(
        settings,
        "TANKGAUGE_DEFAULT_TANK_LIMITS_SOURCE_PRIORITY",
        DEFAULT_LIMITS_SOURCE_PRIORITY,
    )
    if configured in VALID_LIMITS_SOURCE_PRIORITIES:
        return configured

    logger.warning(
        "TANK_LIMITS_PRIORITY_INVALID",
        extra={
            "configured_value": configured,
            "fallback_value": DEFAULT_LIMITS_SOURCE_PRIORITY,
            "reason_code": "invalid_priority_value",
        },
    )
    return DEFAULT_LIMITS_SOURCE_PRIORITY


def _official_limits(mapping) -> dict:
    tank_type = mapping.tank_type
    return {
        "capacity_gallons": tank_type.capacity if tank_type else None,
        "max_depth_inches": tank_type.max_depth if tank_type else None,
        "source": "OFFICIAL",
    }


def _veeder_limits(mapping) -> dict:
    estimation = TankEstimation.objects.filter(
        tank_mapping=mapping,
        is_active=True,
    ).first()
    if not estimation or not estimation.radius or not estimation.length:
        return {
            "capacity_gallons": None,
            "max_depth_inches": None,
            "source": "VEEDER",
        }

    radius_inches = float(estimation.radius)
    length_inches = float(estimation.length)
    capacity_gallons = (math.pi * radius_inches**2 * length_inches) / 231.0
    max_depth_inches = radius_inches * 2.0
    return {
        "capacity_gallons": int(round(capacity_gallons)),
        "max_depth_inches": int(round(max_depth_inches)),
        "source": "VEEDER",
    }


def resolve_tank_limits(mapping) -> dict:
    """
    Resolve max capacity/depth for a mapped tank.

    Priority is controlled by ``TANKGAUGE_DEFAULT_TANK_LIMITS_SOURCE_PRIORITY``:
    - OFFICIAL_FIRST: use TankType values first, fallback to Veeder-derived estimate.
    - VEEDER_FIRST: use Veeder-derived estimate first, fallback to TankType values.
    """
    official = _official_limits(mapping)
    veeder = _veeder_limits(mapping)

    if _tank_limits_priority() == SOURCE_VEEDER_FIRST:
        primary = veeder
        secondary = official
    else:
        primary = official
        secondary = veeder

    capacity_gallons = (
        primary["capacity_gallons"]
        if primary["capacity_gallons"] is not None
        else secondary["capacity_gallons"]
    )
    max_depth_inches = (
        primary["max_depth_inches"]
        if primary["max_depth_inches"] is not None
        else secondary["max_depth_inches"]
    )

    capacity_from_primary = (
        capacity_gallons is not None and capacity_gallons == primary["capacity_gallons"]
    )
    depth_from_primary = (
        max_depth_inches is not None and max_depth_inches == primary["max_depth_inches"]
    )
    capacity_from_secondary = (
        capacity_gallons is not None
        and capacity_gallons == secondary["capacity_gallons"]
    )
    depth_from_secondary = (
        max_depth_inches is not None
        and max_depth_inches == secondary["max_depth_inches"]
    )

    if capacity_gallons is None and max_depth_inches is None:
        selected_source = "UNAVAILABLE"
    elif (capacity_from_primary or capacity_gallons is None) and (
        depth_from_primary or max_depth_inches is None
    ):
        selected_source = primary["source"]
    elif (capacity_from_secondary or capacity_gallons is None) and (
        depth_from_secondary or max_depth_inches is None
    ):
        selected_source = secondary["source"]
    else:
        selected_source = "MIXED"

    return {
        "capacity_gallons": capacity_gallons,
        "max_depth_inches": max_depth_inches,
        "source": selected_source,
    }
