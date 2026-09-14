from django.contrib import admin

from tankgauge.models import StoreType


@admin.register(StoreType)
class StoreTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
