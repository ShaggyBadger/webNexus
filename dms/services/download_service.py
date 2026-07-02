import logging
import os

from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db import transaction

from dms.models import Document


logger = logging.getLogger(__name__)


class DocumentDownloadService:
    """
    Service to manage document retrieval and download counts.
    """

    @classmethod
    def prepare_download(cls, document_id: str, user: User) -> tuple:
        """
        Retrieves a document, increments its download count within a transaction,
        and returns the file object and its original name/mime-type.
        """
        is_staff_user = bool(user and (user.is_staff or user.is_superuser))

        with transaction.atomic():
            try:
                document = Document.objects.select_for_update().get(id=document_id)
            except Document.DoesNotExist:
                logger.warning(
                    "dms.download.missing_document document_id=%s", document_id
                )
                raise ValueError("Document not found.")

            if document.status != "ACTIVE":
                logger.warning(
                    "dms.download.inactive_document document_id=%s status=%s",
                    document_id,
                    document.status,
                )
                raise ValueError("Document not found or is inactive.")

            if not is_staff_user and not document.is_public:
                logger.warning(
                    "dms.download.access_denied document_id=%s user_id=%s",
                    document_id,
                    getattr(user, "id", None),
                )
                raise PermissionError("You do not have access to this document.")

            if not default_storage.exists(document.file_path):
                logger.error(
                    "dms.download.file_missing document_id=%s file_path=%s",
                    document_id,
                    document.file_path,
                )
                raise FileNotFoundError("Document file does not exist in storage.")

            # Increment download count
            document.download_count += 1
            document.save(update_fields=["download_count"])

        file_obj = default_storage.open(document.file_path, "rb")

        # We determine download filename: prefer original filename if it has extension, or construct from title
        download_name = document.original_filename
        if not download_name:
            _, ext = os.path.splitext(document.stored_filename)
            download_name = f"{document.title}{ext}"

        logger.info(
            "dms.download.completed document_id=%s user_id=%s content_type=%s",
            document_id,
            getattr(user, "id", None),
            document.mime_type,
        )

        return file_obj, download_name, document.mime_type
