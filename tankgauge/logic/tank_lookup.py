import logging
from tankgauge.models import Store, StoreTankMapping
from .store_lookup import get_store_by_any_id

# Tactical Logger
logger = logging.getLogger('tankgauge')

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


def get_tank_mapping(store, fuel_type):
    """
    TACTICAL INTEL:
    Retrieves the primary hardware mapping (Tank Index and Tank Type) for a specific product.
    """
    if not store or not fuel_type:
        return None

    mapping = (
        StoreTankMapping.objects.filter(store=store, fuel_type=fuel_type.lower())
        .select_related("tank_type")
        .first()
    )
    
    if mapping:
        logger.debug(f"MAPPING_FOUND: Store #{store.store_num} {fuel_type} -> Tank {mapping.tank_index}")
    else:
        logger.info(f"MAPPING_MISSING: No tank defined for Store #{store.store_num} {fuel_type}")
        
    return mapping


def get_all_tank_mappings(store, fuel_type):
    """
    TACTICAL INTEL:
    Retrieves all hardware mappings for a specific product (used for manifolded systems).
    """
    if not store or not fuel_type:
        return []

    mappings = (
        StoreTankMapping.objects.filter(store=store, fuel_type=fuel_type.lower())
        .select_related("tank_type")
        .all()
    )
    
    logger.debug(f"MANIFOLD_SCAN: Found {len(mappings)} tanks for Store #{store.store_num} {fuel_type}")
    return mappings
