from django import forms

from genericcharts.pipeline.states import lookup_state
from tankgauge.models import Store, StoreType


class GenericChartReviewForm(forms.Form):
    """Validate the configuration used to assemble the review page."""

    state = forms.ChoiceField(initial="FULL", choices=(), label="State")
    store_type_ids = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.MultipleHiddenInput,
    )
    store_numbers = forms.CharField(
        required=False,
        help_text="Optional comma-separated store numbers.",
    )
    volume_gap_percent = forms.FloatField(
        initial=3.0,
        min_value=0,
        max_value=100,
        label="Volume gap percentage",
        help_text=(
            "Sets the capacity difference required to split tanks into separate "
            "chart buckets. Lower values create more separate charts; higher "
            "values combine more similar capacities."
        ),
    )
    near_duplicate_tolerance_percent = forms.FloatField(
        initial=1.0,
        min_value=0,
        max_value=100,
        label="Near-duplicate tolerance percentage",
        help_text=(
            "Sets how much two generated curves may differ and still count as "
            "the same catalog curve. Lower values preserve more distinctions; "
            "higher values merge more similar curves."
        ),
    )
    outlier_multiplier = forms.FloatField(
        initial=2.0,
        min_value=0.01,
        label="Outlier multiplier",
        help_text=(
            "Sets the review threshold for curves that differ from their bucket "
            "representative. Lower values flag more curves for review; higher "
            "values flag fewer. This changes review flags, not the generated "
            "chart curve or bucket membership."
        ),
    )
    document_description = forms.CharField(
        label="Document description",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
        initial="CoreStarterPack generated from current tank data.",
        help_text="This text is saved as the public DMS document description.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        states = (
            Store.objects.exclude(state__isnull=True)
            .exclude(state="")
            .values_list("state", flat=True)
        )
        unique_states = {}
        for raw_state in states:
            state = lookup_state(raw_state)
            if state is None:
                normalized = (raw_state or "").strip()
                if normalized:
                    unique_states[normalized] = normalized
                continue
            unique_states[state.abbr] = state.name
        self.fields["state"].choices = [
            ("FULL", "FULL - All states"),
            *[
                (abbreviation, name)
                for abbreviation, name in sorted(
                    unique_states.items(), key=lambda item: item[1].casefold()
                )
            ],
        ]
        store_types = StoreType.objects.order_by("name")
        self.store_type_options = tuple(
            (str(store_type.id), store_type.name) for store_type in store_types
        )
        self.fields["store_type_ids"].choices = self.store_type_options
        if self.is_bound:
            submitted = (
                self.data.getlist("store_type_ids")
                if hasattr(self.data, "getlist")
                else self.data.get("store_type_ids", ())
            )
            self.selected_store_type_ids = {str(value) for value in submitted}
        else:
            self.selected_store_type_ids = {
                value for value, _ in self.store_type_options
            }
            self.fields["store_type_ids"].initial = tuple(self.selected_store_type_ids)

    def clean_store_numbers(self) -> tuple[int, ...]:
        value = self.cleaned_data["store_numbers"]
        if not value.strip():
            return ()
        try:
            numbers = tuple(sorted({int(item.strip()) for item in value.split(",")}))
        except ValueError as exc:
            raise forms.ValidationError("Store numbers must be whole numbers.") from exc
        if any(number <= 0 for number in numbers):
            raise forms.ValidationError("Store numbers must be positive.")
        return numbers

    def clean_store_type_ids(self) -> tuple[int, ...]:
        values = self.cleaned_data["store_type_ids"]
        if not values:
            raise forms.ValidationError("Select at least one store type.")
        return tuple(sorted({int(value) for value in values}))

    def selection_spec(self):
        from genericcharts.pipeline.dataclasses import SelectionSpec

        return SelectionSpec(
            state=self.cleaned_data["state"],
            store_numbers=self.cleaned_data["store_numbers"],
            store_type_ids=self.cleaned_data["store_type_ids"],
        )

    def package_options(self) -> dict[str, float | str | list[int]]:
        """Return the validated numeric configuration for a generation job."""

        return {
            "volume_gap_percent": self.cleaned_data["volume_gap_percent"],
            "near_duplicate_tolerance_percent": self.cleaned_data[
                "near_duplicate_tolerance_percent"
            ],
            "outlier_multiplier": self.cleaned_data["outlier_multiplier"],
            "document_description": self.cleaned_data["document_description"].strip(),
            "store_type_ids": list(self.cleaned_data["store_type_ids"]),
        }
