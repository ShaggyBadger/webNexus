import ulid
import os
from django.utils import timezone


def generate_ulid():
    """
    Generates a globally unique, lexicographically sortable identifier (ULID).
    Used as the primary key for ATG tickets and readings to ensure data integrity
    and predictable sorting.
    """
    return ulid.ulid()


def veeder_ticket_upload_path(instance, filename):
    """
    TACTICAL STORAGE LOGIC:
    Partitions uploaded Veeder tickets by Year and Store Number to prevent
    directory saturation and simplify administrative auditing.

    Path: media/veeder/{year}/STORE_{store_num}/{ulid}.{ext}
    """
    now = timezone.now()
    year = now.year
    store_num = instance.store.store_num if instance.store else "UNKNOWN"

    # Preserve extension, discard original filename for security/standardization
    ext = filename.split(".")[-1] if "." in filename else "jpg"

    # We use the instance ID (ULID) as the filename
    new_filename = f"{instance.id}.{ext}"

    return os.path.join("veeder", str(year), f"STORE_{store_num}", new_filename)
