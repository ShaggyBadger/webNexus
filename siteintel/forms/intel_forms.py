from django import forms
import re
from ..models import SiteIntelligence

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
