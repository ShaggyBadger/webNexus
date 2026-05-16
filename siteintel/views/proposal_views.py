import logging
from django import forms
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from ..models import StoreUpdate, TankUpdate, LocationType, Location
from tankgauge.models import Store, StoreTankMapping
from ..forms import StoreUpdateForm, TankUpdateForm, TankUpdateFormSet

# Configure Tactical Logger for Site Intelligence
logger = logging.getLogger('webnexus')

class StoreUpdateFormsetMixin:
    """
    TACTICAL_MIXIN:
    Common logic for handling TankUpdate inline formsets across Create and Update views.
    """
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        
        # Get distinct store types for the dropdown
        existing_types = Store.objects.exclude(store_type__isnull=True).exclude(store_type='').values_list('store_type', flat=True).distinct().order_by('store_type')
        data['existing_store_types'] = list(existing_types)
        
        if self.request.POST:
            data['tank_formset'] = TankUpdateFormSet(self.request.POST, instance=self.object)
        else:
            if self.object:
                # UPDATE: Load existing tank proposals
                data['tank_formset'] = TankUpdateFormSet(instance=self.object)
            else:
                # CREATE: Pre-populate with current canonical mappings
                location_id = self.request.GET.get('location_id')
                store_num = self.request.GET.get('store_num')
                initial_tanks = []
                
                # TACTICAL: Resolve store from location_id first, then fallback to store_num
                store = None
                if location_id and location_id.isdigit():
                    location = Location.objects.filter(id=location_id).first()
                    if location and hasattr(location, 'store_canonical'):
                        store = location.store_canonical
                
                if not store and store_num and store_num.isdigit():
                    store = Store.objects.filter(store_num=store_num).first()
                
                if store:
                    mappings = StoreTankMapping.objects.filter(store=store).order_by('tank_index')
                    for mapping in mappings:
                        initial_tanks.append({
                            'tank_index': mapping.tank_index,
                            'fuel_type': mapping.fuel_type.lower() if mapping.fuel_type else '',
                            'reported_capacity': mapping.tank_type.capacity if mapping.tank_type else 0,
                            'tank_type': mapping.tank_type,
                        })
                
                if initial_tanks:
                    logger.info(f"TANK_SYNC: Initializing {len(initial_tanks)} tank forms for Store {store.store_num if store else 'UNK'}")
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
            # Ensure submitting_by is set on Create, but preserved on Update if needed
            # For simplicity, we assume author doesn't change on Edit
            if not form.instance.pk:
                form.instance.submitted_by = self.request.user
            
            # Linkage logic (same for Create and Update)
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

            # TACTICAL: Apply auto-defaults
            tanks = tank_formset.save(commit=False)
            next_auto_index = 1
            
            for tank in tanks:
                if tank.tank_index is None:
                    while any(t.tank_index == next_auto_index for t in tanks if t.tank_index is not None):
                        next_auto_index += 1
                    tank.tank_index = next_auto_index
                    next_auto_index += 1
                
                if tank.reported_capacity is None:
                    if tank.tank_type and tank.tank_type.capacity is not None:
                        tank.reported_capacity = tank.tank_type.capacity
                    else:
                        tank.reported_capacity = 0
                
                tank.save()

            for obj in tank_formset.deleted_objects:
                obj.delete()
            
            logger.info(f"PROPOSAL_ACTION: Success for Store {store_num} by {self.request.user}")
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

class StoreUpdateCreateView(LoginRequiredMixin, StoreUpdateFormsetMixin, CreateView):
    """
    OPERATIONAL FLOW:
    Provides the field interface for submitting site intelligence proposals.
    """
    model = StoreUpdate
    form_class = StoreUpdateForm
    template_name = 'siteintel/proposal_form.html'
    success_url = reverse_lazy('siteintel:proposal_list')

    def get_initial(self):
        """Pre-populates the proposal form with known site data."""
        initial = super().get_initial()
        location_id = self.request.GET.get('location_id')
        store_num = self.request.GET.get('store_num')
        riso_num = self.request.GET.get('riso_num')
        
        # 1. Handle Location-based pre-population (The Robust Method)
        if location_id and location_id.isdigit():
            location = Location.objects.filter(id=location_id).first()
            if location:
                initial['location'] = location.id
                initial['location_type'] = location.location_type.id
                initial['store_name'] = location.name
                initial['address'] = location.address
                initial['city'] = location.city
                initial['state'] = location.state
                initial['zip_code'] = location.zip_code
                initial['lat'] = location.lat
                initial['lon'] = location.lon
                
                # Linkage to canonical store
                if hasattr(location, 'store_canonical'):
                    store = location.store_canonical
                    initial['store'] = store.id
                    initial['store_num'] = store.store_num
                    initial['riso_num'] = store.riso_num
                    initial['store_type'] = store.store_type

                # Specialized Data
                if hasattr(location, 'fuel_rack'):
                    initial['rack_lockout_days'] = location.fuel_rack.lockout_days
                    initial['rack_config_json'] = location.fuel_rack.config_json
                if hasattr(location, 'yard'):
                    initial['yard_notes'] = location.yard.notes
                
                return initial

        # 2. Fallback to ID-based pre-population
        if store_num and store_num.isdigit():
            initial['store_num'] = store_num
        if riso_num and riso_num.isdigit():
            initial['riso_num'] = riso_num

        gas_station = LocationType.objects.filter(name="Gas Station").first()
        if gas_station:
            initial['location_type'] = gas_station.id

        target_store = None
        if store_num and store_num.isdigit():
            target_store = Store.objects.filter(store_num=store_num).first()
        elif riso_num and riso_num.isdigit():
            target_store = Store.objects.filter(riso_num=riso_num).first()

        if target_store:
            initial['store'] = target_store.id
            initial['store_name'] = target_store.store_name
            initial['store_type'] = target_store.store_type
            if target_store.location:
                initial['location'] = target_store.location.id
                if target_store.location.location_type:
                    initial['location_type'] = target_store.location.location_type.id

        return initial

class StoreUpdateUpdateView(LoginRequiredMixin, UserPassesTestMixin, StoreUpdateFormsetMixin, UpdateView):
    """
    OPERATIONAL FLOW:
    Allows agents to correct or refine their PENDING proposals.
    """
    model = StoreUpdate
    form_class = StoreUpdateForm
    template_name = 'siteintel/proposal_form.html'
    success_url = reverse_lazy('siteintel:proposal_list')

    def test_func(self):
        """Security: Only author can edit, and only if PENDING."""
        obj = self.get_object()
        return obj.submitted_by == self.request.user and obj.status == 'PENDING'

class StoreUpdateDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    OPERATIONAL FLOW:
    Allows agents to retract PENDING proposals.
    """
    model = StoreUpdate
    template_name = 'siteintel/proposal_confirm_delete.html'
    success_url = reverse_lazy('siteintel:proposal_list')

    def test_func(self):
        """Security: Only author can delete, and only if PENDING."""
        obj = self.get_object()
        return obj.submitted_by == self.request.user and obj.status == 'PENDING'

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
