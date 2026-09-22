from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .services.distance import distance_miles
from .services.open_meteo_client import ProviderResponse, build_forecast_url
from .services.weather_presenter import normalize_weather
from .models import WeatherRequest


def weather_payload():
    """Build a deterministic twelve-point provider fixture."""

    times = [f"2026-08-29T{hour:02d}:00" for hour in range(12)]
    return {
        "latitude": 35.7,
        "longitude": -78.6,
        "timezone": "America/New_York",
        "current_units": {
            "temperature_2m": "°F",
            "wind_speed_10m": "mp/h",
        },
        "current": {
            "time": times[0],
            "temperature_2m": 72,
            "apparent_temperature": 73,
            "weather_code": 2,
            "precipitation": 0,
            "visibility": 16093,
            "wind_speed_10m": 8,
            "wind_direction_10m": 315,
            "wind_gusts_10m": 14,
        },
        "hourly": {
            "time": times,
            "temperature_2m": list(range(72, 84)),
            "precipitation_probability": [10] * 12,
            "precipitation": [0] * 12,
            "weather_code": [2] * 12,
            "visibility": [16093] * 12,
            "wind_speed_10m": [8] * 12,
            "wind_direction_10m": [315] * 12,
            "wind_gusts_10m": [14] * 12,
        },
        "daily": {
            "sunrise": ["2026-08-29T06:30"],
            "sunset": ["2026-08-29T19:52"],
        },
    }


class WeatherDistanceTests(TestCase):
    """Verify the weather cache's geographic distance primitive."""

    def test_same_coordinates_have_zero_distance(self):
        self.assertAlmostEqual(distance_miles(35.7, -78.6, 35.7, -78.6), 0)

    def test_forecast_url_contains_required_parameters(self):
        url = build_forecast_url(35.7, -78.6)
        self.assertIn("forecast_hours=12", url)
        self.assertIn("timezone=auto", url)
        self.assertIn("daily=sunrise%2Csunset", url)


class WeatherPresenterTests(TestCase):
    """Verify normalized provider data used by the homepage component."""

    def test_normalize_weather_returns_twelve_points_and_miles(self):
        normalized = normalize_weather(
            weather_payload(),
            source="provider",
            fetched_at=datetime(2026, 8, 29, tzinfo=datetime_timezone.utc),
        )
        self.assertEqual(len(normalized["hourly"]), 12)
        self.assertEqual(normalized["current"]["visibility"], 10.0)
        self.assertEqual(normalized["advisory"]["level"], "NORMAL")
        self.assertEqual(
            {event["type"] for event in normalized["events"]}, {"sunrise", "sunset"}
        )


class WeatherApiTests(TestCase):
    """Verify cache-first API behavior without calling the real provider."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("weather:current")

    @patch("weather.services.weather_service.fetch_forecast")
    def test_cache_miss_calls_provider_and_stores_result(self, fetch_mock):
        fetch_mock.return_value = ProviderResponse(weather_payload(), 200)
        response = self.client.post(
            self.url,
            {"latitude": 35.7, "longitude": -78.6},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["source"], "provider")
        self.assertEqual(WeatherRequest.objects.count(), 1)
        self.assertEqual(WeatherRequest.objects.first().status, "SUCCEEDED")

    @patch("weather.services.weather_service.fetch_forecast")
    def test_fresh_nearby_cache_does_not_call_provider(self, fetch_mock):
        fetch_mock.return_value = ProviderResponse(weather_payload(), 200)
        self.client.post(
            self.url, {"latitude": 35.7, "longitude": -78.6}, format="json"
        )
        fetch_mock.reset_mock()
        response = self.client.post(
            self.url,
            {"latitude": 35.71, "longitude": -78.61},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["source"], "cache")
        fetch_mock.assert_not_called()

    def test_invalid_coordinates_use_error_contract(self):
        response = self.client.post(
            self.url,
            {"latitude": 999, "longitude": -78.6},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_coordinates")

    @override_settings(WEATHER_PROVIDER_MAX_ATTEMPTS=0)
    def test_budget_exhaustion_returns_standard_error(self):
        response = self.client.post(
            self.url,
            {"latitude": 35.7, "longitude": -78.6},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "weather_budget_exhausted")

    @patch("weather.services.weather_service.fetch_forecast")
    def test_malformed_provider_payload_uses_error_contract(self, fetch_mock):
        payload = weather_payload()
        payload["current_units"] = None
        fetch_mock.return_value = ProviderResponse(payload, 200)

        response = self.client.post(
            self.url,
            {"latitude": 35.7, "longitude": -78.6},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "weather_unavailable")
        self.assertEqual(WeatherRequest.objects.first().status, "FAILED")


class WeatherStripTemplateTests(TestCase):
    """Verify the homepage includes only the critical weather status line."""

    def test_forecast_controls_and_empty_state_are_server_rendered(self):
        response = self.client.get(reverse("homepage:homepage"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'x-text="hasWeather ? currentLine : status"')
        self.assertContains(response, 'aria-live="polite"')
        self.assertNotContains(response, "TEMPERATURE TREND")
        self.assertNotContains(response, "weather-chart")
