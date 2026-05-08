from django.apps import AppConfig


class SiteintelConfig(AppConfig):
    name = "siteintel"

    def ready(self):
        import siteintel.logic.signals
