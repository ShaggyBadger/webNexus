from dms.models import Document
from tankcharts.services.dms_storage_service import DMSChartStorageService
from tankgauge.models import Store


class ChartCacheService:
    """
    Thin wrapper around DMSChartStorageService for cache operations.
    Insolates higher-level services from direct DMS storage details.
    """

    def __init__(self) -> None:
        self.dms_service = DMSChartStorageService()

    def find_existing_store(self, store: Store) -> Document | None:
        """Find active store chart document in DMS."""
        return self.dms_service.find_existing_store(store_num=store.store_num)

    def is_store_stale(self, store: Store, document: Document) -> bool:
        """Check if store chart document is stale compared to latest store data."""
        return self.dms_service.is_store_stale(
            document=document,
            store_num=store.store_num,
        )

    def store_store_chart(
        self, store: Store, pdf_bytes: bytes, metadata: dict
    ) -> Document:
        """Store new store chart PDF document in DMS."""
        return self.dms_service.store_store_chart(
            store_num=store.store_num,
            pdf_bytes=pdf_bytes,
            metadata=metadata,
        )

    def get_store_download_url(self, store: Store) -> str | None:
        """Get download URL for store chart PDF in DMS."""
        return self.dms_service.get_store_download_url(store_num=store.store_num)
