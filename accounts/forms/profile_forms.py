from django import forms
from django.contrib.auth.models import User
from ..models import Profile

class TacticalProfileForm(forms.ModelForm):
    """
    Field-built Profile editor for maintaining agent identity records.
    
    - Provides text input for first and last names.
    - Locks the 'email' field to 'readonly' to maintain system ID stability;
      modifying primary identity requires command-level intervention.
    """
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'tactical-input', 
                'placeholder': 'FIRST_NAME'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'tactical-input', 
                'placeholder': 'LAST_NAME'
            }),
            'email': forms.TextInput(attrs={
                'class': 'tactical-input', 
                'readonly': 'readonly'
            }),
        }

class TacticalProfileModelForm(forms.ModelForm):
    """
    Profile-specific form for operational preferences.
    """
    class Meta:
        model = Profile
        fields = ("callsign", "map_preference")
        widgets = {
            'callsign': forms.TextInput(attrs={
                'class': 'tactical-input', 
                'placeholder': 'CALLSIGN'
            }),
            'map_preference': forms.Select(attrs={
                'class': 'tactical-input mono',
                'style': 'background-color: #1a1d21; color: var(--primary-color); border-color: var(--navbar-border);'
            }),
        }
