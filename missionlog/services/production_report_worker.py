import logging
import time

from django.db import transaction
from django.utils import timezone

from missionlog.models import ProductionReportEmailAudit
from missionlog.services.production_report_email_service import (
    ProductionReportEmailService,
)
from missionlog.services.production_report_service import ProductionReportService

logger = logging.getLogger("webnexus")


def process_production_report_email(*, audit_id: int) -> None:
    """
    Commander's Intent:
    Processes one queued audit request and attempts report generation + email
    delivery exactly once so users receive deterministic send behavior.
    """
    audit = (
        ProductionReportEmailAudit.objects.select_related("user")
        .filter(id=audit_id)
        .first()
    )
    if not audit:
        logger.warning(
            "MISSIONLOG_REPORT_EMAIL_AUDIT_NOT_FOUND",
            extra={"audit_id": audit_id},
        )
        return

    if audit.status != ProductionReportEmailAudit.Status.QUEUED:
        logger.info(
            "MISSIONLOG_REPORT_EMAIL_AUDIT_SKIPPED",
            extra={"audit_id": audit_id, "status": audit.status},
        )
        return

    if not audit.recipient_email:
        _mark_failed(
            audit=audit,
            failure_reason="Queued report has no recipient email.",
            exception_type="MissingRecipientError",
            generation_duration_ms=None,
            render_duration_ms=None,
            smtp_duration_ms=None,
        )
        logger.error(
            "MISSIONLOG_REPORT_EMAIL_RECIPIENT_MISSING",
            extra={"audit_id": audit.id, "user_id": audit.user_id},
        )
        return

    generation_started = time.monotonic()
    render_duration_ms = None
    try:
        report_payload = ProductionReportService.build_report(
            user=audit.user,
            report_range=audit.report_range,
            period_start_date=audit.period_start,
            period_end_date=audit.period_end,
        )
        generation_duration_ms = int((time.monotonic() - generation_started) * 1000)
        render_duration_ms = generation_duration_ms
    except Exception as error:
        generation_duration_ms = int((time.monotonic() - generation_started) * 1000)
        _mark_failed(
            audit=audit,
            failure_reason=str(error),
            exception_type=error.__class__.__name__,
            generation_duration_ms=generation_duration_ms,
            render_duration_ms=render_duration_ms,
            smtp_duration_ms=None,
        )
        logger.exception(
            "MISSIONLOG_REPORT_EMAIL_GENERATION_FAILED",
            extra={"audit_id": audit.id, "user_id": audit.user_id},
        )
        return

    email_result = ProductionReportEmailService.send_report(
        recipient_email=audit.recipient_email,
        report_payload=report_payload,
    )

    if email_result.get("status") == "success":
        try:
            with transaction.atomic():
                locked = ProductionReportEmailAudit.objects.select_for_update().get(
                    id=audit.id
                )
                locked.status = ProductionReportEmailAudit.Status.SENT
                locked.failure_reason = ""
                locked.exception_type = ""
                locked.generation_duration_ms = generation_duration_ms
                locked.render_duration_ms = render_duration_ms
                locked.smtp_duration_ms = email_result.get("smtp_duration_ms")
                locked.updated_at = timezone.now()
                locked.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "exception_type",
                        "generation_duration_ms",
                        "render_duration_ms",
                        "smtp_duration_ms",
                        "updated_at",
                    ]
                )
        except Exception:
            logger.exception(
                "MISSIONLOG_REPORT_EMAIL_AUDIT_UPDATE_AFTER_SEND_FAILED",
                extra={"audit_id": audit.id, "user_id": audit.user_id},
            )
        return

    _mark_failed(
        audit=audit,
        failure_reason=email_result.get("failure_reason", "Email delivery failed."),
        exception_type=email_result.get("exception_type", "EmailSendError"),
        generation_duration_ms=generation_duration_ms,
        render_duration_ms=render_duration_ms,
        smtp_duration_ms=email_result.get("smtp_duration_ms"),
    )


def _mark_failed(
    *,
    audit: ProductionReportEmailAudit,
    failure_reason: str,
    exception_type: str,
    generation_duration_ms: int | None,
    render_duration_ms: int | None,
    smtp_duration_ms: int | None,
) -> None:
    try:
        with transaction.atomic():
            locked = ProductionReportEmailAudit.objects.select_for_update().get(
                id=audit.id
            )
            locked.status = ProductionReportEmailAudit.Status.FAILED
            locked.failure_reason = failure_reason[:2000]
            locked.exception_type = exception_type[:128]
            locked.generation_duration_ms = generation_duration_ms
            locked.render_duration_ms = render_duration_ms
            locked.smtp_duration_ms = smtp_duration_ms
            locked.updated_at = timezone.now()
            locked.save(
                update_fields=[
                    "status",
                    "failure_reason",
                    "exception_type",
                    "generation_duration_ms",
                    "render_duration_ms",
                    "smtp_duration_ms",
                    "updated_at",
                ]
            )
    except Exception:
        logger.exception(
            "MISSIONLOG_REPORT_EMAIL_AUDIT_MARK_FAILED_ERROR",
            extra={"audit_id": audit.id, "user_id": audit.user_id},
        )
