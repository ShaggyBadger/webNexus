"""Canonical catalog names, aliases, and collision handling."""

from __future__ import annotations

import string

from .grouping import Bucket, build_groups

ALIAS_TO_NEW_NAME = {
    "tt96": "12k96",
    "120k126": "12k126",
    "15k126": "16k126",
    "15k91": "14k91",
}
NEAR_DUPLICATE_CURVE_TOLERANCE = 0.01


def bucket_name(bucket: Bucket) -> str:
    """Return the canonical compact name for a generated bucket."""

    return f"{round(bucket.nominal_volume_gallons / 1000)}k{bucket.depth_inches}"


def resolve_name_collisions(named_buckets):
    """Add stable alphabetical suffixes to colliding bucket names."""

    by_name = {}
    for name, bucket in named_buckets:
        by_name.setdefault(name, []).append(bucket)

    resolved = []
    collisions = []
    for name, buckets in by_name.items():
        if len(buckets) == 1:
            resolved.append((name, buckets[0]))
            continue
        buckets = sorted(buckets, key=lambda bucket: bucket.nominal_volume_gallons)
        names = []
        for index, bucket in enumerate(buckets):
            if index >= len(string.ascii_lowercase):
                raise ValueError(f"too many buckets collide on name '{name}'")
            resolved_name = f"{name}{string.ascii_lowercase[index]}"
            resolved.append((resolved_name, bucket))
            names.append(resolved_name)
        collisions.append(
            {
                "base_name": name,
                "names": names,
                "nominals": [bucket.nominal_volume_gallons for bucket in buckets],
            }
        )
    return tuple(resolved), tuple(collisions)


def build_new_catalog(tanks, gap_fraction: float = 0.03):
    """Build the generated catalog and a collision report."""

    named = [
        (bucket_name(bucket), bucket)
        for buckets in build_groups(tanks, gap_fraction).values()
        for bucket in buckets
    ]
    resolved, collisions = resolve_name_collisions(named)
    return {name: bucket for name, bucket in resolved}, collisions


def build_official_chart_aliases(
    catalog,
    official_charts,
    near_duplicate_tolerance: float = NEAR_DUPLICATE_CURVE_TOLERANCE,
):
    """Map distinct official curves to discoverable canonical names."""

    if not 0 <= near_duplicate_tolerance <= 1:
        raise ValueError("near_duplicate_tolerance must be between 0 and 1")
    candidates = {}
    for legacy_name, curve in official_charts.items():
        if legacy_name in catalog or not curve:
            continue
        depth = max(int(point["inches"]) for point in curve)
        capacity = max(float(point["gallons"]) for point in curve)
        base_name = f"{round(capacity / 1000)}k{depth}"
        candidates.setdefault(base_name, []).append((legacy_name, curve))

    aliases = {}
    used_names = set(catalog)
    for base_name, candidates_for_name in sorted(candidates.items()):
        groups = []
        for legacy_name, curve in sorted(candidates_for_name):
            group = next(
                (
                    group
                    for group in groups
                    if _curves_near_duplicate(
                        group["curve"], curve, near_duplicate_tolerance
                    )
                ),
                None,
            )
            if group:
                group["names"].append(legacy_name)
            else:
                groups.append({"curve": curve, "names": [legacy_name]})
        for index, group in enumerate(groups):
            if index == 0 and base_name not in used_names:
                name = base_name
                used_names.add(name)
            elif index == 0 and base_name in used_names:
                name = base_name
            else:
                suffix_index = index - 1
                if suffix_index >= len(string.ascii_lowercase):
                    raise ValueError(f"too many official curves share '{base_name}'")
                name = f"{base_name}({string.ascii_lowercase[suffix_index]})"
                while name in used_names:
                    suffix_index += 1
                    if suffix_index >= len(string.ascii_lowercase):
                        raise ValueError(
                            f"too many official curves share '{base_name}'"
                        )
                    name = f"{base_name}({string.ascii_lowercase[suffix_index]})"
                used_names.add(name)
            aliases.update({legacy_name: name for legacy_name in group["names"]})
    return aliases


def _curves_near_duplicate(first, second, tolerance):
    first_values = {int(point["inches"]): float(point["gallons"]) for point in first}
    second_values = {int(point["inches"]): float(point["gallons"]) for point in second}
    if first_values.keys() != second_values.keys():
        return False
    capacity = max(max(first_values.values()), max(second_values.values()), 1.0)
    difference = max(
        abs(first_values[depth] - second_values[depth]) for depth in first_values
    )
    return difference / capacity <= tolerance
