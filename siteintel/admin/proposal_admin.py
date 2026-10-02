from django.contrib import admin
from django.utils import timezone
from ..models import StoreUpdate, TankUpdate, MapOverlayUpdate


class TankUpdateInline(admin.TabularInline):
    model = TankUpdate
    extra = 0
    fields = (
        "tank_index",
        "fuel_type",
        "reported_capacity",
        "tank_type",
        "is_unverified",
    )


@admin.register(StoreUpdate)
class StoreUpdateAdmin(admin.ModelAdmin):
    """
    OPERATIONAL FLOW:
    Provides the administrative interface for reviewing and approving
    field-submitted site intelligence.
    """

    list_display = (
        "store_name",
        "store_type",
        "status",
        "submitted_by",
        "submitted_at",
        "approved_by",
    )
    list_filter = ("status", "submitted_at", "state", "store_type")
    search_fields = (
        "store_name",
        "store_num",
        "riso_num",
        "submitted_by__username",
        "store_type",
    )
    inlines = [TankUpdateInline]

    fieldsets = (
        (
            "Proposal Status",
            {
                "fields": (
                    "status",
                    "location_type",
                    "submitted_by",
                    "submitted_at",
                    "approved_by",
                    "approved_at",
                )
            },
        ),
        ("Canonical Links", {"fields": ("location", "store")}),
        (
            "Proposed Site Details",
            {
                "fields": (
                    "store_name",
                    "store_type",
                    "store_num",
                    "riso_num",
                    "address",
                    "city",
                    "state",
                    "zip_code",
                    "lat",
                    "lon",
                )
            },
        ),
        (
            "Specialized Proposals",
            {
                "fields": ("rack_lockout_days", "rack_config_json", "yard_notes"),
                "description": "Type-specific data for Fuel Racks and Yards",
            },
        ),
        (
            "Proposed Metadata",
            {
                "fields": ("proposed_metadata",),
                "description": "Site quirks and manifold data (JSON)",
            },
        ),
    )

    readonly_fields = ("submitted_at", "approved_at")
    actions = ["approve_and_apply"]

    def approve_and_apply(self, request, queryset):
        """
        OPERATIONAL ACTION:
        Approves the selected proposals and applies them to the canonical database.
        """
        success_count = 0
        for obj in queryset:
            if obj.status == "PENDING":
                obj.status = "APPROVED"
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
                try:
                    obj.apply_update()
                    success_count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Error applying update {obj.id}: {str(e)}",
                        level="ERROR",
                    )

        if success_count:
            self.message_user(
                request,
                f"Successfully approved and applied {success_count} site intelligence updates.",
            )

    approve_and_apply.short_description = (
        "[ APPROVE & APPLY ] Selected Site Intelligence"
    )

    def save_model(self, request, obj, form, change):
        """
        Save proposal fields and remember approval state for post-inline sync.
        """
        previous_state = None
        if obj.status == "APPROVED":
            if change:
                previous = StoreUpdate.objects.only(
                    "status", "approved_by", "approved_at"
                ).get(pk=obj.pk)
                if previous.status != "APPROVED":
                    previous_state = {
                        "status": previous.status,
                        "approved_by_id": previous.approved_by_id,
                        "approved_at": previous.approved_at,
                    }
            else:
                previous_state = {
                    "status": "PENDING",
                    "approved_by_id": None,
                    "approved_at": None,
                }

        if previous_state is not None:
            if not obj.approved_by_id:
                obj.approved_by = request.user
            if not obj.approved_at:
                obj.approved_at = timezone.now()

        super().save_model(request, obj, form, change)

        if previous_state is not None:
            # Inline TankUpdate rows are saved later by Django's save_related
            # lifecycle. Defer synchronization to that hook so it sees them.
            obj._siteintel_previous_approval_state = previous_state

    def save_related(self, request, form, formsets, change):
        """Apply approval after the submitted inline tank proposals are saved."""
        super().save_related(request, form, formsets, change)

        obj = form.instance
        previous_state = getattr(obj, "_siteintel_previous_approval_state", None)
        if previous_state is None:
            return

        try:
            obj.apply_update()
        except Exception as exc:
            # apply_update rolls back canonical changes in its atomic block.
            # Restore only approval metadata: keep submitted proposal edits so
            # an administrator can correct the cause and retry.
            obj.status = previous_state["status"]
            obj.approved_by_id = previous_state["approved_by_id"]
            obj.approved_at = previous_state["approved_at"]
            obj.save(update_fields=("status", "approved_by", "approved_at"))

            from django.contrib import messages

            messages.error(request, f"SYNC_ERROR: {str(exc)}")
        finally:
            delattr(obj, "_siteintel_previous_approval_state")


@admin.register(MapOverlayUpdate)
class MapOverlayUpdateAdmin(admin.ModelAdmin):
    list_display = ("location", "status", "submitted_by", "submitted_at", "approved_by")
    list_filter = ("status", "submitted_at")
    search_fields = ("location__name", "submitted_by__username")
    actions = ["approve_and_apply"]

    def approve_and_apply(self, request, queryset):
        success_count = 0
        for obj in queryset:
            if obj.status == "PENDING":
                obj.status = "APPROVED"
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
                try:
                    obj.apply_overlay()
                    obj.save()
                    success_count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Error applying overlay {obj.id}: {str(e)}",
                        level="ERROR",
                    )

        if success_count:
            self.message_user(
                request,
                f"Successfully approved and applied {success_count} tactical map overlays.",
            )

    approve_and_apply.short_description = "[ APPROVE & APPLY ] Selected Map Overlays"
