from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.db import connection

from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import Store, StoreTankMapping


@dataclass(frozen=True)
class TankMappingSyncResult:
    """Counts of tank mappings created, updated, and reused unchanged."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0


def sync_store_tank_mappings(
    *, store: Store, tank_updates: Iterable[Any]
) -> TankMappingSyncResult:
    """
    Preserve field operators' tank history while applying approved assignments.

    Reuses mappings by physical tank index after validating fuel identity, adds
    new indexed mappings, and deliberately leaves unmentioned mappings intact.
    The caller must run this operation inside the proposal's atomic transaction.

    Args:
        store: Canonical store receiving the proposed tank assignments.
        tank_updates: Proposed TankUpdate model instances.

    Returns:
        Counts of created, changed, and unchanged mappings.

    Raises:
        ValidationError: If indexes, physical identities, or tank types cannot
            be resolved safely.
        RuntimeError: If called outside a database transaction.
    """
    if not connection.in_atomic_block:
        raise RuntimeError(
            "Tank mapping synchronization requires an atomic transaction."
        )

    updates = list(tank_updates)
    if not updates:
        return TankMappingSyncResult()

    # Serialize proposal synchronizations for this store before checking that
    # each physical index still has a single canonical mapping.
    Store.objects.select_for_update().only("pk").get(pk=store.pk)

    validation_errors = []
    proposed_by_index = {}
    for tank_update in updates:
        tank_index = tank_update.tank_index
        if tank_index is None or tank_index < 1:
            validation_errors.append(
                "Every proposed tank must have a positive physical tank index."
            )
            continue

        if tank_index in proposed_by_index:
            validation_errors.append(
                f"Tank index {tank_index} appears more than once in this proposal."
            )
            continue

        canonical_fuel_type = canonicalize_fuel(tank_update.fuel_type)
        if not canonical_fuel_type:
            validation_errors.append(
                f"Tank index {tank_index} must have a valid fuel type."
            )
            continue

        proposed_by_index[tank_index] = (tank_update, canonical_fuel_type)

    if validation_errors:
        raise ValidationError(validation_errors)

    existing_by_index = defaultdict(list)
    existing_mappings = (
        StoreTankMapping.objects.select_for_update()
        .filter(store=store, tank_index__in=proposed_by_index)
        .order_by("tank_index", "id")
    )
    for mapping in existing_mappings:
        existing_by_index[mapping.tank_index].append(mapping)

    resolved_mappings = {}
    for tank_index, (tank_update, canonical_fuel_type) in proposed_by_index.items():
        indexed_mappings = existing_by_index[tank_index]
        if len(indexed_mappings) > 1:
            validation_errors.append(
                f"Store {store.store_num or store.pk} has multiple mappings for "
                f"tank index {tank_index}; resolve the duplicate before applying "
                "this update."
            )
            continue

        if indexed_mappings:
            mapping = indexed_mappings[0]
            existing_fuel_type = canonicalize_fuel(
                mapping.canonical_fuel_type or mapping.fuel_type
            )
            if existing_fuel_type != canonical_fuel_type:
                validation_errors.append(
                    f"Tank index {tank_index} is already mapped to "
                    f"'{existing_fuel_type or 'an unknown fuel'}', not "
                    f"'{canonical_fuel_type}'. Correct the existing mapping before "
                    "applying this update."
                )
                continue
            resolved_mappings[tank_index] = mapping
            continue

        if tank_update.tank_type_id is None:
            validation_errors.append(
                f"Tank index {tank_index} has no selected tank type and cannot be "
                "added to canonical tank mappings."
            )
            continue

        resolved_mappings[tank_index] = None

    if validation_errors:
        raise ValidationError(validation_errors)

    created_count = 0
    updated_count = 0
    unchanged_count = 0

    for tank_index, (tank_update, canonical_fuel_type) in proposed_by_index.items():
        mapping = resolved_mappings[tank_index]
        if mapping is None:
            StoreTankMapping.objects.create(
                store=store,
                tank_index=tank_index,
                fuel_type=canonical_fuel_type,
                canonical_fuel_type=canonical_fuel_type,
                tank_type=tank_update.tank_type,
            )
            created_count += 1
            continue

        changed_fields = []
        if mapping.fuel_type != canonical_fuel_type:
            mapping.fuel_type = canonical_fuel_type
            changed_fields.append("fuel_type")
        if mapping.canonical_fuel_type != canonical_fuel_type:
            mapping.canonical_fuel_type = canonical_fuel_type
            changed_fields.append("canonical_fuel_type")
        if (
            tank_update.tank_type_id is not None
            and mapping.tank_type_id != tank_update.tank_type_id
        ):
            mapping.tank_type = tank_update.tank_type
            changed_fields.append("tank_type")

        if changed_fields:
            mapping.save(update_fields=changed_fields)
            updated_count += 1
        else:
            unchanged_count += 1

    return TankMappingSyncResult(
        created=created_count,
        updated=updated_count,
        unchanged=unchanged_count,
    )
