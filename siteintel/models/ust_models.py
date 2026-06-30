from django.db import models
from django.db.models import Q, UniqueConstraint
from django.contrib.auth.models import User
from tankgauge.models import Store


class USTPermit(models.Model):
    """
    OPERATIONAL_INTEL:
    Represents the current known permit information for a physical store.
    One store may have many historical permits, but only ONE active permit at a time.
    """

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="ust_permits"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="If true, this is the current authoritative permit for the store.",
    )

    permit_number = models.CharField(max_length=100, blank=True, null=True)
    issue_date = models.DateField(blank=True, null=True)
    expiration_date = models.DateField()
    permit_image = models.ImageField(upload_to="ust_permits/", blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "UST Permit"
        verbose_name_plural = "UST Permits"
        constraints = [
            UniqueConstraint(
                fields=["store"],
                condition=Q(is_active=True),
                name="unique_active_permit_per_store",
            )
        ]

    def __str__(self):
        status = " [ACTIVE]" if self.is_active else " [EXPIRED/HISTORICAL]"
        return f"Permit for {self.store.store_num} (Expires: {self.expiration_date}){status}"


class USTVerification(models.Model):
    """
    AUDIT_TRAIL:
    Represents a physical confirmation event by a field agent.
    Strictly append-only and immutable.
    """

    VERIFICATION_TYPES = [
        ("confirmed", "Confirmed"),
        ("updated", "Updated"),
    ]

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="ust_verifications"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ust_verifications"
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPES)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "UST Verification"
        verbose_name_plural = "UST Verification Records"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.verification_type.capitalize()} by {self.user.username} at {self.store.store_num}"
