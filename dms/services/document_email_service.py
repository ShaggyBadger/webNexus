import logging
import os
import time
from smtplib import SMTPConnectError, SMTPServerDisconnected

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string

from dms.models import Document

logger = logging.getLogger(__name__)

_RETRY_DELAYS_SECONDS = [2, 4, 8]


class DocumentEmailService:
    """
    Commander's Intent:
    Allows operators to dispatch any DMS document directly to inboxes from the
    dashboard. If this fails, field teams lose a mobile-friendly handoff path.
    """

    def send_document(
        self,
        *,
        document: Document,
        recipient_email: str,
    ) -> dict[str, str]:
        """Send one DMS document via SMTP with retry/backoff."""
        download_url = f"/dms/documents/{document.id}/download/"
        site_url = getattr(settings, "SITE_URL", "https://thejoshproject.xyz")
        context = {
            "document": document,
            "recipient_email": recipient_email,
            "site_url": site_url,
        }
        html_body = render_to_string("dms/partials/document_email.html", context)
        text_body = render_to_string("dms/partials/document_email.txt", context)

        _, extension = os.path.splitext(document.original_filename or "")
        fallback_ext = extension or ".bin"
        subject = f"DMS DOCUMENT — {document.title}".strip()

        try:
            with default_storage.open(document.file_path, "rb") as file_handle:
                file_bytes = file_handle.read()
        except Exception:
            logger.exception(
                "DMS_DOCUMENT_EMAIL_FILE_READ_FAILED",
                extra={
                    "document_id": document.id,
                    "reason_code": "file_read_failed",
                },
            )
            return {
                "status": "error",
                "code": "document_email_file_read_failed",
                "message": "Failed to read document file.",
                "download_url": download_url,
            }

        last_error: Exception | None = None
        for attempt_number, delay_seconds in enumerate(_RETRY_DELAYS_SECONDS, start=1):
            try:
                message = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient_email],
                )
                message.attach_alternative(html_body, "text/html")
                message.attach(
                    filename=document.original_filename
                    or f"document_{document.id}{fallback_ext}",
                    content=file_bytes,
                    mimetype=document.mime_type or "application/octet-stream",
                )
                message.send()
                self._increment_email_count(document=document)
                logger.info(
                    "DMS_DOCUMENT_EMAIL_SENT",
                    extra={
                        "document_id": document.id,
                        "recipient_email": recipient_email,
                        "reason_code": "send_success",
                        "attempt_number": attempt_number,
                    },
                )
                return {
                    "status": "success",
                    "message": f"Document sent to {recipient_email}.",
                    "download_url": download_url,
                }
            except (SMTPServerDisconnected, SMTPConnectError) as smtp_error:
                last_error = smtp_error
                logger.warning(
                    "DMS_DOCUMENT_EMAIL_RETRY",
                    extra={
                        "document_id": document.id,
                        "recipient_email": recipient_email,
                        "attempt_number": attempt_number,
                        "delay_seconds": delay_seconds,
                        "reason_code": "smtp_retry",
                        "error": str(smtp_error),
                    },
                )
                time.sleep(delay_seconds)
            except Exception as error:
                logger.exception(
                    "DMS_DOCUMENT_EMAIL_FAILED",
                    extra={
                        "document_id": document.id,
                        "recipient_email": recipient_email,
                        "reason_code": "send_failed",
                        "error": str(error),
                    },
                )
                return {
                    "status": "error",
                    "code": "document_email_delivery_failed",
                    "message": "Failed to send document email.",
                    "download_url": download_url,
                }

        logger.error(
            "DMS_DOCUMENT_EMAIL_RETRIES_EXHAUSTED",
            extra={
                "document_id": document.id,
                "recipient_email": recipient_email,
                "reason_code": "smtp_retries_exhausted",
                "error": str(last_error),
            },
        )
        return {
            "status": "error",
            "code": "document_email_delivery_failed",
            "message": "Failed to send document email after retries.",
            "download_url": download_url,
        }

    @staticmethod
    def _increment_email_count(*, document: Document) -> None:
        """Increment document email_count under a row lock for concurrency safety."""
        try:
            with transaction.atomic():
                locked_document = Document.objects.select_for_update().get(
                    id=document.id
                )
                locked_document.email_count += 1
                locked_document.save(update_fields=["email_count"])
        except Exception:
            logger.exception(
                "DMS_DOCUMENT_EMAIL_COUNT_INCREMENT_FAILED",
                extra={
                    "document_id": document.id,
                    "reason_code": "email_count_increment_error",
                },
            )
