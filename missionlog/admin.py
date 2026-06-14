from django.contrib import admin
from .models import (
    FuelType,
    Mission,
    OrderNumber,
    PurchaseOrder,
    LoadDelivery,
    TruckFuelLog,
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
