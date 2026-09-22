from django.apps import AppConfig


class WeatherConfig(AppConfig):
    """Configure the weather integration application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "weather"
