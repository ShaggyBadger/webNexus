from django.contrib import admin
from django import forms
from tankgauge.models import Store

from ..models import VeederReading


class VeederReadingForm(forms.ModelForm):
    """
    TACTICAL ADMIN FORM:
    Allows manual correction of the store association directly from the reading view.
    Updates the parent VeederTicket.
    """

    store = forms.ModelChoiceField(
        queryset=Store.objects.all(),
        required=False,
        help_text="Update the store location for the parent Veeder Ticket.",
    )

    class Meta:
        model = VeederReading
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, "ticket") and self.instance.ticket:
            self.fields["store"].initial = self.instance.ticket.store


@admin.register(VeederReading)
class VeederReadingAdmin(admin.ModelAdmin):
    form = VeederReadingForm
    list_display = (
        "id",
        "get_store",
        "ticket",
        "tank_index",
        "fuel_type",
        "volume",
        "height",
        "is_user_corrected",
    )
    list_filter = ("fuel_type", "is_user_corrected", "ticket__store")
    search_fields = ("ticket__id", "raw_line_text", "ticket__store__store_num")
    readonly_fields = ("id",)

    fields = (
        "ticket",
        "store",
        "tank_index",
        "fuel_type",
        "volume",
        "ullage",
        "height",
        "temp",
        "water",
        "raw_line_text",
        "confidence_score",
        "is_user_corrected",
    )

    @admin.display(description="Store", ordering="ticket__store")
    def get_store(self, obj):
        if obj.ticket and obj.ticket.store:
            return obj.ticket.store
        return "UNKNOWN"

    def save_model(self, request, obj, form, change):
        """
        Intercept save to update parent ticket store if changed.
        """
        store = form.cleaned_data.get("store")
        if obj.ticket:
            obj.ticket.store = store
            obj.ticket.save()
        super().save_model(request, obj, form, change)

        if obj.ticket and obj.ticket.store and obj.is_user_corrected:
            from atg.services.auto_mapper import AutoMapperService

            AutoMapperService.trigger_updates(
                obj.ticket.store,
                obj.fuel_type.name,
                obj.tank_index,
            )
