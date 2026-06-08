import ulid
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

    name = models.CharField(
        max_length=100, unique=True, help_text="Category name"
    )
    slug = models.SlugField(
        max_length=100, unique=True, help_text="Slug for API URLs"
    )
    active = models.BooleanField(
        default=True, help_text="Is this category active?"
    )
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

    name = models.CharField(
        max_length=50, unique=True, help_text="Tag name"
    )
    slug = models.SlugField(
        max_length=50, unique=True, help_text="Tag slug"
    )

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["name"]

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
    file_path = models.CharField(
        max_length=500, help_text="Relative storage file path"
    )
    mime_type = models.CharField(
        max_length=100, help_text="MIME type verified via magic bytes"
    )
    file_size = models.BigIntegerField(help_text="File size in bytes")
    sha256 = models.CharField(
        max_length=64, db_index=True, help_text="SHA256 checksum for duplicate detection"
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
    version = models.IntegerField(default=1, help_text="Version increment number")
    download_count = models.PositiveIntegerField(
        default=0, help_text="Cumulative download count"
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

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.title} (v{self.version})"


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
    sha256 = models.CharField(
        max_length=64, help_text="SHA256 checksum of raw file"
    )

    class Meta:
        verbose_name = "Temporary Upload"
        verbose_name_plural = "Temporary Uploads"
        ordering = ["expires_at"]

    def __str__(self) -> str:
        return f"Temp {self.id} (expires {self.expires_at})"
