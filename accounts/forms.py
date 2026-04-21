from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Profile

class TacticalSignupForm(UserCreationForm):
    """
    Tactical Signup Form for new agent enlistment.
    
    OVERRIDES:
    - Email is required and serves as the primary tactical identity.
    - Username sync is handled via signals (see accounts/logic/signals.py) 
      which duplicates the email into the username field for internal Django compatibility.
    """
    email = forms.EmailField(
        required=True, 
        help_text="Primary communication and authentication ID."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        """Ensures tactical uniqueness of the agent's email ID."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("AN AGENT WITH THIS EMAIL IS ALREADY ENLISTED.")
        return email

    def save(self, commit=True):
        """Initializes the User object with the provided tactical email."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class TacticalLoginForm(AuthenticationForm):
    """
    Standard authentication form with Tactical UI enhancements.
    
    The 'username' label is overridden to suggest both Email and Driver ID
    to guide the agent during field login.
    """
    username = forms.CharField(
        label="EMAIL / DRIVER ID", 
        widget=forms.TextInput(attrs={'autofocus': True})
    )

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
