from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import VeederTicket


class VeederListView(LoginRequiredMixin, ListView):
    """
    TACTICAL UI:
    Historical archive of all ingested Veeder tickets.
    Allows for quick review and target selection.
    """

    model = VeederTicket
    template_name = "atg/veeder_list.html"
    context_object_name = "tickets"
    paginate_by = 10

    def get_queryset(self):
        # Prefetch readings to avoid N+1 queries in the list view
        return (
            VeederTicket.objects.all()
            .select_related("store", "uploaded_by")
            .prefetch_related("readings")
        )


class VeederDetailView(LoginRequiredMixin, DetailView):
    """
    TACTICAL UI:
    High-fidelity view of a single ticket package.
    Displays the original evidence image alongside the structured ML dataset.
    """

    model = VeederTicket
    template_name = "atg/veeder_detail.html"
    context_object_name = "ticket"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Sort readings by tank index for consistency
        context["readings"] = self.object.readings.all().order_by("tank_index")
        return context
