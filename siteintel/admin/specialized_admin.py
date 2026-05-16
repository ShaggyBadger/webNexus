from django.contrib import admin
from ..models import Yard, FuelRack, RackCheckIn

@admin.register(FuelRack)
class FuelRackAdmin(admin.ModelAdmin):
    list_display = ('location', 'lockout_days')
    search_fields = ('location__name',)

@admin.register(Yard)
class YardAdmin(admin.ModelAdmin):
    list_display = ('location',)
    search_fields = ('location__name',)

@admin.register(RackCheckIn)
class RackCheckInAdmin(admin.ModelAdmin):
    list_display = ('user', 'rack', 'timestamp', 'is_verified')
    list_filter = ('is_verified', 'timestamp', 'user')
    search_fields = ('user__username', 'rack__location__name')
    readonly_fields = ('timestamp',)
