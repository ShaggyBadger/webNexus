import math


EARTH_RADIUS_MILES = 3956.0


def distance_miles(
    latitude_one: float,
    longitude_one: float,
    latitude_two: float,
    longitude_two: float,
) -> float:
    """Return the great-circle distance between two decimal-degree points."""

    lat_one, lon_one, lat_two, lon_two = map(
        math.radians,
        (latitude_one, longitude_one, latitude_two, longitude_two),
    )
    delta_lon = lon_two - lon_one
    delta_lat = lat_two - lat_one
    haversine_value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_one) * math.cos(lat_two) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(haversine_value))
