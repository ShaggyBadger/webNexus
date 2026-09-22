import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1_000_000

CURRENT_VARIABLES = (
    "temperature_2m,apparent_temperature,precipitation,weather_code,"
    "visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
)
HOURLY_VARIABLES = (
    "temperature_2m,precipitation_probability,precipitation,weather_code,"
    "visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
)


class OpenMeteoError(Exception):
    """Represent a provider request or response failure."""

    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def build_forecast_url(latitude: float, longitude: float) -> str:
    """Build the bounded operational Open-Meteo request URL."""

    query = {
        "latitude": latitude,
        "longitude": longitude,
        "current": CURRENT_VARIABLES,
        "hourly": HOURLY_VARIABLES,
        "forecast_hours": 12,
        "daily": "sunrise,sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }
    return f"{OPEN_METEO_URL}?{urlencode(query)}"


@dataclass(frozen=True)
class ProviderResponse:
    """Contain a validated JSON response and its HTTP status."""

    payload: dict
    status_code: int


def fetch_forecast(latitude: float, longitude: float) -> ProviderResponse:
    """Fetch one forecast from Open-Meteo without automatic retries."""

    request = Request(
        build_forecast_url(latitude, longitude),
        headers={"Accept": "application/json", "User-Agent": "webNexus-weather/1.0"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            status_code = response.status
    except HTTPError as error:
        raise OpenMeteoError("provider_http_error", str(error), error.code) from error
    except (URLError, TimeoutError) as error:
        raise OpenMeteoError("provider_unavailable", str(error)) from error

    if len(body) > MAX_RESPONSE_BYTES:
        raise OpenMeteoError(
            "provider_response_too_large", "Provider response is too large."
        )

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OpenMeteoError(
            "provider_invalid_json", "Provider returned invalid JSON."
        ) from error
    if not isinstance(payload, dict):
        raise OpenMeteoError(
            "provider_invalid_payload", "Provider returned an invalid payload."
        )
    return ProviderResponse(payload=payload, status_code=status_code)
