from django.contrib import admin
from ..models import SiteIntelligence

@admin.register(SiteIntelligence)
class SiteIntelligenceAdmin(admin.ModelAdmin):
    list_display = ('location', 'author', 'is_default', 'created_at')
    list_filter = ('is_default', 'created_at', 'author')
    search_fields = ('location__name', 'notes', 'author__username')
