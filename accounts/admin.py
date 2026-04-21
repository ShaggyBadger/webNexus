from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile

class ProfileInline(admin.StackedInline):
    """
    Enables inline editing of Tactical Profile parameters within the standard User admin.
    """
    model = Profile
    can_delete = False
    verbose_name_plural = 'Tactical Profile (Field Intel)'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    """
    Overridden UserAdmin (WarMaster Console) with tactical status monitoring.
    """
    inlines = (ProfileInline,)
    list_display = (
        'username', 
        'email', 
        'first_name', 
        'last_name', 
        'is_staff', 
        'get_is_verified'
    )
    list_select_related = ('profile',)

    def get_is_verified(self, instance):
        """Fetches verification status from the linked Profile model."""
        return instance.profile.is_verified_field_agent
    
    get_is_verified.short_description = 'FIELD_VERIFIED'
    get_is_verified.boolean = True

    def get_inline_instances(self, request, obj=None):
        """Only shows the Profile inline when editing an existing agent."""
        if not obj:
            return list()
        return super(UserAdmin, self).get_inline_instances(request, obj)

# UNREGISTER standard User and RE-REGISTER with Tactical Enhancements
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Dedicated admin interface for high-level Tactical Profile management.
    """
    list_display = (
        'user', 
        'is_verified_field_agent', 
        'callsign', 
        'driver_id'
    )
    list_filter = ('is_verified_field_agent',)
    search_fields = (
        'user__username', 
        'user__email', 
        'callsign', 
        'driver_id'
    )
