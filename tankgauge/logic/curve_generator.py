import math


def generate_inch_gallon_curve(
    radius_inches: float,
    length_inches: float,
    max_depth: int,
) -> list[dict]:
    """Generate inch-to-gallon points for a horizontal cylinder tank.

    Args:
        radius_inches: Tank radius in inches.
        length_inches: Tank length in inches.
        max_depth: Maximum chart depth in inches.

    Returns:
        List of points shaped as {"inches": int, "gallons": float}.

    Raises:
        ValueError: If geometric inputs are invalid.
    """
    if radius_inches <= 0:
        raise ValueError("radius_inches must be greater than zero.")
    if length_inches <= 0:
        raise ValueError("length_inches must be greater than zero.")
    if max_depth <= 0:
        return []

    points: list[dict] = []
    max_fill_height_inches = 2 * radius_inches

    for inches in range(1, int(max_depth) + 1):
        fluid_height_inches = min(float(inches), max_fill_height_inches)
        segment_area_square_inches = (radius_inches**2) * math.acos(
            (radius_inches - fluid_height_inches) / radius_inches
        ) - (radius_inches - fluid_height_inches) * math.sqrt(
            max(
                0.0,
                2 * radius_inches * fluid_height_inches - fluid_height_inches**2,
            )
        )
        volume_gallons = (segment_area_square_inches * length_inches) / 231.0
        points.append({"inches": inches, "gallons": round(volume_gallons, 1)})

    return points
