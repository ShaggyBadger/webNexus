import json
import logging
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from missionlog.models import ProductionReportEmailAudit
from missionlog.services.production_report_dispatcher import ProductionReportDispatcher
from missionlog.services.production_report_service import ProductionReportService
from missionlog.views.api_contract import (
    get_trace_id,
    json_error_response,
    json_success_response,
)

logger = logging.getLogger("webnexus")

_ALLOWED_RANGES = {"week", "month", "quarter", "year"}
_FORBIDDEN_RECIPIENT_FIELDS = {"to", "recipient", "email"}
_QUEUED_MESSAGE = (
    "Report generation started. Please allow a few minutes for it to finish, "
    "then check your email and spam folder. If you find it in spam, mark it "
    "as not spam."
)


def production_report_email_request(request):
    """
    Commander's Intent:
    Queue one production-report email job for the authenticated operator so
    report generation happens asynchronously and does not block MissionLog UI.
    """
    if request.method != "POST":
        return json_error_response(
            request=request,
            code="method_not_allowed",
            message="Method not allowed.",
            details={"method": request.method},
            status_code=405,
        )

    if not request.user.is_authenticated:
        return json_error_response(
            request=request,
            code="authentication_required",
            message="Authentication required.",
            status_code=401,
        )

    if _is_throttled(request=request):
        return json_error_response(
            request=request,
            code="rate_limited",
            message="Too many report requests. Please try again shortly.",
            status_code=429,
        )

    user_email = (request.user.email or "").strip()
    if not user_email:
        return json_error_response(
            request=request,
            code="verified_email_required",
            message="A verified account email is required before sending reports.",
            status_code=422,
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return json_error_response(
            request=request,
            code="invalid_json",
            message="Request body must be valid JSON.",
            status_code=400,
        )

    forbidden_supplied = _FORBIDDEN_RECIPIENT_FIELDS.intersection(set(payload.keys()))
    if forbidden_supplied:
        return json_error_response(
            request=request,
            code="recipient_not_allowed",
            message="Recipient fields are not allowed; report is sent to your account email.",
            details={"fields": sorted(list(forbidden_supplied))},
            status_code=400,
        )

    report_range = str(payload.get("range", "")).strip().lower()
    if report_range not in _ALLOWED_RANGES:
        return json_error_response(
            request=request,
            code="invalid_range",
            message="Invalid range. Allowed values: week, month, quarter, year.",
            status_code=400,
        )

    user_tz = ProductionReportService.resolve_user_timezone(request.user)
    bounds = ProductionReportService.resolve_period_bounds(
        report_range=report_range,
        now_utc=timezone.now(),
        tz=user_tz,
    )

    existing_queued = ProductionReportEmailAudit.objects.filter(
        user=request.user,
        report_range=report_range,
        period_start=bounds.period_start_local.date(),
        period_end=bounds.period_end_local.date(),
        status=ProductionReportEmailAudit.Status.QUEUED,
    ).first()
    if existing_queued:
        return json_success_response(
            data={"message": _QUEUED_MESSAGE},
            status_code=202,
        )

    trace_id = get_trace_id(request) or ""
    ip_address = request.META.get("REMOTE_ADDR")

    with transaction.atomic():
        audit = ProductionReportEmailAudit.objects.create(
            user=request.user,
            report_range=report_range,
            period_start=bounds.period_start_local.date(),
            period_end=bounds.period_end_local.date(),
            status=ProductionReportEmailAudit.Status.QUEUED,
            trace_id=trace_id,
            ip_address=ip_address,
        )

    queued = ProductionReportDispatcher.enqueue(audit_id=audit.id)
    if not queued:
        audit.status = ProductionReportEmailAudit.Status.FAILED
        audit.failure_reason = "Queue spawn failed"
        audit.exception_type = "EnqueueError"
        audit.save(
            update_fields=["status", "failure_reason", "exception_type", "updated_at"]
        )
        return json_error_response(
            request=request,
            code="enqueue_unavailable",
            message="Report could not be started. Please try again.",
            status_code=503,
        )

    logger.info(
        "MISSIONLOG_REPORT_EMAIL_QUEUED",
        extra={
            "audit_id": audit.id,
            "user_id": request.user.id,
            "report_range": report_range,
            "trace_id": trace_id,
        },
    )
    return json_success_response(
        data={"message": _QUEUED_MESSAGE},
        status_code=202,
    )


def _is_throttled(*, request) -> bool:
    now_utc = timezone.now()
    minute_key = now_utc.strftime("%Y%m%d%H%M")
    user_limit = int(getattr(settings, "MISSIONLOG_REPORT_USER_RATE_PER_MINUTE", 6))
    ip_limit = int(getattr(settings, "MISSIONLOG_REPORT_IP_RATE_PER_MINUTE", 12))

    user_cache_key = f"missionlog_report_email:user:{request.user.id}:{minute_key}"
    ip_cache_key = (
        f"missionlog_report_email:ip:{request.META.get('REMOTE_ADDR', '')}:{minute_key}"
    )

    user_count = cache.get(user_cache_key, 0) + 1
    ip_count = cache.get(ip_cache_key, 0) + 1
    cache.set(user_cache_key, user_count, timeout=80)
    cache.set(ip_cache_key, ip_count, timeout=80)

    return user_count > user_limit or ip_count > ip_limit
