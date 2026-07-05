import hashlib
import json

from django.contrib.auth.models import User
from django.db import models

from atg.utils.storage import generate_ulid


class VeederReadingPreflightToken(models.Model):
    """One-time preflight token bound to a canonicalized reading payload hash."""

    DECISION_WITHIN_THRESHOLD = "within_threshold"
    DECISION_NEEDS_REVIEW = "outside_threshold_requires_override"
    DECISION_BOOTSTRAP = "bootstrap_requires_confirmation"

    DECISION_CHOICES = [
        (DECISION_WITHIN_THRESHOLD, "Within threshold"),
        (DECISION_NEEDS_REVIEW, "Outside threshold requires override"),
        (DECISION_BOOTSTRAP, "Bootstrap requires confirmation"),
    ]

    id = models.CharField(
        primary_key=True,
        max_length=26,
        default=generate_ulid,
        editable=False,
    )
    store = models.ForeignKey(
        "tankgauge.Store",
        on_delete=models.CASCADE,
        related_name="veeder_preflight_tokens",
    )
    tank_index = models.IntegerField()
    fuel_type = models.ForeignKey(
        "missionlog.FuelType",
        on_delete=models.PROTECT,
        related_name="veeder_preflight_tokens",
    )
    payload_hash = models.CharField(max_length=64, db_index=True)
    decision = models.CharField(max_length=64, choices=DECISION_CHOICES)
    threshold_percent = models.FloatField(default=0.01)
    metrics_snapshot = models.JSONField(default=dict, blank=True)
    trace_id = models.CharField(max_length=64)
    issued_to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_veeder_preflight_tokens",
    )
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by_ticket = models.ForeignKey(
        "atg.VeederTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumed_preflight_tokens",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["store", "tank_index", "fuel_type", "expires_at"]),
            models.Index(fields=["expires_at", "consumed_at"]),
        ]

    @staticmethod
    def build_payload_hash(*, store_id, reading_payload: dict) -> str:
        canonical_payload = {
            "store_id": int(store_id),
            "tank_index": int(reading_payload["tank_index"]),
            "fuel_type_id": int(reading_payload["fuel_type"].id),
            "volume": int(reading_payload["volume"]),
            "ullage": int(reading_payload["ullage"]),
            "height": round(float(reading_payload["height"]), 4),
            "temp": (
                None
                if reading_payload.get("temp") is None
                else round(float(reading_payload["temp"]), 4)
            ),
            "water": (
                None
                if reading_payload.get("water") is None
                else round(float(reading_payload["water"]), 4)
            ),
        }
        payload_bytes = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()
