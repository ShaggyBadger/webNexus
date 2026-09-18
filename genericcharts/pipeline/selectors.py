"""ORM selectors and source normalization for generic chart generation."""

from __future__ import annotations

from django.db.models import Q

from genericcharts.pipeline.dataclasses import (
    CurvePoint,
    GeneratedTank,
    OfficialChartPoint,
    SelectedStore,
    SelectedTank,
    SelectionSpec,
)
from genericcharts.pipeline.states import state_variants
from tankgauge.logic.curve_generator import generate_inch_gallon_curve
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    VirtualTankEstimation,
)
from tankgauge.models import StoreType
from tankgauge.logic.capacity_resolution import CapacityResolutionService


def select_stores(spec: SelectionSpec) -> tuple[SelectedStore, ...]:
    """Select and normalize stores and their current mapped assignments."""

    queryset = Store.objects.prefetch_related("tank_mappings__tank_type").order_by(
        "store_num", "id"
    )
    queryset = queryset.exclude(location__location_type__name__in=("Fuel Rack", "Yard"))
    queryset = _apply_store_filters(queryset, spec)

    selected = []
    for store in queryset:
        tanks = tuple(
            SelectedTank(
                mapping_id=mapping.id,
                tank_index=mapping.tank_index,
                fuel_type=(mapping.fuel_type or "").strip(),
                tank_type_id=mapping.tank_type_id,
                tank_type_name=(
                    (mapping.tank_type.name or "").strip() if mapping.tank_type else ""
                ),
                capacity_gallons=(
                    mapping.tank_type.capacity if mapping.tank_type else None
                ),
                max_depth_inches=(
                    mapping.tank_type.max_depth if mapping.tank_type else None
                ),
            )
            for mapping in store.tank_mappings.all()
        )
        selected.append(
            SelectedStore(
                store_id=store.id,
                store_number=store.store_num,
                riso_number=store.riso_num,
                store_name=(store.store_name or "").strip(),
                state=(store.state or "").strip(),
                store_type=(store.store_type or "").strip(),
                city=(store.city or "").strip(),
                tanks=tanks,
            )
        )
    return tuple(selected)


def select_generated_tanks(spec: SelectionSpec) -> tuple[GeneratedTank, ...]:
    """Select active mapped/virtual geometry with one record per physical tank.

    Mapped geometry wins over virtual geometry. A mapped physical key with an
    unresolved, conflicting, or unsafe profile remains blocked from virtual
    fallback even when its mapped geometry cannot be generated.
    """

    stores = select_stores(spec)
    store_ids = {store.store_id for store in stores}
    if not store_ids:
        return ()

    mappings = {
        mapping.id: mapping
        for mapping in StoreTankMapping.objects.filter(store_id__in=store_ids)
        .select_related("store", "tank_type")
        .order_by("store__store_num", "tank_index", "id")
    }
    candidates: dict[tuple[int, int | None], GeneratedTank] = {}
    blocked_keys: set[tuple[int, int | None]] = set()
    capacity_resolver = CapacityResolutionService()

    active_mapped = (
        TankEstimation.objects.filter(
            tank_mapping__store_id__in=store_ids,
            is_active=True,
        )
        .select_related("tank_mapping__store", "tank_mapping__tank_type")
        .order_by("-created_at", "-id")
    )
    latest_by_mapping: dict[int, TankEstimation] = {}
    for estimation in active_mapped:
        latest_by_mapping.setdefault(estimation.tank_mapping_id, estimation)

    for mapping_id, estimation in latest_by_mapping.items():
        mapping = mappings[mapping_id]
        resolution = capacity_resolver.resolve_mapping(mapping)
        key = (mapping.store_id, mapping.tank_index)
        if _mapping_blocks_virtual_fallback(mapping, estimation, resolution):
            blocked_keys.add(key)
        candidate = _generated_tank_from_estimation(
            mapping=mapping,
            radius_inches=estimation.radius,
            length_inches=estimation.length,
            confidence=estimation.confidence,
            sample_count=estimation.sample_count,
            source="mapped_estimation",
            algorithm_version=estimation.algorithm_version,
            capacity_status=resolution.status,
            capacity_source=resolution.authority,
            estimate_status=estimation.estimate_status,
            profile_version=resolution.profile_version,
            profile_status=mapping.profile_status,
            estimate_id=estimation.id,
        )
        if (
            candidate is not None
            and candidate.estimate_status not in {"STALE", "UNSAFE", "BLOCKED"}
            and key not in blocked_keys
        ):
            _add_candidate(candidates, candidate)

    for mapping in mappings.values():
        key = (mapping.store_id, mapping.tank_index)
        if key in latest_by_mapping:
            continue
        resolution = capacity_resolver.resolve_mapping(mapping)
        if _mapping_blocks_virtual_fallback(mapping, None, resolution):
            blocked_keys.add(key)

    active_virtual = (
        VirtualTankEstimation.objects.filter(store_id__in=store_ids, is_active=True)
        .select_related("store")
        .order_by("-created_at", "-id")
    )
    for estimation in active_virtual:
        mapping = next(
            (
                item
                for item in mappings.values()
                if item.store_id == estimation.store_id
                and item.tank_index == estimation.tank_index
            ),
            None,
        )
        candidate = _generated_tank_from_virtual(
            estimation=estimation,
            mapping=mapping,
            capacity_resolver=capacity_resolver,
        )
        key = (estimation.store_id, estimation.tank_index)
        if (
            candidate is not None
            and candidate.estimate_status not in {"STALE", "UNSAFE", "BLOCKED"}
            and key not in blocked_keys
        ):
            _add_candidate(candidates, candidate)

    return tuple(
        sorted(
            candidates.values(),
            key=lambda tank: (
                tank.store_number is None,
                tank.store_number or 0,
                tank.tank_index or 0,
            ),
        )
    )


def select_official_charts(spec: SelectionSpec) -> tuple[OfficialChartPoint, ...]:
    """Select official charts for selected tank types and store-specific charts."""

    stores = select_stores(spec)
    store_ids = [store.store_id for store in stores]
    tank_type_ids = {
        tank.tank_type_id
        for store in stores
        for tank in store.tanks
        if tank.tank_type_id is not None
    }
    charts = (
        TankChart.objects.filter(is_official=True)
        .filter(Q(tank_type_id__in=tank_type_ids) | Q(store_id__in=store_ids))
        .select_related("tank_type", "store")
        .order_by("tank_type__name", "store__store_num", "inches", "id")
    )
    return tuple(
        OfficialChartPoint(
            tank_type_id=chart.tank_type_id,
            tank_type_name=(
                (chart.tank_type.name or "").strip() if chart.tank_type else ""
            ),
            store_id=chart.store_id,
            store_number=chart.store.store_num if chart.store else None,
            tank_index=chart.tank_index,
            depth_inches=chart.inches,
            volume_gallons=chart.gallons,
            tank_name=(chart.tank_name or "").strip(),
        )
        for chart in charts
    )


def _apply_store_filters(queryset, spec: SelectionSpec):
    if spec.state:
        variants = state_variants(spec.state)
        state_query = Q(state__iexact=variants[0])
        for variant in variants[1:]:
            state_query |= Q(state__iexact=variant)
        queryset = queryset.filter(state_query)
    if spec.store_type_ids:
        store_type_names = StoreType.objects.filter(
            id__in=spec.store_type_ids
        ).values_list("name", flat=True)
        type_query = Q(pk__in=[])
        for name in store_type_names:
            type_query |= Q(store_type__iexact=name)
        queryset = queryset.filter(type_query)
    if spec.store_numbers:
        queryset = queryset.filter(store_num__in=spec.store_numbers)
    return queryset


def _generated_tank_from_estimation(
    *,
    mapping: StoreTankMapping,
    radius_inches: float,
    length_inches: float,
    confidence: float,
    sample_count: int,
    source: str,
    algorithm_version: str,
    capacity_status: str,
    capacity_source: str,
    estimate_status: str,
    profile_version: int | None,
    profile_status: str | None = None,
    estimate_id: int | None = None,
) -> GeneratedTank | None:
    tank_type = mapping.tank_type
    return _build_generated_tank(
        store_id=mapping.store_id,
        store_number=mapping.store.store_num,
        tank_index=mapping.tank_index,
        fuel_type=mapping.fuel_type or "",
        tank_type_id=mapping.tank_type_id,
        tank_type_name=(tank_type.name or "").strip() if tank_type else "",
        radius_inches=radius_inches,
        length_inches=length_inches,
        confidence=confidence,
        sample_count=sample_count,
        source=source,
        algorithm_version=algorithm_version,
        capacity_status=capacity_status,
        capacity_source=capacity_source,
        estimate_status=estimate_status,
        profile_version=profile_version,
        profile_status=profile_status,
        estimate_id=estimate_id,
    )


def _generated_tank_from_virtual(
    *,
    estimation: VirtualTankEstimation,
    mapping: StoreTankMapping | None,
    capacity_resolver: CapacityResolutionService,
) -> GeneratedTank | None:
    tank_type = mapping.tank_type if mapping else None
    resolution = capacity_resolver.resolve_virtual(
        total_capacity_gallons=estimation.physical_capacity_gallons
        or (tank_type.capacity if tank_type else None)
    )
    return _build_generated_tank(
        store_id=estimation.store_id,
        store_number=estimation.store.store_num,
        tank_index=estimation.tank_index,
        fuel_type=estimation.fuel_type,
        tank_type_id=mapping.tank_type_id if mapping else None,
        tank_type_name=(tank_type.name or "").strip() if tank_type else "",
        radius_inches=estimation.radius,
        length_inches=estimation.length,
        confidence=estimation.confidence,
        sample_count=estimation.sample_count,
        source="virtual_estimation",
        algorithm_version=estimation.algorithm_version,
        capacity_status=resolution.status,
        capacity_source=resolution.authority,
        estimate_status=estimation.estimate_status,
        profile_version=(mapping.profile_version if mapping else None),
        profile_status=mapping.profile_status if mapping else None,
        estimate_id=estimation.id,
    )


def _mapping_blocks_virtual_fallback(mapping, estimation, resolution) -> bool:
    """Keep a mapped physical key authoritative when its profile is unsafe."""

    if resolution.status == "UNRESOLVED":
        return True
    if mapping.capacity_source == "CONFLICTING":
        return True
    if mapping.profile_status in {
        "REVIEW_REQUIRED",
        "UNRESOLVED",
        "CONFLICTING",
        "UNSAFE",
    }:
        return True
    return bool(
        estimation and estimation.estimate_status in {"STALE", "UNSAFE", "BLOCKED"}
    )


def _build_generated_tank(**values) -> GeneratedTank | None:
    try:
        radius_inches = float(values["radius_inches"])
        length_inches = float(values["length_inches"])
        max_depth_inches = int(radius_inches * 2)
        raw_curve = generate_inch_gallon_curve(
            radius_inches, length_inches, max_depth_inches
        )
    except (TypeError, ValueError):
        return None

    curve = tuple(
        CurvePoint(
            depth_inches=int(point["inches"]),
            volume_gallons=float(point["gallons"]),
        )
        for point in raw_curve
    )
    values["radius_inches"] = radius_inches
    values["length_inches"] = length_inches
    values["max_depth_inches"] = max_depth_inches
    values["curve"] = curve
    return GeneratedTank(**values)


def _add_candidate(
    candidates: dict[tuple[int, int | None], GeneratedTank], candidate: GeneratedTank
) -> None:
    key = (candidate.store_id, candidate.tank_index)
    existing = candidates.get(key)
    if existing is None:
        candidates[key] = candidate
        return
    if _candidate_rank(candidate) < _candidate_rank(existing):
        candidates[key] = candidate


def _candidate_rank(candidate: GeneratedTank) -> tuple[int, float, int]:
    source_priority = 0 if candidate.source == "mapped_estimation" else 1
    return source_priority, -candidate.confidence, -candidate.sample_count
