import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ..models import FeedbackClickEvent, FeedbackReport
from ..serializers import FeedbackInitiateSerializer, FeedbackSubmitSerializer
from .api_contract import drf_error_response, drf_success_response

logger = logging.getLogger("feedback")


class FeedbackInitiateAPIView(APIView):
    """Capture raw click telemetry for feedback interaction attempts."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "feedback_initiate"

    def throttled(self, request, wait):
        return drf_error_response(
            request=request,
            code="rate_limited",
            message="Too many feedback initiation requests. Try again shortly.",
            details={"wait_seconds": int(wait) if wait else None},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def post(self, request):
        serializer = FeedbackInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return drf_error_response(
                request=request,
                code="validation_error",
                message="Invalid feedback initiation payload.",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = serializer.validated_data
        click_event = FeedbackClickEvent.objects.create(
            user=request.user if request.user.is_authenticated else None,
            url=payload["url"],
            user_agent=payload.get("user_agent")
            or request.META.get("HTTP_USER_AGENT", ""),
            viewport_size=payload.get("viewport_size", ""),
            page_metadata={
                **payload.get("page_metadata", {}),
                "request_meta": {
                    "remote_addr": request.META.get("REMOTE_ADDR"),
                    "referer": request.META.get("HTTP_REFERER"),
                },
            },
        )

        logger.info(
            "FEEDBACK_INITIATED",
            extra={
                "feedback_click_event_id": click_event.id,
                "reason_code": "user_clicked_feedback",
            },
        )
        return drf_success_response(
            data={
                "click_event_id": click_event.id,
                "status": "initiated",
                "timestamp": click_event.timestamp.isoformat(),
            },
            status_code=status.HTTP_201_CREATED,
        )


class FeedbackSubmitAPIView(APIView):
    """Create submitted feedback report from a prior click telemetry record."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "feedback_submit"

    def throttled(self, request, wait):
        return drf_error_response(
            request=request,
            code="rate_limited",
            message="Too many feedback submission requests. Try again shortly.",
            details={"wait_seconds": int(wait) if wait else None},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def post(self, request):
        serializer = FeedbackSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return drf_error_response(
                request=request,
                code="validation_error",
                message="Invalid feedback submission payload.",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = serializer.validated_data
        click_event_id = payload["click_event_id"]
        try:
            click_event = FeedbackClickEvent.objects.get(id=click_event_id)
        except FeedbackClickEvent.DoesNotExist:
            return drf_error_response(
                request=request,
                code="feedback_click_not_found",
                message="Feedback click event not found.",
                details={"click_event_id": click_event_id},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if click_event.user_id and (
            not request.user.is_authenticated or click_event.user_id != request.user.id
        ):
            return drf_error_response(
                request=request,
                code="forbidden",
                message="You cannot submit feedback for this click event.",
                details={"click_event_id": click_event_id},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        submitted_at = timezone.now()
        report = FeedbackReport.objects.create(
            user=click_event.user,
            click_event=click_event,
            url=click_event.url,
            status=FeedbackReport.STATUS_SUBMITTED,
            category=payload["category"],
            message=payload.get("message", ""),
            user_agent=click_event.user_agent,
            viewport_size=click_event.viewport_size,
            page_metadata={
                **(click_event.page_metadata or {}),
                "submitted_context": payload.get("page_metadata", {}),
            },
            submitted_at=submitted_at,
        )

        click_event.is_submitted = True
        click_event.submitted_at = submitted_at
        click_event.save(update_fields=["is_submitted", "submitted_at"])

        logger.info(
            "FEEDBACK_SUBMITTED",
            extra={
                "feedback_report_id": report.id,
                "feedback_click_event_id": click_event.id,
                "status": report.status,
                "reason_code": "user_submitted_feedback",
            },
        )
        return drf_success_response(
            data={
                "id": report.id,
                "click_event_id": click_event.id,
                "status": report.status,
                "category": report.category,
                "submitted_at": (
                    report.submitted_at.isoformat() if report.submitted_at else None
                ),
            },
            status_code=status.HTTP_200_OK,
        )
