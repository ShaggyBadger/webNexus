from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from tankgauge.logic.utils import canonicalize_fuel


class Store(models.Model):
    """
    OPERATIONAL FLOW:
    Canonical record of a physical retail site.
    Serves as the primary anchor for tank configurations and site-specific data.
    """

    store_num = models.IntegerField(unique=True, null=True, blank=True)
    riso_num = models.IntegerField(unique=True, null=True, blank=True)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    store_type = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(
        max_length=50, null=True, blank=True
    )  # Increased from 2 to 50
    zip_code = models.CharField(
        max_length=10, null=True, blank=True
    )  # Added max_length
    county = models.CharField(max_length=255, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    install_date = models.DateField(null=True, blank=True)
    overfill_protection = models.CharField(max_length=255, null=True, blank=True)

    # Tactical linkage to the site intelligence system
    location = models.OneToOneField(
        "siteintel.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="store_canonical",
        help_text="Canonical link to Site Intelligence",
    )

    class Meta:
        indexes = [
            models.Index(fields=["state"], name="tankgauge_s_state_98018f_idx"),
            models.Index(fields=["city"], name="tankgauge_s_city_1947a1_idx"),
        ]

    def __str__(self):
        return f"{self.store_num} - {self.store_name}"


class StoreTankMapping(models.Model):
    """
    OPERATIONAL FLOW:
    The critical linkage between a physical Store and its installed hardware.
    Defines which fuel product is stored in which tank index.
    """

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="tank_mappings"
    )
    tank_type = models.ForeignKey(
        "tankgauge.TankType", on_delete=models.CASCADE, related_name="store_mappings"
    )
    fuel_type = models.CharField(max_length=20, null=True, blank=True)
    canonical_fuel_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Normalized fuel key used for physical tank identity.",
    )
    tank_index = models.IntegerField(
        null=True,
        blank=True,
        help_text="The physical tank number (1, 2, 3...) from on-site ATG.",
    )

    CAPACITY_SOURCES = (
        ("MANUAL_VERIFIED", "Manual verified"),
        ("OFFICIAL_SELECTED", "Official tank type"),
        ("VEEDER_EXPLICIT_SELECTED", "Veeder explicit"),
        ("VEEDER_DERIVED_SELECTED", "Veeder derived"),
        ("LEGACY_ASSUMED", "Legacy assumed"),
        ("UNRESOLVED", "Unresolved"),
        ("CONFLICTING", "Conflicting"),
    )
    PROFILE_STATUSES = (
        ("READY", "Ready"),
        ("LEGACY_UNVERIFIED", "Legacy unverified"),
        ("REVIEW_REQUIRED", "Review required"),
        ("UNSAFE", "Unsafe"),
        ("UNAVAILABLE", "Unavailable"),
    )

    physical_capacity_gallons = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Canonical physical 100% capacity in gallons.",
    )
    capacity_verified = models.BooleanField(
        default=False,
        help_text="True only after an administrator confirms capacity and basis.",
    )
    capacity_source = models.CharField(
        max_length=40,
        choices=CAPACITY_SOURCES,
        default="UNRESOLVED",
    )
    profile_status = models.CharField(
        max_length=24,
        choices=PROFILE_STATUSES,
        default="UNAVAILABLE",
    )
    ullage_endpoint_percent_exact = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Exact percentage represented by the printed ullage endpoint.",
    )
    capacity_notes = models.TextField(blank=True)
    profile_version = models.PositiveIntegerField(default=1)
    capacity_verified_at = models.DateTimeField(null=True, blank=True)
    capacity_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_tank_capacity_profiles",
    )
    capacity_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "canonical_fuel_type", "tank_index"],
                name="uniq_store_fuel_tank_index",
            )
        ]
        permissions = (("backfill_tank_capacity", "Backfill Veeder capacity evidence"),)

    def save(self, *args, **kwargs):
        self.canonical_fuel_type = canonicalize_fuel(self.fuel_type)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.store_id and self.tank_index is not None:
            duplicate = StoreTankMapping.objects.filter(
                store_id=self.store_id, tank_index=self.tank_index
            ).exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError(
                    {
                        "tank_index": (
                            "This store already has a mapping for this tank index. "
                            "Each physical tank index must identify one tank."
                        )
                    }
                )

    def __str__(self):
        return f"{self.store} - {self.tank_type} ({self.fuel_type})"


class TankCapacityProfileHistory(models.Model):
    """Append-only audit history for canonical physical tank capacity changes."""

    mapping = models.ForeignKey(
        StoreTankMapping,
        on_delete=models.PROTECT,
        related_name="capacity_history",
    )
    profile_version = models.PositiveIntegerField()
    previous_capacity_gallons = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    new_capacity_gallons = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    previous_verified = models.BooleanField(null=True, blank=True)
    new_verified = models.BooleanField(null=True, blank=True)
    previous_source = models.CharField(max_length=40, blank=True)
    new_source = models.CharField(max_length=40, blank=True)
    previous_basis_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    new_basis_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    reason = models.TextField()
    actor_type = models.CharField(max_length=20, default="USER")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tank_capacity_profile_changes",
    )
    source_evidence_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["mapping", "-created_at"]),
        ]
