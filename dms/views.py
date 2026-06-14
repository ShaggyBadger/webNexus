import os
from django.db import transaction
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone


from dms.models import Category, Collection, Document, TemporaryUpload, Tag
from dms.serializers import (
    CategorySerializer,
    CollectionSerializer,
    DocumentSerializer,
    DocumentUpdateSerializer,
    TagSerializer,
)
from dms.services.upload_service import DocumentUploadService
from dms.services.download_service import DocumentDownloadService
from dms.services.search_service import DocumentSearchService
from dms.pagination import DMSSerializedPagination


class StandardAPIResponseMixin:
    """
    Mixin to standardize API responses in DMS.
    """

    def success_response(
        self, data, meta=None, status_code=status.HTTP_200_OK
    ) -> Response:
        meta_data = {
            "version": "1.0",
            "timestamp": timezone.now().isoformat(),
        }
        if meta:
            meta_data.update(meta)
        return Response(
            {
                "status": "success",
                "data": data,
                "meta": meta_data,
                "error": None,
            },
            status=status_code,
        )

    def error_response(
        self,
        message,
        code="api_error",
        details=None,
        status_code=status.HTTP_400_BAD_REQUEST,
    ) -> Response:
        return Response(
            {
                "status": "error",
                "data": None,
                "meta": {
                    "version": "1.0",
                    "timestamp": timezone.now().isoformat(),
                },
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                },
            },
            status=status_code,
        )


class IsStaffOrAdminPermission(permissions.BasePermission):
    """
    Permission class checking if the user is a staff member or administrator.
    """

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and (request.user.is_staff or request.user.is_superuser)
        )


class CategoryListView(APIView, StandardAPIResponseMixin):
    """
    GET /api/dms/v1/categories/
    List all active categories.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        categories = Category.objects.filter(active=True)
        serializer = CategorySerializer(categories, many=True)
        return self.success_response(serializer.data)


class CollectionListView(APIView, StandardAPIResponseMixin):
    """
    GET /api/dms/v1/collections/
    List all active collections.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        collections = Collection.objects.all()
        # If standard user, filter collections to only public ones
        if not (request.user.is_staff or request.user.is_superuser):
            collections = collections.filter(is_public=True)

        serializer = CollectionSerializer(collections, many=True)
        return self.success_response(serializer.data)


class TagListView(APIView, StandardAPIResponseMixin):
    """
    GET /api/dms/v1/tags/
    List all tags.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        tags = Tag.objects.all()
        serializer = TagSerializer(tags, many=True)
        return self.success_response(serializer.data)


class DocumentListCreateView(APIView, StandardAPIResponseMixin):
    """
    GET /api/dms/v1/documents/
    List documents with server-side pagination, filtering, and search.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        # Get query parameters
        search_query = request.query_params.get("q")
        category_id = request.query_params.get("category")
        category_slug = request.query_params.get("category_slug")
        collection_id = request.query_params.get("collection")
        status_filter = request.query_params.get(
            "status", "ACTIVE"
        )  # Default to ACTIVE documents
        uploaded_by_id = request.query_params.get("uploaded_by")
        upload_date_start = request.query_params.get("upload_date_start")
        upload_date_end = request.query_params.get("upload_date_end")
        tag_id = request.query_params.get("tag")
        tag_slug = request.query_params.get("tag_slug")
        state_filter = request.query_params.get("state")

        # Standard users can only view ACTIVE documents
        is_public_only = not (request.user.is_staff or request.user.is_superuser)
        if is_public_only:
            status_filter = "ACTIVE"

        queryset = Document.objects.all()

        # Filter queryset based on service layer
        queryset = DocumentSearchService.search_documents(
            queryset=queryset,
            search_query=search_query,
            category_id=category_id,
            category_slug=category_slug,
            collection_id=collection_id,
            status=status_filter,
            uploaded_by_id=uploaded_by_id,
            upload_date_start=upload_date_start,
            upload_date_end=upload_date_end,
            state=state_filter,
            tag_id=tag_id,
            tag_slug=tag_slug,
            is_public_only=is_public_only,
        )

        paginator = DMSSerializedPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = DocumentSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = DocumentSerializer(queryset, many=True)
        return self.success_response(serializer.data)


class DocumentDetailView(APIView, StandardAPIResponseMixin):
    """
    GET /api/dms/v1/documents/<ulid>/ -> Get metadata
    PATCH /api/dms/v1/documents/<ulid>/ -> Update metadata (Staff/Admin only)
    DELETE /api/dms/v1/documents/<ulid>/ -> Soft-delete/Archive document (Staff/Admin only)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ["PATCH", "DELETE"]:
            return [permissions.IsAuthenticated(), IsStaffOrAdminPermission()]
        return super().get_permissions()

    def get_object(self, ulid: str) -> Document:
        try:
            document = Document.objects.get(id=ulid)
            # Standard users cannot see non-active or non-public documents
            if not (self.request.user.is_staff or self.request.user.is_superuser):
                if document.status != "ACTIVE" or not document.is_public:
                    raise Http404("Document not found.")
            return document
        except Document.DoesNotExist:
            raise Http404("Document not found.")

    def get(self, request, ulid: str) -> Response:
        document = self.get_object(ulid)
        serializer = DocumentSerializer(document)
        return self.success_response(serializer.data)

    def patch(self, request, ulid: str) -> Response:
        document = self.get_object(ulid)

        # Parse and resolve tags if provided as tag names or slugs
        data = request.data.copy()
        tags_input = data.get("tags")
        if tags_input is not None:
            tag_ids = []
            from django.utils.text import slugify

            for tag_item in tags_input:
                if isinstance(tag_item, int) or (
                    isinstance(tag_item, str) and tag_item.isdigit()
                ):
                    tag_ids.append(int(tag_item))
                elif isinstance(tag_item, str) and tag_item.strip():
                    name = tag_item.strip()
                    slug = slugify(name)
                    tag_obj, _ = Tag.objects.get_or_create(
                        slug=slug, defaults={"name": name}
                    )
                    tag_ids.append(tag_obj.id)
            data["tags"] = tag_ids

        serializer = DocumentUpdateSerializer(document, data=data, partial=True)
        if serializer.is_valid():
            updated_doc = serializer.save()
            return self.success_response(DocumentSerializer(updated_doc).data)
        return self.error_response(
            message="Validation error",
            code="validation_error",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, ulid: str) -> Response:
        """
        Soft-delete a document: Move physical file to trash and update status to ARCHIVED.
        """
        document = self.get_object(ulid)
        if document.status == "ARCHIVED":
            return self.error_response(
                "Document is already archived.", status_code=status.HTTP_400_BAD_REQUEST
            )

        original_file_path = document.file_path
        filename = os.path.basename(original_file_path)
        trash_relative_path = os.path.join("trash", filename)

        with transaction.atomic():
            # 1. Move file in filesystem using default_storage
            if default_storage.exists(original_file_path):
                # Read content
                with default_storage.open(original_file_path, "rb") as f:
                    content = f.read()
                # Save to trash
                from django.core.files.base import ContentFile

                default_storage.save(trash_relative_path, ContentFile(content))
                # Delete original
                default_storage.delete(original_file_path)

            # 2. Update Database Record
            document.status = "ARCHIVED"
            document.file_path = trash_relative_path
            document.save(update_fields=["status", "file_path"])

        return self.success_response(
            {"message": "Document successfully soft-deleted/archived."}
        )


class RawUploadView(APIView, StandardAPIResponseMixin):
    """
    POST /api/dms/v1/upload/raw/
    Phase A: Upload a raw file, verify MIME, return temp_id.
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdminPermission]

    def post(self, request) -> Response:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return self.error_response(
                "No file provided in the request.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = DocumentUploadService.handle_raw_upload(
                uploaded_file, request.user
            )
            return self.success_response(result, status_code=status.HTTP_201_CREATED)
        except Exception as e:
            return self.error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)


class FinalizeUploadView(APIView, StandardAPIResponseMixin):
    """
    POST /api/dms/v1/upload/finalize/
    Phase B: Finalize upload from temp_id, providing metadata.
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdminPermission]

    def post(self, request) -> Response:
        temp_id = request.data.get("temp_id")
        title = request.data.get("title")
        description = request.data.get("description", "")
        category_id = request.data.get("category")
        collection_ids = request.data.get("collections", [])
        content_type_val = request.data.get("content_type")
        object_id = request.data.get("object_id")
        is_public = request.data.get("is_public", False)
        tags_input = request.data.get("tags", [])

        # Standardize is_public to boolean
        if isinstance(is_public, str):
            is_public = is_public.lower() in ["true", "1", "yes"]

        # Parse and resolve tags if provided as tag names or slugs
        tag_ids = []
        if tags_input:
            from django.utils.text import slugify

            for tag_item in tags_input:
                if isinstance(tag_item, int) or (
                    isinstance(tag_item, str) and tag_item.isdigit()
                ):
                    tag_ids.append(int(tag_item))
                elif isinstance(tag_item, str) and tag_item.strip():
                    name = tag_item.strip()
                    slug = slugify(name)
                    tag_obj, _ = Tag.objects.get_or_create(
                        slug=slug, defaults={"name": name}
                    )
                    tag_ids.append(tag_obj.id)

        content_type_id = None
        resolved_object_id = object_id

        if content_type_val:
            from django.contrib.contenttypes.models import ContentType

            try:
                if content_type_val == "location":
                    content_type_id = ContentType.objects.get(
                        app_label="siteintel", model="location"
                    ).id
                    # Note: For locations, we currently assume the ID is the PK (often ULID or Int).
                elif content_type_val == "store":
                    ct = ContentType.objects.get(app_label="tankgauge", model="store")
                    content_type_id = ct.id
                    # Resolve store_num to PK
                    if object_id and (
                        isinstance(object_id, int) or object_id.isdigit()
                    ):
                        from tankgauge.models.store_models import Store

                        store = Store.objects.filter(store_num=int(object_id)).first()
                        if store:
                            resolved_object_id = str(store.id)
                        else:
                            return self.error_response(
                                f"Store #{object_id} not found in database.",
                                status_code=status.HTTP_404_NOT_FOUND,
                            )
            except ContentType.DoesNotExist:
                return self.error_response(
                    f"Invalid content type: {content_type_val}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        if not temp_id or not title:
            return self.error_response(
                "temp_id and title are required fields.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = DocumentUploadService.finalize_upload(
                temp_id=temp_id,
                user=request.user,
                title=title,
                description=description,
                category_id=category_id,
                collection_ids=collection_ids,
                content_type_id=content_type_id,
                object_id=resolved_object_id,
                is_public=is_public,
                tag_ids=tag_ids,
            )
            serializer = DocumentSerializer(document)
            return self.success_response(
                serializer.data, status_code=status.HTTP_201_CREATED
            )
        except ValueError as ve:
            return self.error_response(str(ve), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.error_response(
                str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentDownloadView(APIView):
    """
    GET /dms/documents/<ulid>/download/
    Routed download endpoint: verifies permissions, increments count, serves file.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ulid: str) -> FileResponse:
        try:
            file_obj, filename, mime_type = DocumentDownloadService.prepare_download(
                ulid
            )
            response = FileResponse(file_obj, content_type=mime_type)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except ValueError as ve:
            raise Http404(str(ve))
        except FileNotFoundError as fnfe:
            # TODO: Future enhancement - replace generic 404 with a custom "Missing File"
            # error page or administrative notification workflow.
            raise Http404(str(fnfe))


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Template view to display the DMS dashboard.
    """

    template_name = "dms/dashboard.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(active=True)
        context["tags"] = Tag.objects.all()

        collections = Collection.objects.all()
        # Non-staff/superuser can only see public collections
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            collections = collections.filter(is_public=True)
        context["collections"] = collections

        # Pull filtering params for server-rendered initial context
        search_query = self.request.GET.get("q")
        category_id = self.request.GET.get("category")
        collection_id = self.request.GET.get("collection")
        tag_id = self.request.GET.get("tag")
        tag_slug = self.request.GET.get("tag_slug")
        state_filter = self.request.GET.get("state")
        status_filter = self.request.GET.get("status", "ACTIVE")

        # Standard users only see ACTIVE and PUBLIC
        is_public_only = not (
            self.request.user.is_staff or self.request.user.is_superuser
        )
        if is_public_only:
            status_filter = "ACTIVE"

        queryset = DocumentSearchService.search_documents(
            search_query=search_query,
            category_id=category_id,
            collection_id=collection_id,
            status=status_filter,
            state=state_filter,
            tag_id=tag_id,
            tag_slug=tag_slug,
            is_public_only=is_public_only,
        )

        context["documents"] = queryset
        return context
