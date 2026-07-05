from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.api_views import (
    VeederTicketViewSet,
    VeederReadingViewSet,
    VeederStatsView,
    StoreViewSet,
    StoreTankProfileAPIView,
    VeederQuickCaptureAPIView,
    VeederReadingsPreflightAPIView,
)
from .views.review_api_views import (
    FuelTypeListAPIView,
    VeederReviewQueueDetailAPIView,
    VeederReviewQueueFinalizeAPIView,
    VeederReviewQueueListAPIView,
)
from .views.ticket_views import VeederUploadView
from .views.dashboard_views import VeederListView, VeederDetailView
from .views.review_views import VeederReviewQueueView
from .views.remote_ocr_views import (
    RemoteOCRInstructionsView,
    RemoteOCRFetchJobView,
    RemoteOCRResolveJobView,
)

app_name = "atg"

router = DefaultRouter()
router.register(r"tickets", VeederTicketViewSet, basename="ticket")
router.register(r"readings", VeederReadingViewSet, basename="reading")
router.register(r"stores", StoreViewSet, basename="store")


urlpatterns = [
    path(
        "api/v1/readings/validate-preflight/",
        VeederReadingsPreflightAPIView.as_view(),
        name="readings_preflight",
    ),
    path(
        "api/v1/tickets/quick-capture/",
        VeederQuickCaptureAPIView.as_view(),
        name="ticket_quick_capture",
    ),
    path(
        "api/v1/review-queue/",
        VeederReviewQueueListAPIView.as_view(),
        name="veeder_review_queue_list",
    ),
    path(
        "api/v1/review-queue/fuel-types/",
        FuelTypeListAPIView.as_view(),
        name="veeder_review_queue_fuel_types",
    ),
    path(
        "api/v1/review-queue/<str:ticket_id>/",
        VeederReviewQueueDetailAPIView.as_view(),
        name="veeder_review_queue_detail",
    ),
    path(
        "api/v1/review-queue/<str:ticket_id>/finalize/",
        VeederReviewQueueFinalizeAPIView.as_view(),
        name="veeder_review_queue_finalize",
    ),
    path("api/v1/", include(router.urls)),
    path("api/v1/stats/", VeederStatsView.as_view(), name="veeder_stats"),
    path(
        "api/v1/stores/<int:store_num>/tank-profile/",
        StoreTankProfileAPIView.as_view(),
        name="store_tank_profile_api",
    ),
    path(
        "api/v1/remote-ocr/instructions/",
        RemoteOCRInstructionsView.as_view(),
        name="remote_ocr_instructions",
    ),
    path(
        "api/v1/remote-ocr/fetch-job/",
        RemoteOCRFetchJobView.as_view(),
        name="remote_ocr_fetch",
    ),
    path(
        "api/v1/remote-ocr/resolve-job/",
        RemoteOCRResolveJobView.as_view(),
        name="remote_ocr_resolve",
    ),
    path("upload/", VeederUploadView.as_view(), name="ticket_upload"),
    path("review-queue/", VeederReviewQueueView.as_view(), name="review_queue"),
    path("archive/", VeederListView.as_view(), name="veeder_list"),
    path("archive/<str:pk>/", VeederDetailView.as_view(), name="veeder_detail"),
]
