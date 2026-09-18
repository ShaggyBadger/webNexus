"""Transactional updates for canonical tank-capacity profiles."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from tankgauge.models import StoreTankMapping, TankCapacityProfileHistory


class CapacityProfileError(ValueError):
    """Raised when a capacity profile cannot be safely updated."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class CapacityProfileService:
    """Apply verified capacity changes without silently recalculating geometry."""

    @staticmethod
    @transaction.atomic
    def verify_mapping(
        *,
        mapping_id: int,
        physical_capacity_gallons,
        ullage_endpoint_percent_exact,
        profile_version: int,
        reason: str,
        user,
    ) -> StoreTankMapping:
        """Verify one mapping profile and append its audit history."""

        try:
            capacity = Decimal(str(physical_capacity_gallons))
            basis = Decimal(str(ullage_endpoint_percent_exact))
        except (InvalidOperation, TypeError, ValueError):
            raise CapacityProfileError(
                "invalid_capacity_profile",
                "Capacity and ullage basis must be valid decimal values.",
            )

        if capacity <= 0 or basis <= 0:
            raise CapacityProfileError(
                "invalid_capacity_profile",
                "Capacity and ullage basis must be greater than zero.",
            )
        if not reason or len(reason.strip()) < 3:
            raise CapacityProfileError(
                "verification_reason_required",
                "A verification reason is required.",
            )

        mapping = StoreTankMapping.objects.select_for_update().get(pk=mapping_id)
        if mapping.profile_version != profile_version:
            raise CapacityProfileError(
                "stale_profile_version",
                "The tank profile changed. Reload it before verifying.",
            )

        previous = {
            "capacity": mapping.physical_capacity_gallons,
            "verified": mapping.capacity_verified,
            "source": mapping.capacity_source,
            "basis": mapping.ullage_endpoint_percent_exact,
        }
        mapping.physical_capacity_gallons = capacity
        mapping.ullage_endpoint_percent_exact = basis
        mapping.capacity_verified = True
        mapping.capacity_source = "MANUAL_VERIFIED"
        mapping.profile_status = "READY"
        mapping.profile_version += 1
        mapping.capacity_verified_at = timezone.now()
        mapping.capacity_verified_by = user
        mapping.capacity_notes = reason.strip()
        mapping.save(
            update_fields=[
                "physical_capacity_gallons",
                "ullage_endpoint_percent_exact",
                "capacity_verified",
                "capacity_source",
                "profile_status",
                "profile_version",
                "capacity_verified_at",
                "capacity_verified_by",
                "capacity_notes",
                "capacity_updated_at",
            ]
        )
        TankCapacityProfileHistory.objects.create(
            mapping=mapping,
            profile_version=mapping.profile_version,
            previous_capacity_gallons=previous["capacity"],
            new_capacity_gallons=capacity,
            previous_verified=previous["verified"],
            new_verified=True,
            previous_source=previous["source"],
            new_source=mapping.capacity_source,
            previous_basis_percent=previous["basis"],
            new_basis_percent=basis,
            reason=reason.strip(),
            changed_by=user,
        )
        return mapping
