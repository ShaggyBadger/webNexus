"""Runtime safety gates for generated chart documents."""

from __future__ import annotations

import logging

from django.utils import timezone

from dms.models import Document
from tankgauge.logic.utils import canonicalize_fuel

logger = logging.getLogger(__name__)


def chart_document_safety_reason(document: Document) -> str | None:
    """Return a stable blocking reason for a generated chart, if one exists."""
    if document.operational_state in {"STALE", "SUPERSEDED"}:
        _record_invalidation(
            document, document.operational_state, "document_not_current"
        )
        return "document_not_current"
    category_slug = getattr(document.category, "slug", None)
    if category_slug == "tankchart":
        from tankcharts.services.dms_storage_service import DMSChartStorageService

        return DMSChartStorageService().document_safety_reason(document)

    if document.tags.filter(slug="generic-tank-charts").exists():
        reason = _generic_chart_safety_reason(document)
        if reason:
            return reason

    if document.operational_state == "UNSAFE":
        _record_invalidation(
            document, "UNSAFE", document.invalidation_reason or "unsafe"
        )
        return "document_marked_unsafe"

    return None


def _generic_chart_safety_reason(document: Document) -> str | None:
    def blocked(reason: str, state: str = "UNSAFE") -> str:
        _record_invalidation(document, state, reason)
        return reason

    generation = (
        document.generic_chart_generations.filter(status="completed")
        .order_by("-created_at")
        .first()
    )
    if generation is None or generation.document_id != document.id:
        return blocked("generic_generation_not_current", "STALE")

    for source in (generation.summary or {}).get("source_validity", ()):
        if source.get("estimate_status") in {"STALE", "UNSAFE", "BLOCKED"}:
            return blocked("generic_estimate_unsafe")
        if source.get("profile_status") in {"UNSAFE", "REVIEW_REQUIRED"}:
            return blocked("generic_profile_unsafe")
        if (
            source.get("profile_status") == "UNAVAILABLE"
            and source.get("estimate_status") != "LEGACY_UNVERIFIED"
        ):
            return blocked("generic_profile_unsafe")
        if source.get("store_id") is not None and source.get("tank_index") is not None:
            from tankgauge.models import StoreTankMapping, TankEstimation

            mappings = StoreTankMapping.objects.filter(
                store_id=source["store_id"], tank_index=source["tank_index"]
            )
            fuel_type = source.get("fuel_type")
            if fuel_type:
                mappings = mappings.filter(
                    canonical_fuel_type=canonicalize_fuel(fuel_type)
                )
            mapping = mappings.first()
            if mapping is not None:
                if source.get("profile_version") is not None and (
                    mapping.profile_version != source["profile_version"]
                ):
                    return blocked("generic_profile_changed", "STALE")
                if source.get("estimate_id") is not None:
                    current = (
                        TankEstimation.objects.filter(
                            tank_mapping=mapping, is_active=True
                        )
                        .order_by("-created_at")
                        .first()
                    )
                    if current is None or current.id != source["estimate_id"]:
                        return blocked("generic_estimate_changed", "STALE")

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
