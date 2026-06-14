from django.contrib import admin
from dms.models import Category, Tag, Document, Collection, TemporaryUpload


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class DocumentCollectionInline(admin.TabularInline):
    model = Collection.documents.through
    extra = 1


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status",
        "version",
        "is_public",
        "uploaded_by",
        "uploaded_at",
    )
    list_filter = ("status", "is_public", "category", "uploaded_at")
    search_fields = ("title", "description", "original_filename", "id")
    readonly_fields = (
        "id",
        "original_filename",
        "stored_filename",
        "file_path",
        "mime_type",
        "file_size",
        "sha256",
        "uploaded_at",
        "updated_at",
        "download_count",
    )
    filter_horizontal = ("tags",)
    fieldsets = (
        (
            "Core Identity",
            {"fields": ("id", "title", "description", "status", "version")},
        ),
        ("Classification", {"fields": ("category", "tags", "is_public")}),
        (
            "File Metadata",
            {
                "fields": (
                    "original_filename",
                    "stored_filename",
                    "file_path",
                    "mime_type",
                    "file_size",
                    "sha256",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Ownership & Stats",
            {"fields": ("uploaded_by", "uploaded_at", "updated_at", "download_count")},
        ),
        (
            "Generic Linkage",
            {"fields": ("content_type", "object_id")},
        ),
    )


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_public", "document_count")
    list_filter = ("is_public",)
    search_fields = ("name", "description")
    filter_horizontal = ("documents",)

    def document_count(self, obj):
        return obj.documents.count()

    document_count.short_description = "Documents"


@admin.register(TemporaryUpload)
class TemporaryUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "uploaded_by", "expires_at")
    readonly_fields = (
        "id",
        "file",
        "original_filename",
        "uploaded_by",
        "expires_at",
        "sha256",
    )
    search_fields = ("id", "original_filename")
