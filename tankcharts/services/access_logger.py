from django.contrib.auth.models import User
from dms.models import Document
from tankcharts.models import TankChartAccessLog
from tankgauge.models import Store


class AccessLogger:
    """
    HTTP-agnostic logging class for tank chart access (downloads & email delivery).
    Called from the view layer with extracted HTTP metadata.
    """

    @staticmethod
    def log_access(
        *,
        store: Store,
        delivery_method: str,
        status: str,
        chart_document: Document | None = None,
        chart_source: str | None = None,
        generation_duration_ms: int | None = None,
        recipient_email: str = "",
        user: User | None = None,
        trace_id: str = "",
        ip_address: str | None = None,
        user_agent: str = "",
        failure_reason: str = "",
    ) -> TankChartAccessLog:
        file_size_bytes = chart_document.file_size if chart_document else None
        sent_by_user = user if (user and user.is_authenticated) else None

        return TankChartAccessLog.objects.create(
            store=store,
            delivery_method=delivery_method,
            status=status,
            chart_document=chart_document,
            chart_source=chart_source or "",
            generation_duration_ms=generation_duration_ms,
            file_size_bytes=file_size_bytes,
            recipient_email=recipient_email,
            sent_by_user=sent_by_user,
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )
