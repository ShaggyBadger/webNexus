from django.contrib import admin
from ..models import VeederReading


@admin.register(VeederReading)
class VeederReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticket",
        "tank_index",
        "fuel_type",
        "volume",
        "height",
        "is_user_corrected",
    )
    list_filter = ("fuel_type", "is_user_corrected")
    search_fields = ("ticket__id", "ticket__store__store_num", "raw_line_text")
    readonly_fields = ("id",)
