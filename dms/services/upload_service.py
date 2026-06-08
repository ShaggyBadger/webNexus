import hashlib
import os
from datetime import timedelta
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from django.db import transaction
import magic
import ulid

from dms.models import TemporaryUpload, Document, Category, Collection, Tag


class DocumentUploadService:
    """
    Service to handle raw uploads (Phase A) and finalizing uploads (Phase B).
    """

    @staticmethod
    def calculate_sha256(file_obj) -> str:
        """
        Calculate SHA256 hash of a file object.
        """
        sha256 = hashlib.sha256()
        # Ensure we start reading from the beginning
        file_obj.seek(0)
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        file_obj.seek(0)
        return sha256.hexdigest()

    @classmethod
    def handle_raw_upload(cls, uploaded_file, user: User) -> dict:
        """
        Phase A: Handle raw file upload, perform MIME verification, calculate SHA256,
        and save to media/temp/ as a TemporaryUpload.
        """
        # 1. Read first block for MIME inspection
        uploaded_file.seek(0)
        header_data = uploaded_file.read(2048)
        uploaded_file.seek(0)

        # 2. Inspect MIME via python-magic
        detected_mime = magic.from_buffer(header_data, mime=True)
        
        # 3. Calculate SHA256 checksum
        sha256_hash = cls.calculate_sha256(uploaded_file)

        # 4. Check for duplicates in permanent documents
        is_duplicate = Document.objects.filter(sha256=sha256_hash, status="ACTIVE").exists()

        # 5. Generate Temporary ULID
        temp_ulid = ulid.ulid()
        _, ext = os.path.splitext(uploaded_file.name)
        temp_filename = f"{temp_ulid}{ext}"
        temp_relative_path = os.path.join("temp", temp_filename)

        # 6. Save file to temporary storage using Storage Abstraction API
        saved_path = default_storage.save(temp_relative_path, uploaded_file)

        # 7. Create TemporaryUpload record
        expires_at = timezone.now() + timedelta(hours=2)  # Temporary files expire in 2 hours
        temp_upload = TemporaryUpload.objects.create(
            id=temp_ulid,
            file=saved_path,
            uploaded_by=user,
            expires_at=expires_at,
            sha256=sha256_hash,
            original_filename=uploaded_file.name,
        )

        return {
            "temp_id": temp_upload.id,
            "original_name": uploaded_file.name,
            "mime_type": detected_mime,
            "is_duplicate": is_duplicate,
            "sha256": sha256_hash,
            "file_size": uploaded_file.size,
        }

    @classmethod
    def finalize_upload(
        cls,
        temp_id: str,
        user: User,
        title: str,
        description: str = "",
        category_id: int = None,
        collection_ids: list = None,
        content_type_id: int = None,
        object_id: str = None,
        is_public: bool = False,
        tag_ids: list = None,
    ) -> Document:
        """
        Phase B: Finalize upload, move file to permanent storage, and create Document record.
        Uses transactional integrity to ensure DB record and file storage align.
        """

        # 1. Retrieve TemporaryUpload record
        try:
            temp_upload = TemporaryUpload.objects.get(id=temp_id)
        except TemporaryUpload.DoesNotExist:
            raise ValueError("Temporary upload not found or has expired.")

        # Check expiration
        if temp_upload.expires_at < timezone.now():
            # Clean up files if expired
            if default_storage.exists(temp_upload.file.name):
                default_storage.delete(temp_upload.file.name)
            temp_upload.delete()
            raise ValueError("Temporary upload has expired.")

        # 2. Get category if provided
        category = None
        if category_id:
            try:
                category = Category.objects.get(id=category_id, active=True)
            except Category.DoesNotExist:
                raise ValueError("Specified active Category does not exist.")

        # 3. Get collections and tags if provided
        collections = []
        if collection_ids:
            collections = list(Collection.objects.filter(id__in=collection_ids))

        tags = []
        if tag_ids:
            tags = list(Tag.objects.filter(id__in=tag_ids))

        # 4. Generate permanent ULID
        perm_ulid = ulid.ulid()
        original_name = temp_upload.original_filename
        _, ext = os.path.splitext(original_name)
        stored_filename = f"{perm_ulid}{ext}"

        current_year = timezone.now().strftime("%Y")
        perm_relative_path = os.path.join("documents", current_year, stored_filename)

        # Open the temp file
        temp_file_path = temp_upload.file.name
        if not default_storage.exists(temp_file_path):
            raise FileNotFoundError("Temporary file does not exist in storage.")

        # Use transaction to ensure both DB creation and storage operations succeed
        with transaction.atomic():
            # Read file content from temp storage
            with default_storage.open(temp_file_path, "rb") as f:
                content = f.read()

            # Save to permanent storage
            default_storage.save(perm_relative_path, ContentFile(content))

            # Create Document Database Record
            document = Document.objects.create(
                id=perm_ulid,
                title=title,
                description=description,
                original_filename=original_name,
                stored_filename=stored_filename,
                file_path=perm_relative_path,
                mime_type=magic.from_buffer(content[:2048], mime=True),
                file_size=len(content),
                sha256=temp_upload.sha256,
                uploaded_by=user,
                status="ACTIVE",
                version=1,
                category=category,
                content_type_id=content_type_id,
                object_id=object_id,
                is_public=is_public,
            )

            # Set ManyToMany relationships
            if collections:
                document.collections.set(collections)
            if tags:
                document.tags.set(tags)

            # Remove temporary upload DB record & file
            default_storage.delete(temp_file_path)
            temp_upload.delete()

        return document
