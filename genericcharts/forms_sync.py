from django import forms


class TankEstimateSyncForm(forms.Form):
    """Validate the scope and mode for an admin estimation repair run."""

    scope = forms.ChoiceField(
        choices=(
            ("all", "All stores"),
            ("store", "One store"),
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

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == "store" and not cleaned.get("store_number"):
            self.add_error("store_number", "Enter a store number for a targeted sync.")
        if cleaned.get("scope") == "all":
            cleaned["store_number"] = None
        return cleaned
