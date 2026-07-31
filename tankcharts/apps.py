from django.apps import AppConfig


class TankChartsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tankcharts"
    verbose_name = "Tank Charts"

    def ready(self) -> None:
        import tankcharts.signals  # noqa: F401
