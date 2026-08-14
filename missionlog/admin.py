from django.contrib import admin
from .models import (
    FuelType,
    Mission,
    MissionLogConfig,
    OrderNumber,
    PurchaseOrder,
    LoadDelivery,
    ProductionReportEmailAudit,
    TruckFuelLog,
)


@admin.register(MissionLogConfig)
class MissionLogConfigAdmin(admin.ModelAdmin):
    """Admin interface for the singleton MissionLog configuration."""

    fields = ("production_gph_target", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not MissionLogConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect

        config = MissionLogConfig.get_solo()
        return redirect(f"missionlogconfig/{config.pk}/change/")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_save_and_add_another"] = False
        extra_context["show_save_and_continue"] = False
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )


@admin.register(FuelType)
class FuelTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "color_name", "color_hex")
    search_fields = ("name",)


class OrderNumberInline(admin.TabularInline):
    model = OrderNumber
    extra = 0


class TruckFuelLogInline(admin.TabularInline):
    model = TruckFuelLog
    extra = 0


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "shift_start", "shift_end", "is_completed")
    list_filter = ("is_completed", "user")
    search_fields = ("user__username", "notes")
    inlines = [OrderNumberInline, TruckFuelLogInline]


@admin.register(OrderNumber)
class OrderNumberAdmin(admin.ModelAdmin):
    list_display = ("order_number", "mission")
    search_fields = ("order_number",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "order_parent")
    search_fields = ("po_number",)


@admin.register(LoadDelivery)
class LoadDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "purchase_order", "fuel_type", "store", "gross_gal")
    list_filter = ("fuel_type", "store")


@admin.register(TruckFuelLog)
class TruckFuelLogAdmin(admin.ModelAdmin):
    list_display = ("mission", "gallons", "price_per_gallon", "timestamp")


@admin.register(ProductionReportEmailAudit)
class ProductionReportEmailAuditAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "recipient_email",
        "report_range",
        "period_start",
        "period_end",
        "status",
        "requested_at",
    )
    list_filter = ("report_range", "status")
    search_fields = (
        "user__username",
        "user__email",
        "recipient_email",
        "trace_id",
    )
