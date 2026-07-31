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
