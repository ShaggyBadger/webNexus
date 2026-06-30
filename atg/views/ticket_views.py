from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from missionlog.models import FuelType


class VeederUploadView(LoginRequiredMixin, TemplateView):
    """
    TACTICAL UI:
    The primary mobile-optimized entry point for ATG data collection.
    Allows field agents to log tank readings quickly.
    """

    template_name = "atg/ticket_upload.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fuel_types = list(FuelType.objects.all().order_by("name").values("id", "name"))
        context["fuel_types"] = fuel_types
        return context
