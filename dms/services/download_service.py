from django.core.files.storage import default_storage
from django.db import transaction
from dms.models import Document
from django.http import FileResponse
import os


class DocumentDownloadService:
    """
    Service to manage document retrieval and download counts.
    """

    @classmethod
    def prepare_download(cls, document_id: str) -> tuple:
        """
        Retrieves a document, increments its download count within a transaction,
        and returns the file object and its original name/mime-type.
        """
        with transaction.atomic():
            try:
                document = Document.objects.select_for_update().get(
                    id=document_id, status="ACTIVE"
                )
            except Document.DoesNotExist:
                raise ValueError("Document not found or is inactive.")

            # Increment download count
            document.download_count += 1
            document.save(update_fields=["download_count"])

        # Retrieve file from storage
        if not default_storage.exists(document.file_path):
            # TODO: Enhance integrity failure handling.
            # Instead of just a 404, consider logging a system alert,
            # flagging the DB record as 'MISSING', or notifying administrators.
            raise FileNotFoundError("Document file does not exist in storage.")

        file_obj = default_storage.open(document.file_path, "rb")

        # We determine download filename: prefer original filename if it has extension, or construct from title
        download_name = document.original_filename
        if not download_name:
            _, ext = os.path.splitext(document.stored_filename)
            download_name = f"{document.title}{ext}"

        return file_obj, download_name, document.mime_type
