import logging
from django.core.cache import cache
from tankgauge.models import Store, StoreTankMapping
from .store_lookup import get_store_by_any_id
from .utils import canonicalize_fuel

# Tactical Logger
logger = logging.getLogger("tankgauge")

MAPPING_METRIC_PREFIX = "tankgauge:mapping_resolution"


def _increment_mapping_metric(metric_name):
    metric_key = f"{MAPPING_METRIC_PREFIX}:{metric_name}"
    cache.add(metric_key, 0, timeout=None)
    try:
        cache.incr(metric_key)
    except ValueError:
        cache.set(metric_key, 1, timeout=None)


def get_mapping_resolution_metrics():
    return {
        "strict_match": cache.get(f"{MAPPING_METRIC_PREFIX}:strict_match", 0),
        "fallback_no_exact_index_match": cache.get(
            f"{MAPPING_METRIC_PREFIX}:fallback_no_exact_index_match", 0
        ),
        "fallback_no_index_provided": cache.get(
            f"{MAPPING_METRIC_PREFIX}:fallback_no_index_provided", 0
        ),
    }


def reset_mapping_resolution_metrics():
    cache.delete_many(
        [
            f"{MAPPING_METRIC_PREFIX}:strict_match",
            f"{MAPPING_METRIC_PREFIX}:fallback_no_exact_index_match",
            f"{MAPPING_METRIC_PREFIX}:fallback_no_index_provided",
        ]
    )


def get_store_and_preset_status(store_id):
    """
    OPERATIONAL FLOW:
    Resolves a store identifier into a Store object and determines if it's a 'Preset' scenario.

    SPECIAL_CASE: '7-11_STD'
    Maps to Store #6949, which serves as the canonical baseline for standard 7-Eleven sites.
    """
    if store_id == "7-11_STD":
        logger.info("PRESET_ACQUISITION: Using Store #6949 as 7-11 Standard Preset")
        return Store.objects.filter(store_num=6949).first(), True

    store = get_store_by_any_id(store_id)
    if not store:
        logger.warning(f"LOOKUP_FAILED: No store found for identifier '{store_id}'")

    return store, False


def get_tank_mapping(store, fuel_type, tank_index=None):
    """
    Retrieves the primary hardware mapping (Tank Index and Tank Type) for a specific product.
    Tolerant resolution: tries store + fuel + tank_index first if tank_index is provided.
    Falls back to legacy store + fuel .first() if not found or if tank_index is not provided.
    """
    if not store or not fuel_type:
        return None

    search_fuel = canonicalize_fuel(fuel_type)
    mapping = None

    if tank_index is not None:
        try:
            val = int(tank_index)
            if val >= 1:
                mapping = (
                    StoreTankMapping.objects.filter(
                        store=store, fuel_type=search_fuel, tank_index=val
                    )
                    .select_related("tank_type")
                    .first()
                )
                if mapping:
                    _increment_mapping_metric("strict_match")
                    logger.debug(
                        f"MAPPING_FOUND_STRICT: reason_code=strict_match store={store.store_num} fuel={search_fuel} tank_index={val} mapping_id={mapping.id}"
                    )
                    return mapping
        except (ValueError, TypeError):
            pass

    # Legacy compatibility fallback
    mapping = (
        StoreTankMapping.objects.filter(store=store, fuel_type=search_fuel)
        .select_related("tank_type")
        .first()
    )
    if mapping:
        if tank_index is not None:
            _increment_mapping_metric("fallback_no_exact_index_match")
            logger.warning(
                f"MAPPING_FALLBACK: reason_code=fallback_no_exact_index_match store={store.store_num} fuel={search_fuel} requested_tank_index={tank_index} mapping_id={mapping.id} mapping_tank_index={mapping.tank_index}"
            )
        else:
            _increment_mapping_metric("fallback_no_index_provided")
            logger.debug(
                f"MAPPING_FOUND_LEGACY: reason_code=fallback_no_index_provided store={store.store_num} fuel={search_fuel} mapping_id={mapping.id} mapping_tank_index={mapping.tank_index}"
            )
    else:
        logger.warning(
            f"MAPPING_MISSING: No tank defined for Store #{store.store_num} {fuel_type} (searched for: {search_fuel})"
        )

    return mapping


def get_all_tank_mappings(store, fuel_type):
    """
    TACTICAL INTEL:
    Retrieves all hardware mappings for a specific product (used for manifolded systems).
    """
    if not store or not fuel_type:
        return []

    search_fuel = canonicalize_fuel(fuel_type)
    mappings = (
        StoreTankMapping.objects.filter(store=store, fuel_type=search_fuel)
        .select_related("tank_type")
        .all()
    )

    logger.debug(
        f"MANIFOLD_SCAN: Found {len(mappings)} tanks for Store #{store.store_num} {fuel_type}"
    )
    return mappings
