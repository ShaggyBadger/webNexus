import logging

from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView

from tankgauge.views.api.error_contract import (
    drf_error_response,
    drf_success_response,
)
from tankcharts.rendering import PDFRenderer
from tankcharts.services import (
    DMSChartStorageService,
    TankChartService,
)
from tankcharts.services.field_chart_service import TankFieldChartService
from tankgauge.models import StoreTankMapping

logger = logging.getLogger(__name__)


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
