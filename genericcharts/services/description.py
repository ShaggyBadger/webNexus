"""Human-readable descriptions for generated CoreStarterPack documents."""

from __future__ import annotations

from tankgauge.models import StoreType


def store_type_names(store_type_ids) -> tuple[str, ...]:
    """Resolve selected reference IDs into stable display names."""

    if not store_type_ids:
        return ()
    return tuple(
        StoreType.objects.filter(id__in=store_type_ids)
        .order_by("name")
        .values_list("name", flat=True)
    )


def selection_label(*, state: str, store_numbers=(), store_type_ids=()) -> str:
    """Build the human-readable identity for one generated package scope."""

    label = "all states" if state == "FULL" else state
    names = store_type_names(store_type_ids)
    if names:
        label = f"{label} - {', '.join(names)}"
    if store_numbers:
        numbers = ", ".join(str(number) for number in sorted(store_numbers))
        label = f"{label} stores {numbers}"
    return label


def package_title(*, state: str, store_type_ids=()) -> str:
    """Build the human-readable DMS title for one package scope."""

    return f"CoreStarterPack [{selection_label(state=state, store_type_ids=store_type_ids)}]"


def default_document_description(*, selection, package) -> str:
    """Build the editable description shown before generation starts."""

    scope = selection_label(
        state="FULL" if selection.is_full else selection.state,
        store_numbers=selection.store_numbers,
        store_type_ids=selection.store_type_ids,
    )
    coverage = package.coverage_report
    review_count = len(coverage.get("review_required", ()))
    stores_covered = coverage.get("stores_covered", 0)
    return (
        f"{scope} CoreStarterPack generated from {len(package.stores)} stores.\n"
        f"{len(package.generated_tanks)} generated tanks, "
        f"{len(package.catalog)} chart definitions, "
        f"{stores_covered} stores covered.\n"
        f"{review_count} assignments require review."
    )


def summary_document_description(*, generation, summary: dict) -> str:
    """Build a safe fallback for callers that bypass the review form."""

    options = generation.options or {}
    store_numbers = tuple(options.get("store_numbers", ()))
    scope = selection_label(
        state=generation.state,
        store_numbers=store_numbers,
        store_type_ids=tuple(options.get("store_type_ids", ())),
    )
    coverage = summary.get("coverage") or {}
    review_count = len(coverage.get("review_required", ()))
    return (
        f"{scope} CoreStarterPack generated from {summary.get('stores', 0)} stores.\n"
        f"{summary.get('generated_tanks', 0)} generated tanks, "
        f"{summary.get('catalog_size', 0)} chart definitions, "
        f"{coverage.get('stores_covered', 0)} stores covered.\n"
        f"{review_count} assignments require review."
    )
