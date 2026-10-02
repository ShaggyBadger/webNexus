"""Django app configuration for binder payments."""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Registers the public payment-link page with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
