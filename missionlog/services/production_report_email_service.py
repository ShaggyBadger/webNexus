import time
from email.mime.image import MIMEImage
from smtplib import SMTPConnectError, SMTPServerDisconnected

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

_RETRY_DELAYS_SECONDS = [2, 4, 8]


class ProductionReportEmailService:
    """
    Commander's Intent:
    Deliver production visibility directly to operators' inboxes so they can
    review performance without opening the dashboard mid-route.
    """

    @staticmethod
    def send_report(*, recipient_email: str, report_payload: dict) -> dict:
        summary = report_payload["summary"]
        period = report_payload["period"]
        chart_png_bytes = report_payload["chart_png_bytes"]

        context = {
            "period": period,
            "summary": summary,
            "comparison_text": report_payload["comparison_text"],
        }
        html_body = render_to_string("email/production_report.html", context)
        text_body = render_to_string("email/production_report.txt", context)

        start_date_display = period["start_date"].strftime("%b %d, %Y")
        end_date_display = period["end_date"].strftime("%b %d, %Y")
        subject = (
            f"Production Report - {period['type_label']} "
            f"({start_date_display} to {end_date_display})"
        )
        last_error = None

        for attempt_number, delay_seconds in enumerate(_RETRY_DELAYS_SECONDS, start=1):
            smtp_started = time.monotonic()
            try:
                message = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=settings.MISSIONLOG_REPORT_FROM_EMAIL,
                    to=[recipient_email],
                )
                message.attach_alternative(html_body, "text/html")

                inline_image = MIMEImage(chart_png_bytes, _subtype="png")
                inline_image.add_header("Content-ID", "<production-gph-chart>")
                inline_image.add_header(
                    "Content-Disposition",
                    "inline",
                    filename="mission_production_chart.png",
                )
                message.attach(inline_image)
                message.send()
                smtp_duration_ms = int((time.monotonic() - smtp_started) * 1000)
                return {
                    "status": "success",
                    "attempt_number": attempt_number,
                    "smtp_duration_ms": smtp_duration_ms,
                }
            except (SMTPServerDisconnected, SMTPConnectError) as error:
                last_error = error
                time.sleep(delay_seconds)
            except Exception as error:
                smtp_duration_ms = int((time.monotonic() - smtp_started) * 1000)
                return {
                    "status": "failed",
                    "failure_reason": str(error),
                    "exception_type": error.__class__.__name__,
                    "smtp_duration_ms": smtp_duration_ms,
                }

        return {
            "status": "failed",
            "failure_reason": str(last_error or "SMTP retry limit reached."),
            "exception_type": (
                last_error.__class__.__name__ if last_error else "SMTPError"
            ),
            "smtp_duration_ms": None,
        }
