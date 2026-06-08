from django.urls import path
from dms.views import (
    CategoryListView,
    TagListView,
    CollectionListView,
    DocumentListCreateView,
    DocumentDetailView,
    RawUploadView,
    FinalizeUploadView,
    DocumentDownloadView,
    DashboardView,
)

app_name = "dms"

urlpatterns = [
    # Dashboard route
    path("", DashboardView.as_view(), name="dashboard"),
    # Document download routed path
    path(
        "documents/<str:ulid>/download/",
        DocumentDownloadView.as_view(),
        name="document_download",
    ),
    # API endpoints
    path("api/dms/v1/categories/", CategoryListView.as_view(), name="api_categories"),
    path("api/dms/v1/tags/", TagListView.as_view(), name="api_tags"),
    path(
        "api/dms/v1/collections/",
        CollectionListView.as_view(),
        name="api_collections",
    ),
    path("api/dms/v1/documents/", DocumentListCreateView.as_view(), name="api_documents"),
    path(
        "api/dms/v1/documents/<str:ulid>/",
        DocumentDetailView.as_view(),
        name="api_document_detail",
    ),
    path("api/dms/v1/upload/raw/", RawUploadView.as_view(), name="api_raw_upload"),
    path(
        "api/dms/v1/upload/finalize/",
        FinalizeUploadView.as_view(),
        name="api_finalize_upload",
    ),
]
