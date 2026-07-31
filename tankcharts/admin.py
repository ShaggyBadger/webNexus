from django.contrib import admin
from tankcharts.models import StoreChartGeneration


@admin.register(StoreChartGeneration)
class StoreChartGenerationAdmin(admin.ModelAdmin):
    list_display = (
        "store",
        "status",
        "started_at",
        "completed_at",
        "failure_count",
        "retry_after",
    )
    list_filter = ("status",)
    search_fields = ("store__store_num", "failure_reason")
    readonly_fields = (
        "started_at",
        "completed_at",
        "failure_count",
        "failure_reason",
        "retry_after",
    )
