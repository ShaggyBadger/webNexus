from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from ..reports.context import Shift

DEFAULT_HOURLY_RATE = Decimal("30.00")


def calculate_earnings(
    shift: Shift, hourly_rate: Decimal = DEFAULT_HOURLY_RATE
) -> Dict[str, Any]:
    """
    Computes estimated earnings based on hours.
    """
    hours = shift.duration_hours or 0
    hours_decimal = Decimal(str(hours))
    earnings = (hours_decimal * hourly_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return {
        "estimated_earnings": {
            "value": float(earnings),
            "type": "estimated",
            "math": f"{hours:.2f} hrs * ${hourly_rate:.2f}/hr",
        }
    }
