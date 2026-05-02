from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, ListView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django import forms
from .models import StoreUpdate, TankUpdate, Location, LocationType, SiteIntelligence, MapOverlayUpdate, FuelRack, RackCheckIn
from tankgauge.models import Store, TankType, StoreTankMapping
from tankgauge.logic.utils import haversine
from .forms import StoreUpdateForm, TankUpdateForm, TankUpdateFormSet, SiteIntelligenceForm
from .logic import rack_ops
import logging
import json
import urllib.request
from urllib.error import URLError

# Configure Tactical Logger for Site Intelligence
logger = logging.getLogger('webnexus')

@login_required
def reverse_geocode_api(request):
    """
    TACTICAL INTEL:
    Reverse geocoding using Nominatim (OpenStreetMap).
    Converts LAT/LON coordinates into a physical address to reduce manual entry errors.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        logger.warning("GEOCODE_ATTEMPT_FAILED: Missing coordinates in request.")
        return JsonResponse({'error': 'LAT and LON are required'}, status=400)
    
    logger.info(f"GEOCODE_REQUEST: Lat {lat}, Lon {lon} triggered by user {request.user}")
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'webNexus-Tactical-Agent/1.0'}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
            address = data.get('address', {})
            # Tactical normalization of address components
            result = {
                'address': address.get('house_number', '') + ' ' + address.get('road', '') if address.get('road') else address.get('pedestrian', ''),
                'city': address.get('city') or address.get('town') or address.get('village') or address.get('suburb', ''),
                'state': address.get('state', ''),
                'zip_code': address.get('postcode', '')
            }
            logger.info(f"GEOCODE_SUCCESS: Decoded to {result.get('address')}, {result.get('city')}")
            return JsonResponse(result)
            
    except URLError as e:
        logger.error(f"GEOCODE_SERVICE_UNAVAILABLE: {str(e)}")
        return JsonResponse({'error': 'Service unavailable'}, status=503)
    except Exception as e:
        logger.error(f"GEOCODE_UNEXPECTED_FAILURE: {str(e)}")
        return JsonResponse({'error': 'Internal error'}, status=500)

@login_required
def proximity_check_api(request):
    """
    TACTICAL INTEL:
    Checks for existing stores within a ~250ft (0.05 mile) radius.
    Used as a duplication safeguard during new site proposals.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    exclude_num = request.GET.get('exclude_store_num')
    
    if not lat or not lon:
        logger.warning("PROXIMITY_CHECK_ABORTED: Missing coordinates.")
        return JsonResponse({'error': 'LAT and LON are required'}, status=400)
    
    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except ValueError:
        logger.warning(f"PROXIMITY_CHECK_FAILED: Invalid coordinates provided: {lat}, {lon}")
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)
        
    # Search radius in miles (0.05 miles is approx 264 feet)
    RADIUS = 0.05
    
    matches = []
    stores = Store.objects.exclude(lat__isnull=True).exclude(lon__isnull=True)
    
    if exclude_num:
        stores = stores.exclude(store_num=exclude_num)
        
    for store in stores:
        dist = haversine(lat_val, lon_val, store.lat, store.lon)
        if dist <= RADIUS:
            matches.append({
                'store_num': store.store_num,
                'store_name': store.store_name,
                'distance_ft': int(dist * 5280) # Convert miles to feet
            })
    
    if matches:
        logger.warning(f"PROXIMITY_ALERT: {len(matches)} sites detected near Lat {lat}, Lon {lon} by user {request.user}")
    else:
        logger.info(f"PROXIMITY_CLEARED: No conflicting sites detected for Lat {lat}, Lon {lon}")
            
    return JsonResponse({'matches': matches})

@login_required
def rack_status_api(request):
    """
    TACTICAL INTEL:
    Returns the lockout status for fuel racks relative to the current user.
    Can be filtered by a specific rack_id.
    """
    rack_id = request.GET.get('rack_id')
    
    if rack_id:
        rack = get_object_or_404(FuelRack, id=rack_id)
        status = rack_ops.get_rack_status(request.user, rack)
        return JsonResponse({
            'rack_id': rack.id,
            'name': rack.location.name,
            'status': status
        })
    
    # Return all racks with user status
    racks = FuelRack.objects.all().select_related('location')
    results = []
    for rack in racks:
        status = rack_ops.get_rack_status(request.user, rack)
        results.append({
            'id': rack.id,
            'name': rack.location.name,
            'lat': rack.location.lat,
            'lon': rack.location.lon,
            'status': status
        })
        
    return JsonResponse({'racks': results})

@login_required
def rack_checkin_api(request):
    """
    TACTICAL INTEL:
    POST endpoint to record a fuel rack check-in.
    Resets the lockout timer for the user.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    try:
        data = json.loads(request.body)
        rack_id = data.get('rack_id')
        lat = data.get('lat')
        lon = data.get('lon')
        accuracy = data.get('accuracy')
        
        if not rack_id:
            return JsonResponse({'error': 'rack_id is required'}, status=400)
            
        rack = get_object_or_404(FuelRack, id=rack_id)
        checkin = rack_ops.record_checkin(
            user=request.user,
            rack=rack,
            lat=float(lat) if lat is not None else None,
            lon=float(lon) if lon is not None else None,
            accuracy=float(accuracy) if accuracy is not None else None
        )
        
        status = rack_ops.get_rack_status(request.user, rack)
        
        return JsonResponse({
            'success': True,
            'message': f"Check-in recorded at {rack.location.name}",
            'is_verified': checkin.is_verified,
            'status': status
        })
        
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"RACK_CHECKIN_ERROR: Invalid data - {str(e)}")
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    except Exception as e:
        logger.error(f"RACK_CHECKIN_CRITICAL: {str(e)}")
        return JsonResponse({'error': 'Server error'}, status=500)

class StoreUpdateCreateView(LoginRequiredMixin, CreateView):
    """
    OPERATIONAL FLOW:
    Provides the field interface for submitting site intelligence proposals.
    Handles both Store metadata and Tank configurations in a single submission.
    """
    model = StoreUpdate
    form_class = StoreUpdateForm
    template_name = 'siteintel/proposal_form.html'
    success_url = reverse_lazy('siteintel:proposal_list')

    def get_initial(self):
        """Pre-populates the proposal form with known site data."""
        initial = super().get_initial()
        store_num = self.request.GET.get('store_num')
        riso_num = self.request.GET.get('riso_num')
        
        # Default to "Gas Station" as the baseline
        gas_station = LocationType.objects.filter(name="Gas Station").first()
        if gas_station:
            initial['location_type'] = gas_station.id

        # If targeting an existing store, override with its current type
        target_store = None
        if store_num:
            target_store = Store.objects.filter(store_num=store_num).first()
        elif riso_num:
            target_store = Store.objects.filter(riso_num=riso_num).first()

        if target_store:
            logger.info(f"PROPOSAL_INIT: Pre-populating form for Store #{target_store.store_num}")
            initial['store_num'] = target_store.store_num
            initial['riso_num'] = target_store.riso_num
            initial['store_name'] = target_store.store_name
            initial['store_type'] = target_store.store_type
            if target_store.location and target_store.location.location_type:
                initial['location_type'] = target_store.location.location_type.id

        return initial

    def get_context_data(self, **kwargs):
        """Injects distinct store types and tank formsets into the context."""
        data = super().get_context_data(**kwargs)
        
        # Get distinct store types for the dropdown
        existing_types = Store.objects.exclude(store_type__isnull=True).exclude(store_type='').values_list('store_type', flat=True).distinct().order_by('store_type')
        data['existing_store_types'] = list(existing_types)
        
        store_num = self.request.GET.get('store_num')
        
        if self.request.POST:
            data['tank_formset'] = TankUpdateFormSet(self.request.POST)
        else:
            # TACTICAL INTEL: Pre-populate formset with current canonical tank mapping
            # if we are targeting an existing store.
            initial_tanks = []
            if store_num:
                store = Store.objects.filter(store_num=store_num).first()
                if store:
                    mappings = StoreTankMapping.objects.filter(store=store).order_by('tank_index')
                    for mapping in mappings:
                        initial_tanks.append({
                            'tank_index': mapping.tank_index,
                            'fuel_type': mapping.fuel_type.lower() if mapping.fuel_type else '',
                            'reported_capacity': mapping.tank_type.capacity if mapping.tank_type else 0,
                            'tank_type': mapping.tank_type, # Pass the object itself
                        })
            
            if initial_tanks:
                logger.info(f"TANK_SYNC: Initializing {len(initial_tanks)} tank forms for Store {store_num}")
                # TACTICAL: Create a one-off factory. 
                # InlineFormSet needs extra to be set to the length of initial if instance is None
                CustomFormSet = forms.inlineformset_factory(
                    StoreUpdate, TankUpdate, form=TankUpdateForm, 
                    extra=len(initial_tanks), can_delete=True
                )
                data['tank_formset'] = CustomFormSet(initial=initial_tanks)
            else:
                data['tank_formset'] = TankUpdateFormSet()
                
        return data

    def form_valid(self, form):
        """Finalizes the submission, linking to existing store/location if found."""
        context = self.get_context_data()
        tank_formset = context['tank_formset']
        
        if tank_formset.is_valid():
            # Auto-assign the submitting agent
            form.instance.submitted_by = self.request.user
            
            # Check if this update targets an existing store/location
            store_num = form.cleaned_data.get('store_num')
            riso_num = form.cleaned_data.get('riso_num')
            
            existing_store = None
            if store_num:
                existing_store = Store.objects.filter(store_num=store_num).first()
            if not existing_store and riso_num:
                existing_store = Store.objects.filter(riso_num=riso_num).first()
            
            if existing_store:
                form.instance.store = existing_store
                form.instance.location = existing_store.location
                logger.info(f"PROPOSAL_LINK: Linking submission to existing Store #{existing_store.store_num}")

            self.object = form.save()
            tank_formset.instance = self.object
            tank_formset.save()
            
            logger.info(f"PROPOSAL_SUBMITTED: Store {store_num} by Agent {self.request.user}")
            return super().form_valid(form)
        else:
            logger.warning(f"PROPOSAL_REJECTED: Tank formset validation failed for Agent {self.request.user}")
            return self.render_to_response(self.get_context_data(form=form))

class StoreUpdateListView(LoginRequiredMixin, ListView):
    """
    OPERATIONAL FLOW:
    Allows agents to track their own pending and historical proposals.
    """
    model = StoreUpdate
    template_name = 'siteintel/proposal_list.html'
    context_object_name = 'proposals'

    def get_queryset(self):
        """Filters proposals to only show those belonging to the current agent."""
        return StoreUpdate.objects.filter(submitted_by=self.request.user).order_by('-submitted_at')

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

@login_required
def tank_type_search_api(request):
    """
    TACTICAL INTEL:
    AJAX endpoint for the 'Tank Picker'.
    Queries TankType records within a +/- 10% tolerance of the reported capacity.
    """
    capacity = request.GET.get('capacity')
    query = request.GET.get('q')
    
    if not capacity and not query:
        return JsonResponse({'error': 'Capacity or Query is required'}, status=400)
    
    filters = Q()
    
    if capacity:
        try:
            cap_val = int(capacity)
            lower_bound = cap_val * 0.9
            upper_bound = cap_val * 1.1
            filters &= Q(capacity__gte=lower_bound, capacity__lte=upper_bound)
            logger.info(f"TANK_SEARCH: Capacity near {cap_val}G for {request.user}")
        except ValueError:
            logger.warning(f"TANK_SEARCH_FAILED: Invalid capacity '{capacity}'")
            
    if query:
        filters &= (Q(name__icontains=query) | Q(manufacturer__icontains=query) | Q(model__icontains=query))
    
    matches = TankType.objects.filter(filters).values('id', 'name', 'manufacturer', 'capacity', 'max_depth')[:20]
    return JsonResponse({'results': list(matches)})

@login_required
def store_lookup_api(request):
    """
    TACTICAL INTEL:
    AJAX endpoint for pre-filling the proposal form if a store is identified.
    Returns store metadata and canonical tank mappings.
    """
    query = request.GET.get('q')
    if not query:
        return JsonResponse({'error': 'Query is required'}, status=400)
    
    logger.info(f"STORE_LOOKUP_REQUEST: ID '{query}' triggered by {request.user}")
    store = Store.objects.filter(
        Q(store_num=query) | Q(riso_num=query)
    ).first()
    
    if store:
        logger.info(f"STORE_LOOKUP_HIT: Found Store #{store.store_num}")
        mappings = StoreTankMapping.objects.filter(store=store).order_by('tank_index')
        tanks = []
        for m in mappings:
            tanks.append({
                'tank_index': m.tank_index,
                'fuel_type': m.fuel_type,
                'capacity': m.tank_type.capacity if m.tank_type else 0,
                'max_depth': m.tank_type.max_depth if m.tank_type else 0,
                'tank_type_id': m.tank_type.id if m.tank_type else None,
                'tank_type_name': m.tank_type.name if m.tank_type else 'UNKNOWN'
            })

        data = {
            'store_num': store.store_num,
            'riso_num': store.riso_num,
            'store_name': store.store_name,
            'store_type': store.store_type,
            'address': store.address,
            'city': store.city,
            'state': store.state,
            'zip_code': store.zip_code,
            'lat': store.lat,
            'lon': store.lon,
            'tanks': tanks
        }
        return JsonResponse(data)
    
    logger.info(f"STORE_LOOKUP_MISS: No record found for ID '{query}'")
    return JsonResponse({'error': 'Store not found'}, status=404)

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
        
        # Tank Mappings (Digital Twin)
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
        from .models import SiteAttributeDefinition
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

class SiteSelectorView(TemplateView):
    """
    OPERATIONAL FLOW:
    A dedicated 'Target Acquisition' page for finding site intelligence.
    """
    template_name = 'siteintel/site_selector.html'

def site_lookup_api(request):
    """
    TACTICAL INTEL:
    Numeric-focused lookup for site selection.
    Targets Store Numbers and RISO identifiers. 
    Optimized for high-speed target acquisition in field conditions.
    """
    q = request.GET.get('q', '').strip()
    if not q or not q.isdigit():
        return JsonResponse({'results': []})
    
    user_str = request.user.username if request.user.is_authenticated else "ANONYMOUS"
    logger.info(f"TARGET_SCAN: Searching for site ID '{q}' by user {user_str}")
    
    # SEARCH_STORES: Target canonical retail sites by ID
    stores = Store.objects.filter(
        Q(store_num__icontains=q) | Q(riso_num__icontains=q)
    ).select_related('location')[:10]
    
    results = []
    for s in stores:
        loc_id = s.location.id if s.location else None
        results.append({
            'type': 'STORE',
            'id': loc_id,
            'store_pk': s.id,
            'store_num': s.store_num,
            'name': s.store_name or f"Store #{s.store_num}",
            'city': s.city or "UNKNOWN LOC",
            'has_location': loc_id is not None
        })
    
    logger.info(f"TARGET_SCAN_COMPLETE: Identified {len(results)} potential targets for ID '{q}'")
    return JsonResponse({'results': results})

@login_required
def initialize_location_for_store(request, store_id):
    """
    OPERATIONAL_INIT:
    Ensures a Store has a corresponding Location record so intel can be recorded.
    This enables organic growth of the site intelligence database as agents visit sites.
    """
    store = get_object_or_404(Store, id=store_id)
    
    if not store.location:
        logger.info(f"INTEL_BOOTSTRAP: Initializing Location record for Store #{store.store_num}")
        
        # Create a basic location from store data
        gas_station, created = LocationType.objects.get_or_create(
            name="Gas Station",
            defaults={'description': "Retail fuel site or convenience store."}
        )
        if created:
            logger.info("INTEL_BOOTSTRAP: Created new 'Gas Station' LocationType")
        
        loc = Location.objects.create(
            name=store.store_name or f"Store #{store.store_num}",
            location_type=gas_station,
            address=store.address,
            city=store.city,
            state=store.state,
            zip_code=store.zip_code,
            lat=store.lat,
            lon=store.lon
        )
        
        store.location = loc
        store.save()
        logger.info(f"INTEL_INIT_SUCCESS: Store #{store.store_num} linked to Location ID {loc.id} by {request.user}")
    
    return redirect('siteintel:location_detail', pk=store.location.id)
