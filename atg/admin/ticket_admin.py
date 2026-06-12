from django.contrib import admin
from ..models import VeederTicket, VeederReading

class VeederReadingInline(admin.TabularInline):
    model = VeederReading
    extra = 0
    fields = ('tank_index', 'fuel_type', 'volume', 'ullage', 'height', 'temp', 'is_user_corrected')

@admin.register(VeederTicket)
class VeederTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'store', 'uploaded_by', 'uploaded_at', 'ticket_timestamp')
    list_filter = ('store', 'uploaded_by', 'uploaded_at')
    search_fields = ('id', 'store__store_num', 'store__store_name', 'notes')
    inlines = [VeederReadingInline]
    readonly_fields = ('id', 'uploaded_at')
