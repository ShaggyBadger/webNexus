from django.contrib import admin
from .models import (
    LocationType, Location, StoreUpdate, TankUpdate, SiteIntelligence, 
    MapOverlayUpdate, FuelRack, RackCheckIn, SiteAttributeDefinition
)

@admin.register(SiteAttributeDefinition)
class SiteAttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ('label', 'field_key', 'field_type', 'sort_weight', 'is_required')
    list_editable = ('sort_weight', 'is_required')
    search_fields = ('label', 'field_key')

@admin.register(FuelRack)
class FuelRackAdmin(admin.ModelAdmin):
    list_display = ('location', 'lockout_days')
    search_fields = ('location__name',)

@admin.register(RackCheckIn)
class RackCheckInAdmin(admin.ModelAdmin):
    list_display = ('user', 'rack', 'timestamp', 'is_verified')
    list_filter = ('is_verified', 'timestamp', 'user')
    search_fields = ('user__username', 'rack__location__name')
    readonly_fields = ('timestamp',)

@admin.register(MapOverlayUpdate)
class MapOverlayUpdateAdmin(admin.ModelAdmin):
    list_display = ('location', 'status', 'submitted_by', 'submitted_at', 'approved_by')
    list_filter = ('status', 'submitted_at')
    search_fields = ('location__name', 'submitted_by__username')
    actions = ['approve_and_apply']

    def approve_and_apply(self, request, queryset):
        success_count = 0
        for obj in queryset:
            if obj.status == 'PENDING':
                obj.status = 'APPROVED'
                obj.approved_by = request.user
                from django.utils import timezone
                obj.approved_at = timezone.now()
                try:
                    obj.apply_overlay()
                    obj.save()
                    success_count += 1
                except Exception as e:
                    self.message_user(request, f"Error applying overlay {obj.id}: {str(e)}", level='ERROR')
        
        if success_count:
            self.message_user(request, f"Successfully approved and applied {success_count} tactical map overlays.")

    approve_and_apply.short_description = "[ APPROVE & APPLY ] Selected Map Overlays"

@admin.register(SiteIntelligence)
class SiteIntelligenceAdmin(admin.ModelAdmin):
    list_display = ('location', 'author', 'is_default', 'created_at')
    list_filter = ('is_default', 'created_at', 'author')
    search_fields = ('location__name', 'notes', 'author__username')

@admin.register(LocationType)
class LocationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'city', 'state', 'lat', 'lon')
    list_filter = ('location_type', 'state')
    search_fields = ('name', 'address', 'city')
    fieldsets = (
        ('Site Info', {
            'fields': ('name', 'location_type', 'notes')
        }),
        ('Geospatial', {
            'fields': ('address', 'city', 'state', 'zip_code', 'lat', 'lon', 'tactical_overlay')
        }),
        ('Hybrid Metadata', {
            'fields': ('metadata',),
            'description': 'Structured site quirks and manifold data (JSON)'
        }),
    )

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
    list_display = ('store_name', 'store_type', 'status', 'submitted_by', 'submitted_at', 'approved_by')
    list_filter = ('status', 'submitted_at', 'state', 'store_type')
    search_fields = ('store_name', 'store_num', 'riso_num', 'submitted_by__username', 'store_type')
    inlines = [TankUpdateInline]
    
    fieldsets = (
        ('Proposal Status', {
            'fields': ('status', 'location_type', 'submitted_by', 'submitted_at', 'approved_by', 'approved_at')
        }),
        ('Canonical Links', {
            'fields': ('location', 'store')
        }),
        ('Proposed Site Details', {
            'fields': ('store_name', 'store_type', 'store_num', 'riso_num', 'address', 'city', 'state', 'zip_code', 'lat', 'lon')
        }),
        ('Proposed Metadata', {
            'fields': ('proposed_metadata',),
            'description': 'Site quirks and manifold data (JSON)'
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
        Also triggers apply_update() if status is changing to APPROVED.
        """
        is_becoming_approved = False
        if obj.status == 'APPROVED':
            if not change: # New record created as APPROVED
                is_becoming_approved = True
            else:
                # Use a fresh fetch to see what's currently in the DB
                old_status = StoreUpdate.objects.get(pk=obj.pk).status
                if old_status != 'APPROVED':
                    is_becoming_approved = True

        if is_becoming_approved:
            from django.utils import timezone
            if not obj.approved_by:
                obj.approved_by = request.user
            if not obj.approved_at:
                obj.approved_at = timezone.now()
            
            # Canonical synchronization
            try:
                # We save before applying to ensure the status is 'APPROVED' 
                # inside apply_update's check.
                super().save_model(request, obj, form, change)
                obj.apply_update()
                return # Skip the final super().save_model below
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f"SYNC_ERROR: {str(e)}")
        
        super().save_model(request, obj, form, change)
