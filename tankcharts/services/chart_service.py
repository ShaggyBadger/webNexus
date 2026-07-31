import logging
from typing import Any

from tankcharts.services.cache_service import ChartCacheService
from tankcharts.services.generation_service import ChartGenerationService
from tankcharts.services.status_service import ChartStatusService
from tankgauge.models import Store

logger = logging.getLogger(__name__)


class TankChartService:
    """
    Thin orchestrator for store tank chart operations.
    Resolves store numbers and routes calls to sub-services.
    """

    def __init__(
        self,
        cache_service: ChartCacheService | None = None,
        status_service: ChartStatusService | None = None,
        generation_service: ChartGenerationService | None = None,
    ) -> None:
        self.cache_service = cache_service or ChartCacheService()
        self.status_service = status_service or ChartStatusService()
        self.generation_service = generation_service or ChartGenerationService(
            cache_service=self.cache_service
        )

    def get_store_chart(self, store_num: int, force: bool = False) -> dict[str, Any]:
        """
        Commander's Intent:
        Resolves store number and fetches or generates store-wide chart PDF.
        """
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            return {
                "success": False,
                "code": "store_not_found",
                "message": f"Store {store_num} not found.",
                "status_code": 404,
            }

        try:
            result = self.generation_service.get_or_generate(store, force=force)
            return {
                "success": True,
                "source": result.get("source"),
                "document": result.get("document"),
                "download_url": result.get("download_url"),
                "status_code": 200,
            }
        except ValueError as val_err:
            return {
                "success": False,
                "code": "store_chart_generation_unavailable",
                "message": str(val_err),
                "status_code": 422,
            }
        except Exception as exc:
            logger.exception(
                "TANK_CHART_SERVICE_GET_STORE_CHART_FAILED",
                extra={"store_num": store_num},
            )
            return {
                "success": False,
                "code": "store_chart_generation_failed",
                "message": "Failed to generate store-wide tank chart PDF.",
                "details": str(exc),
                "status_code": 500,
            }

    def get_chart_status(self, store_num: int) -> dict[str, Any]:
        """
        Resolves store number and returns read-only chart status.
        """
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            return {
                "success": False,
                "code": "store_not_found",
                "message": f"Store {store_num} not found.",
                "status_code": 404,
            }

        status_data = self.status_service.get_status(store)
        return {
            "success": True,
            "data": status_data,
            "status_code": 200,
        }
