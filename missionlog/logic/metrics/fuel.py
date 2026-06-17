from typing import Any, Dict, List

from ..reports.context import Delivery

def calculate_fuel_metrics(deliveries: List[Delivery]) -> Dict[str, Any]:
    """
    Computes aggregated fuel metrics and thermal variance.
    """
    total_gross = sum(d.gross_gal or 0 for d in deliveries)
    total_net = sum(d.net_gal or 0 for d in deliveries)
    
    thermal_variance = total_net - total_gross
    
    product_mix: Dict[str, Dict[str, Any]] = {}
    for d in deliveries:
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
        "total_gross_gallons": {"value": total_gross, "type": "exact"},
        "total_net_gallons": {"value": total_net, "type": "exact"},
        "thermal_variance": {"value": thermal_variance, "type": "calculated", "math": f"{total_net} - {total_gross}"},
        "product_mix": product_mix,
    }
