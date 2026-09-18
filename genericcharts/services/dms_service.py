"""DMS lifecycle for versioned CoreStarterPack documents."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.text import slugify

from dms.models import Category, Document, Tag, generate_ulid
from genericcharts.services.description import (
    package_title,
    summary_document_description,
    store_type_names,
)
from genericcharts.version import PACKAGE_VERSION


class GenericChartDMSService:
    """Publish one package without disturbing another scope's active document."""

    category_slug = "fng"

    def publish(
        self,
        *,
        generation,
        pdf_bytes: bytes,
        summary: dict,
        description: str | None = None,
    ) -> Document:
        """Create the new active document and supersede only its own scope."""

        scope_key = generation.package_scope_key
        filename_prefix = f"core_starter_pack_{scope_key}_"
        filename = f"core_starter_pack_{scope_key}_v{PACKAGE_VERSION}.pdf"
        category, _ = Category.objects.get_or_create(
            slug=self.category_slug,
            defaults={"name": "FNG", "active": True},
        )
        store_type_ids = tuple((generation.options or {}).get("store_type_ids", ()))
        tags = self._tags(generation.state, store_type_ids)
        with transaction.atomic():
            previous = list(
                Document.objects.select_for_update().filter(
                    category=category,
                    original_filename__startswith=filename_prefix,
                    status="ACTIVE",
                )
            )
            version = (
                Document.objects.filter(
                    category=category,
                    original_filename__startswith=filename_prefix,
                )
                .order_by("-version")
                .values_list("version", flat=True)
                .first()
                or 0
            ) + 1
            ulid_value = generate_ulid()
            file_path = f"documents/{datetime.now(UTC):%Y}/{ulid_value}.pdf"
            description = description or summary_document_description(
                generation=generation, summary=summary
            )
            document_title = package_title(
                state=generation.state,
                store_type_ids=store_type_ids,
            )
            document = Document.objects.create(
                title=f"{document_title} version {PACKAGE_VERSION}",
                description=description,
                original_filename=filename,
                stored_filename=f"{ulid_value}.pdf",
                file_path=file_path,
                mime_type="application/pdf",
                file_size=len(pdf_bytes),
                sha256=sha256(pdf_bytes).hexdigest(),
                uploaded_by=generation.requested_by,
                status="ACTIVE",
                version=version,
                category=category,
                is_public=True,
                operational_state=(
                    "UNSAFE"
                    if any(
                        item.get("estimate_status") in {"UNSAFE", "BLOCKED"}
                        or item.get("profile_status") in {"UNSAFE", "REVIEW_REQUIRED"}
                        for item in (summary or {}).get("source_validity", ())
                    )
                    else "USABLE"
                ),
            )
            document.tags.add(*tags)
            default_storage.save(file_path, ContentFile(pdf_bytes))
            for old_document in previous:
                old_document.status = "SUPERSEDED"
                old_document.is_public = False
                old_document.operational_state = "SUPERSEDED"
                old_document.save(
                    update_fields=[
                        "status",
                        "is_public",
                        "operational_state",
                        "updated_at",
                    ]
                )
        return document

    def _tags(self, state: str, store_type_ids=()):
        names = [
            state.casefold(),
            "core-starter-pack",
            "generic-tank-charts",
            "store-tank-map",
        ]
        names.extend(
            f"store-type-{name.casefold()}" for name in store_type_names(store_type_ids)
        )
        tags = []
        for name in names:
            slug = slugify(name)
            tag, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
            tags.append(tag)
        return tags
