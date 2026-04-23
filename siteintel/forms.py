from django import forms
from .models import StoreUpdate, TankUpdate
from tankgauge.models import TankType

class StoreUpdateForm(forms.ModelForm):
    """
    OPERATIONAL FLOW:
    Captures the primary metadata for a store intelligence proposal.
    """
    class Meta:
        model = StoreUpdate
        fields = [
            'store_num', 'riso_num', 'store_name', 
            'address', 'city', 'state', 'zip_code', 
            'lat', 'lon'
        ]
        widgets = {
            'store_num': forms.TextInput(attrs={'class': 'form-control mono', 'placeholder': 'Physical Store #'}),
            'riso_num': forms.TextInput(attrs={'class': 'form-control mono', 'placeholder': 'RISO ID'}),
            'store_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Site Name'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'lat': forms.TextInput(attrs={'class': 'form-control mono', 'readonly': 'readonly'}),
            'lon': forms.TextInput(attrs={'class': 'form-control mono', 'readonly': 'readonly'}),
        }

class TankUpdateForm(forms.ModelForm):
    """
    OPERATIONAL FLOW:
    Captures a single tank configuration proposal.
    Integrates with the AJAX 'Tank Picker' on the frontend.
    """
    class Meta:
        model = TankUpdate
        fields = [
            'tank_index', 'fuel_type', 'reported_capacity', 
            'tank_type', 'is_unverified'
        ]
        widgets = {
            'tank_index': forms.NumberInput(attrs={'class': 'form-control mono', 'min': 1, 'placeholder': 'ATG Index'}),
            'fuel_type': forms.Select(attrs={'class': 'form-select'}),
            'reported_capacity': forms.NumberInput(attrs={'class': 'form-control mono', 'placeholder': 'Gallons'}),
            'tank_type': forms.HiddenInput(),
            'is_unverified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# Formset for handling multiple tanks per store update
TankUpdateFormSet = forms.inlineformset_factory(
    StoreUpdate, 
    TankUpdate, 
    form=TankUpdateForm, 
    extra=1, 
    can_delete=True
)
