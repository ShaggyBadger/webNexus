from django.contrib import admin
from django.urls import path

from tankcharts.admin_views import trigger_generate_all_tank_charts
from tankcharts.models import StoreChartGeneration


@admin.register(StoreChartGeneration)
class StoreChartGenerationAdmin(admin.ModelAdmin):
    change_list_template = "admin/tankcharts/storechartgeneration/change_list.html"
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "generate-all/",
                self.admin_site.admin_view(trigger_generate_all_tank_charts),
                name="tankcharts_storechartgeneration_generate_all",
            ),
        ]
        return custom_urls + urls
