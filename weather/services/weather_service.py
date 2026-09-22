import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import WeatherQuotaLock, WeatherRequest
from .distance import distance_miles
from .open_meteo_client import OpenMeteoError, fetch_forecast
from .weather_presenter import normalize_weather

logger = logging.getLogger("weather")


def _coordinates(latitude: float, longitude: float) -> tuple[Decimal, Decimal]:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid_coordinates")
    return Decimal(f"{latitude:.6f}"), Decimal(f"{longitude:.6f}")


def _find_cached(latitude: Decimal, longitude: Decimal, *, max_age_minutes: int):
    cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
    candidates = WeatherRequest.objects.filter(
        status=WeatherRequest.Status.SUCCEEDED,
        completed_at__gte=cutoff,
        response_json__isnull=False,
    ).order_by("-completed_at")
    for request in candidates:
        miles = distance_miles(
            float(latitude),
            float(longitude),
            float(request.latitude),
            float(request.longitude),
        )
        if miles <= settings.WEATHER_CACHE_RADIUS_MILES:
            return request
    return None


def _serialize(request: WeatherRequest, source: str) -> dict:
    fetched_at = request.completed_at or request.requested_at
    data = normalize_weather(
        request.response_json, source=source, fetched_at=fetched_at
    )
    data["latitude"] = float(request.latitude)
    data["longitude"] = float(request.longitude)
    data["age_seconds"] = max(0, int((timezone.now() - fetched_at).total_seconds()))
    return data


def get_weather(*, latitude: float, longitude: float) -> tuple[dict, int]:
    """Return nearby weather, reserving one provider attempt only on a miss."""

    latitude_decimal, longitude_decimal = _coordinates(latitude, longitude)
    cached = _find_cached(latitude_decimal, longitude_decimal, max_age_minutes=15)
    if cached:
        return _serialize(cached, "cache"), 200

    now = timezone.now()
    # Keep the quota lock through the provider call. This serializes cache misses
    # so concurrent requests cannot reserve duplicate provider calls.
    with transaction.atomic():
        quota_lock, _ = WeatherQuotaLock.objects.select_for_update().get_or_create(
            singleton_key=1
        )
        del quota_lock
        WeatherRequest.objects.filter(
            status=WeatherRequest.Status.RESERVED,
            reservation_expires_at__lt=now,
        ).update(status=WeatherRequest.Status.ABANDONED, completed_at=now)
        cached = _find_cached(latitude_decimal, longitude_decimal, max_age_minutes=15)
        if cached:
            return _serialize(cached, "cache"), 200
        cutoff = now - timedelta(hours=settings.WEATHER_PROVIDER_WINDOW_HOURS)
        used = WeatherRequest.objects.filter(requested_at__gte=cutoff).count()
        if used >= settings.WEATHER_PROVIDER_MAX_ATTEMPTS:
            stale = _find_cached(
                latitude_decimal, longitude_decimal, max_age_minutes=60
            )
            if stale:
                return _serialize(stale, "stale"), 200
            return {"error_code": "weather_budget_exhausted"}, 503
        reservation = WeatherRequest.objects.create(
            latitude=latitude_decimal,
            longitude=longitude_decimal,
            status=WeatherRequest.Status.RESERVED,
            requested_at=now,
            reservation_expires_at=now + timedelta(minutes=2),
        )
        try:
            provider_response = fetch_forecast(
                float(latitude_decimal), float(longitude_decimal)
            )
            request_data = normalize_weather(
                provider_response.payload,
                source="provider",
                fetched_at=timezone.now(),
            )
        except OpenMeteoError as error:
            WeatherRequest.objects.filter(pk=reservation.pk).update(
                status=WeatherRequest.Status.FAILED,
                completed_at=timezone.now(),
                http_status=error.status_code,
                error_code=error.code,
                error_message=str(error),
            )
            stale = _find_cached(
                latitude_decimal, longitude_decimal, max_age_minutes=60
            )
            if stale:
                return _serialize(stale, "stale"), 200
            return {"error_code": error.code}, 502
        except (AttributeError, TypeError, ValueError, KeyError) as error:
            WeatherRequest.objects.filter(pk=reservation.pk).update(
                status=WeatherRequest.Status.FAILED,
                completed_at=timezone.now(),
                error_code="provider_invalid_payload",
                error_message=str(error),
            )
            stale = _find_cached(
                latitude_decimal, longitude_decimal, max_age_minutes=60
            )
            if stale:
                return _serialize(stale, "stale"), 200
            return {"error_code": "provider_invalid_payload"}, 502

        WeatherRequest.objects.filter(pk=reservation.pk).update(
            status=WeatherRequest.Status.SUCCEEDED,
            completed_at=timezone.now(),
            response_json=provider_response.payload,
            http_status=provider_response.status_code,
        )
        request_data["latitude"] = float(latitude_decimal)
        request_data["longitude"] = float(longitude_decimal)
        return request_data, 200
