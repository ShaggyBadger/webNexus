from django import forms

from genericcharts.models import TankEstimateSyncRun
from tankgauge.models import StoreTankMapping


class TankEstimateSyncForm(forms.Form):
    """Validate the scope and mode for an admin estimation repair run."""

    scope = forms.ChoiceField(
        choices=(
            ("all", "All stores"),
            ("store", "One store"),
            ("mapping", "One mapped tank"),
        ),
        initial="all",
    )
    store_number = forms.IntegerField(
        required=False,
        min_value=1,
        label="Store number",
    )
    mapped_only = forms.BooleanField(
        required=False,
        initial=True,
        label="Mapped tanks only",
        help_text="Use this to repair active mappings without processing virtual tanks.",
    )
    mapping = forms.ModelChoiceField(
        queryset=StoreTankMapping.objects.select_related("store").order_by(
            "store__store_num", "tank_index"
        ),
        required=False,
        label="Mapping",
    )
    preview = forms.BooleanField(required=False, initial=False, label="Preview only")
    idempotency_key = forms.CharField(required=False, max_length=100)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == "store" and not cleaned.get("store_number"):
            self.add_error("store_number", "Enter a store number for a targeted sync.")
        if cleaned.get("scope") == "all":
            cleaned["store_number"] = None
        if cleaned.get("scope") == "mapping" and not cleaned.get("mapping"):
            self.add_error(
                "mapping", "Select a tank mapping for a mapping-scoped sync."
            )
        if cleaned.get("scope") == "mapping":
            cleaned["store_number"] = None
            cleaned["mapped_only"] = True
        return cleaned

    def clean_idempotency_key(self):
        key = self.cleaned_data.get("idempotency_key", "").strip()
        if key and TankEstimateSyncRun.objects.filter(idempotency_key=key).exists():
            raise forms.ValidationError("This idempotency key already has a sync run.")
        return key
