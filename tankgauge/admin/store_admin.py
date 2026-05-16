from django.contrib import admin
from ..models import Store, StoreTankMapping

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('store_num', 'store_name', 'city', 'state')
    search_fields = ('store_num', 'store_name', 'city')

@admin.register(StoreTankMapping)
class StoreTankMappingAdmin(admin.ModelAdmin):
    list_display = ('store', 'tank_type', 'fuel_type', 'tank_index')
    list_filter = ('fuel_type',)
