from django.contrib import admin
from django.utils.html import format_html
from ..models import TankGaugeConfig


@admin.register(TankGaugeConfig)
class TankGaugeConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for the TankGauge singleton configuration.

    Enforces the singleton pattern by blocking 'add' when the record already
    exists, and redirecting directly to the change page for the only instance.
    """

    # Only expose the fields an operator would want to touch
    fields = ("mode_priority", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        """Block adding a second config row — only one should ever exist."""
        return not TankGaugeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton."""
        return False

    def changelist_view(self, request, extra_context=None):
        """
        Skip the changelist entirely and redirect straight to the single
        instance's change form, auto-creating it if needed.
        """
        from django.shortcuts import redirect

        config = TankGaugeConfig.get_solo()
        return redirect(
            f"tankgaugeconfig/{config.pk}/change/"
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_save_and_add_another"] = False
        extra_context["show_save_and_continue"] = False
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )
