from django import forms

class DeliveryEstimationForm(forms.Form):
    """
    OPERATIONAL FLOW:
    Mission initialization form.
    Captures the target site identifier and the products slated for delivery.
    """
    FUEL_CHOICES = [
        ("regular", "Regular"),
        ("plus", "Plus"),
        ("premium", "Premium"),
        ("kerosene", "Kerosene"),
        ("diesel", "Diesel"),
    ]

    store_number = forms.CharField(
        label="Store Number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg mono",
                "placeholder": "Enter store number",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
            }
        ),
    )

    fuel_types = forms.MultipleChoiceField(
        choices=FUEL_CHOICES, widget=forms.CheckboxSelectMultiple, required=True
    )


class TankDataForm(forms.Form):
    """
    OPERATIONAL FLOW:
    Real-time data entry for a specific physical tank.
    Captures stick readings and planned delivery amounts.
    """
    delivery_gallons = forms.FloatField(
        label="Delivery Gallons",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control mono text-primary",
                "placeholder": "e.g. 4200",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
            }
        ),
    )
    current_inches = forms.FloatField(
        label="Current Inches",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control mono text-primary",
                "placeholder": "e.g. 29",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
            }
        ),
    )
