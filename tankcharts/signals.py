import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from tankcharts.services.chart_service import TankChartService
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankEstimation,
    VirtualTankEstimation,
)

logger = logging.getLogger(__name__)


def regenerate_store_chart_for_store_id(*, store_id: int, reason_code: str) -> None:
    """
    Ensures freshly estimated tank geometry is reflected in pre-warmed store PDFs.

    Commander's Intent:
    If automatic re-warm fails, operators work from stale charts and risk bad
    delivery decisions. This function logs failures and never raises.

    Args:
        store_id: Primary key for the store whose chart should be regenerated.
        reason_code: Stable reason code indicating the trigger path.
    """

    def regenerate() -> None:
        try:
            store = Store.objects.filter(pk=store_id).first()
            if not store:
                logger.info(
                    "VEEDER_TICKET_AUTO_REGENERATE_SKIPPED",
                    extra={
                        "store_id": store_id,
                        "reason_code": "store_not_found",
                        "trigger_reason_code": reason_code,
                    },
                )
                return

            chart_service = TankChartService()
            result = chart_service.get_store_chart(
                store_num=store.store_num, force=True
            )

            if not result.get("success"):
                logger.error(
                    "VEEDER_TICKET_AUTO_REGENERATE_FAILED",
                    extra={
                        "store_id": store_id,
                        "store_num": store.store_num,
                        "reason_code": "chart_service_failure",
                        "trigger_reason_code": reason_code,
                        "error_code": result.get("code"),
                    },
                )
                return

            logger.info(
                "VEEDER_TICKET_AUTO_REGENERATE_SUCCESS",
                extra={
                    "store_id": store_id,
                    "store_num": store.store_num,
                    "reason_code": reason_code,
                },
            )
        except Exception:
            logger.exception(
                "VEEDER_TICKET_AUTO_REGENERATE_FAILED",
                extra={
                    "store_id": store_id,
                    "reason_code": "unhandled_exception",
                    "trigger_reason_code": reason_code,
                },
            )

    transaction.on_commit(regenerate)


@receiver(post_save, sender=TankEstimation)
def auto_regenerate_on_tank_estimation(
    sender, instance: TankEstimation, created: bool, **kwargs
) -> None:
    """Trigger chart re-warm when a new active mapped-tank estimation is created."""
    if not created:
        return
    if not instance.is_active:
        logger.info(
            "VEEDER_TICKET_AUTO_REGENERATE_SKIPPED",
            extra={
                "store_id": instance.tank_mapping.store_id,
                "reason_code": "inactive_tank_estimation",
                "estimation_id": instance.id,
            },
        )
        return
    regenerate_store_chart_for_store_id(
        store_id=instance.tank_mapping.store_id,
        reason_code="tank_estimation_created",
    )


@receiver(post_save, sender=VirtualTankEstimation)
def auto_regenerate_on_virtual_estimation(
    sender, instance: VirtualTankEstimation, created: bool, **kwargs
) -> None:
    """Trigger chart re-warm when a new active virtual estimation is created."""
    if not created:
        return
    if not instance.is_active:
        logger.info(
            "VEEDER_TICKET_AUTO_REGENERATE_SKIPPED",
            extra={
                "store_id": instance.store_id,
                "reason_code": "inactive_virtual_tank_estimation",
                "estimation_id": instance.id,
            },
        )
        return
    if not StoreTankMapping.objects.filter(
        store=instance.store,
        fuel_type__iexact=instance.fuel_type,
        tank_index=instance.tank_index,
    ).exists():
        logger.info(
            "VEEDER_TICKET_AUTO_REGENERATE_SKIPPED",
            extra={
                "store_id": instance.store_id,
                "reason_code": "virtual_estimation_mapping_pending",
                "estimation_id": instance.id,
            },
        )
        return
    regenerate_store_chart_for_store_id(
        store_id=instance.store_id,
        reason_code="virtual_tank_estimation_created",
    )
