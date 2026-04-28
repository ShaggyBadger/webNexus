import math
import logging
from tankgauge.models import TankChart
from .utils import haversine

# Tactical Logger
logger = logging.getLogger('tankgauge')

def perform_tank_calc(tank_type, fuel_type, current_inches, delivery_gallons):
    """
    OPERATIONAL FLOW:
    Executes the core volume estimation for a single tank.
    Translates physical depth into gallons, factors in planned delivery,
    and validates against safety limits (90% capacity).
    
    Returns a dictionary of tactical results.
    """
    logger.info(f"CALC_START: TankType '{tank_type}' ({fuel_type}) @ {current_inches} in + {delivery_gallons}G delivery")
    
    initial_gallons = get_volume_from_depth(tank_type, current_inches)
    final_gallons = initial_gallons + delivery_gallons
    final_inches = get_depth_from_volume(tank_type, final_gallons)

    # SAFETY_MARGIN: 90% availability check
    # Standard operational limit to prevent overfills and allow for thermal expansion.
    capacity = tank_type.capacity or 0
    ninety_percent_limit = capacity * 0.9
    avail_90 = max(0, ninety_percent_limit - initial_gallons)

    # NO_FIT_WARNING: Triggered if the final volume exceeds the 90% safety threshold.
    no_fit_warning = final_gallons > ninety_percent_limit
    
    if no_fit_warning:
        logger.warning(f"NO_FIT_ALERT: Final volume {int(final_gallons)}G exceeds 90% limit ({int(ninety_percent_limit)}G)")

    result = {
        "fuel_type": fuel_type,
        "initial_inches": current_inches,
        "initial_gallons": int(initial_gallons),
        "delivery_gallons": int(delivery_gallons),
        "avail_90": int(avail_90),
        "final_gallons": int(final_gallons),
        "final_inches": final_inches,
        "no_fit_warning": no_fit_warning,
    }
    
    logger.info(f"CALC_COMPLETE: Initial {int(initial_gallons)}G -> Final {int(final_gallons)}G")
    return result


def get_volume_from_depth(tank_type, depth):
    """
    TACTICAL INTEL:
    Converts physical depth (inches) to volume (gallons) using chart interpolation.
    
    ALGORITHM:
    1. Exact Match: If the depth is an integer, fetch the exact chart entry.
    2. Linear Interpolation: For fractional depths, interpolate between bounding entries.
    3. Boundary Protection: Caps results at 0 or the maximum chart volume.
    """
    if depth <= 0:
        return 0.0

    # BOUNDARY_CHECK: Handle depth exceeding chart limits
    max_entry = (
        TankChart.objects.filter(tank_type=tank_type).order_by("-inches").first()
    )
    if max_entry and depth >= max_entry.inches:
        return float(max_entry.gallons)

    # OPTIMIZATION: Check for exact integer depth match
    if depth == int(depth):
        chart_entry = TankChart.objects.filter(
            tank_type=tank_type, inches=int(depth)
        ).first()
        if chart_entry:
            return float(chart_entry.gallons)

    # INTERPOLATION_LOGIC: Find bounding inches
    lower_inch = math.floor(depth)
    upper_inch = math.ceil(depth)

    # Fetch bounding charts for linear interpolation
    charts = TankChart.objects.filter(
        tank_type=tank_type, inches__in=[lower_inch, upper_inch]
    ).order_by("inches")

    if charts.count() == 2:
        c1, c2 = charts[0], charts[1]
        # Standard Linear Interpolation: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
        # Note: x2 - x1 is always 1 in this context.
        volume = c1.gallons + (depth - c1.inches) * (c2.gallons - c1.gallons)
        return float(volume)
    elif charts.count() == 1:
        # Fallback to nearest match if bounding fails
        return float(charts[0].gallons)

    return 0.0


def get_depth_from_volume(tank_type, target_gallons):
    """
    TACTICAL INTEL:
    Reverse calculation: Converts volume (gallons) to physical depth (inches).
    Used to estimate the 'Final Stick' reading after a delivery.
    
    ALGORITHM:
    1. Bracketing: Finds chart entries immediately above and below the target volume.
    2. Linear Interpolation: Calculates precise floating-point depth.
    """
    if target_gallons <= 0:
        return 0.0

    # BOUNDARY_CHECK: Handle target exceeding chart capacity
    max_entry = (
        TankChart.objects.filter(tank_type=tank_type).order_by("-gallons").first()
    )
    if max_entry and target_gallons >= max_entry.gallons:
        return float(max_entry.inches)

    # BRACKETING: Find entries that bracket the target gallons
    lower_entry = (
        TankChart.objects.filter(tank_type=tank_type, gallons__lte=target_gallons)
        .order_by("-gallons")
        .first()
    )
    upper_entry = (
        TankChart.objects.filter(tank_type=tank_type, gallons__gte=target_gallons)
        .order_by("gallons")
        .first()
    )

    if not lower_entry:
        return 0.0

    if upper_entry:
        if lower_entry == upper_entry or lower_entry.gallons == upper_entry.gallons:
            return float(lower_entry.inches)

        # INTERPOLATION: Solve for depth (inches)
        x1, y1 = lower_entry.inches, lower_entry.gallons
        x2, y2 = upper_entry.inches, upper_entry.gallons

        depth = x1 + (target_gallons - y1) * (x2 - x1) / (y2 - y1)
        return round(float(depth), 2)

    return float(lower_entry.inches)
