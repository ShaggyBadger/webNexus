from typing import Any, Dict
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.request import Request
from rest_framework.response import Response

from dms.models import Document
from dms.services.hub_search_service import HubSearchService
from tankgauge.models import Store
from tankgauge.views.api.error_contract import (
    drf_success_response,
    drf_error_response,
)


class HubSearchAnonRateThrottle(AnonRateThrottle):
    scope = "hub_search"


class LocationHubSearchAPIView(APIView):
    """
    Search endpoint for Location Document Hub.
    Returns matching locations and documents for a given search query.
    """

    permission_classes = [AllowAny]
    throttle_classes = [HubSearchAnonRateThrottle]

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "")
        default_limit = settings.HUB_SEARCH_LIMIT
        try:
            limit = int(request.query_params.get("limit", default_limit))
        except (ValueError, TypeError):
            limit = default_limit

        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0

        public_only = not request.user.is_authenticated

        results = HubSearchService.search(
            query=query,
            limit=limit,
            offset=offset,
            public_only=public_only,
        )

        return drf_success_response(data=results)


class LocationDocumentSummaryAPIView(APIView):
    """
    Location Document Summary endpoint for Location Document Hub.
    Returns location details, grouped documents by category, and tank chart status.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, store_num: int) -> Response:
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            return drf_error_response(
                request=request,
                code="STORE_NOT_FOUND",
                message=f"Store #{store_num} was not found.",
                status_code=404,
            )

        public_only = not request.user.is_authenticated
        store_ct = ContentType.objects.get_for_model(Store)

        # Lazy import of ChartStatusService per intent / service-level dependency
        from tankcharts.services.status_service import ChartStatusService

        chart_status_service = ChartStatusService()
        chart_status = chart_status_service.get_status(store)

        # Fetch tanks for store
        tank_mappings = store.tank_mappings.select_related("tank_type").order_by(
            "tank_index"
        )
        tanks_data = []
        for tm in tank_mappings:
            tanks_data.append(
                {
                    "fuel_type": tm.fuel_type or "Unknown",
                    "tank_index": tm.tank_index or 1,
                }
            )

        # Fetch documents linked to store via GenericFK
        doc_qs = (
            Document.objects.filter(
                content_type=store_ct,
                object_id=str(store.id),
                status="ACTIVE",
            )
            .select_related("category")
            .order_by("title")
        )

        if public_only:
            doc_qs = doc_qs.filter(is_public=True)

        grouped_docs: Dict[str, Any] = {
            "Tank Chart": {
                "category": "Tank Chart",
                "chart_status": chart_status,
                "download_url": (
                    f"/tankcharts/store/{store_num}/download/"
                    if chart_status.get("cache_state") != "missing"
                    else None
                ),
                "tanks": tanks_data,
            }
        }

        for doc in doc_qs:
            cat_name = doc.category.name if doc.category else "Other Documents"
            if cat_name == "Tank Chart":
                continue  # Managed by chart_status block

            if cat_name not in grouped_docs:
                grouped_docs[cat_name] = {
                    "category": cat_name,
                    "documents": [],
                }

            grouped_docs[cat_name]["documents"].append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "file_size": doc.file_size,
                    "download_url": f"/dms/documents/{doc.id}/download/",
                }
            )

        location_data = {
            "store_num": store.store_num,
            "store_name": store.store_name or f"STORE #{store.store_num}",
            "city": store.city or "",
            "state": store.state or "",
            "address": store.address or "",
        }

        return drf_success_response(
            data={
                "location": location_data,
                "documents": grouped_docs,
            }
        )
