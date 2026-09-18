"""Resolve physical tank capacity and ullage-basis facts for calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db.models import F


@dataclass(frozen=True)
class CapacityResolution:
    """Describe the capacity available to one mapped or virtual calculation."""

    scope: str
    status: str
    physical_capacity_gallons: Decimal | None
    ullage_endpoint_percent_exact: Decimal | None
    authority: str
    evidence_ids: tuple[str, ...] = ()
    profile_version: int | None = None
    warning_codes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def usable(self) -> bool:
        """Return whether a geometry calculation may use this resolution."""

        return self.physical_capacity_gallons is not None and self.status in {
            "READY",
            "LEGACY_UNVERIFIED",
        }


class CapacityResolutionService:
    """Resolve canonical mapped capacity or a provisional legacy baseline."""

    LEGACY_WARNING = "legacy_capacity_unverified"

    def resolve_mapping(self, mapping) -> CapacityResolution:
        """Resolve capacity for a mapped tank without mutating database state."""

        capacity = self._decimal(mapping.physical_capacity_gallons)
        if capacity and capacity > 0:
            if mapping.capacity_verified:
                return CapacityResolution(
                    scope="MAPPED_AUTHORITATIVE",
                    status="READY",
                    physical_capacity_gallons=capacity,
                    ullage_endpoint_percent_exact=self._decimal(
                        mapping.ullage_endpoint_percent_exact
                    ),
                    authority=mapping.capacity_source,
                    profile_version=mapping.profile_version,
                )

            return CapacityResolution(
                scope="MAPPED_AUTHORITATIVE",
                status="LEGACY_UNVERIFIED",
                physical_capacity_gallons=capacity,
                ullage_endpoint_percent_exact=self._decimal(
                    mapping.ullage_endpoint_percent_exact
                ),
                authority=mapping.capacity_source or "LEGACY_ASSUMED",
                profile_version=mapping.profile_version,
                warning_codes=(self.LEGACY_WARNING,),
            )

        reading = self._latest_reading(mapping)
        if reading is not None:
            endpoint = self._decimal(reading.volume) + self._decimal(reading.ullage)
            if endpoint > 0:
                return CapacityResolution(
                    scope="MAPPED_AUTHORITATIVE",
                    status="LEGACY_UNVERIFIED",
                    physical_capacity_gallons=endpoint,
                    ullage_endpoint_percent_exact=self._decimal(
                        reading.ullage_endpoint_percent_exact
                    ),
                    authority="LEGACY_ASSUMED",
                    evidence_ids=(str(reading.id),),
                    profile_version=mapping.profile_version,
                    warning_codes=(self.LEGACY_WARNING,),
                )

        tank_type_capacity = self._decimal(
            mapping.tank_type.capacity if mapping.tank_type else None
        )
        if tank_type_capacity and tank_type_capacity > 0:
            return CapacityResolution(
                scope="MAPPED_AUTHORITATIVE",
                status="LEGACY_UNVERIFIED",
                physical_capacity_gallons=tank_type_capacity,
                ullage_endpoint_percent_exact=None,
                authority="OFFICIAL_AVAILABLE",
                profile_version=mapping.profile_version,
                warning_codes=(self.LEGACY_WARNING,),
            )

        return CapacityResolution(
            scope="MAPPED_AUTHORITATIVE",
            status="UNRESOLVED",
            physical_capacity_gallons=None,
            ullage_endpoint_percent_exact=None,
            authority="UNRESOLVED",
            profile_version=mapping.profile_version,
            warning_codes=("capacity_unresolved",),
        )

    def resolve_virtual(
        self,
        *,
        total_capacity_gallons,
        evidence_ids: tuple[str, ...] = (),
        basis_percent_exact=None,
    ) -> CapacityResolution:
        """Resolve a provisional capacity for an unmapped tank estimate."""

        capacity = self._decimal(total_capacity_gallons)
        if capacity is None or capacity <= 0:
            return CapacityResolution(
                scope="VIRTUAL_PROVISIONAL",
                status="UNRESOLVED",
                physical_capacity_gallons=None,
                ullage_endpoint_percent_exact=None,
                authority="UNRESOLVED",
                warning_codes=("capacity_unresolved",),
            )

        return CapacityResolution(
            scope="VIRTUAL_PROVISIONAL",
            status="LEGACY_UNVERIFIED",
            physical_capacity_gallons=capacity,
            ullage_endpoint_percent_exact=self._decimal(basis_percent_exact),
            authority="LEGACY_ASSUMED",
            evidence_ids=evidence_ids,
            warning_codes=(self.LEGACY_WARNING,),
        )

    @staticmethod
    def _latest_reading(mapping):
        from atg.models import VeederReading

        return (
            VeederReading.objects.filter(
                ticket__store_id=mapping.store_id,
                tank_index=mapping.tank_index,
                acceptance_status="ACCEPTED",
            )
            .filter(fuel_type__name__iexact=mapping.fuel_type)
            .select_related("ticket")
            .order_by(
                F("ticket__ticket_timestamp").desc(nulls_last=True),
                F("ticket__uploaded_at").desc(nulls_last=True),
                F("created_at").desc(nulls_last=True),
                F("id").desc(nulls_last=True),
            )
            .first()
        )

    @staticmethod
    def _decimal(value) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
