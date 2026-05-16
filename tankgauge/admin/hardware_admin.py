from django.contrib import admin
from ..models import TankType, TankChart

@admin.register(TankType)
class TankTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'manufacturer', 'capacity')
    search_fields = ('name', 'manufacturer')

@admin.register(TankChart)
class TankChartAdmin(admin.ModelAdmin):
    list_display = ('tank_name', 'inches', 'gallons')
    search_fields = ('tank_name',)
