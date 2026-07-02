import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from dms.api.mixins import StandardAPIResponseMixin
from dms.api.permissions import IsStaffOrAdminPermission
from dms.models import Tag
from dms.serializers import DocumentSerializer, FinalizeUploadRequestSerializer
from dms.services.upload_service import DocumentUploadService


logger = logging.getLogger(__name__)


class RawUploadView(APIView, StandardAPIResponseMixin):
    """
    POST /api/v1/upload/raw/
    Phase A: Upload a raw file, verify MIME, return temp_id.
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdminPermission]

    def post(self, request) -> Response:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            logger.warning(
                "dms.api.raw_upload.missing_file user_id=%s",
                getattr(request.user, "id", None),
            )
            return self.error_response(
                "No file provided in the request.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = DocumentUploadService.handle_raw_upload(
                uploaded_file, request.user
            )
            return self.success_response(result, status_code=status.HTTP_201_CREATED)
        except ValueError as value_error:
            logger.warning(
                "dms.api.raw_upload.validation_failed user_id=%s message=%s",
                getattr(request.user, "id", None),
                str(value_error),
            )
            return self.error_response(
                str(value_error),
                code="upload_validation_error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "dms.api.raw_upload.unexpected_error user_id=%s",
                getattr(request.user, "id", None),
            )
            return self.error_response(
                "Unexpected server error during raw upload.",
                code="upload_internal_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FinalizeUploadView(APIView, StandardAPIResponseMixin):
    """
    POST /api/v1/upload/finalize/
    Phase B: Finalize upload from temp_id, providing metadata.
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdminPermission]

    def post(self, request) -> Response:
        request_serializer = FinalizeUploadRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            logger.warning(
                "dms.api.finalize_upload.validation_failed user_id=%s",
                getattr(request.user, "id", None),
            )
            return self.error_response(
                message="Validation error",
                code="validation_error",
                details=request_serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = request_serializer.validated_data
        temp_id = validated_data["temp_id"]
        title = validated_data["title"]
        description = validated_data.get("description", "")
        category_id = validated_data.get("category")
        collection_ids = validated_data.get("collections", [])
        content_type_val = validated_data.get("content_type")
        object_id = validated_data.get("object_id")
        is_public = validated_data.get("is_public", False)
        tags_input = validated_data.get("tags", [])

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
                elif content_type_val == "store":
                    ct = ContentType.objects.get(app_label="tankgauge", model="store")
                    content_type_id = ct.id
                    if object_id and (
                        isinstance(object_id, int) or object_id.isdigit()
                    ):
                        from tankgauge.models.store_models import Store

                        store = Store.objects.filter(store_num=int(object_id)).first()
                        if store:
                            resolved_object_id = str(store.id)
                        else:
                            logger.warning(
                                "dms.api.finalize_upload.store_not_found user_id=%s requested_store_num=%s",
                                getattr(request.user, "id", None),
                                object_id,
                            )
                            return self.error_response(
                                f"Store #{object_id} not found in database.",
                                status_code=status.HTTP_404_NOT_FOUND,
                            )
            except ContentType.DoesNotExist:
                logger.warning(
                    "dms.api.finalize_upload.invalid_content_type user_id=%s content_type=%s",
                    getattr(request.user, "id", None),
                    content_type_val,
                )
                return self.error_response(
                    f"Invalid content type: {content_type_val}",
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
            serializer = DocumentSerializer(
                document,
                context={"include_linked_object": True},
            )
            return self.success_response(
                serializer.data, status_code=status.HTTP_201_CREATED
            )
        except ValueError as value_error:
            logger.warning(
                "dms.api.finalize_upload.failed user_id=%s message=%s",
                getattr(request.user, "id", None),
                str(value_error),
            )
            return self.error_response(
                str(value_error),
                code="finalize_upload_error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "dms.api.finalize_upload.unexpected_error user_id=%s",
                getattr(request.user, "id", None),
            )
            return self.error_response(
                "Unexpected server error during finalize upload.",
                code="finalize_upload_internal_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
