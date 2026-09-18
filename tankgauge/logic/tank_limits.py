import logging
import math

from django.conf import settings

from tankgauge.models import TankEstimation
from .capacity_resolution import CapacityResolutionService

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
    resolver = CapacityResolutionService()
    try:
        capacity_resolution = resolver.resolve_mapping(mapping)
    except TypeError as exc:
        # Older mappings can reach the resolver's official-only fallback before
        # that legacy branch has all profile fields. Keep the limits path usable
        # without bypassing the resolver for the fallback capacity itself.
        logger.warning(
            "TANK_LIMITS_CAPACITY_RESOLUTION_LEGACY_FALLBACK",
            extra={"mapping_id": mapping.id, "reason_code": "legacy_profile_shape"},
        )
        if not mapping.tank_type or not mapping.tank_type.capacity:
            raise exc
        capacity_resolution = resolver.resolve_virtual(
            total_capacity_gallons=mapping.tank_type.capacity,
        )
    estimation = TankEstimation.objects.filter(
        tank_mapping=mapping,
        is_active=True,
    ).first()
    if not estimation or not estimation.radius or not estimation.length:
        if capacity_resolution.usable:
            return {
                "capacity_gallons": int(capacity_resolution.physical_capacity_gallons),
                "max_depth_inches": None,
                "source": "VEEDER",
                "capacity_status": capacity_resolution.status,
                "capacity_warning_codes": list(capacity_resolution.warning_codes),
            }
        return {
            "capacity_gallons": None,
            "max_depth_inches": None,
            "source": "VEEDER",
            "capacity_status": capacity_resolution.status,
            "capacity_warning_codes": list(capacity_resolution.warning_codes),
        }

    radius_inches = float(estimation.radius)
    length_inches = float(estimation.length)
    geometry_implied_capacity = (math.pi * radius_inches**2 * length_inches) / 231.0
    # Until the one-time profile backfill runs, preserve the existing behavior
    # for legacy mappings by using fitted geometry when no explicit profile
    # capacity exists. Once a profile value is present, it is authoritative.
    has_explicit_profile_capacity = mapping.physical_capacity_gallons is not None
    capacity_gallons = (
        int(round(capacity_resolution.physical_capacity_gallons))
        if has_explicit_profile_capacity
        else int(round(geometry_implied_capacity))
    )
    max_depth_inches = radius_inches * 2.0
    return {
        "capacity_gallons": int(round(capacity_gallons)),
        "max_depth_inches": int(round(max_depth_inches)),
        "source": "VEEDER",
        "geometry_implied_capacity_gallons": int(round(geometry_implied_capacity)),
        "capacity_status": capacity_resolution.status,
        "capacity_warning_codes": list(capacity_resolution.warning_codes),
    }


def resolve_tank_limits(mapping) -> dict:
    """
    Resolve max capacity/depth for a mapped tank.

    For stores with accepted Veeder readings, only Veeder-derived limits or
    accepted reading capacity are returned. Otherwise priority is controlled by
    ``TANKGAUGE_DEFAULT_TANK_LIMITS_SOURCE_PRIORITY``:
    - OFFICIAL_FIRST: use TankType values first, fallback to Veeder-derived estimate.
    - VEEDER_FIRST: use Veeder-derived estimate first, fallback to TankType values.
    """
    from .veeder_source_policy import VeederSourcePolicy

    if VeederSourcePolicy.store_has_readings(mapping.store):
        return _veeder_limits(mapping)

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
