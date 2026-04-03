from django import forms

class DeliveryEstimationForm(forms.Form):
    FUEL_CHOICES = [
        ('regular', 'Regular'),
        ('plus', 'Plus'),
        ('premium', 'Premium'),
        ('kerosene', 'Kerosene'),
        ('diesel', 'Diesel'),
    ]

    store_number = forms.CharField(
        label="Store Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg mono',
            'placeholder': 'Enter store number',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
        })
    )
    
    fuel_types = forms.MultipleChoiceField(
        choices=FUEL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
