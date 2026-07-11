from django.contrib import admin, messages
from django.db.models import Q
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import FeedbackClickEvent, FeedbackReport


@admin.register(FeedbackClickEvent)
class FeedbackClickEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "is_submitted",
        "user",
        "short_url",
        "timestamp",
        "submitted_at",
    )
    list_filter = ("is_submitted", "timestamp")
    search_fields = (
        "url",
        "user__username",
        "user__email",
        "user_agent",
    )
    readonly_fields = ("timestamp", "submitted_at")

    def short_url(self, obj):
        if len(obj.url) <= 60:
            return obj.url
        return f"{obj.url[:57]}..."

    short_url.short_description = "URL"


@admin.register(FeedbackReport)
class FeedbackReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "category",
        "user",
        "short_url",
        "timestamp",
        "submitted_at",
        "resolved_at",
    )
    list_filter = ("status", "category", "timestamp")
    search_fields = ("url", "message", "user__username", "user__email", "user_agent")
    readonly_fields = ("timestamp", "submitted_at", "resolved_at")
    actions = ["mark_resolved"]
    change_list_template = "admin/feedback/feedbackreport/change_list.html"

    def short_url(self, obj):
        if len(obj.url) <= 60:
            return obj.url
        return f"{obj.url[:57]}..."

    short_url.short_description = "URL"

    @admin.action(description="Mark selected feedback as resolved")
    def mark_resolved(self, request, queryset):
        updated_count = queryset.update(
            status=FeedbackReport.STATUS_RESOLVED,
            resolved_at=timezone.now(),
        )
        self.message_user(
            request,
            f"Resolved {updated_count} feedback report(s).",
            level=messages.SUCCESS,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "operations/",
                self.admin_site.admin_view(self.operations_view),
                name="feedback_feedbackreport_operations",
            )
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["feedback_ops_url"] = reverse(
            "admin:feedback_feedbackreport_operations"
        )
        return super().changelist_view(request, extra_context=extra_context)

    def operations_view(self, request):
        queryset = FeedbackReport.objects.select_related("user").all()
        status_filter = request.GET.get("status", "").strip()
        category_filter = request.GET.get("category", "").strip()
        search_query = request.GET.get("q", "").strip()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        if search_query:
            queryset = queryset.filter(
                Q(url__icontains=search_query)
                | Q(message__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(user__email__icontains=search_query)
            )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "reports": queryset[:200],
            "status_filter": status_filter,
            "category_filter": category_filter,
            "search_query": search_query,
            "status_choices": FeedbackReport.STATUS_CHOICES,
            "category_choices": FeedbackReport.CATEGORY_CHOICES,
            "changelist_url": reverse("admin:feedback_feedbackreport_changelist"),
        }
        return TemplateResponse(
            request,
            "admin/feedback/feedbackreport/operations.html",
            context,
        )
