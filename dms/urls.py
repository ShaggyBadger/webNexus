from django.urls import path
from dms.api.views import (
    CategoryListView,
    TagListView,
    CollectionListView,
    DocumentListCreateView,
    DocumentDetailView,
    RawUploadView,
    FinalizeUploadView,
    DocumentDownloadView,
)
from dms.views import DashboardView, DocumentMetadataEditView, DocumentUploadView

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
    path(
        "documents/<str:ulid>/edit/",
        DocumentMetadataEditView.as_view(),
        name="document_edit",
    ),
    path("upload/", DocumentUploadView.as_view(), name="upload_page"),
    # API endpoints (primary v1 paths)
    path("api/v1/categories/", CategoryListView.as_view(), name="api_categories"),
    path("api/v1/tags/", TagListView.as_view(), name="api_tags"),
    path("api/v1/collections/", CollectionListView.as_view(), name="api_collections"),
    path("api/v1/documents/", DocumentListCreateView.as_view(), name="api_documents"),
    path(
        "api/v1/documents/<str:ulid>/",
        DocumentDetailView.as_view(),
        name="api_document_detail",
    ),
    path("api/v1/upload/raw/", RawUploadView.as_view(), name="api_raw_upload"),
    path(
        "api/v1/upload/finalize/",
        FinalizeUploadView.as_view(),
        name="api_finalize_upload",
    ),
    # Legacy compatibility aliases
    path(
        "api/dms/v1/categories/",
        CategoryListView.as_view(),
        name="api_categories_legacy",
    ),
    path("api/dms/v1/tags/", TagListView.as_view(), name="api_tags_legacy"),
    path(
        "api/dms/v1/collections/",
        CollectionListView.as_view(),
        name="api_collections_legacy",
    ),
    path(
        "api/dms/v1/documents/",
        DocumentListCreateView.as_view(),
        name="api_documents_legacy",
    ),
    path(
        "api/dms/v1/documents/<str:ulid>/",
        DocumentDetailView.as_view(),
        name="api_document_detail_legacy",
    ),
    path(
        "api/dms/v1/upload/raw/",
        RawUploadView.as_view(),
        name="api_raw_upload_legacy",
    ),
    path(
        "api/dms/v1/upload/finalize/",
        FinalizeUploadView.as_view(),
        name="api_finalize_upload_legacy",
    ),
]
