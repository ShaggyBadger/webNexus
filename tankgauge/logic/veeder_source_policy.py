"""Centralized operational source selection for store tank data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Exists, OuterRef, Q, QuerySet


@dataclass(frozen=True)
class VeederSourceDecision:
    """Describe the operational source and readiness for a store."""

    source: str
    readiness: str
    reason_code: str


class VeederSourcePolicy:
    """Resolve whether operational store data must use Veeder evidence."""

    OFFICIAL = "OFFICIAL"
    VEEDER_ONLY = "VEEDER_ONLY"
    READY = "READY"
    PENDING = "PENDING"
    UNAVAILABLE = "UNAVAILABLE"

    @classmethod
    def store_has_readings(cls, store: Any) -> bool:
        """Return whether a store has at least one accepted Veeder reading."""
        from atg.models import VeederReading

        store_id = getattr(store, "pk", store)
        return VeederReading.objects.filter(ticket__store_id=store_id).exists()

    @classmethod
    def resolve_store(cls, store: Any) -> VeederSourceDecision:
        """Resolve store-level operational source from accepted evidence."""
        if cls.store_has_readings(store):
            return VeederSourceDecision(
                source=cls.VEEDER_ONLY,
                readiness=cls.READY,
                reason_code="accepted_veeder_reading_exists",
            )
        return VeederSourceDecision(
            source=cls.OFFICIAL,
            readiness=cls.READY,
            reason_code="no_accepted_veeder_reading",
        )

    @classmethod
    def mapping_has_readings(cls, mapping: Any) -> bool:
        """Return whether a physical mapping has accepted Veeder evidence."""
        from atg.models import VeederReading

        if mapping.tank_index is None:
            return False
        readings = VeederReading.objects.filter(
            ticket__store_id=mapping.store_id,
            tank_index=mapping.tank_index,
        )
        if mapping.fuel_type:
            readings = readings.filter(fuel_type__name__iexact=mapping.fuel_type)
        return readings.exists()

    @classmethod
    def filter_operational_mappings(cls, mappings: QuerySet) -> QuerySet:
        """Hide stale official-only mappings for Veeder-active stores."""
        from atg.models import VeederReading

        active_store = VeederReading.objects.filter(
            ticket__store_id=OuterRef("store_id")
        )
        matching_reading = VeederReading.objects.filter(
            ticket__store_id=OuterRef("store_id"),
            tank_index=OuterRef("tank_index"),
        )
        return mappings.annotate(
            _veeder_store_active=Exists(active_store),
            _veeder_mapping_has_reading=Exists(
                matching_reading.filter(fuel_type__name__iexact=OuterRef("fuel_type"))
            ),
        ).filter(Q(_veeder_store_active=False) | Q(_veeder_mapping_has_reading=True))

    @classmethod
    def mapping_readiness(cls, mapping: Any, *, has_geometry: bool) -> str:
        """Return readiness without permitting official fallback."""
        if has_geometry:
            return cls.READY
        if cls.mapping_has_readings(mapping):
            return cls.PENDING
        return cls.UNAVAILABLE
