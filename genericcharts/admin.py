from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import path

from genericcharts.forms import GenericChartReviewForm
from genericcharts.models import GenericChartGeneration
from genericcharts.models import TankEstimateSyncRun
from genericcharts.services.generation_service import (
    create_generation,
    launch_generation,
)
from genericcharts.services.description import default_document_description
from genericcharts.services.review_service import build_review_context
from genericcharts.forms_sync import TankEstimateSyncForm
from genericcharts.services.tank_estimate_sync import launch_tank_estimate_sync


@admin.register(GenericChartGeneration)
class GenericChartGenerationAdmin(admin.ModelAdmin):
    change_list_template = "admin/genericcharts/genericchartgeneration/change_list.html"
    list_display = (
        "state",
        "package_scope_key",
        "generator_version",
        "status",
        "requested_by",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "state", "generator_version")
    search_fields = (
        "state",
        "package_scope_key",
        "failure_reason",
        "requested_by__username",
    )
    readonly_fields = (
        "generator_version",
        "package_scope_key",
        "options",
        "status",
        "requested_by",
        "started_at",
        "completed_at",
        "summary",
        "failure_reason",
        "document",
        "created_at",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "review/",
                self.admin_site.admin_view(self.review_view),
                name="genericcharts_genericchartgeneration_review",
            ),
            path(
                "generate/",
                self.admin_site.admin_view(self.generate_view),
                name="genericcharts_genericchartgeneration_generate",
            ),
        ]
        return custom_urls + urls

    def review_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        form = GenericChartReviewForm(request.POST or None)
        context = {**self.admin_site.each_context(request), "form": form}
        if request.method == "POST" and form.is_valid():
            review_context = build_review_context(
                selection=form.selection_spec(),
                volume_gap_percent=form.cleaned_data["volume_gap_percent"],
                near_duplicate_tolerance_percent=form.cleaned_data[
                    "near_duplicate_tolerance_percent"
                ],
                outlier_multiplier=form.cleaned_data["outlier_multiplier"],
            )
            form.data = form.data.copy()
            form.data["document_description"] = default_document_description(
                selection=form.selection_spec(), package=review_context["package"]
            )
            context.update(review_context)
        return render(
            request,
            "admin/genericcharts/genericchartgeneration/review.html",
            context,
        )

    def generate_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method != "POST":
            return render(
                request,
                "admin/genericcharts/genericchartgeneration/review.html",
                {
                    **self.admin_site.each_context(request),
                    "form": GenericChartReviewForm(),
                },
            )
        form = GenericChartReviewForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "admin/genericcharts/genericchartgeneration/review.html",
                {**self.admin_site.each_context(request), "form": form},
                status=400,
            )
        generation = create_generation(
            requested_by=request.user,
            selection=form.selection_spec(),
            options={
                **form.package_options(),
                "store_numbers": list(form.cleaned_data["store_numbers"]),
            },
        )
        launch_generation(generation.id)
        from django.contrib import messages
        from django.shortcuts import redirect

        messages.success(request, f"Package generation {generation.id} started.")
        return redirect(
            "admin:genericcharts_genericchartgeneration_change", generation.id
        )


@admin.register(TankEstimateSyncRun)
class TankEstimateSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store_number",
        "mapped_only",
        "scope_type",
        "mapping",
        "status",
        "requested_by",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "mapped_only")
    readonly_fields = (
        "store_number",
        "mapped_only",
        "status",
        "requested_by",
        "started_at",
        "completed_at",
        "output",
        "failure_reason",
        "result_summary",
        "affected_count",
        "succeeded_count",
        "skipped_count",
        "failed_count",
        "warning_count",
        "preview",
        "idempotency_key",
        "created_at",
    )


def tank_estimate_sync_view(request):
    if not request.user.is_staff or not request.user.has_perm(
        "genericcharts.run_tank_estimate_sync"
    ):
        raise PermissionDenied
    if request.method == "POST":
        form = TankEstimateSyncForm(request.POST)
        if form.is_valid():
            run = TankEstimateSyncRun.objects.create(
                store_number=form.cleaned_data["store_number"],
                mapped_only=form.cleaned_data["mapped_only"],
                scope_type=form.cleaned_data["scope"],
                mapping=form.cleaned_data["mapping"],
                requested_profile_version=(
                    form.cleaned_data["mapping"].profile_version
                    if form.cleaned_data["mapping"]
                    else None
                ),
                preview=form.cleaned_data["preview"],
                idempotency_key=form.cleaned_data["idempotency_key"] or None,
                requested_by=request.user,
            )
            launch_tank_estimate_sync(run)
            from django.contrib import messages

            messages.success(request, f"Tank estimate sync {run.id} started.")
            return redirect("admin_sync_tank_estimates")
    else:
        initial = {}
        if request.GET.get("scope") == "store":
            initial = {
                "scope": "store",
                "store_number": request.GET.get("store_number", ""),
                "mapped_only": request.GET.get("mapped_only") == "on",
            }
        form = TankEstimateSyncForm(initial=initial)
    return render(
        request,
        "admin/tankgauge/tank_estimate_sync.html",
        {
            **admin.site.each_context(request),
            "form": form,
            "runs": TankEstimateSyncRun.objects.select_related("requested_by")[:20],
        },
    )
