from typing import Dict, Any
from ..reports.context import Shift

def calculate_efficiency_metrics(shift: Shift) -> Dict[str, Any]:
    """
    Computes efficiency metrics (MPG).
    """
    miles = shift.total_miles
    total_truck_fuel = sum(log.gallons for log in shift.truck_fuel_logs)
    
    mpg = miles / float(total_truck_fuel) if total_truck_fuel > 0 else 0
    
    return {
        "mpg": {"value": round(mpg, 2), "type": "calculated", "math": f"{miles} / {total_truck_fuel}"}
    }
