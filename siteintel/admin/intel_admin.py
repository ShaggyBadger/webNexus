from django.contrib import admin

from ..models import SiteIntelligence, HandDrawnMap


@admin.register(SiteIntelligence)
class SiteIntelligenceAdmin(admin.ModelAdmin):
    list_display = ("location", "author", "is_default", "created_at")
    list_filter = ("is_default", "created_at", "author")
    search_fields = ("location__name", "notes", "author__username")
    actions = ["make_default"]

    @admin.action(description="Mark selected as default")
    def make_default(self, request, queryset):
        selected_ids = list(queryset.values_list("pk", flat=True))
        count = SiteIntelligence.objects.filter(pk__in=selected_ids).update(
            is_default=True
        )
        affected_locations = (
            SiteIntelligence.objects.filter(pk__in=selected_ids)
            .values_list("location_id", flat=True)
            .distinct()
        )
        unset = 0
        for location_id in affected_locations:
            unset += (
                SiteIntelligence.objects.filter(
                    location_id=location_id, is_default=True
                )
                .exclude(pk__in=selected_ids)
                .update(is_default=False)
            )
        self.message_user(
            request,
            f"{count} record(s) marked as default; {unset} other record(s) "
            f"unmarked to keep one default per location.",
        )


@admin.register(HandDrawnMap)
class HandDrawnMapAdmin(admin.ModelAdmin):
    list_display = ("location", "author", "is_default", "created_at", "updated_at")
    list_filter = ("is_default", "created_at", "author")
    search_fields = ("location__name", "author__username")
    readonly_fields = ("created_at", "updated_at")
    actions = ["make_default"]

    @admin.action(description="Mark selected as default")
    def make_default(self, request, queryset):
        selected_ids = list(queryset.values_list("pk", flat=True))
        count = HandDrawnMap.objects.filter(pk__in=selected_ids).update(is_default=True)
        affected_locations = (
            HandDrawnMap.objects.filter(pk__in=selected_ids)
            .values_list("location_id", flat=True)
            .distinct()
        )
        unset = 0
        for location_id in affected_locations:
            unset += (
                HandDrawnMap.objects.filter(location_id=location_id, is_default=True)
                .exclude(pk__in=selected_ids)
                .update(is_default=False)
            )
        self.message_user(
            request,
            f"{count} map(s) marked as default; {unset} other map(s) "
            f"unmarked to keep one default per location.",
        )
