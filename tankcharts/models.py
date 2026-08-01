from django.db import models


class StoreChartGeneration(models.Model):
    """
    Tracks generation state and mutex lock for store-wide tank chart PDFs.
    Ensures field operators have persistent status tracking and failure backoff.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATING = "generating", "Generating"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    store = models.OneToOneField(
        "tankgauge.Store",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="chart_generation",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    failure_count = models.IntegerField(default=0)
    failure_reason = models.TextField(blank=True)
    retry_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tankcharts_storechartgeneration"
        verbose_name = "Store Chart Generation"
        verbose_name_plural = "Store Chart Generations"

    def __str__(self) -> str:
        return f"Store {self.store_id} Chart Generation ({self.status})"


class TankChartAccessLog(models.Model):
    """
    Unified access log for tank chart downloads and emails.
    Captures delivery method, recipient email, status, and request telemetry.
    """

    class DeliveryMethod(models.TextChoices):
        DOWNLOAD = "download", "Download"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    class ChartSource(models.TextChoices):
        CACHED = "cached", "Cached"
        GENERATED = "generated", "Generated"

    id = models.AutoField(primary_key=True)
    store = models.ForeignKey("tankgauge.Store", on_delete=models.CASCADE)
    recipient_email = models.EmailField(blank=True)
    sent_by_user = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    chart_document = models.ForeignKey(
        "dms.Document", null=True, blank=True, on_delete=models.SET_NULL
    )
    delivery_method = models.CharField(max_length=20, choices=DeliveryMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    failure_reason = models.TextField(blank=True)
    chart_source = models.CharField(
        max_length=20, choices=ChartSource.choices, blank=True
    )
    generation_duration_ms = models.IntegerField(null=True, blank=True)
    file_size_bytes = models.IntegerField(null=True, blank=True)
    trace_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tankcharts_accesslog"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["store", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["delivery_method"]),
        ]

    def __str__(self) -> str:
        return f"AccessLog {self.id}: Store {self.store_id} ({self.delivery_method}/{self.status})"
