from django import forms
import re
from .models import StoreUpdate, TankUpdate, SiteIntelligence
from tankgauge.models import TankType

class StoreUpdateForm(forms.ModelForm):
    """
    OPERATIONAL FLOW:
    Captures the primary metadata for a store intelligence proposal.
    Includes tactical sanitization to prevent XSS and injection.
    """
    class Meta:
        model = StoreUpdate
        fields = [
            'location_type', 'store_num', 'riso_num', 'store_name', 'store_type',
            'address', 'city', 'state', 'zip_code', 
            'lat', 'lon'
        ]
        widgets = {
            'location_type': forms.Select(attrs={'class': 'form-select mono', 'style': 'font-size: 0.8rem;'}),
            'store_num': forms.TextInput(attrs={'class': 'form-control mono', 'placeholder': 'Physical Store #'}),
            'riso_num': forms.TextInput(attrs={'class': 'form-control mono', 'placeholder': 'RISO ID'}),
            'store_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Site Name'}),
            'store_type': forms.HiddenInput(), # Handled by custom UI logic
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street Address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Zip Code'}),
            'lat': forms.TextInput(attrs={'class': 'form-control mono', 'readonly': 'readonly'}),
            'lon': forms.TextInput(attrs={'class': 'form-control mono', 'readonly': 'readonly'}),
        }

    def clean_store_num(self):
        """
        Ensure store number is strictly numeric and clean of any artifacts.
        """
        val = self.cleaned_data.get('store_num')
        if val is not None:
            # Check if it contains anything other than digits
            if not re.match(r'^\d+$', str(val)):
                raise forms.ValidationError("STORE_ID_ERROR: MUST BE NUMERIC DIGITS ONLY")
        return val

    def clean(self):
        """
        TACTICAL SANITIZATION:
        Strips HTML tags from all text inputs to prevent XSS.
        """
        cleaned_data = super().clean()
        for field in cleaned_data:
            value = cleaned_data.get(field)
            if isinstance(value, str):
                # Strip HTML tags using regex for a zero-dependency tactical fix
                # This ensures any <b> or <script> tags are removed before saving.
                clean_value = re.sub(r'<[^>]*>', '', value)
                cleaned_data[field] = clean_value.strip()
        return cleaned_data

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

class SiteIntelligenceForm(forms.ModelForm):
    """
    OPERATIONAL FLOW:
    Captures field intelligence (notes and stuff) for a specific site.
    """
    class Meta:
        model = SiteIntelligence
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control tactical-input', 
                'placeholder': 'ENTER_FIELD_OBSERVATIONS...',
                'rows': 10
            }),
        }

    def clean_notes(self):
        """
        TACTICAL SANITIZATION:
        Strips HTML tags from notes.
        """
        notes = self.cleaned_data.get('notes')
        if notes:
            return re.sub(r'<[^>]*>', '', notes).strip()
        return notes
