from django.contrib import admin
from .models import LocationType, Location, StoreUpdate, TankUpdate

@admin.register(LocationType)
class LocationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'city', 'state', 'lat', 'lon')
    list_filter = ('location_type', 'state')
    search_fields = ('name', 'address', 'city')

class TankUpdateInline(admin.TabularInline):
    model = TankUpdate
    extra = 0
    fields = ('tank_index', 'fuel_type', 'reported_capacity', 'tank_type', 'is_unverified')

@admin.register(StoreUpdate)
class StoreUpdateAdmin(admin.ModelAdmin):
    """
    OPERATIONAL FLOW:
    Provides the administrative interface for reviewing and approving
    field-submitted site intelligence. 
    """
    list_display = ('store_name', 'status', 'submitted_by', 'submitted_at', 'approved_by')
    list_filter = ('status', 'submitted_at', 'state')
    search_fields = ('store_name', 'store_num', 'riso_num', 'submitted_by__username')
    inlines = [TankUpdateInline]
    
    fieldsets = (
        ('Proposal Status', {
            'fields': ('status', 'submitted_by', 'submitted_at', 'approved_by', 'approved_at')
        }),
        ('Canonical Links', {
            'fields': ('location', 'store')
        }),
        ('Proposed Site Details', {
            'fields': ('store_name', 'store_num', 'riso_num', 'address', 'city', 'state', 'zip_code', 'lat', 'lon')
        }),
    )
    
    readonly_fields = ('submitted_at', 'approved_at')
    actions = ['approve_and_apply']

    def approve_and_apply(self, request, queryset):
        """
        OPERATIONAL ACTION:
        Approves the selected proposals and applies them to the canonical database.
        """
        success_count = 0
        for obj in queryset:
            if obj.status == 'PENDING':
                obj.status = 'APPROVED'
                obj.approved_by = request.user
                from django.utils import timezone
                obj.approved_at = timezone.now()
                try:
                    obj.apply_update()
                    success_count += 1
                except Exception as e:
                    self.message_user(request, f"Error applying update {obj.id}: {str(e)}", level='ERROR')
        
        if success_count:
            self.message_user(request, f"Successfully approved and applied {success_count} site intelligence updates.")

    approve_and_apply.short_description = "[ APPROVE & APPLY ] Selected Site Intelligence"

    def save_model(self, request, obj, form, change):
        """
        Auto-capture the approving user when status is set to APPROVED.
        """
        if obj.status == 'APPROVED' and not obj.approved_by:
            obj.approved_by = request.user
            from django.utils import timezone
            obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)
