from datetime import datetime

from .weather_advisory import classify_advisory


WMO_CONDITIONS = {
    0: "CLEAR",
    1: "MAINLY CLEAR",
    2: "PARTLY CLOUDY",
    3: "OVERCAST",
    45: "FOG",
    48: "DEPOSITING RIME FOG",
    51: "LIGHT DRIZZLE",
    53: "DRIZZLE",
    55: "HEAVY DRIZZLE",
    56: "LIGHT FREEZING DRIZZLE",
    57: "FREEZING DRIZZLE",
    61: "LIGHT RAIN",
    63: "RAIN",
    65: "HEAVY RAIN",
    66: "LIGHT FREEZING RAIN",
    67: "FREEZING RAIN",
    71: "LIGHT SNOW",
    73: "SNOW",
    75: "HEAVY SNOW",
    77: "SNOW GRAINS",
    80: "LIGHT SHOWERS",
    81: "SHOWERS",
    82: "HEAVY SHOWERS",
    85: "LIGHT SNOW SHOWERS",
    86: "HEAVY SNOW SHOWERS",
    95: "THUNDERSTORM",
    96: "THUNDERSTORM WITH HAIL",
    99: "THUNDERSTORM WITH HEAVY HAIL",
}


def condition_label(code: int | None) -> str:
    """Return a stable display label for a WMO weather code."""

    return WMO_CONDITIONS.get(code, "UNKNOWN CONDITIONS")


def _event(
    event_type: str,
    value: str,
    severity: str = "info",
    glyph: str = "!",
) -> dict:
    return {
        "type": event_type,
        "time": value,
        "label": event_type.upper(),
        "severity": severity,
        "glyph": glyph,
    }


def _visibility_miles(value):
    if value is None:
        return None
    return round(float(value) / 1609.344, 2)


def normalize_weather(payload: dict, *, source: str, fetched_at: datetime) -> dict:
    """Convert an Open-Meteo response into the browser weather contract."""

    current = payload.get("current")
    hourly = payload.get("hourly")
    daily = payload.get("daily")
    if not isinstance(current, dict) or not isinstance(hourly, dict):
        raise ValueError("provider_missing_weather_sections")

    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    if not isinstance(times, list) or not isinstance(temperatures, list):
        raise ValueError("provider_missing_hourly_series")
    if len(times) != len(temperatures) or len(times) < 12:
        raise ValueError("provider_invalid_hourly_alignment")

    def value_at(key: str, index: int):
        values = hourly.get(key)
        return (
            values[index] if isinstance(values, list) and index < len(values) else None
        )

    hourly_points = []
    for index, time_value in enumerate(times[:12]):
        code = value_at("weather_code", index)
        hourly_points.append(
            {
                "time": time_value,
                "temperature": temperatures[index],
                "precipitation_probability": value_at(
                    "precipitation_probability", index
                ),
                "precipitation": value_at("precipitation", index),
                "weather_code": code,
                "condition": condition_label(code),
                "visibility": _visibility_miles(value_at("visibility", index)),
                "wind_speed": value_at("wind_speed_10m", index),
                "wind_direction": value_at("wind_direction_10m", index),
                "wind_gusts": value_at("wind_gusts_10m", index),
            }
        )

    events = []
    if isinstance(daily, dict):
        for event_type in ("sunrise", "sunset"):
            values = daily.get(event_type)
            if isinstance(values, list) and values:
                glyph = "☀" if event_type == "sunrise" else "◒"
                events.append(_event(event_type, values[0], glyph=glyph))
    for point in hourly_points:
        if point["weather_code"] in (95, 96, 99):
            events.append(_event("storm", point["time"], "warning", "⚡"))
        elif (point.get("precipitation") or 0) > 0:
            events.append(_event("precipitation", point["time"], glyph="●"))

    current_code = current.get("weather_code")
    current_data = {
        "time": current.get("time"),
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "weather_code": current_code,
        "condition": condition_label(current_code),
        "precipitation": current.get("precipitation"),
        "visibility": _visibility_miles(current.get("visibility")),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),
    }
    return {
        "source": source,
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "fetched_at": fetched_at.isoformat(),
        "age_seconds": 0,
        "timezone": payload.get("timezone"),
        "units": {
            "temperature": payload.get("current_units", {}).get(
                "temperature_2m", "fahrenheit"
            ),
            "wind_speed": payload.get("current_units", {}).get("wind_speed_10m", "mph"),
            "visibility": "miles",
        },
        "current": current_data,
        "hourly": hourly_points,
        "events": events,
        "advisory": classify_advisory(current_data, hourly_points),
    }
