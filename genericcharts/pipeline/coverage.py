"""Pure four-tier store/tank coverage mapping."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import ALIAS_TO_NEW_NAME
from .dataclasses import GeneratedTank
from .grouping import Bucket


@dataclass(frozen=True)
class CoverageEntry:
    """Printable identity and source information for one tank assignment."""

    name: str | None
    source: str
    nominal_volume_gallons: int | None
    radius_inches: float | None
    length_inches: float | None
    max_depth_inches: int | None
    fuel_type: str | None
    legacy_name: str | None
    display_name: str
    review_reason: str | None


def build_store_tank_map(
    generated_tanks: tuple[GeneratedTank, ...],
    catalog: dict[str, Bucket],
    legacy_assignments: dict[tuple[int, int | None], dict | str] | None = None,
    official_charts: dict[str, tuple[dict, ...]] | None = None,
    official_aliases: dict[str, str] | None = None,
):
    """Map every generated or legacy assignment through the coverage cascade."""

    legacy_assignments = legacy_assignments or {}
    official_charts = official_charts or {}
    official_aliases = official_aliases or {}
    generated_by_key = {
        (tank.store_id, tank.tank_index): tank for tank in generated_tanks
    }
    store_map = {}
    review_required = []
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for key in sorted(
        set(generated_by_key) | set(legacy_assignments),
        key=lambda item: (item[0], item[1] is None, item[1] or 0),
    ):
        store_id, tank_index = key
        generated = generated_by_key.get(key)
        if generated:
            name = _generated_name(generated, catalog)
            bucket = catalog[name]
            entry = CoverageEntry(
                name=name,
                source="veeder_bucket",
                nominal_volume_gallons=bucket.nominal_volume_gallons,
                radius_inches=bucket.median_radius_inches,
                length_inches=bucket.median_length_inches,
                max_depth_inches=bucket.depth_inches,
                fuel_type=generated.fuel_type,
                legacy_name=None,
                display_name=name,
                review_reason=None,
            )
            tier_counts[1] += 1
        else:
            assignment = legacy_assignments[key]
            if isinstance(assignment, dict):
                legacy_name = assignment.get("tank_type_name")
                fuel_type = assignment.get("fuel_type")
            else:
                legacy_name = assignment
                fuel_type = None
            effective_name = ALIAS_TO_NEW_NAME.get(legacy_name, legacy_name)
            if effective_name in catalog:
                bucket = catalog[effective_name]
                entry = CoverageEntry(
                    name=effective_name,
                    source="legacy_name_new_catalog",
                    nominal_volume_gallons=bucket.nominal_volume_gallons,
                    radius_inches=bucket.median_radius_inches,
                    length_inches=bucket.median_length_inches,
                    max_depth_inches=bucket.depth_inches,
                    fuel_type=fuel_type,
                    legacy_name=legacy_name,
                    display_name=effective_name,
                    review_reason=None,
                )
                tier_counts[2] += 1
            elif legacy_name in official_charts:
                chart = official_charts[legacy_name]
                entry = CoverageEntry(
                    name=official_aliases.get(legacy_name, legacy_name),
                    source="official_chart",
                    nominal_volume_gallons=int(chart[-1]["gallons"]),
                    radius_inches=None,
                    length_inches=None,
                    max_depth_inches=None,
                    fuel_type=fuel_type,
                    legacy_name=legacy_name,
                    display_name=official_aliases.get(legacy_name, legacy_name),
                    review_reason=None,
                )
                tier_counts[3] += 1
            else:
                reason = (
                    "missing_legacy_name"
                    if not legacy_name
                    else "incomplete_legacy_name"
                )
                entry = CoverageEntry(
                    name=None,
                    source="no_chart",
                    nominal_volume_gallons=None,
                    radius_inches=None,
                    length_inches=None,
                    max_depth_inches=None,
                    fuel_type=fuel_type,
                    legacy_name=legacy_name,
                    display_name=f"NO CHART:{legacy_name or 'UNKNOWN TANK TYPE'}",
                    review_reason=reason,
                )
                review_required.append(
                    {
                        "store_id": store_id,
                        "tank_index": assignment.get("tank_index", tank_index),
                        "legacy_name": legacy_name,
                        "reason": reason,
                    }
                )
                tier_counts[4] += 1
        store_map.setdefault(store_id, {})[tank_index] = entry

    report = {
        "veeder_tanks": len(generated_by_key),
        "catalog_size": len(catalog),
        "tier_counts": tier_counts,
        "review_required": review_required,
        "review_counts": {
            "incomplete_legacy_name": sum(
                item["reason"] == "incomplete_legacy_name" for item in review_required
            ),
            "missing_legacy_name": sum(
                item["reason"] == "missing_legacy_name" for item in review_required
            ),
        },
        "stores_covered": len(store_map),
        "legacy_assignments_given": len(legacy_assignments),
    }
    return store_map, report


def _generated_name(tank: GeneratedTank, catalog: dict[str, Bucket]) -> str:
    matching = [name for name, bucket in catalog.items() if tank in bucket.tanks]
    if not matching:
        raise ValueError(
            f"generated tank {tank.store_id}/{tank.tank_index} is not in the catalog"
        )
    return matching[0]
