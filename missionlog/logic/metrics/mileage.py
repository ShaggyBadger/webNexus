from typing import Dict, Any
from ..reports.context import Shift


def calculate_mileage_metrics(shift: Shift) -> Dict[str, Any]:
    """
    Computes mileage metrics.
    """
    miles = shift.total_miles
    stops = len(shift.deliveries)

    avg_miles_per_stop = miles / stops if stops > 0 else 0

    return {
        "total_miles": {"value": miles, "type": "exact"},
        "avg_miles_per_stop": {
            "value": round(avg_miles_per_stop, 2),
            "type": "calculated",
            "math": f"{miles} / {stops}",
        },
    }
