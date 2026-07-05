from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, reverse
from ..models import VeederTicket, VeederReading


class VeederReadingInline(admin.TabularInline):
    model = VeederReading
    extra = 0
    fields = (
        "tank_index",
        "fuel_type",
        "volume",
        "ullage",
        "height",
        "temp",
        "is_user_corrected",
    )


@admin.register(VeederTicket)
class VeederTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "uploaded_by", "uploaded_at", "ticket_timestamp")
    list_filter = ("store", "uploaded_by", "uploaded_at")
    search_fields = ("id", "store__store_num", "store__store_name", "notes")
    inlines = [VeederReadingInline]
    readonly_fields = ("id", "uploaded_at")
    change_list_template = "admin/atg/veederticket/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "review-queue/",
                self.admin_site.admin_view(self.review_queue_view),
                name="atg_veederticket_review_queue",
            ),
        ]
        return custom_urls + urls

    def review_queue_view(self, request):
        return redirect(reverse("atg:review_queue"))
