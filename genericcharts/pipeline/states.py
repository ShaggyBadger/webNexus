"""Canonical US state names and legacy database aliases."""

from __future__ import annotations

import us


_LEGACY_STATE_ALIASES = {"NO": "NC"}


def lookup_state(value: str | None):
    """Return the ``us`` state record for a stored or submitted value."""

    normalized = (value or "").strip()
    normalized = _LEGACY_STATE_ALIASES.get(normalized.upper(), normalized)
    return us.states.lookup(normalized)


def canonical_state(value: str | None) -> str:
    """Return a canonical USPS abbreviation, preserving unknown values."""

    normalized = (value or "").strip()
    state = lookup_state(normalized)
    return state.abbr if state else normalized


def state_variants(value: str | None) -> tuple[str, ...]:
    """Return database values that represent the same state."""

    normalized = (value or "").strip()
    state = lookup_state(normalized)
    if state is None:
        return (normalized,)

    variants = {state.abbr, state.name}
    variants.update(
        alias
        for alias, abbreviation in _LEGACY_STATE_ALIASES.items()
        if abbreviation == state.abbr
    )
    return tuple(sorted(variants))
