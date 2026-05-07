from django import forms
import re
from .models import StoreUpdate, TankUpdate, SiteIntelligence
from tankgauge.models import TankType

class StoreUpdateForm(forms.ModelForm):
    """
    OPERATIONAL FLOW:
    Captures the primary metadata for a store intelligence proposal.
    Includes tactical sanitization to prevent XSS and injection.
    Dynamically injects fields for SiteAttributeDefinition records.
    """
    # Hidden field to store custom attributes added via JS on the frontend
    custom_metadata_json = forms.CharField(widget=forms.HiddenInput(), required=False)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # DYNAMIC_INJECTION: Add fields for all defined global attributes
        from .models import SiteAttributeDefinition
        definitions = SiteAttributeDefinition.objects.all()
        
        # If we have an instance (e.g. updating an existing proposal), 
        # load current values from proposed_metadata.
        # If we are targeting an existing store, load from its Location.metadata.
        current_metadata = {}
        if self.instance.pk:
            current_metadata = self.instance.proposed_metadata or {}
        elif 'initial' in kwargs and 'store_num' in kwargs['initial']:
            from tankgauge.models import Store
            store = Store.objects.filter(store_num=kwargs['initial']['store_num']).first()
            if store and store.location:
                current_metadata = store.location.metadata or {}

        for definition in definitions:
            field_name = f"attr_{definition.field_key}"
            label = definition.label
            required = definition.is_required
            initial_val = current_metadata.get(definition.field_key, '')

            if definition.field_type == 'boolean':
                self.fields[field_name] = forms.ChoiceField(
                    choices=[('', 'Unknown'), ('Yes', 'Yes'), ('No', 'No')],
                    required=required,
                    label=label,
                    initial=initial_val,
                    widget=forms.Select(attrs={'class': 'form-select mono'})
                )
            elif definition.field_type == 'number':
                self.fields[field_name] = forms.DecimalField(
                    required=required,
                    label=label,
                    initial=initial_val,
                    widget=forms.NumberInput(attrs={'class': 'form-control mono'})
                )
            else: # Text
                self.fields[field_name] = forms.CharField(
                    required=required,
                    label=label,
                    initial=initial_val,
                    widget=forms.TextInput(attrs={'class': 'form-control mono'})
                )
        
        # Load any non-global attributes into custom_metadata_json for the JS layer
        custom_data = {k: v for k, v in current_metadata.items() if not definitions.filter(field_key=k).exists()}
        import json
        self.fields['custom_metadata_json'].initial = json.dumps(custom_data)

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
        Also aggregates dynamic fields and custom JSON into proposed_metadata.
        """
        cleaned_data = super().clean()
        
        # 1. HTML Sanitization
        for field in list(cleaned_data.keys()):
            value = cleaned_data.get(field)
            if isinstance(value, str):
                # Strip HTML tags using regex for a zero-dependency tactical fix
                # This ensures any <b> or <script> tags are removed before saving.
                clean_value = re.sub(r'<[^>]*>', '', value)
                cleaned_data[field] = clean_value.strip()

        # 2. Metadata Aggregation
        proposed_metadata = {}
        
        # Add values from dynamic global attribute fields
        from .models import SiteAttributeDefinition
        definitions = SiteAttributeDefinition.objects.all()
        for definition in definitions:
            field_name = f"attr_{definition.field_key}"
            if field_name in cleaned_data:
                val = cleaned_data.get(field_name)
                # Store all values (including empty ones) to allow for "clearing" fields
                if val is not None:
                    proposed_metadata[definition.field_key] = val

        # Add values from custom metadata JSON field
        custom_json = cleaned_data.get('custom_metadata_json')
        if custom_json:
            try:
                import json
                custom_data = json.loads(custom_json)
                if isinstance(custom_data, dict):
                    proposed_metadata.update(custom_data)
            except json.JSONDecodeError:
                pass # Silent fail for malformed custom JSON

        self.instance.proposed_metadata = proposed_metadata
        return cleaned_data

class TankUpdateForm(forms.ModelForm):
    """
    OPERATIONAL FLOW:
    Captures a single tank configuration proposal.
    Integrates with the AJAX 'Tank Picker' on the frontend.
    """
    tank_index = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control mono', 'min': 1, 'placeholder': 'ATG Index'})
    )

    class Meta:
        model = TankUpdate
        fields = [
            'tank_index', 'fuel_type', 'reported_capacity', 
            'tank_type', 'is_unverified'
        ]
        widgets = {
            'fuel_type': forms.Select(attrs={'class': 'form-select'}),
            'reported_capacity': forms.NumberInput(attrs={'class': 'form-control mono', 'placeholder': 'Gallons'}),
            'tank_type': forms.HiddenInput(),
            'is_unverified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reported_capacity'].required = False

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
