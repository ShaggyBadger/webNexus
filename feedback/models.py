from django.conf import settings
from django.db import models


class FeedbackClickEvent(models.Model):
    """Raw click telemetry for feedback button interaction attempts."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_click_events",
    )
    url = models.CharField(max_length=1024)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)
    viewport_size = models.CharField(max_length=32, blank=True)
    page_metadata = models.JSONField(default=dict, blank=True)
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["is_submitted", "timestamp"]),
        ]

    def __str__(self) -> str:
        return f"FeedbackClickEvent #{self.id}"


class FeedbackReport(models.Model):
    """Operational feedback record with initiated/submitted lifecycle state."""

    STATUS_INITIATED = "initiated"
    STATUS_SUBMITTED = "submitted"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    CATEGORY_CHART_WRONG = "chart_wrong"
    CATEGORY_DATA_DISCREPANCY = "data_discrepancy"
    CATEGORY_UI_GLITCH = "ui_glitch"
    CATEGORY_QUESTION = "question"
    CATEGORY_GENERAL = "general"
    CATEGORY_CHOICES = [
        (CATEGORY_CHART_WRONG, "Chart Wrong"),
        (CATEGORY_DATA_DISCREPANCY, "Data Discrepancy"),
        (CATEGORY_UI_GLITCH, "UI Glitch"),
        (CATEGORY_QUESTION, "Question"),
        (CATEGORY_GENERAL, "General Feedback"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_reports",
    )
    click_event = models.ForeignKey(
        FeedbackClickEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )
    url = models.CharField(max_length=1024)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_INITIATED,
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        null=True,
        blank=True,
    )
    message = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)
    viewport_size = models.CharField(max_length=32, blank=True)
    page_metadata = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["status", "timestamp"]),
            models.Index(fields=["category", "timestamp"]),
        ]

    def __str__(self) -> str:
        return f"FeedbackReport #{self.id} [{self.status}]"
