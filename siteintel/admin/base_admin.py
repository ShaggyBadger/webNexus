from django.contrib import admin
from ..models import LocationType, Location, SiteAttributeDefinition

@admin.register(SiteAttributeDefinition)
class SiteAttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ('label', 'field_key', 'field_type', 'sort_weight', 'is_required')
    list_editable = ('sort_weight', 'is_required')
    search_fields = ('label', 'field_key')

@admin.register(LocationType)
class LocationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'city', 'state', 'lat', 'lon')
    list_filter = ('location_type', 'state')
    search_fields = ('name', 'address', 'city')
    fieldsets = (
        ('Site Info', {
            'fields': ('name', 'location_type', 'notes')
        }),
        ('Geospatial', {
            'fields': ('address', 'city', 'state', 'zip_code', 'lat', 'lon', 'tactical_overlay')
        }),
        ('Hybrid Metadata', {
            'fields': ('metadata',),
            'description': 'Structured site quirks and manifold data (JSON)'
        }),
    )
