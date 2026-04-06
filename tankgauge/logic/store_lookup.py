from tankgauge.models import Store
from django.db.models import Q


def get_store_by_any_id(identifier):
    """
    Looks up a store by store_num or riso_num.
    The identifier can be a string or an integer.
    """
    if not identifier:
        return None

    # Try to convert to int if it's a string
    try:
        val = int(identifier)
    except (ValueError, TypeError):
        # If it's something like "7-11_STD", it won't be in this Store model
        return None

    return Store.objects.filter(Q(store_num=val) | Q(riso_num=val)).first()
