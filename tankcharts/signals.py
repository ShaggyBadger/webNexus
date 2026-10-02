import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from tankcharts.services.chart_service import TankChartService
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankEstimation,
    VirtualTankEstimation,
)

logger = logging.getLogger(__name__)

MAPPING_CHART_INPUT_FIELDS = (
    "store",
    "tank_type",
    "fuel_type",
    "canonical_fuel_type",
    "tank_index",
    "physical_capacity_gallons",
    "capacity_verified",
    "capacity_source",
    "profile_status",
    "ullage_endpoint_percent_exact",
    "profile_version",
)


@receiver(pre_save, sender=StoreTankMapping)
def track_mapping_chart_input_changes(sender, instance, update_fields=None, **kwargs):
    """Record whether this save changes tank data embedded in store charts."""
    if instance._state.adding:
        instance._tank_chart_inputs_changed = True
        return

    fields_to_compare = MAPPING_CHART_INPUT_FIELDS
    if update_fields is not None:
        fields_to_compare = tuple(
            field_name
            for field_name in MAPPING_CHART_INPUT_FIELDS
            if field_name in update_fields
        )
        if not fields_to_compare:
            instance._tank_chart_inputs_changed = False
            return

    field_attname = {
        field_name: sender._meta.get_field(field_name).attname
        for field_name in fields_to_compare
    }
    previous_values = (
        sender.objects.filter(pk=instance.pk).values(*field_attname.values()).first()
    )
    instance._tank_chart_inputs_changed = bool(
        previous_values
        and any(
            previous_values[attname] != getattr(instance, attname)
            for attname in field_attname.values()
        )
    )


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


@receiver(post_save, sender=StoreTankMapping)
def auto_regenerate_on_mapping_created(
    sender, instance: StoreTankMapping, created: bool, **kwargs
) -> None:
    """Refresh store charts after creation or a chart-relevant mapping change."""
    if not created and not getattr(instance, "_tank_chart_inputs_changed", False):
        return
    reason_code = "tank_mapping_created" if created else "tank_mapping_updated"
    regenerate_store_chart_for_store_id(
        store_id=instance.store_id,
        reason_code=reason_code,
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
