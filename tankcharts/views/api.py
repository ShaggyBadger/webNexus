import logging
from datetime import timedelta

from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from tankgauge.views.api.error_contract import (
    drf_error_response,
    drf_success_response,
)
from tankcharts.rendering import PDFRenderer
from tankcharts.services import (
    AccessLogger,
    DMSChartStorageService,
    EmailChartService,
    TankChartService,
)
from tankcharts.services.field_chart_service import TankFieldChartService
from tankgauge.models import Store, StoreTankMapping

logger = logging.getLogger(__name__)

_IDEMPOTENCY_WINDOW_SECONDS = 60


class TankChartPDFAPIView(APIView):
    """Get a single tank chart PDF for a store and tank index."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = TankFieldChartService()
        self.pdf_renderer = PDFRenderer()
        self.storage_service = DMSChartStorageService()

    def get(self, request, store_num: int, tank_index: int):
        mapping = (
            StoreTankMapping.objects.select_related("store", "tank_type")
            .filter(store__store_num=store_num, tank_index=tank_index)
            .first()
        )

        if not mapping:
            return drf_error_response(
                request=request,
                code="tank_mapping_not_found",
                message="No tank mapping found for store and tank index.",
                details={"store_num": store_num, "tank_index": tank_index},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        existing = self.storage_service.find_existing(
            store_num=store_num,
            fuel_type=mapping.fuel_type,
            tank_index=tank_index,
        )
        if existing and not self.storage_service.is_stale(
            document=existing,
            store_num=store_num,
            tank_index=tank_index,
        ):
            download_url = self.storage_service.get_download_url(
                store_num=store_num,
                fuel_type=mapping.fuel_type,
                tank_index=tank_index,
            )
            if download_url:
                return HttpResponseRedirect(download_url)

        try:
            chart = self.chart_service.build(
                store_num=store_num,
                tank_index=tank_index,
            )
            pdf_bytes = self.pdf_renderer.render(chart)

            metadata = {
                "store_num": chart.store_num,
                "fuel_type": chart.fuel_type,
                "tank_index": chart.tank_index,
                "official_row_count": chart.official_row_count,
                "generated_at": chart.generated_at.isoformat(),
            }
            document = self.storage_service.store(
                store_num=store_num,
                fuel_type=mapping.fuel_type,
                tank_index=tank_index,
                pdf_bytes=pdf_bytes,
                metadata=metadata,
            )
            logger.info(
                "TANKCHART_PDF_GENERATED",
                extra={
                    "store_num": store_num,
                    "fuel_type": mapping.fuel_type,
                    "tank_index": tank_index,
                    "document_id": document.id,
                },
            )
            return HttpResponseRedirect(
                self.storage_service.get_download_url(
                    store_num=store_num,
                    fuel_type=mapping.fuel_type,
                    tank_index=tank_index,
                )
            )
        except ValueError as error:
            return drf_error_response(
                request=request,
                code="tank_chart_generation_unavailable",
                message=str(error),
                details={"store_num": store_num, "tank_index": tank_index},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as error:
            logger.exception(
                "TANKCHART_PDF_GENERATION_FAILED",
                extra={
                    "store_num": store_num,
                    "fuel_type": mapping.fuel_type,
                    "tank_index": tank_index,
                },
            )
            return drf_error_response(
                request=request,
                code="tank_chart_generation_failed",
                message="Failed to generate tank chart PDF.",
                details={"error": str(error)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TankChartMetaAPIView(APIView):
    """Metadata view for tank charts."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = TankFieldChartService()
        self.storage_service = DMSChartStorageService()

    def get(self, request, store_num: int, tank_index: int):
        mapping = (
            StoreTankMapping.objects.select_related("store", "tank_type")
            .filter(store__store_num=store_num, tank_index=tank_index)
            .first()
        )

        if not mapping:
            return drf_error_response(
                request=request,
                code="tank_mapping_not_found",
                message="No tank mapping found for store and tank index.",
                details={"store_num": store_num, "tank_index": tank_index},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        chart = self.chart_service.build(
            store_num=store_num,
            tank_index=tank_index,
        )

        existing = self.storage_service.find_existing(
            store_num=store_num,
            fuel_type=mapping.fuel_type,
            tank_index=tank_index,
        )
        is_stale = (
            self.storage_service.is_stale(
                document=existing,
                store_num=store_num,
                tank_index=tank_index,
            )
            if existing
            else True
        )

        download_url = None
        if existing and not is_stale:
            download_url = self.storage_service.get_download_url(
                store_num=store_num,
                fuel_type=mapping.fuel_type,
                tank_index=tank_index,
            )

        payload = {
            "store_num": store_num,
            "fuel_type": mapping.fuel_type,
            "tank_index": tank_index,
            "official_row_count": chart.official_row_count,
            "generated_at": chart.generated_at.isoformat(),
            "has_cached_document": existing is not None,
            "is_stale": is_stale,
            "download_url": download_url,
        }
        return drf_success_response(data=payload)


class StoreChartPDFAPIView(APIView):
    """Get a store-wide chart PDF for all mapped tanks at a store."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = TankChartService()

    def get(self, request, store_num: int):
        result = self.orchestrator.get_store_chart(store_num=store_num)

        if not result["success"]:
            return drf_error_response(
                request=request,
                code=result.get("code", "store_chart_generation_failed"),
                message=result.get("message", "Error getting store chart."),
                details=result.get("details") or {"store_num": store_num},
                status_code=result.get("status_code", 500),
            )

        download_url = result.get("download_url")
        if download_url:
            return HttpResponseRedirect(download_url)

        return drf_error_response(
            request=request,
            code="store_chart_url_missing",
            message="Chart generated but download URL unavailable.",
            details={"store_num": store_num},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class StoreChartStatusAPIView(APIView):
    """Read-only API view for checking store tank chart status."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = TankChartService()

    def get(self, request, store_num: int):
        result = self.orchestrator.get_chart_status(store_num=store_num)

        if not result["success"]:
            return drf_error_response(
                request=request,
                code=result.get("code", "store_status_failed"),
                message=result.get("message", "Failed to retrieve store chart status."),
                details={"store_num": store_num},
                status_code=result.get("status_code", 404),
            )

        return drf_success_response(data=result["data"])


class TankChartBatchGenerateAPIView(APIView):
    """Generate all tank charts for a store."""

    permission_classes = [IsAdminUser]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.storage_service = DMSChartStorageService()

    def post(self, request, store_num: int):
        force = str(request.data.get("force", "false")).lower() in {
            "true",
            "1",
            "yes",
            "y",
        }
        summary = self.storage_service.batch_generate(store_num=store_num, force=force)
        return drf_success_response(data=summary)


class ChartEmailAnonThrottle(AnonRateThrottle):
    scope = "chart_email_anon"


class ChartEmailUserThrottle(UserRateThrottle):
    scope = "chart_email_user"


class StoreChartEmailAPIView(APIView):
    """
    Commander's Intent:
    Delivers the store-wide tank chart PDF to a field operator's email inbox.
    If chart generation or SMTP delivery fails, the response includes a
    download_url so the operator is never left without a way to get the chart.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ChartEmailAnonThrottle, ChartEmailUserThrottle]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = TankChartService()
        self.email_service = EmailChartService()

    def post(self, request, store_num: int):
        # --- Resolve recipient email ---
        body_email = (request.data.get("email") or "").strip()

        if body_email:
            recipient_email = body_email
        elif request.user.is_authenticated and request.user.email:
            recipient_email = request.user.email
        else:
            return drf_error_response(
                request=request,
                code="email_required",
                message="Email address is required. Provide 'email' in request body.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # --- Idempotency key (60s window, ULID format recommended) ---
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if idempotency_key:
            cache_key = f"chart_email_idempotency:{store_num}:{idempotency_key}"
            cached = cache.get(cache_key)
            if cached is not None:
                return drf_success_response(data=cached)

        # --- Resolve store ---
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            return drf_error_response(
                request=request,
                code="store_not_found",
                message=f"Store #{store_num} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # --- Get or generate chart PDF ---
        chart_result = self.chart_service.get_store_chart(store_num=store_num)
        if not chart_result["success"]:
            return drf_error_response(
                request=request,
                code="chart_generation_unavailable",
                message=chart_result.get(
                    "message", "Store chart could not be generated."
                ),
                details={
                    "store_num": store_num,
                    "reason": chart_result.get("message", ""),
                },
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        document = chart_result.get("document")
        chart_source = chart_result.get("source", "")

        # --- Extract request telemetry for access log ---
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        trace_id = (
            request.META.get("HTTP_X_TRACE_ID")
            or request.META.get("HTTP_X_REQUEST_ID")
            or ""
        )
        user = request.user if request.user.is_authenticated else None

        # --- Send email ---
        email_result = self.email_service.send_store_chart(
            store=store,
            document=document,
            recipient_email=recipient_email,
        )

        delivery_status = email_result.get("status")

        # --- Log access ---
        AccessLogger.log_access(
            store=store,
            delivery_method="email",
            status="success" if delivery_status == "success" else "failed",
            chart_document=document,
            chart_source=chart_source,
            recipient_email=recipient_email,
            user=user,
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=email_result.get("failure_reason", ""),
        )

        if delivery_status == "success":
            success_payload = {
                "message": email_result.get(
                    "message",
                    f"Tank chart for store {store_num} sent to {recipient_email}",
                )
            }
            # Cache idempotency result
            if idempotency_key:
                cache.set(
                    cache_key, success_payload, timeout=_IDEMPOTENCY_WINDOW_SECONDS
                )
            return drf_success_response(data=success_payload)

        return drf_error_response(
            request=request,
            code=email_result.get("code", "email_delivery_failed"),
            message=email_result.get(
                "message", "Failed to deliver email. Download directly instead."
            ),
            details={"download_url": email_result.get("download_url", "")},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
