from django.db import models


class TankGaugeConfig(models.Model):
    """
    Singleton configuration model for TankGauge operational settings.

    Only one instance of this model should ever exist. All code should
    access it via TankGaugeConfig.get_solo() to ensure safe get-or-create behavior.

    This allows admin-level control over engine behavior without requiring
    a deployment or environment variable change.
    """

    MODE_PRIORITY_CHOICES = [
        ("OFFICIAL_FIRST", "Official Tank Chart (Priority)"),
        ("MATHEMATICAL_FIRST", "Mathematical / Veeder-Root (Priority)"),
    ]

    mode_priority = models.CharField(
        max_length=30,
        choices=MODE_PRIORITY_CHOICES,
        default="OFFICIAL_FIRST",
        verbose_name="Default Mode Priority",
        help_text=(
            "Controls which data source the calculation engine prefers when BOTH "
            "a Tank Chart AND sufficient Veeder-Root data are available for a tank. "
            "If only one source exists, that source is always used regardless of this setting."
        ),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "TankGauge Configuration"
        verbose_name_plural = "TankGauge Configuration"

    def __str__(self):
        return f"TankGauge Config — Priority: {self.get_mode_priority_display()}"

    @classmethod
    def get_solo(cls):
        """
        Returns the singleton config instance, creating it with defaults if it
        does not yet exist. This is the canonical access pattern for this model.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
