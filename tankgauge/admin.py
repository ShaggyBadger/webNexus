from django.contrib import admin
from .models import Store, TankType, StoreTankMapping, TankChart


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("store_num", "store_name", "city", "state")
    search_fields = ("store_num", "store_name", "city")
    list_filter = ("state", "store_type")


@admin.register(TankType)
class TankTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "manufacturer", "model", "capacity")
    search_fields = ("name", "manufacturer", "model")


@admin.register(StoreTankMapping)
class StoreTankMappingAdmin(admin.ModelAdmin):
    list_display = ("store", "tank_type", "fuel_type")
    list_filter = ("fuel_type",)
    search_fields = ("store__store_name", "tank_type__name")


@admin.register(TankChart)
class TankChartAdmin(admin.ModelAdmin):
    list_display = ("tank_name", "inches", "gallons", "tank_type")
    search_fields = ("tank_name", "tank_type__name")
    list_filter = ("tank_type",)
