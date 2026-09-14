"""Stable identifiers for generated package selection scopes."""

from __future__ import annotations

import re

from .states import lookup_state


def package_scope_key(
    state: str | None,
    store_numbers: tuple[int, ...],
    store_type_ids: tuple[int, ...] = (),
) -> str:
    """Return a stable, filename-safe key for one normalized selection."""

    normalized_state = (state or "").strip()
    state_record = lookup_state(normalized_state)
    state_key = _slug(state_record.name if state_record else normalized_state)
    if not state_key:
        state_key = "full"

    scope_parts = [state_key]
    if store_numbers:
        stores = "-".join(str(number) for number in store_numbers)
        scope_parts.append(f"stores-{stores}")
    if store_type_ids:
        types = "-".join(str(type_id) for type_id in store_type_ids)
        scope_parts.append(f"types-{types}")
    return "-".join(scope_parts)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
