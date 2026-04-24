from django.shortcuts import render
from django.views.generic import CreateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from django import forms
from .models import StoreUpdate, TankUpdate, Location, LocationType
from tankgauge.models import Store, TankType, StoreTankMapping
from tankgauge.logic.utils import haversine
from .forms import StoreUpdateForm, TankUpdateForm, TankUpdateFormSet
import logging
import json
import urllib.request
from urllib.error import URLError

logger = logging.getLogger('webnexus')

@login_required
def reverse_geocode_api(request):
    """
    TACTICAL INTEL:
    Reverse geocoding using Nominatim (OpenStreetMap).
    Converts LAT/LON coordinates into a physical address.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'error': 'LAT and LON are required'}, status=400)
    
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
            return JsonResponse(result)
            
    except URLError as e:
        logger.error(f"Geocoding Error: {str(e)}")
        return JsonResponse({'error': 'Service unavailable'}, status=503)
    except Exception as e:
        logger.error(f"Unexpected Geocoding Error: {str(e)}")
        return JsonResponse({'error': 'Internal error'}, status=500)

@login_required
def proximity_check_api(request):
    """
    TACTICAL INTEL:
    Checks for existing stores within a ~250ft (0.05 mile) radius.
    Used to prevent duplicate site creation.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    exclude_num = request.GET.get('exclude_store_num')
    
    if not lat or not lon:
        return JsonResponse({'error': 'LAT and LON are required'}, status=400)
    
    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except ValueError:
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
            
    return JsonResponse({'matches': matches})

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
            initial['store_num'] = target_store.store_num
            initial['riso_num'] = target_store.riso_num
            initial['store_type'] = target_store.store_type
            if target_store.location and target_store.location.location_type:
                initial['location_type'] = target_store.location.location_type.id

        return initial

    def get_context_data(self, **kwargs):
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
            
            logger.info(f"Initial Tanks for Store {store_num}: {initial_tanks}")
            
            if initial_tanks:
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

            self.object = form.save()
            tank_formset.instance = self.object
            tank_formset.save()
            
            logger.info(f"Field Proposal Submitted: Store {store_num} by {self.request.user}")
            return super().form_valid(form)
        else:
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
        queryset = Store.objects.all().order_by('store_num')
        q = self.request.GET.get('q')
        if q:
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
    Queries TankType records within a +/- 10% tolerance of the reported capacity
    and/or matching a text query.
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
        except ValueError:
            pass # Ignore invalid capacity if query is present
            
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
    
    store = Store.objects.filter(
        Q(store_num=query) | Q(riso_num=query)
    ).first()
    
    if store:
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
    
    return JsonResponse({'error': 'Store not found'}, status=404)
