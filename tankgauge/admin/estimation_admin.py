from django.contrib import admin

from tankgauge.models import TankEstimation, VirtualTankEstimation


@admin.register(TankEstimation)
class TankEstimationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store_num",
        "fuel_type",
        "tank_index",
        "sample_count",
        "confidence",
        "mean_error",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "tank_mapping__fuel_type")
    search_fields = (
        "tank_mapping__store__store_num",
        "tank_mapping__fuel_type",
        "tank_mapping__tank_index",
    )
    readonly_fields = ("created_at",)

    @admin.display(description="Store")
    def store_num(self, obj):
        return obj.tank_mapping.store.store_num

    @admin.display(description="Fuel")
    def fuel_type(self, obj):
        return obj.tank_mapping.fuel_type

    @admin.display(description="Tank")
    def tank_index(self, obj):
        return obj.tank_mapping.tank_index


@admin.register(VirtualTankEstimation)
class VirtualTankEstimationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store",
        "fuel_type",
        "tank_index",
        "sample_count",
        "confidence",
        "mean_error",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "fuel_type")
    search_fields = ("store__store_num", "fuel_type", "tank_index")
    readonly_fields = ("created_at",)
