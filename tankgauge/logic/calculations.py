import math
from tankgauge.models import TankChart

def get_volume_from_depth(tank_type, depth):
    """
    Given a tank_type and depth (inches), returns the volume (gallons).
    Supports linear interpolation for float depths.
    Caps at min/max available in chart.
    """
    if depth <= 0:
        return 0.0
    
    # Get max inches in chart to handle "over-depth"
    max_entry = TankChart.objects.filter(tank_type=tank_type).order_by('-inches').first()
    if max_entry and depth >= max_entry.inches:
        return float(max_entry.gallons)

    # Get exact match if depth is an integer or has no fractional part
    if depth == int(depth):
        chart_entry = TankChart.objects.filter(tank_type=tank_type, inches=int(depth)).first()
        if chart_entry:
            return float(chart_entry.gallons)
    
    # For float depths, interpolate
    lower_inch = math.floor(depth)
    upper_inch = math.ceil(depth)
    
    # Get charts for the lower and upper bounds
    charts = TankChart.objects.filter(tank_type=tank_type, inches__in=[lower_inch, upper_inch]).order_by('inches')
    
    if charts.count() == 2:
        c1, c2 = charts[0], charts[1]
        volume = c1.gallons + (depth - c1.inches) * (c2.gallons - c1.gallons)
        return float(volume)
    elif charts.count() == 1:
        return float(charts[0].gallons)
    
    return 0.0

def get_depth_from_volume(tank_type, target_gallons):
    """
    Given a tank_type and target_gallons, returns the depth (inches).
    Supports linear interpolation to return a float (2 decimal places).
    Caps at min/max available in chart.
    """
    if target_gallons <= 0:
        return 0.0

    # Handle over-gallons: find max gallons in chart
    max_entry = TankChart.objects.filter(tank_type=tank_type).order_by('-gallons').first()
    if max_entry and target_gallons >= max_entry.gallons:
        return float(max_entry.inches)

    # Find the entries that bracket our target_gallons
    lower_entry = TankChart.objects.filter(tank_type=tank_type, gallons__lte=target_gallons).order_by('-gallons').first()
    upper_entry = TankChart.objects.filter(tank_type=tank_type, gallons__gte=target_gallons).order_by('gallons').first()

    if not lower_entry:
        return 0.0
    
    if upper_entry:
        if lower_entry == upper_entry or lower_entry.gallons == upper_entry.gallons:
            return float(lower_entry.inches)
        
        # Linear interpolation
        x1, y1 = lower_entry.inches, lower_entry.gallons
        x2, y2 = upper_entry.inches, upper_entry.gallons
        
        depth = x1 + (target_gallons - y1) * (x2 - x1) / (y2 - y1)
        return round(float(depth), 2)
    
    return float(lower_entry.inches)
