import logging
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Location, SiteIntelligence, MapOverlayUpdate, SiteAttributeDefinition
from tankgauge.models import StoreTankMapping
from ..forms import SiteIntelligenceForm
from ..logic import rack_ops

# Configure Tactical Logger for Site Intelligence
logger = logging.getLogger('webnexus')

class LocationDetailView(DetailView):
    """
    OPERATIONAL FLOW:
    The central intelligence hub for a specific site.
    Displays canonical site metadata, tank configurations, and field intelligence.
    Implements the fallback logic: Personal Notes > Default Notes.
    
    HYBRID METADATA: 
    Processes and orders site-specific attributes by merging global 
    definitions (SiteAttributeDefinition) with custom site quirks (JSON).
    
    ACCESSIBILITY: Publicly viewable.
    """
    model = Location
    template_name = 'siteintel/location_detail.html'
    context_object_name = 'location'

    def get_context_data(self, **kwargs):
        """Resolves the intelligence layer and canonical tank configurations."""
        context = super().get_context_data(**kwargs)
        loc = self.get_object()
        
        # Canonical Store Link
        context['store'] = getattr(loc, 'store_canonical', None)
        
        # Specialized Linked Data
        context['fuel_rack'] = getattr(loc, 'fuel_rack', None)
        context['yard'] = getattr(loc, 'yard', None)

        # Rack Status Sync
        if context['fuel_rack']:
            context['rack_status'] = rack_ops.get_rack_status(self.request.user, context['fuel_rack']) if self.request.user.is_authenticated else None

        # Tank Mappings (Digital Twin) - Only for Stores
        if context['store']:
            context['tanks'] = StoreTankMapping.objects.filter(store=context['store']).order_by('tank_index')
        
        # Intelligence Layer (Dual-Layer Sync)
        personal_intel = None
        default_intel = SiteIntelligence.objects.filter(location=loc, is_default=True).first()
        
        if self.request.user.is_authenticated:
            personal_intel = SiteIntelligence.objects.filter(location=loc, author=self.request.user).first()
            
            # TACTICAL: Determine initial display mode
            # If agent has personal notes, prioritize them; otherwise show shared layer.
            context['intel_mode'] = 'PERSONAL' if personal_intel else 'DEFAULT'
        else:
            # Anonymous users only see shared layer
            context['intel_mode'] = 'PUBLIC'
            
        context['personal_intel'] = personal_intel
        context['default_intel'] = default_intel
        
        # Hybrid Metadata Layer: Order by Global Definitions, then Custom
        # This ensures that standard fields (e.g., Manifolds) appear in a fixed, 
        # prioritized order while still allowing site-specific quirks to follow.
        definitions = SiteAttributeDefinition.objects.all().order_by('sort_weight')
        metadata = loc.metadata or {}
        ordered_attrs = []
        seen_keys = set()
        
        # 1. Process Global Attributes
        for df in definitions:
            if df.field_key in metadata:
                val = metadata[df.field_key]
                # Filter out empty/null values to keep the UI de-cluttered
                if val is not None and val != '':
                    ordered_attrs.append({'label': df.label, 'value': val})
                seen_keys.add(df.field_key)
        
        # 2. Append remaining Custom Attributes (Site Quirks)
        for key, val in metadata.items():
            if key not in seen_keys:
                if val is not None and val != '':
                    # Normalize key label (replace underscores, title case)
                    ordered_attrs.append({'label': key.replace('_', ' ').title(), 'value': val})
        
        context['site_attributes'] = ordered_attrs
        logger.info(f"METADATA_LOAD: Processed {len(ordered_attrs)} attributes for Location {loc.id}")

        # Legacy support for existing logic
        context['intel'] = personal_intel if personal_intel else default_intel
        
        logger.info(f"SITE_ACCESS: Site ID {loc.id} accessed by {self.request.user.username if self.request.user.is_authenticated else 'ANONYMOUS'}")
        return context

class MapOverlayUpdateView(LoginRequiredMixin, CreateView):
    """
    OPERATIONAL FLOW:
    Dedicated interface for drawing tactical map overlays.
    Submits a proposal for administrative review.
    """
    model = MapOverlayUpdate
    fields = ['geojson_data']
    template_name = 'siteintel/map_edit.html'

    def get_context_data(self, **kwargs):
        """Attaches the target location to the drawing context."""
        context = super().get_context_data(**kwargs)
        context['location'] = get_object_or_404(Location, id=self.kwargs.get('location_id'))
        return context

    def form_valid(self, form):
        """Assigns the drawing metadata and logs the submission."""
        loc = get_object_or_404(Location, id=self.kwargs.get('location_id'))
        form.instance.location = loc
        form.instance.submitted_by = self.request.user
        logger.info(f"OVERLAY_PROPOSAL: Map update submitted for Site {loc.id} by Agent {self.request.user}")
        return super().form_valid(form)

    def get_success_url(self):
        """Returns to the site detail view upon successful submission."""
        return reverse('siteintel:location_detail', kwargs={'pk': self.kwargs.get('location_id')})

class SiteIntelligenceUpdateView(LoginRequiredMixin, UpdateView):
    """
    OPERATIONAL FLOW:
    Allows agents to record or update their own field intelligence for a site.
    """
    model = SiteIntelligence
    form_class = SiteIntelligenceForm
    template_name = 'siteintel/intel_form.html'

    def get_object(self, queryset=None):
        """Retrieves or initializes the agent's personal intel record."""
        location_id = self.kwargs.get('location_id')
        location = get_object_or_404(Location, id=location_id)
        intel, created = SiteIntelligence.objects.get_or_create(
            location=location, 
            author=self.request.user,
            defaults={'notes': ''}
        )
        if created:
            logger.info(f"INTEL_INIT: Initialized new field report for Site {location_id} by Agent {self.request.user}")
        return intel

    def get_success_url(self):
        """Returns to the site detail view upon successful update."""
        return reverse('siteintel:location_detail', kwargs={'pk': self.object.location.id})
