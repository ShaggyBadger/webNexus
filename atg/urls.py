from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.api_views import (
    VeederTicketViewSet,
    VeederReadingViewSet,
    VeederStatsView,
    StoreViewSet,
    StoreTankProfileAPIView,
    VeederQuickCaptureAPIView,
)
from .views.ticket_views import VeederUploadView
from .views.dashboard_views import VeederListView, VeederDetailView
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
        "api/v1/tickets/quick-capture/",
        VeederQuickCaptureAPIView.as_view(),
        name="ticket_quick_capture",
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
    path("archive/", VeederListView.as_view(), name="veeder_list"),
    path("archive/<str:pk>/", VeederDetailView.as_view(), name="veeder_detail"),
]
