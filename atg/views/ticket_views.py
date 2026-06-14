from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from missionlog.models import FuelType
from tankgauge.models import Store


class VeederUploadView(LoginRequiredMixin, TemplateView):
    """
    TACTICAL UI:
    The primary mobile-optimized entry point for ATG data collection.
    Allows field agents to upload a ticket photo and log tank readings.
    """

    template_name = "atg/ticket_upload.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide fuel types for the standardized dropdowns
        context["fuel_types"] = FuelType.objects.all().order_by("name")
        # We might want to pass recent tickets or stores if needed,
        # but for now, we'll let the frontend handle store search via API.
        return context
