import logging

from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView

from tankgauge.models import StoreTankMapping
from tankgauge.views.api.error_contract import drf_error_response, drf_success_response
from tankcharts.rendering import PDFRenderer
from tankcharts.services import DMSChartStorageService, TankFieldChartService

logger = logging.getLogger("tankcharts")


class TankChartPDFAPIView(APIView):
    """Get chart PDF for store/tank, generating when missing or stale."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = TankFieldChartService()
        self.pdf_renderer = PDFRenderer()
        self.storage_service = DMSChartStorageService()

    def get(self, request, store_num: int, tank_index: int):
        mapping = (
            StoreTankMapping.objects.filter(
                store__store_num=store_num,
                tank_index=tank_index,
            )
            .order_by("id")
            .first()
        )
        if not mapping:
            return drf_error_response(
                request=request,
                code="tank_not_found",
                message="Tank mapping not found for this store and tank index.",
                details={"store_num": store_num, "tank_index": tank_index},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        fuel_type = mapping.fuel_type or "unknown"
        existing = self.storage_service.find_existing(
            store_num=store_num,
            fuel_type=fuel_type,
            tank_index=tank_index,
        )

        if existing and not self.storage_service.is_stale(
            document=existing,
            store_num=store_num,
            tank_index=tank_index,
        ):
            download_url = self.storage_service.get_download_url(
                store_num=store_num,
                fuel_type=fuel_type,
                tank_index=tank_index,
            )
            if download_url:
                return HttpResponseRedirect(download_url)

        try:
            chart = self.chart_service.build(store_num=store_num, tank_index=tank_index)
            pdf_bytes = self.pdf_renderer.render(chart)
            metadata = {
                "store_num": chart.store_num,
                "tank_index": chart.tank_index,
                "fuel_type": chart.fuel_type,
                "official_row_count": chart.official_row_count,
                "veeder_count": chart.veeder_observation_count,
                "estimation_id": chart.estimation_id,
                "generated_at": chart.generated_at.isoformat(),
            }
            document = self.storage_service.store(
                store_num=store_num,
                fuel_type=chart.fuel_type,
                tank_index=tank_index,
                pdf_bytes=pdf_bytes,
                metadata=metadata,
            )
            logger.info(
                "TANKCHART_PDF_GENERATED",
                extra={
                    "store_num": store_num,
                    "tank_index": tank_index,
                    "document_id": document.id,
                },
            )
            return HttpResponseRedirect(
                self.storage_service.get_download_url(
                    store_num=store_num,
                    fuel_type=chart.fuel_type,
                    tank_index=tank_index,
                )
            )
        except ValueError as error:
            return drf_error_response(
                request=request,
                code="chart_generation_unavailable",
                message=str(error),
                details={"store_num": store_num, "tank_index": tank_index},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as error:
            logger.exception(
                "TANKCHART_PDF_GENERATION_FAILED",
                extra={"store_num": store_num, "tank_index": tank_index},
            )
            return drf_error_response(
                request=request,
                code="chart_generation_failed",
                message="Failed to generate tank field chart PDF.",
                details={"error": str(error)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TankChartMetaAPIView(APIView):
    """Return tank chart metadata and freshness status."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = TankFieldChartService()
        self.storage_service = DMSChartStorageService()

    def get(self, request, store_num: int, tank_index: int):
        mapping = (
            StoreTankMapping.objects.select_related("store")
            .filter(store__store_num=store_num, tank_index=tank_index)
            .first()
        )
        if not mapping:
            return drf_error_response(
                request=request,
                code="tank_not_found",
                message="Tank mapping not found for this store and tank index.",
                details={"store_num": store_num, "tank_index": tank_index},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        fuel_type = mapping.fuel_type or "unknown"
        existing = self.storage_service.find_existing(
            store_num=store_num,
            fuel_type=fuel_type,
            tank_index=tank_index,
        )
        is_stale = False
        if existing:
            is_stale = self.storage_service.is_stale(
                document=existing,
                store_num=store_num,
                tank_index=tank_index,
            )

        has_official = False
        has_estimation = False
        coverage_percent = 0.0
        veeder_count = 0

        try:
            chart = self.chart_service.build(store_num=store_num, tank_index=tank_index)
            has_official = chart.has_official_chart
            has_estimation = chart.estimation_id is not None
            coverage_percent = chart.coverage_percent
            veeder_count = chart.veeder_observation_count
        except Exception:
            has_official = False
            has_estimation = False

        return drf_success_response(
            data={
                "store_num": store_num,
                "tank_index": tank_index,
                "fuel_type": fuel_type,
                "has_official": has_official,
                "has_estimation": has_estimation,
                "coverage_percent": coverage_percent,
                "veeder_count": veeder_count,
                "available": existing is not None,
                "is_stale": is_stale,
                "dms_document_id": existing.id if existing else None,
                "generated_at": existing.uploaded_at.isoformat() if existing else None,
            }
        )


class StoreChartPDFAPIView(APIView):
    """Get a store-wide chart PDF for all mapped tanks at a store."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = TankFieldChartService()
        self.pdf_renderer = PDFRenderer()
        self.storage_service = DMSChartStorageService()

    def get(self, request, store_num: int):
        has_mappings = StoreTankMapping.objects.filter(
            store__store_num=store_num
        ).exists()
        if not has_mappings:
            return drf_error_response(
                request=request,
                code="store_not_found",
                message="Store has no mapped tanks.",
                details={"store_num": store_num},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        existing = self.storage_service.find_existing_store(store_num=store_num)
        if existing and not self.storage_service.is_store_stale(
            document=existing,
            store_num=store_num,
        ):
            download_url = self.storage_service.get_store_download_url(
                store_num=store_num
            )
            if download_url:
                return HttpResponseRedirect(download_url)

        try:
            chart = self.chart_service.build_store(store_num=store_num)
            tank_chunks = self.chart_service.chunk_store_tanks(chart, page_size=4)
            pdf_bytes = self.pdf_renderer.render_store(
                chart,
                tank_chunks=tank_chunks,
            )

            metadata = {
                "store_num": chart.store_num,
                "tank_count": len(chart.tanks),
                "tank_indices": [tank.tank_index for tank in chart.tanks],
                "official_row_counts": {
                    str(tank.tank_index): tank.official_row_count
                    for tank in chart.tanks
                },
                "generated_at": chart.generated_at.isoformat(),
            }
            document = self.storage_service.store_store_chart(
                store_num=store_num,
                pdf_bytes=pdf_bytes,
                metadata=metadata,
            )
            logger.info(
                "STORE_TANKCHART_PDF_GENERATED",
                extra={
                    "store_num": store_num,
                    "document_id": document.id,
                    "tank_count": len(chart.tanks),
                },
            )
            return HttpResponseRedirect(
                self.storage_service.get_store_download_url(store_num=store_num)
            )
        except ValueError as error:
            return drf_error_response(
                request=request,
                code="store_chart_generation_unavailable",
                message=str(error),
                details={"store_num": store_num},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as error:
            logger.exception(
                "STORE_TANKCHART_PDF_GENERATION_FAILED",
                extra={"store_num": store_num},
            )
            return drf_error_response(
                request=request,
                code="store_chart_generation_failed",
                message="Failed to generate store-wide tank chart PDF.",
                details={"error": str(error)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
