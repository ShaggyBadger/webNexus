import uuid

from django.db import models


class WeatherQuotaLock(models.Model):
    """Singleton row used to serialize rolling provider-call reservations."""

    singleton_key = models.PositiveSmallIntegerField(unique=True, default=1)
    updated_at = models.DateTimeField(auto_now=True)


class WeatherRequest(models.Model):
    """Record one reserved or completed request to the Open-Meteo provider."""

    class Status(models.TextChoices):
        RESERVED = "RESERVED", "Reserved"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        ABANDONED = "ABANDONED", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    status = models.CharField(max_length=16, choices=Status.choices)
    requested_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    request_version = models.CharField(max_length=20, default="v1")

    class Meta:
        indexes = [
            models.Index(fields=("requested_at",), name="weather_req_time_idx"),
            models.Index(
                fields=("status", "requested_at"),
                name="weather_req_status_time_idx",
            ),
            models.Index(fields=("completed_at",), name="weather_req_done_idx"),
        ]
