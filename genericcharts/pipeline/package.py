"""Assemble the typed data contract consumed by review, PDF, and DMS stages."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import build_new_catalog, build_official_chart_aliases
from .coverage import build_store_tank_map
from .grouping import Bucket
from .review import ReviewGraph, build_review_graphs
from .selectors import (
    select_generated_tanks,
    select_official_charts,
    select_stores,
)


@dataclass(frozen=True)
class PackageData:
    """All normalized package data needed after ORM selection."""

    selection: object
    stores: tuple
    generated_tanks: tuple
    catalog: dict[str, Bucket]
    collisions: tuple[dict, ...]
    official_charts: dict[str, tuple[dict, ...]]
    official_aliases: dict[str, str]
    store_map: dict
    coverage_report: dict
    review_graphs: tuple[ReviewGraph, ...]
    options: dict[str, float]


def build_package_data(
    *,
    selection,
    volume_gap_percent: float,
    near_duplicate_tolerance_percent: float,
    outlier_multiplier: float,
) -> PackageData:
    """Select current ORM data and normalize it for every downstream stage."""

    stores = select_stores(selection)
    generated_tanks = select_generated_tanks(selection)
    catalog, collisions = build_new_catalog(
        generated_tanks,
        gap_fraction=volume_gap_percent / 100,
    )

    official_charts: dict[str, list[dict]] = {}
    for point in select_official_charts(selection):
        name = point.tank_type_name or point.tank_name
        if not name:
            continue
        official_charts.setdefault(name, []).append(
            {"inches": point.depth_inches, "gallons": point.volume_gallons}
        )
    official_chart_tuples = {
        name: tuple(points) for name, points in official_charts.items()
    }
    official_aliases = build_official_chart_aliases(
        catalog,
        official_chart_tuples,
        near_duplicate_tolerance=near_duplicate_tolerance_percent / 100,
    )
    legacy_assignments = {}
    for store in stores:
        for tank in store.tanks:
            assignment_key = (store.store_id, tank.tank_index)
            if assignment_key in legacy_assignments and tank.tank_index is None:
                # Null tank indexes are valid legacy inventory, but cannot be
                # unique dictionary keys when a store has several of them.
                assignment_key = (store.store_id, -tank.mapping_id)
            legacy_assignments[assignment_key] = {
                "tank_type_name": tank.tank_type_name,
                "fuel_type": tank.fuel_type,
                "tank_index": tank.tank_index,
            }
    store_map, coverage_report = build_store_tank_map(
        generated_tanks,
        catalog,
        legacy_assignments=legacy_assignments,
        official_charts=official_chart_tuples,
        official_aliases=official_aliases,
    )
    options = {
        "volume_gap_percent": volume_gap_percent,
        "near_duplicate_tolerance_percent": near_duplicate_tolerance_percent,
        "outlier_multiplier": outlier_multiplier,
    }
    return PackageData(
        selection=selection,
        stores=stores,
        generated_tanks=generated_tanks,
        catalog=catalog,
        collisions=collisions,
        official_charts=official_chart_tuples,
        official_aliases=official_aliases,
        store_map=store_map,
        coverage_report=coverage_report,
        review_graphs=build_review_graphs(catalog, outlier_multiplier),
        options=options,
    )
