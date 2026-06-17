from typing import List
from .base import BaseValidator, ValidationIssue, Severity


class MissionValidator(BaseValidator):
    """
    Checks for high-level mission data integrity.
    """

    def validate(self) -> List[ValidationIssue]:
        issues = []
        shift = self.context.shift

        # 1. Missing End Mileage for Completed Missions
        if shift.is_completed and shift.end_miles is None:
            issues.append(
                ValidationIssue(
                    code="MISSING_END_MILEAGE",
                    message="Mission marked completed but is missing ending odometer reading.",
                    severity=Severity.CRITICAL,
                    affected_ids=[shift.id]
                )
            )

        # 2. Duration Anomaly (e.g., > 16 hours)
        duration = shift.duration_hours
        if duration and duration > 16:
            issues.append(
                ValidationIssue(
                    code="LONG_SHIFT_DURATION",
                    message=f"Mission duration is unusually long ({duration:.2f} hours).",
                    severity=Severity.WARNING,
                    affected_ids=[shift.id]
                )
            )

        return issues
