from typing import Any

from tankcharts.models import StoreChartGeneration
from tankcharts.services.cache_service import ChartCacheService
from tankgauge.models import Store


class ChartStatusService:
    """
    Read-only status lookup service for store tank charts.
    Provides cache state and generation history without triggering builds.
    """

    def __init__(self, cache_service: ChartCacheService | None = None) -> None:
        self.cache_service = cache_service or ChartCacheService()

    def get_status(self, store: Store) -> dict[str, Any]:
        """
        Retrieves store chart status and cache details.

        Args:
            store: The Store model instance.

        Returns:
            Dictionary containing cache_state, generation_status, timestamps, and URLs.
        """
        existing_doc = self.cache_service.find_existing_store(store)

        if not existing_doc:
            cache_state = "missing"
        elif self.cache_service.is_store_stale(store, existing_doc):
            cache_state = "stale"
        else:
            cache_state = "fresh"

        gen_record = StoreChartGeneration.objects.filter(store=store).first()

        generation_status = gen_record.status if gen_record else "idle"
        generated_at = gen_record.completed_at if gen_record else None
        failure_reason = gen_record.failure_reason if gen_record else ""
        retry_after = gen_record.retry_after if gen_record else None
        file_size_bytes = existing_doc.file_size if existing_doc else None

        download_url = None
        if existing_doc and cache_state != "missing":
            download_url = self.cache_service.get_store_download_url(store)

        return {
            "cache_state": cache_state,
            "generation_status": generation_status,
            "generated_at": generated_at.isoformat() if generated_at else None,
            "file_size_bytes": file_size_bytes,
            "failure_reason": failure_reason,
            "retry_after": retry_after.isoformat() if retry_after else None,
            "download_url": download_url,
        }
