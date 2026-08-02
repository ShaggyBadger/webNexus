import logging
import time
from smtplib import SMTPConnectError, SMTPServerDisconnected
from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from dms.models import Document
from tankgauge.models import Store

logger = logging.getLogger(__name__)

_RETRY_DELAYS_SECONDS = [2, 4, 8]


class EmailChartService:
    """
    Commander's Intent:
    Ensures field operators receive tank chart PDFs in their inbox without
    needing to download on a mobile device. If delivery fails, the caller
    receives a download_url fallback so operators are never left empty-handed.
    """

    def send_store_chart(
        self,
        *,
        store: Store,
        document: Document,
        recipient_email: str,
    ) -> dict[str, Any]:
        """
        Sends a store-wide tank chart PDF via configured SMTP relay.

        Retries on transient SMTP disconnects (SMTPServerDisconnected,
        SMTPConnectError) with exponential backoff (2s → 4s → 8s, max 3
        attempts). On permanent failure returns an error dict with download_url.

        Args:
            store: Store model instance (provides number, name, city, state).
            document: DMS Document containing the PDF file_path and metadata.
            recipient_email: Destination email address.

        Returns:
            {"status": "success", "message": "..."} on delivery.
            {"status": "error", "code": "...", "message": "...",
             "download_url": "..."} on permanent failure.
        """
        download_url = f"/tankcharts/store/{store.store_num}/"

        generated_at = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
        site_url = getattr(settings, "SITE_URL", "https://thejoshproject.xyz")

        context = {
            "store": store,
            "document": document,
            "generated_at": generated_at,
            "site_url": site_url,
        }

        html_body = render_to_string("email/tank_chart_email.html", context)
        text_body = render_to_string("email/tank_chart_email.txt", context)

        subject = (
            f"TANK CHARTS — STORE #{store.store_num} — "
            f"{(store.city or '').upper()} {(store.state or '').upper()}"
        ).strip()

        try:
            pdf_bytes = self._read_document_bytes(document)
        except Exception as exc:
            logger.error(
                "EMAIL_CHART_FILE_READ_FAILED",
                extra={"store_num": store.store_num, "document_id": document.id},
                exc_info=True,
            )
            return {
                "status": "error",
                "code": "email_delivery_failed",
                "message": "Failed to read chart file. Download directly instead.",
                "download_url": download_url,
            }

        last_error: Exception | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS_SECONDS, start=1):
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient_email],
                )
                msg.attach_alternative(html_body, "text/html")
                msg.attach(
                    filename=f"tank_chart_store_{store.store_num}.pdf",
                    content=pdf_bytes,
                    mimetype="application/pdf",
                )
                msg.send()
                self._increment_email_count(document=document)
                logger.info(
                    "EMAIL_CHART_SENT",
                    extra={
                        "store_num": store.store_num,
                        "recipient": recipient_email,
                        "attempt": attempt,
                    },
                )
                return {
                    "status": "success",
                    "message": (
                        f"Tank chart for store {store.store_num} "
                        f"sent to {recipient_email}"
                    ),
                }
            except (SMTPServerDisconnected, SMTPConnectError) as smtp_err:
                last_error = smtp_err
                logger.warning(
                    "EMAIL_CHART_SMTP_RETRY",
                    extra={
                        "store_num": store.store_num,
                        "attempt": attempt,
                        "delay_s": delay,
                        "error": str(smtp_err),
                    },
                )
                time.sleep(delay)
            except Exception as exc:
                # Non-retriable failure (auth error, bad address, etc.)
                logger.error(
                    "EMAIL_CHART_FAILED_PERMANENT",
                    extra={"store_num": store.store_num, "error": str(exc)},
                    exc_info=True,
                )
                return {
                    "status": "error",
                    "code": "email_delivery_failed",
                    "message": "Failed to deliver email. Download directly instead.",
                    "download_url": download_url,
                    "failure_reason": str(exc),
                }

        # All retries exhausted
        logger.error(
            "EMAIL_CHART_RETRIES_EXHAUSTED",
            extra={
                "store_num": store.store_num,
                "recipient": recipient_email,
                "error": str(last_error),
            },
        )
        return {
            "status": "error",
            "code": "email_delivery_failed",
            "message": "Failed to deliver email. Download directly instead.",
            "download_url": download_url,
            "failure_reason": str(last_error),
        }

    @staticmethod
    def _read_document_bytes(document: Document) -> bytes:
        """Read the PDF bytes from Django default_storage."""
        with default_storage.open(document.file_path, "rb") as f:
            return f.read()

    @staticmethod
    def _increment_email_count(*, document: Document) -> None:
        """
        Preserve per-document email send telemetry for admin audit visibility.

        Commander's Intent:
        Operators depend on delivery telemetry to confirm charts are actually being
        distributed in the field. Counter failures must never block chart delivery.
        """
        try:
            with transaction.atomic():
                locked_document = Document.objects.select_for_update().get(id=document.id)
                locked_document.email_count += 1
                locked_document.save(update_fields=["email_count"])
        except Exception:
            logger.exception(
                "EMAIL_CHART_COUNT_INCREMENT_FAILED",
                extra={
                    "document_id": document.id,
                    "reason_code": "email_count_increment_error",
                },
            )
