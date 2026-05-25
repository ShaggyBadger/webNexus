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
            "first_name": forms.TextInput(
                attrs={"class": "tactical-input", "placeholder": "FIRST_NAME"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "tactical-input", "placeholder": "LAST_NAME"}
            ),
            "email": forms.TextInput(
                attrs={"class": "tactical-input", "readonly": "readonly"}
            ),
        }


DAYS_OF_WEEK = [
    ("MON", "Monday"),
    ("TUE", "Tuesday"),
    ("WED", "Wednesday"),
    ("THU", "Thursday"),
    ("FRI", "Friday"),
    ("SAT", "Saturday"),
    ("SUN", "Sunday"),
]

TIMEZONE_CHOICES = [
    ("America/New_York", "Eastern Time (ET)"),
    ("America/Chicago", "Central Time (CT)"),
    ("America/Denver", "Mountain Time (MT)"),
    ("America/Phoenix", "Mountain Time - Phoenix (no DST)"),
    ("America/Los_Angeles", "Pacific Time (PT)"),
    ("America/Anchorage", "Alaska Time (AKT)"),
    ("America/Honolulu", "Hawaii Time (HST)"),
    ("UTC", "Coordinated Universal Time (UTC)"),
]


class TacticalProfileModelForm(forms.ModelForm):
    """
    Profile-specific form for operational preferences.
    """

    work_days_select = forms.MultipleChoiceField(
        choices=DAYS_OF_WEEK,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "form-check-input tactical-checkbox"}
        ),
        required=False,
        label="Normal Work Days",
    )

    class Meta:
        model = Profile
        fields = (
            "callsign",
            "map_preference",
            "normal_shift_start",
            "normal_shift_end",
            "timezone",
            "hourly_pay_rate",
        )
        widgets = {
            "callsign": forms.TextInput(
                attrs={"class": "tactical-input", "placeholder": "CALLSIGN"}
            ),
            "map_preference": forms.Select(
                attrs={
                    "class": "tactical-input mono",
                    "style": "background-color: #1a1d21; color: var(--primary-color); border-color: var(--navbar-border);",
                }
            ),
            "normal_shift_start": forms.TimeInput(
                format="%H:%M",
                attrs={"class": "tactical-input", "type": "time", "placeholder": "HH:MM"},
            ),
            "normal_shift_end": forms.TimeInput(
                format="%H:%M",
                attrs={"class": "tactical-input", "type": "time", "placeholder": "HH:MM"},
            ),
            "timezone": forms.Select(
                choices=TIMEZONE_CHOICES,
                attrs={
                    "class": "tactical-input mono",
                    "style": "background-color: #1a1d21; color: var(--primary-color); border-color: var(--navbar-border);",
                },
            ),
            "hourly_pay_rate": forms.NumberInput(
                attrs={"class": "tactical-input", "step": "0.01", "placeholder": "0.00"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["work_days_select"].initial = self.instance.work_days or []

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.work_days = self.cleaned_data.get("work_days_select", [])
        if commit:
            profile.save()
        return profile
