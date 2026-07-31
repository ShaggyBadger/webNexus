import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from atg.models import VeederTicket
from tankcharts.services.chart_service import TankChartService
from tankgauge.models import Store

logger = logging.getLogger(__name__)


@receiver(post_save, sender=VeederTicket)
def auto_regenerate_on_veeder_ticket(
    sender, instance: VeederTicket, created: bool, **kwargs
) -> None:
    """
    Auto-regenerates store tank chart after a Veeder-Root ticket is OCR processed.

    Commander's Intent:
    Ensures tank charts are kept pre-warmed whenever a new fuel delivery is ingested.
    Non-blocking: failures are logged without disrupting ticket saving.
    """
    if not instance.parsed_json:
        return  # Only fire on fully processed tickets

    if not instance.store_id:
        return  # No store linked — nothing to regenerate

    store_id = instance.store_id

    def regenerate() -> None:
        try:
            store = Store.objects.filter(pk=store_id).first()
            if not store:
                return
            chart_service = TankChartService()
            chart_service.get_store_chart(store_num=store.store_num, force=True)
            logger.info(
                "VEEDER_TICKET_AUTO_REGENERATE_SUCCESS",
                extra={"store_id": store_id, "store_num": store.store_num},
            )
        except Exception:
            logger.exception(
                "VEEDER_TICKET_AUTO_REGENERATE_FAILED",
                extra={"store_id": store_id},
            )

    transaction.on_commit(regenerate)
