import logging
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from ..models import FuelRack
from tankgauge.models import Store
from ..logic import rack_ops

# Configure Tactical Logger for Site Intelligence
logger = logging.getLogger('webnexus')

class FuelRackListView(LoginRequiredMixin, ListView):
    """
    OPERATIONAL FLOW:
    Provides a centralized 'Sector Hub' for all fuel racks.
    
    This view fulfills the requirement for manual target selection when 
    automatic GPS detection is unavailable or undesirable. It calculates 
    real-time lockout status for the authenticated agent across all racks.
    """
    model = FuelRack
    template_name = 'siteintel/rack_list.html'
    context_object_name = 'racks'

    def get_context_data(self, **kwargs):
        """
        Enriches the rack list with tactical status metadata.
        """
        logger.info(f"RACK_SECTOR_ACCESS: Fuel Rack list accessed by Agent {self.request.user}")
        context = super().get_context_data(**kwargs)
        
        # TACTICAL_STATUS_SYNC:
        # We pre-calculate status for the entire sector to ensure the UI
        # reflects current lockout windows immediately upon load.
        rack_data = []
        for rack in context['racks']:
            status = rack_ops.get_rack_status(self.request.user, rack)
            rack_data.append({
                'rack': rack,
                'status': status
            })
        
        context['rack_data'] = rack_data
        return context

class SiteIntelDashboardView(LoginRequiredMixin, ListView):
    """
    OPERATIONAL FLOW:
    Central hub for managing site intelligence.
    Lists existing stores and provides pathways for creating new entries or updates.
    """
    model = Store
    template_name = 'siteintel/dashboard.html'
    context_object_name = 'stores'
    paginate_by = 25

    def get_queryset(self):
        """Handles numeric search and target acquisition logic."""
        queryset = Store.objects.all().order_by('store_num')
        q = self.request.GET.get('q')
        if q:
            logger.info(f"DASHBOARD_QUERY: Filtering by '{q}' triggered by {self.request.user}")
            queryset = queryset.filter(
                Q(store_num__icontains=q) | 
                Q(riso_num__icontains=q) | 
                Q(store_name__icontains=q) |
                Q(city__icontains=q)
            )
        return queryset

class SiteSelectorView(TemplateView):
    """
    OPERATIONAL FLOW:
    A dedicated 'Target Acquisition' page for finding site intelligence.
    """
    template_name = 'siteintel/site_selector.html'
