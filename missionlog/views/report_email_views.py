import json
import logging
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
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
_RECIPIENT_FIELD = "recipient_email"
_QUEUED_MESSAGE = (
    "Report queued for {recipient_email}. Please allow a few minutes for it to finish, "
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

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return json_error_response(
            request=request,
            code="invalid_json",
            message="Request body must be valid JSON.",
            status_code=400,
        )

    if not isinstance(payload, dict):
        return json_error_response(
            request=request,
            code="invalid_json",
            message="Request body must be a JSON object.",
            status_code=400,
        )

    forbidden_supplied = _FORBIDDEN_RECIPIENT_FIELDS.intersection(set(payload.keys()))
    if forbidden_supplied:
        return json_error_response(
            request=request,
            code="recipient_not_allowed",
            message="Use the recipient_email field for the report destination.",
            details={"fields": sorted(list(forbidden_supplied))},
            status_code=400,
        )

    recipient_email = _normalize_recipient_email(payload.get(_RECIPIENT_FIELD))
    if not recipient_email:
        return json_error_response(
            request=request,
            code="recipient_email_required",
            message="A recipient email address is required.",
            status_code=400,
        )

    if not _is_valid_recipient_email(recipient_email):
        return json_error_response(
            request=request,
            code="invalid_recipient_email",
            message="Enter one valid recipient email address.",
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

    throttle_code = _get_throttle_code(request=request)
    if throttle_code:
        return json_error_response(
            request=request,
            code=throttle_code,
            message=(
                "Daily report-email quota exceeded."
                if throttle_code == "daily_quota_exceeded"
                else "Too many report requests. Please try again shortly."
            ),
            status_code=429,
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
        recipient_email__iexact=recipient_email,
        status=ProductionReportEmailAudit.Status.QUEUED,
    ).first()
    if existing_queued:
        return json_success_response(
            data={
                "message": _QUEUED_MESSAGE.format(recipient_email=recipient_email),
                "recipient_email": recipient_email,
            },
            status_code=202,
        )

    trace_id = get_trace_id(request) or ""
    ip_address = request.META.get("REMOTE_ADDR")

    with transaction.atomic():
        audit = ProductionReportEmailAudit.objects.create(
            user=request.user,
            recipient_email=recipient_email,
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
        data={
            "message": _QUEUED_MESSAGE.format(recipient_email=recipient_email),
            "recipient_email": recipient_email,
        },
        status_code=202,
    )


def _normalize_recipient_email(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_valid_recipient_email(value: str) -> bool:
    if any(character in value for character in ("\r", "\n", ",", ";")):
        return False
    try:
        validate_email(value)
    except ValidationError:
        return False
    return True


def _get_throttle_code(*, request) -> str | None:
    now_utc = timezone.now()
    minute_key = now_utc.strftime("%Y%m%d%H%M")
    day_key = now_utc.strftime("%Y%m%d")
    user_limit = int(getattr(settings, "MISSIONLOG_REPORT_USER_RATE_PER_MINUTE", 6))
    ip_limit = int(getattr(settings, "MISSIONLOG_REPORT_IP_RATE_PER_MINUTE", 12))
    user_day_limit = int(
        getattr(settings, "MISSIONLOG_REPORT_USER_RATE_PER_DAY", 10)
    )
    ip_day_limit = int(getattr(settings, "MISSIONLOG_REPORT_IP_RATE_PER_DAY", 30))

    user_cache_key = f"missionlog_report_email:user:{request.user.id}:{minute_key}"
    ip_cache_key = (
        f"missionlog_report_email:ip:{request.META.get('REMOTE_ADDR', '')}:{minute_key}"
    )
    user_day_cache_key = f"missionlog_report_email:user:{request.user.id}:day:{day_key}"
    ip_day_cache_key = (
        f"missionlog_report_email:ip:{request.META.get('REMOTE_ADDR', '')}:day:{day_key}"
    )

    user_count = _increment_cache_counter(user_cache_key, timeout=80)
    ip_count = _increment_cache_counter(ip_cache_key, timeout=80)
    user_day_count = _increment_cache_counter(user_day_cache_key, timeout=172800)
    ip_day_count = _increment_cache_counter(ip_day_cache_key, timeout=172800)

    if user_day_count > user_day_limit or ip_day_count > ip_day_limit:
        return "daily_quota_exceeded"
    if user_count > user_limit or ip_count > ip_limit:
        return "rate_limited"
    return None


def _increment_cache_counter(key: str, *, timeout: int) -> int:
    if cache.add(key, 0, timeout=timeout):
        return cache.incr(key)

    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1
