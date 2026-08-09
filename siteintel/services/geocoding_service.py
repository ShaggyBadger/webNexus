"""Nominatim geocoding services used by Site Intelligence."""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError


NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_USER_AGENT = "webNexus-Tactical-Agent/1.0"


class GeocodingServiceError(Exception):
    """Raised when Nominatim cannot fulfill a geocoding request."""


class GeocodingNoResultError(GeocodingServiceError):
    """Raised when Nominatim returns no matching location."""


@dataclass(frozen=True)
class GeocodingResult:
    """Normalized coordinates returned by Nominatim."""

    latitude: float
    longitude: float


def _request_nominatim(path: str, params: dict[str, str]) -> list[dict]:
    """Fetch a JSON result list from Nominatim."""
    query_string = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{NOMINATIM_BASE_URL}{path}?{query_string}",
        headers={"User-Agent": NOMINATIM_USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GeocodingServiceError("Nominatim request failed") from exc

    if not isinstance(data, list):
        raise GeocodingServiceError("Nominatim returned an invalid response")
    return data


def forward_geocode(address_query: str) -> GeocodingResult:
    """Locate an entered address so field operators can start near the target."""
    results = _request_nominatim(
        "/search",
        {
            "q": address_query,
            "format": "jsonv2",
            "limit": "1",
        },
    )
    if not results:
        raise GeocodingNoResultError("No matching address found")

    try:
        return GeocodingResult(
            latitude=float(results[0]["lat"]),
            longitude=float(results[0]["lon"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingServiceError("Nominatim returned invalid coordinates") from exc


def reverse_geocode(latitude: str, longitude: str) -> dict[str, str]:
    """Convert coordinates into normalized address fields for the proposal form."""
    results = _request_nominatim(
        "/reverse",
        {
            "format": "jsonv2",
            "lat": latitude,
            "lon": longitude,
        },
    )
    if not results:
        raise GeocodingNoResultError("No address found for coordinates")

    address = results[0].get("address", {})
    return {
        "address": (
            f"{address.get('house_number', '')} {address.get('road', '')}".strip()
            if address.get("road")
            else address.get("pedestrian", "")
        ),
        "city": address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("suburb", ""),
        "state": address.get("state", ""),
        "zip_code": address.get("postcode", ""),
    }
