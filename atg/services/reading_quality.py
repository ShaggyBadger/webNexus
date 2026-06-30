from __future__ import annotations

from typing import Iterable

from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import StoreTankMapping


def _confidence_is_valid(confidence_score: float | None) -> bool:
    if confidence_score is None:
        return True
    return 0.0 <= float(confidence_score) <= 1.0


def get_hard_errors_for_payload(payload: dict) -> list[str]:
    """Return non-negotiable data-quality errors for one reading payload."""
    errors: list[str] = []

    tank_index = payload.get("tank_index")
    volume = payload.get("volume")
    ullage = payload.get("ullage")
    height = payload.get("height")
    water = payload.get("water")
    temp = payload.get("temp")
    confidence_score = payload.get("confidence_score")

    if tank_index is None or int(tank_index) < 1:
        errors.append("tank_index must be >= 1")

    if volume is None or float(volume) < 0:
        errors.append("volume must be >= 0")

    if ullage is None or float(ullage) < 0:
        errors.append("ullage must be >= 0")

    if height is None or float(height) < 0:
        errors.append("height must be >= 0")

    if water is not None and float(water) < 0:
        errors.append("water must be >= 0 when provided")

    if temp is not None and abs(float(temp)) > 200:
        errors.append("temp out of plausible range (-200 to 200)")

    if not _confidence_is_valid(confidence_score):
        errors.append("confidence_score must be between 0 and 1")

    if volume is not None and ullage is not None:
        if float(volume) + float(ullage) <= 0:
            errors.append("volume + ullage must be > 0")

    return errors


def get_mapping_sanity_issues(store, payload: dict) -> list[str]:
    """Return mapping-based sanity issues (soft checks) for one reading payload."""
    issues: list[str] = []

    fuel_type = payload.get("fuel_type")
    fuel_key = canonicalize_fuel(
        getattr(fuel_type, "name", fuel_type),
    )
    tank_index = payload.get("tank_index")
    if tank_index is None:
        return issues

    mapping = (
        StoreTankMapping.objects.filter(
            store=store,
            fuel_type=fuel_key,
            tank_index=tank_index,
        )
        .select_related("tank_type")
        .first()
    )

    if mapping is None:
        issues.append("no store mapping found for store/fuel/index")
        return issues

    if not mapping.tank_type:
        issues.append("mapping has no tank_type")
        return issues

    volume = float(payload.get("volume") or 0)
    ullage = float(payload.get("ullage") or 0)
    height = float(payload.get("height") or 0)
    implied_capacity = volume + ullage

    if mapping.tank_type.capacity:
        capacity = float(mapping.tank_type.capacity)
        if implied_capacity > capacity * 1.25:
            issues.append(
                f"implied capacity {implied_capacity:.1f} exceeds 125% of mapped capacity {capacity:.1f}"
            )

    if mapping.tank_type.max_depth:
        max_depth = float(mapping.tank_type.max_depth)
        if height > max_depth * 1.2:
            issues.append(
                f"height {height:.2f} exceeds 120% of mapped max_depth {max_depth:.2f}"
            )

    return issues


def validate_readings_for_store(store, validated_readings: Iterable[dict]) -> list[str]:
    """Return a list of full validation errors for a batch of readings."""
    errors: list[str] = []
    for idx, reading in enumerate(validated_readings, start=1):
        hard_errors = get_hard_errors_for_payload(reading)
        if hard_errors:
            errors.append(f"reading #{idx}: " + "; ".join(hard_errors))

    return errors
