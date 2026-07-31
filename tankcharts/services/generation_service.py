import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from tankcharts.models import StoreChartGeneration
from tankcharts.rendering.pdf_renderer import PDFRenderer
from tankcharts.services.cache_service import ChartCacheService
from tankcharts.services.field_chart_service import TankFieldChartService
from tankgauge.models import Store

logger = logging.getLogger(__name__)

# Constants for lock and backoff
LOCK_TIMEOUT_SECONDS = 300  # 5 minutes stale generation reset
MAX_LOCK_WAIT_RETRIES = 5
LOCK_WAIT_SLEEP_SECONDS = 0.5
BASE_BACKOFF_MINUTES = 2
MAX_BACKOFF_MINUTES = 60


class ChartGenerationService:
    """
    Handles PDF generation mutex locks, sync builds, and error backoffs.
    Ensures field operators always receive fresh or cached charts efficiently.
    """

    def __init__(
        self,
        cache_service: ChartCacheService | None = None,
        chart_service: TankFieldChartService | None = None,
        pdf_renderer: PDFRenderer | None = None,
    ) -> None:
        self.cache_service = cache_service or ChartCacheService()
        self.chart_service = chart_service or TankFieldChartService()
        self.pdf_renderer = pdf_renderer or PDFRenderer()

    def get_or_generate(self, store: Store, force: bool = False) -> dict[str, Any]:
        """
        Retrieves cached store chart or generates one synchronously under a DB lock.

        Commander's Intent:
        Ensures field operators get tank charts in under 200ms when warm,
        or under 2s when generation is required.

        Args:
            store: Store model instance.
            force: If True, ignores cache and forces regeneration.

        Returns:
            Dict containing result status, document, or download_url.
        """
        if not force:
            existing = self.cache_service.find_existing_store(store)
            if existing and not self.cache_service.is_store_stale(store, existing):
                url = self.cache_service.get_store_download_url(store)
                return {
                    "source": "cached",
                    "document": existing,
                    "download_url": url,
                }

        # Stale or missing chart — attempt generation with lock
        return self._generate_with_lock(store)

    def _generate_with_lock(self, store: Store) -> dict[str, Any]:
        """Acquire DB lock and generate store chart PDF synchronously."""
        now = timezone.now()

        for attempt in range(MAX_LOCK_WAIT_RETRIES):
            acquired = False
            with transaction.atomic():
                (
                    gen_record,
                    _,
                ) = StoreChartGeneration.objects.select_for_update().get_or_create(
                    store=store
                )

                # Reset stale 'generating' status if crashed (> 5 mins)
                if gen_record.status == StoreChartGeneration.Status.GENERATING:
                    if (
                        gen_record.started_at
                        and (now - gen_record.started_at).total_seconds()
                        > LOCK_TIMEOUT_SECONDS
                    ):
                        logger.warning(
                            "CHART_GENERATION_LOCK_STALE_RESET",
                            extra={"store_num": store.store_num},
                        )
                        gen_record.status = StoreChartGeneration.Status.FAILED
                        gen_record.failure_reason = "Generation lock timed out"
                        gen_record.save()

                # Check backoff window if failed
                if (
                    gen_record.status == StoreChartGeneration.Status.FAILED
                    and gen_record.retry_after
                ):
                    if now < gen_record.retry_after:
                        # Return existing document if available despite failure
                        existing = self.cache_service.find_existing_store(store)
                        if existing:
                            return {
                                "source": "cached_fallback",
                                "document": existing,
                                "download_url": self.cache_service.get_store_download_url(
                                    store
                                ),
                            }
                        raise ValueError(
                            f"Chart generation in backoff window until {gen_record.retry_after}. Reason: {gen_record.failure_reason}"
                        )

                if gen_record.status != StoreChartGeneration.Status.GENERATING:
                    gen_record.status = StoreChartGeneration.Status.GENERATING
                    gen_record.started_at = now
                    gen_record.save()
                    acquired = True

            if acquired:
                break

            # Another process is generating; sleep briefly and retry loop
            time.sleep(LOCK_WAIT_SLEEP_SECONDS)

        if not acquired:
            # Fallback check after waiting
            existing = self.cache_service.find_existing_store(store)
            if existing:
                return {
                    "source": "cached_wait_fallback",
                    "document": existing,
                    "download_url": self.cache_service.get_store_download_url(store),
                }
            raise RuntimeError("Could not acquire generation lock for store chart.")

        # Lock acquired — execute generation
        try:
            chart = self.chart_service.build_store(store_num=store.store_num)
            tank_chunks = self.chart_service.chunk_store_tanks(chart, page_size=4)
            pdf_bytes = self.pdf_renderer.render_store(chart, tank_chunks=tank_chunks)

            metadata = {
                "store_num": chart.store_num,
                "tank_count": len(chart.tanks),
                "tank_indices": [tank.tank_index for tank in chart.tanks],
                "official_row_counts": {
                    str(tank.tank_index): tank.official_row_count
                    for tank in chart.tanks
                },
                "generated_at": chart.generated_at.isoformat(),
            }

            document = self.cache_service.store_store_chart(
                store=store,
                pdf_bytes=pdf_bytes,
                metadata=metadata,
            )

            # Update generation record success state
            with transaction.atomic():
                gen_record = StoreChartGeneration.objects.select_for_update().get(
                    store=store
                )
                gen_record.status = StoreChartGeneration.Status.COMPLETED
                gen_record.completed_at = timezone.now()
                gen_record.failure_count = 0
                gen_record.failure_reason = ""
                gen_record.retry_after = None
                gen_record.save()

            return {
                "source": "generated",
                "document": document,
                "download_url": self.cache_service.get_store_download_url(store),
            }

        except Exception as exc:
            logger.exception(
                "STORE_CHART_GENERATION_FAILED",
                extra={"store_num": store.store_num},
            )
            # Record failure state & exponential backoff
            with transaction.atomic():
                gen_record = StoreChartGeneration.objects.select_for_update().get(
                    store=store
                )
                gen_record.status = StoreChartGeneration.Status.FAILED
                gen_record.failure_count += 1
                gen_record.failure_reason = str(exc)

                backoff_mins = min(
                    BASE_BACKOFF_MINUTES ** (gen_record.failure_count - 1),
                    MAX_BACKOFF_MINUTES,
                )
                gen_record.retry_after = timezone.now() + timedelta(
                    minutes=backoff_mins
                )
                gen_record.save()
            raise
