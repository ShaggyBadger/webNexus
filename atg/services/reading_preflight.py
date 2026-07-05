from __future__ import annotations

from datetime import timedelta
from statistics import median
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from tankgauge.logic.geometry import GeometryEngine
from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import StoreTankMapping, TankEstimation, VirtualTankEstimation

from ..models import VeederReading, VeederReadingPreflightToken


class ReadingPreflightService:
    """Preflight validation and one-time token minting for Veeder reading submissions."""

    DEFAULT_THRESHOLD_PERCENT = 0.01
    TOKEN_TTL_MINUTES = 10

    @classmethod
    def validate_and_issue_tokens(
        cls,
        *,
        store,
        validated_readings: list[dict],
        user,
    ) -> dict:
        trace_id = str(uuid4())
        rows: list[dict] = []
        now = timezone.now()
        expires_at = now + timedelta(minutes=cls.TOKEN_TTL_MINUTES)

        for reading in validated_readings:
            analysis = cls._analyze_reading(
                store=store,
                validated_reading=reading,
                threshold_percent=cls.DEFAULT_THRESHOLD_PERCENT,
            )

            payload_hash = VeederReadingPreflightToken.build_payload_hash(
                store_id=store.id,
                reading_payload=reading,
            )

            token = VeederReadingPreflightToken.objects.create(
                store=store,
                tank_index=reading.get("tank_index"),
                fuel_type=reading.get("fuel_type"),
                payload_hash=payload_hash,
                decision=analysis["decision"],
                threshold_percent=analysis["threshold_percent"],
                metrics_snapshot=analysis["metrics"],
                trace_id=trace_id,
                issued_to_user=(
                    user if getattr(user, "is_authenticated", False) else None
                ),
                expires_at=expires_at,
            )

            rows.append(
                {
                    "tank_index": reading.get("tank_index"),
                    "fuel_type_id": reading.get("fuel_type").id,
                    "fuel_type_name": reading.get("fuel_type").name,
                    "decision": analysis["decision"],
                    "threshold_percent": analysis["threshold_percent"],
                    "metrics": analysis["metrics"],
                    "graph": analysis["graph"],
                    "preflight_token": token.id,
                    "expires_at": expires_at.isoformat(),
                }
            )

        return {
            "trace_id": trace_id,
            "rows": rows,
        }

    @classmethod
    def verify_and_consume_tokens(
        cls,
        *,
        store,
        validated_readings: list[dict],
        preflight_tokens: list[str],
        override_reasons: dict,
        ticket,
    ) -> None:
        if not preflight_tokens:
            raise ValueError("Preflight tokens are required before final submit.")

        if len(preflight_tokens) != len(validated_readings):
            raise ValueError("Preflight token count does not match reading count.")

        now = timezone.now()

        with transaction.atomic():
            token_qs = VeederReadingPreflightToken.objects.select_for_update().filter(
                id__in=preflight_tokens,
                store=store,
            )
            token_by_id = {token.id: token for token in token_qs}

            if len(token_by_id) != len(preflight_tokens):
                raise ValueError("One or more preflight tokens are invalid.")

            for token_id, reading in zip(preflight_tokens, validated_readings):
                token = token_by_id[token_id]

                if token.consumed_at is not None:
                    raise ValueError("A preflight token was already consumed.")

                if token.expires_at <= now:
                    raise ValueError(
                        "A preflight token has expired. Re-run validation."
                    )

                expected_hash = VeederReadingPreflightToken.build_payload_hash(
                    store_id=store.id,
                    reading_payload=reading,
                )
                if token.payload_hash != expected_hash:
                    raise ValueError(
                        "Reading payload changed after preflight. Re-run validation."
                    )

                if token.tank_index != reading.get("tank_index"):
                    raise ValueError("Preflight token tank mismatch.")

                if token.fuel_type_id != reading.get("fuel_type").id:
                    raise ValueError("Preflight token fuel mismatch.")

                if token.decision == VeederReadingPreflightToken.DECISION_NEEDS_REVIEW:
                    reason = f"{override_reasons.get(token.id, '')}".strip()
                    if len(reason) < 5:
                        raise ValueError(
                            "Override reason is required for out-of-threshold readings."
                        )

                token.consumed_at = now
                token.consumed_by_ticket = ticket
                token.save(update_fields=["consumed_at", "consumed_by_ticket"])

    @classmethod
    def _analyze_reading(
        cls,
        *,
        store,
        validated_reading: dict,
        threshold_percent: float,
    ) -> dict:
        tank_index = int(validated_reading.get("tank_index"))
        fuel_name = validated_reading.get("fuel_type").name
        fuel_key = canonicalize_fuel(fuel_name)

        input_volume = float(validated_reading.get("volume") or 0)
        input_height = float(validated_reading.get("height") or 0)
        water_inches = float(validated_reading.get("water") or 0)

        history_qs = VeederReading.objects.filter(
            ticket__store=store,
            tank_index=tank_index,
            fuel_type__name__iexact=fuel_key,
            height__isnull=False,
            volume__isnull=False,
        )
        history_points = [
            {
                "inches": float(height),
                "gallons": float(volume),
            }
            for height, volume in history_qs.values_list("height", "volume")[:40]
        ]

        expected_volume, source = cls._expected_volume(
            store=store,
            fuel_key=fuel_key,
            tank_index=tank_index,
            input_height=input_height,
            water_inches=water_inches,
            history_qs=history_qs,
        )

        if expected_volume is None:
            decision = VeederReadingPreflightToken.DECISION_BOOTSTRAP
            absolute_error = None
            percent_error = None
        else:
            absolute_error = abs(input_volume - expected_volume)
            percent_error = absolute_error / max(expected_volume, 1.0)
            if percent_error <= threshold_percent:
                decision = VeederReadingPreflightToken.DECISION_WITHIN_THRESHOLD
            else:
                decision = VeederReadingPreflightToken.DECISION_NEEDS_REVIEW

        return {
            "decision": decision,
            "threshold_percent": threshold_percent,
            "metrics": {
                "input_volume": round(input_volume, 3),
                "input_height_inches": round(input_height, 3),
                "water_inches": round(water_inches, 3) if water_inches else 0.0,
                "expected_volume": (
                    round(expected_volume, 3) if expected_volume is not None else None
                ),
                "absolute_error": (
                    round(absolute_error, 3) if absolute_error is not None else None
                ),
                "percent_error": (
                    round(percent_error, 6) if percent_error is not None else None
                ),
                "source": source,
                "history_count": history_qs.count(),
            },
            "graph": {
                "historical_points": history_points,
                "candidate_point": {
                    "inches": input_height,
                    "gallons": input_volume,
                },
            },
        }

    @classmethod
    def _expected_volume(
        cls,
        *,
        store,
        fuel_key: str,
        tank_index: int,
        input_height: float,
        water_inches: float,
        history_qs,
    ) -> tuple[float | None, str]:
        mapping = (
            StoreTankMapping.objects.filter(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
            )
            .select_related("tank_type")
            .first()
        )

        estimation = None
        if mapping is not None:
            estimation = TankEstimation.objects.filter(
                tank_mapping=mapping,
                is_active=True,
            ).first()
        if estimation is None:
            estimation = VirtualTankEstimation.objects.filter(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
                is_active=True,
            ).first()

        if estimation and estimation.radius and estimation.length:
            engine = GeometryEngine()
            total_volume = engine.volume_from_depth(
                float(estimation.radius),
                float(estimation.length),
                input_height,
            )
            water_volume = 0.0
            if water_inches > 0:
                water_volume = engine.volume_from_depth(
                    float(estimation.radius),
                    float(estimation.length),
                    water_inches,
                )
            return max(total_volume - water_volume, 0.0), "estimation_geometry"

        history_capacity = [
            float(volume)
            for volume in history_qs.values_list("volume", flat=True)
            if volume is not None
        ]
        if history_capacity:
            return float(median(history_capacity)), "history_fallback"

        return None, "bootstrap"
