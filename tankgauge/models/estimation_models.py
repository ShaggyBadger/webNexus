from django.db import models


class TankEstimation(models.Model):
    """
    ANALYTICAL INTELLIGENCE:
    Stores mathematically reconstructed geometry for a specific physical tank.
    These records are immutable; new estimates create new records rather than overwriting.
    """

    tank_mapping = models.ForeignKey(
        "tankgauge.StoreTankMapping",
        on_delete=models.CASCADE,
        related_name="estimations",
        help_text="The physical tank being modeled.",
    )

    # Geometry Results
    radius = models.FloatField(help_text="Estimated tank radius in inches.")
    length = models.FloatField(help_text="Estimated tank length in inches.")

    # Confidence & Quality Metrics
    confidence = models.FloatField(
        help_text="Overall confidence score (0.0 to 1.0) for this estimate."
    )
    mean_error = models.FloatField(
        null=True, blank=True, help_text="Mean absolute error in gallons."
    )
    max_error = models.FloatField(
        null=True, blank=True, help_text="Maximum observed error in gallons."
    )
    sample_count = models.IntegerField(
        help_text="Number of (height, volume) points used for this estimation."
    )

    # Metadata & Versioning
    estimation_method = models.CharField(
        max_length=100,
        default="HORIZONTAL_CYLINDER",
        help_text="The mathematical model used (e.g., Horizontal Cylinder).",
    )
    algorithm_version = models.CharField(
        max_length=50, help_text="Version of the GeometryEngine used."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="True if this is the designated 'current' estimate for this tank.",
    )

    # Diagnostics (Stored as JSON for future-proofing)
    diagnostics = models.JSONField(
        null=True, blank=True, help_text="Detailed iteration data and fitting metrics."
    )

    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tank Estimation"
        verbose_name_plural = "Tank Estimations"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Estimate {self.id} | Tank {self.tank_mapping} (v{self.algorithm_version})"
        )
