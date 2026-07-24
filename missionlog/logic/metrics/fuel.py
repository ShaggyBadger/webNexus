from typing import Any, Dict
from ..reports.context import Shift

def calculate_fuel_metrics(shift: Shift) -> Dict[str, Any]:
    """
    Computes aggregated fuel metrics and thermal variance.
    """
    is_basic = (shift.entry_type == "basic")

    if shift.total_gallons is not None:
        total_gross = shift.total_gallons
    else:
        total_gross = sum(d.gross_gal or 0 for d in shift.deliveries)

    if is_basic:
        # Basic mode: no thermal variance or product mix, net equals gross.
        return {
            "total_gross_gallons": {
                "value": total_gross,
                "type": "exact",
                "fidelity": "summary_estimate",
            },
            "total_net_gallons": {
                "value": total_gross,
                "type": "exact",
                "fidelity": "summary_estimate",
            },
            "thermal_variance": {
                "value": 0,
                "type": "calculated",
                "math": "N/A - basic mode",
                "status": "NOT_COLLECTED_IN_BASIC_MODE",
            },
            "product_mix": {},
        }
    else:
        # Advanced/Legacy mode
        total_net = sum(d.net_gal or 0 for d in shift.deliveries)
        thermal_variance = total_net - total_gross

        product_mix: Dict[str, Dict[str, Any]] = {}
        for d in shift.deliveries:
            existing = product_mix.get(
                d.fuel_type,
                {
                    "value": 0,
                    "type": "exact",
                    "math": "sum(gross_gal) grouped by fuel_type",
                },
            )
            existing["value"] += d.gross_gal or 0
            product_mix[d.fuel_type] = existing

        return {
            "total_gross_gallons": {
                "value": total_gross,
                "type": "exact",
                "fidelity": "measured_itemized",
            },
            "total_net_gallons": {
                "value": total_net,
                "type": "exact",
                "fidelity": "measured_itemized",
            },
            "thermal_variance": {
                "value": thermal_variance,
                "type": "calculated",
                "math": f"{total_net} - {total_gross}",
                "status": "COMPUTED",
            },
            "product_mix": product_mix,
        }
