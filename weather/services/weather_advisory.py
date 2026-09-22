ADVERSE_CODES = {
    51,
    53,
    55,
    56,
    57,
    61,
    63,
    65,
    66,
    67,
    71,
    73,
    75,
    77,
    80,
    81,
    82,
    85,
    86,
    95,
    96,
    99,
}
STORM_CODES = {95, 96, 99}


def classify_advisory(current: dict, hourly: list[dict]) -> dict:
    """Classify current and near-term weather using deterministic thresholds."""

    reasons = []
    current_code = current.get("weather_code")
    current_temperature = current.get("temperature")
    current_wind = current.get("wind_speed")
    current_gusts = current.get("wind_gusts")
    current_visibility = current.get("visibility")

    if current_code in ADVERSE_CODES:
        reasons.append("active_precipitation")
    if current_code in STORM_CODES:
        reasons.append("thunderstorm")
    if current_wind is not None and current_wind >= 20:
        reasons.append("high_wind")
    if current_gusts is not None and current_gusts >= 30:
        reasons.append("high_gusts")
    if current_visibility is not None and current_visibility < 1:
        reasons.append("low_visibility")
    if current_temperature is not None and (
        current_temperature <= 32 or current_temperature >= 100
    ):
        reasons.append("temperature_boundary")

    near_term = hourly[:3]
    if any((point.get("precipitation_probability") or 0) >= 60 for point in near_term):
        reasons.append("near_term_precipitation_probability")

    adverse_reasons = {
        "active_precipitation",
        "thunderstorm",
        "high_wind",
        "high_gusts",
        "low_visibility",
    }
    level = (
        "ADVERSE"
        if adverse_reasons.intersection(reasons)
        else "WATCH" if reasons else "NORMAL"
    )
    return {
        "level": level,
        "reason_codes": reasons,
        "message": reasons[0].replace("_", " ").upper() if reasons else None,
    }
