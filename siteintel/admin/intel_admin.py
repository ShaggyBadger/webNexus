from django.contrib import admin
from ..models import SiteIntelligence, HandDrawnMap


@admin.register(SiteIntelligence)
class SiteIntelligenceAdmin(admin.ModelAdmin):
    list_display = ("location", "author", "is_default", "created_at")
    list_filter = ("is_default", "created_at", "author")
    search_fields = ("location__name", "notes", "author__username")


@admin.register(HandDrawnMap)
class HandDrawnMapAdmin(admin.ModelAdmin):
    list_display = ("location", "author", "is_default", "created_at", "updated_at")
    list_filter = ("is_default", "created_at", "author")
    search_fields = ("location__name", "author__username")
    readonly_fields = ("created_at", "updated_at")
