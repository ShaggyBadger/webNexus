from django.contrib import admin
from django.core.management import call_command
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import path
from io import StringIO
from ..models import Store, StoreTankMapping, TankCapacityProfileHistory
from tankgauge.logic.utils import canonicalize_fuel


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("store_num", "store_name", "city", "state")
    search_fields = ("store_num", "store_name", "city")


@admin.register(StoreTankMapping)
class StoreTankMappingAdmin(admin.ModelAdmin):
    change_list_template = "admin/tankgauge/storetankmapping/change_list.html"
    list_display = (
        "store",
        "tank_type",
        "fuel_type",
        "tank_index",
        "physical_capacity_gallons",
        "capacity_verified",
        "capacity_source",
        "profile_status",
        "profile_version",
    )
    list_filter = ("fuel_type",)
    search_fields = ("store__store_num", "store__store_name", "tank_index")
    autocomplete_fields = ("tank_type",)
    readonly_fields = (
        "canonical_fuel_type",
        "profile_version",
        "capacity_updated_at",
        "capacity_verified_at",
        "capacity_verified_by",
    )

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = StoreTankMapping.objects.get(pk=obj.pk)

        obj.canonical_fuel_type = canonicalize_fuel(obj.fuel_type)
        if obj.capacity_verified:
            obj.capacity_verified_at = obj.capacity_verified_at or timezone.now()
            obj.capacity_verified_by = obj.capacity_verified_by or request.user
            if obj.capacity_source in {"UNRESOLVED", "LEGACY_ASSUMED"}:
                obj.capacity_source = "MANUAL_VERIFIED"
            obj.profile_status = "READY"
        elif obj.capacity_source == "UNRESOLVED":
            obj.profile_status = "UNAVAILABLE"

        tracked_fields = (
            "physical_capacity_gallons",
            "capacity_verified",
            "capacity_source",
            "ullage_endpoint_percent_exact",
            "capacity_notes",
            "profile_status",
        )
        changed = previous is None or any(
            getattr(previous, field) != getattr(obj, field) for field in tracked_fields
        )
        if changed and previous is not None:
            obj.profile_version = previous.profile_version + 1

        super().save_model(request, obj, form, change)

        if changed:
            TankCapacityProfileHistory.objects.create(
                mapping=obj,
                profile_version=obj.profile_version,
                previous_capacity_gallons=(
                    previous.physical_capacity_gallons if previous else None
                ),
                new_capacity_gallons=obj.physical_capacity_gallons,
                previous_verified=previous.capacity_verified if previous else None,
                new_verified=obj.capacity_verified,
                previous_source=previous.capacity_source if previous else "",
                new_source=obj.capacity_source,
                previous_basis_percent=(
                    previous.ullage_endpoint_percent_exact if previous else None
                ),
                new_basis_percent=obj.ullage_endpoint_percent_exact,
                reason=obj.capacity_notes or "Admin tank profile update",
                changed_by=request.user,
            )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        query = request.GET.get("q", "").strip()
        extra_context["geometry_store_number"] = int(query) if query.isdigit() else None
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "backfill-capacity/",
                self.admin_site.admin_view(self.backfill_capacity_view),
                name="tankgauge_storetankmapping_backfill_capacity",
            )
        ] + urls

    def backfill_capacity_view(self, request):
        if not request.user.has_perm("tankgauge.backfill_tank_capacity"):
            raise PermissionDenied
        if request.method == "POST":
            store = request.POST.get("store") or None
            output = StringIO()
            command_args = ["--apply"] if request.POST.get("apply") else []
            if store:
                command_args.extend(["--store", store])
            call_command("backfill_tank_capacities", *command_args, stdout=output)
            return render(
                request,
                "admin/tankgauge/backfill_capacity.html",
                {
                    **self.admin_site.each_context(request),
                    "output": output.getvalue(),
                    "applied": bool(request.POST.get("apply")),
                },
            )
        return render(
            request,
            "admin/tankgauge/backfill_capacity.html",
            {**self.admin_site.each_context(request), "output": ""},
        )


class TankCapacityProfileHistoryInline(admin.TabularInline):
    model = TankCapacityProfileHistory
    extra = 0
    can_delete = False
    readonly_fields = (
        "profile_version",
        "previous_capacity_gallons",
        "new_capacity_gallons",
        "previous_verified",
        "new_verified",
        "previous_source",
        "new_source",
        "previous_basis_percent",
        "new_basis_percent",
        "reason",
        "actor_type",
        "changed_by",
        "source_evidence_ids",
        "created_at",
    )


StoreTankMappingAdmin.inlines = [TankCapacityProfileHistoryInline]
