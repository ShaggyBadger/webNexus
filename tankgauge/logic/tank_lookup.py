from tankgauge.models import Store, StoreTankMapping
from .store_lookup import get_store_by_any_id


def get_store_and_preset_status(store_id):
    """
    Returns (Store object, is_preset_boolean).
    Handles the "7-11_STD" special case by mapping it to Store #6949.
    """
    if store_id == "7-11_STD":
        # Use Store #6949 as the standard for 7-11
        return Store.objects.filter(store_num=6949).first(), True

    return get_store_by_any_id(store_id), False


def get_tank_mapping(store, fuel_type):
    """
    Retrieves the StoreTankMapping for a given store and fuel type.
    """
    if not store or not fuel_type:
        return None

    return (
        StoreTankMapping.objects.filter(store=store, fuel_type=fuel_type.lower())
        .select_related("tank_type")
        .first()
    )
