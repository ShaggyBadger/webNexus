from django.conf import settings
from django.db import models


class GenericChartGeneration(models.Model):
    """Track one CoreStarterPack generation job and its published document."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    state = models.CharField(
        max_length=100,
        help_text="Normalized state name or FULL for the complete package.",
    )
    package_scope_key = models.CharField(
        max_length=180,
        help_text="Stable selection key used to isolate package files and DMS history.",
        default="full",
    )
    generator_version = models.CharField(max_length=20)
    options = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="generic_chart_generations",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict)
    failure_reason = models.TextField(blank=True)
    document = models.ForeignKey(
        "dms.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generic_chart_generations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["state", "-created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"CoreStarterPack [{self.state}] v{self.generator_version} "
            f"({self.status})"
        )


class TankEstimateSyncRun(models.Model):
    """Track an admin-launched tank estimation repair run."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        PARTIAL_FAILURE = "partial_failure", "Partial failure"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class ScopeType(models.TextChoices):
        MAPPING = "mapping", "One mapping"
        STORE = "store", "One store"
        ALL = "all", "All stores"

    store_number = models.IntegerField(null=True, blank=True)
    mapped_only = models.BooleanField(default=False)
    scope_type = models.CharField(
        max_length=20, choices=ScopeType.choices, default=ScopeType.ALL
    )
    mapping = models.ForeignKey(
        "tankgauge.StoreTankMapping",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="estimate_sync_runs",
    )
    requested_profile_version = models.PositiveIntegerField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=100, null=True, blank=True)
    affected_count = models.PositiveIntegerField(default=0)
    succeeded_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    preview = models.BooleanField(default=False)
    result_summary = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tank_estimate_sync_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    output = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                name="uniq_tank_sync_idempotency_key",
            )
        ]
        permissions = (("run_tank_estimate_sync", "Run tank estimate sync"),)

    def __str__(self) -> str:
        scope = self.store_number or "all stores"
        return f"Tank estimate sync [{scope}] ({self.status})"
