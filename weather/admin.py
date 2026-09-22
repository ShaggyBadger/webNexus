from django.contrib import admin

from .models import WeatherQuotaLock, WeatherRequest


@admin.register(WeatherRequest)
class WeatherRequestAdmin(admin.ModelAdmin):
    """Provide read-only operational visibility into weather provider calls."""

    list_display = ("requested_at", "status", "latitude", "longitude", "http_status")
    list_filter = ("status", "request_version")
    search_fields = ("error_code", "error_message")
    readonly_fields = [field.name for field in WeatherRequest._meta.fields]


@admin.register(WeatherQuotaLock)
class WeatherQuotaLockAdmin(admin.ModelAdmin):
    """Expose the singleton quota lock without editable operational fields."""

    readonly_fields = ["singleton_key", "updated_at"]
