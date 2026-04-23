from django.shortcuts import render
from django.views.generic import CreateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from django import forms
from .models import StoreUpdate, TankUpdate, Location
from tankgauge.models import Store, TankType, StoreTankMapping
from .forms import StoreUpdateForm, TankUpdateForm, TankUpdateFormSet
import logging

logger = logging.getLogger('webnexus')

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
        if store_num:
            initial['store_num'] = store_num
        if riso_num:
            initial['riso_num'] = riso_num
        return initial

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
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
