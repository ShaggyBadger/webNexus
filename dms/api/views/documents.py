import logging
import os

from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from dms.api.mixins import StandardAPIResponseMixin
from dms.api.permissions import IsStaffOrAdminPermission
from dms.models import Document, Tag
from dms.pagination import DMSSerializedPagination
from dms.serializers import DocumentSerializer, DocumentUpdateSerializer
from dms.services.download_service import DocumentDownloadService
from dms.services.search_service import DocumentSearchService


logger = logging.getLogger(__name__)


class DocumentListCreateView(APIView, StandardAPIResponseMixin):
    """
    GET /api/v1/documents/
    List documents with server-side pagination, filtering, and search.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request) -> Response:
        search_query = request.query_params.get("q")
        category_id = request.query_params.get("category")
        category_slug = request.query_params.get("category_slug")
        collection_id = request.query_params.get("collection")
        status_filter = request.query_params.get("status", "ACTIVE")
        uploaded_by_id = request.query_params.get("uploaded_by")
        upload_date_start = request.query_params.get("upload_date_start")
        upload_date_end = request.query_params.get("upload_date_end")
        tag_id = request.query_params.get("tag")
        tag_slug = request.query_params.get("tag_slug")
        state_filter = request.query_params.get("state")

        is_staff_user = bool(
            request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )
        is_public_only = not request.user.is_authenticated
        if not is_staff_user:
            status_filter = "ACTIVE"

        queryset = DocumentSearchService.search_documents(
            queryset=Document.objects.all(),
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
            serializer = DocumentSerializer(
                page,
                many=True,
                context={"include_linked_object": False},
            )
            return paginator.get_paginated_response(serializer.data)

        serializer = DocumentSerializer(
            queryset,
            many=True,
            context={"include_linked_object": False},
        )
        return self.success_response(serializer.data)


class DocumentDetailView(APIView, StandardAPIResponseMixin):
    """
    GET /api/v1/documents/<ulid>/ -> Get metadata
    PATCH /api/v1/documents/<ulid>/ -> Update metadata (Staff/Admin only)
    DELETE /api/v1/documents/<ulid>/ -> Soft-delete/Archive document (Staff/Admin only)
    """

    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if self.request.method in ["PATCH", "DELETE"]:
            return [permissions.IsAuthenticated(), IsStaffOrAdminPermission()]
        return super().get_permissions()

    def get_object(self, ulid: str) -> Document:
        try:
            document = DocumentSearchService.optimize_queryset(Document.objects).get(
                id=ulid
            )
            is_staff_user = bool(
                self.request.user.is_authenticated
                and (self.request.user.is_staff or self.request.user.is_superuser)
            )
            if not is_staff_user and document.status != "ACTIVE":
                raise Http404("Document not found.")
            if not self.request.user.is_authenticated and not document.is_public:
                raise Http404("Document not found.")
            return document
        except Document.DoesNotExist:
            raise Http404("Document not found.")

    def get(self, request, ulid: str) -> Response:
        document = self.get_object(ulid)
        serializer = DocumentSerializer(
            document,
            context={"include_linked_object": True},
        )
        return self.success_response(serializer.data)

    def patch(self, request, ulid: str) -> Response:
        document = self.get_object(ulid)

        data = request.data.copy()
        tags_input = data.get("tags")
        if tags_input is not None:
            if isinstance(tags_input, str):
                tags_input = [
                    tag.strip() for tag in tags_input.split(",") if tag.strip()
                ]
            elif not isinstance(tags_input, list):
                return self.error_response(
                    message="Validation error",
                    code="validation_error",
                    details={"tags": ["Expected a list of tag values."]},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

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
            return self.success_response(
                DocumentSerializer(
                    updated_doc,
                    context={"include_linked_object": True},
                ).data
            )
        return self.error_response(
            message="Validation error",
            code="validation_error",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, ulid: str) -> Response:
        document = self.get_object(ulid)
        if document.status == "ARCHIVED":
            return self.error_response(
                "Document is already archived.", status_code=status.HTTP_400_BAD_REQUEST
            )

        original_file_path = document.file_path
        filename = os.path.basename(original_file_path)
        trash_relative_path = os.path.join("trash", filename)

        with transaction.atomic():
            if default_storage.exists(original_file_path):
                with default_storage.open(original_file_path, "rb") as file_obj:
                    content = file_obj.read()

                from django.core.files.base import ContentFile

                default_storage.save(trash_relative_path, ContentFile(content))
                default_storage.delete(original_file_path)

            document.status = "ARCHIVED"
            document.file_path = trash_relative_path
            document.save(update_fields=["status", "file_path"])

        logger.info(
            "dms.api.document.archived document_id=%s user_id=%s new_file_path=%s",
            document.id,
            getattr(request.user, "id", None),
            document.file_path,
        )

        return self.success_response(
            {"message": "Document successfully soft-deleted/archived."}
        )


class DocumentDownloadView(APIView):
    """
    GET /dms/documents/<ulid>/download/
    Routed download endpoint: verifies permissions, increments count, serves file.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, ulid: str) -> FileResponse:
        try:
            file_obj, filename, mime_type = DocumentDownloadService.prepare_download(
                ulid, request.user
            )
            response = FileResponse(file_obj, content_type=mime_type)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except PermissionError:
            logger.warning(
                "dms.api.document.download_denied document_id=%s user_id=%s",
                ulid,
                getattr(request.user, "id", None),
            )
            raise Http404("Document not found.")
        except ValueError as value_error:
            logger.warning(
                "dms.api.document.download_invalid document_id=%s user_id=%s message=%s",
                ulid,
                getattr(request.user, "id", None),
                str(value_error),
            )
            raise Http404(str(value_error))
        except FileNotFoundError as not_found_error:
            logger.error(
                "dms.api.document.download_file_missing document_id=%s user_id=%s message=%s",
                ulid,
                getattr(request.user, "id", None),
                str(not_found_error),
            )
            raise Http404(str(not_found_error))
