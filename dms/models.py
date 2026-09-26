import ulid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


def generate_ulid() -> str:
    """
    Generate a 26-character unique ULID string.
    """
    return ulid.ulid()


class Category(models.Model):
    """
    Category Model
    Controlled vocabulary for document types (e.g., "Tank Chart", "Safety").
    """

    name = models.CharField(max_length=100, unique=True, help_text="Category name")
    slug = models.SlugField(max_length=100, unique=True, help_text="Slug for API URLs")
    active = models.BooleanField(default=True, help_text="Is this category active?")
    sort_order = models.IntegerField(
        default=0, help_text="Order in lists (lower numbers first)"
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    """
    Tag Model
    Provides flexible search and organization for documents.
    """

    name = models.CharField(max_length=50, unique=True, help_text="Tag name")
    slug = models.SlugField(max_length=50, unique=True, help_text="Tag slug")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="dms_tag_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Document(models.Model):
    """
    Document Model
    The core entity representing an operational document.
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("ARCHIVED", "Archived"),
        ("SUPERSEDED", "Superseded"),
        ("DRAFT", "Draft"),
    ]
    OPERATIONAL_STATE_CHOICES = [
        ("USABLE", "Usable"),
        ("STALE", "Stale"),
        ("UNSAFE", "Unsafe"),
        ("SUPERSEDED", "Superseded"),
    ]

    id = models.CharField(
        max_length=26,
        primary_key=True,
        default=generate_ulid,
        editable=False,
        help_text="Unique ULID identifier",
    )
    title = models.CharField(max_length=255, help_text="User-facing document name")
    description = models.TextField(
        blank=True, null=True, help_text="Optional document description"
    )
    original_filename = models.CharField(
        max_length=255, help_text="Original uploaded filename"
    )
    stored_filename = models.CharField(
        max_length=255, help_text="Filename stored in filesystem (ULID + ext)"
    )
    file_path = models.CharField(max_length=500, help_text="Relative storage file path")
    mime_type = models.CharField(
        max_length=100, help_text="MIME type verified via magic bytes"
    )
    file_size = models.BigIntegerField(help_text="File size in bytes")
    sha256 = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256 checksum for duplicate detection",
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="uploaded_documents",
        help_text="User who uploaded the document",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when document was uploaded"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when document was last updated"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        help_text="Document lifecycle status",
    )
    operational_state = models.CharField(
        max_length=20,
        choices=OPERATIONAL_STATE_CHOICES,
        default="USABLE",
        db_index=True,
        help_text="Whether the document is safe to use as the current operational artifact.",
    )
    invalidation_reason = models.CharField(max_length=255, blank=True)
    source_profile_version = models.PositiveIntegerField(null=True, blank=True)
    source_estimate_version = models.PositiveIntegerField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    invalidated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invalidated_documents",
    )
    version = models.IntegerField(default=1, help_text="Version increment number")
    download_count = models.PositiveIntegerField(
        default=0, help_text="Cumulative download count"
    )
    email_count = models.PositiveIntegerField(
        default=0, help_text="Cumulative email send count"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
        help_text="Controlled vocabulary category classification",
    )
    is_public = models.BooleanField(
        default=False, help_text="Is this document visible to standard users?"
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="documents",
        help_text="Flexible search and organization tags",
    )

    # Generic Foreign Key Contextual Linkage
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Linked model content type (e.g. siteintel.Location)",
    )
    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Linked object primary key identifier",
    )
    content_object = GenericForeignKey("content_type", "object_id")

    @property
    def linked_object(self):
        """
        Alias for content_object to maintain consistency with serializers
        and template expectations.
        """
        return self.content_object

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="dms_doc_gfk_idx"),
            models.Index(fields=["status"], name="dms_doc_status_idx"),
            models.Index(
                fields=["operational_state"], name="dms_doc_operational_state_idx"
            ),
            models.Index(fields=["title"], name="dms_doc_title_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} (v{self.version})"


class DocumentDownloadFailure(models.Model):
    """Immutable diagnostic event for a failed routed document download."""

    REASON_CHOICES = [
        ("document_missing", "Document not found"),
        ("document_inactive", "Document inactive"),
        ("document_not_current", "Document is no longer current"),
        ("document_marked_unsafe", "Document marked unsafe"),
        ("generic_generation_not_current", "Generated chart is not current"),
        ("generic_estimate_unsafe", "Generated chart estimate is unsafe"),
        ("generic_profile_unsafe", "Generated chart profile is unsafe"),
        ("generic_profile_changed", "Generated chart profile changed"),
        ("generic_estimate_changed", "Generated chart estimate changed"),
        ("estimate_unsafe", "Tank chart estimate is unsafe"),
        ("profile_unsafe", "Tank chart profile is unsafe"),
        ("source_data_newer_than_document", "Source data is newer than chart"),
        ("tank_mapping_missing", "Tank mapping is missing"),
        ("profile_version_changed", "Tank profile changed"),
        ("estimate_changed", "Tank estimate changed"),
        ("access_denied", "Access denied"),
        ("file_missing", "File missing from storage"),
    ]

    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="download_failures",
    )
    document_ulid = models.CharField(max_length=26, db_index=True)
    document_title = models.CharField(max_length=255, blank=True)
    reason_code = models.CharField(max_length=40, choices=REASON_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_download_failures",
    )
    trace_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["reason_code", "occurred_at"],
                name="dms_dl_fail_reason_time_idx",
            ),
        ]
        verbose_name = "Document Download Failure"
        verbose_name_plural = "Document Download Failures"

    def __str__(self) -> str:
        return f"{self.document_ulid}: {self.get_reason_code_display()}"

    def save(self, *args, **kwargs) -> None:
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Download failure events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Download failure events are append-only.")


class Collection(models.Model):
    """
    Collection Model
    Groups documents into logical Packages.
    """

    id = models.CharField(
        max_length=26,
        primary_key=True,
        default=generate_ulid,
        editable=False,
        help_text="Unique ULID identifier",
    )
    name = models.CharField(max_length=255, help_text="Collection package name")
    description = models.TextField(
        blank=True, null=True, help_text="Collection details"
    )
    documents = models.ManyToManyField(
        Document, related_name="collections", help_text="Documents in this collection"
    )
    is_public = models.BooleanField(
        default=True, help_text="Visible to standard users?"
    )

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TemporaryUpload(models.Model):
    """
    TemporaryUpload Model
    Holds file uploads temporarily during the two-phase upload process.
    """

    id = models.CharField(
        max_length=26,
        primary_key=True,
        default=generate_ulid,
        editable=False,
        help_text="Unique ULID identifier",
    )
    file = models.FileField(
        upload_to="temp/", help_text="Uploaded temporary file location"
    )
    original_filename = models.CharField(
        max_length=255, default="", help_text="Original uploaded filename"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="temporary_uploads",
        help_text="User who performed raw upload",
    )
    expires_at = models.DateTimeField(
        help_text="Expiry timestamp after which file is purged"
    )
    sha256 = models.CharField(max_length=64, help_text="SHA256 checksum of raw file")

    class Meta:
        verbose_name = "Temporary Upload"
        verbose_name_plural = "Temporary Uploads"
        ordering = ["expires_at"]

    def __str__(self) -> str:
        return f"Temp {self.id} (expires {self.expires_at})"
