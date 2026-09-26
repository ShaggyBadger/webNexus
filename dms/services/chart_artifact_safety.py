"""Runtime safety gates for generated chart documents."""

from __future__ import annotations

from django.utils import timezone

from dms.models import Document


def chart_document_safety_reason(document: Document) -> str | None:
    """Allow active chart artifacts as snapshots; retain ordinary document safety."""
    category_slug = getattr(document.category, "slug", None)
    is_chart_artifact = (
        category_slug == "tankchart"
        or document.tags.filter(slug="generic-tank-charts").exists()
    )

    if is_chart_artifact:
        return None if document.status == "ACTIVE" else "document_not_current"

    if document.operational_state in {"STALE", "SUPERSEDED"}:
        _record_invalidation(
            document, document.operational_state, "document_not_current"
        )
        return "document_not_current"
    if document.operational_state == "UNSAFE":
        _record_invalidation(
            document, "UNSAFE", document.invalidation_reason or "unsafe"
        )
        return "document_marked_unsafe"

    return None


def _record_invalidation(document: Document, state: str, reason: str) -> None:
    """Persist the first runtime invalidation without changing publication status."""
    if (
        document.operational_state == state
        and document.invalidation_reason == reason
        and document.invalidated_at is not None
    ):
        return
    document.operational_state = state
    document.invalidation_reason = reason
    document.invalidated_at = document.invalidated_at or timezone.now()
    document.save(
        update_fields=[
            "operational_state",
            "invalidation_reason",
            "invalidated_at",
            "updated_at",
        ]
    )
