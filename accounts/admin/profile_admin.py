from django.contrib import admin
from ..models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'callsign', 'driver_id', 'is_verified_field_agent')
    search_fields = ('user__username', 'callsign', 'driver_id')
    list_filter = ('is_verified_field_agent', 'map_preference')
