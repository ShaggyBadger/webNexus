from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from missionlog.models import FuelType


class VeederReviewQueueView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Staff-only Alpine review workspace for quick-capture Veeder tickets."""

    template_name = "atg/review_queue.html"

    def test_func(self):
        return bool(self.request.user and self.request.user.is_staff)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fuel_types"] = list(
            FuelType.objects.all().order_by("name").values("id", "name")
        )
        return context
