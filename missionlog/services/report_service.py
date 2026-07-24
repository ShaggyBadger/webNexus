from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Prefetch, QuerySet

from missionlog.models import LoadDelivery, Mission
from missionlog.logic.reports.context import ReportContext
from missionlog.logic.validators.mission import MissionValidator
from missionlog.logic.metrics.fuel import calculate_fuel_metrics
from missionlog.logic.metrics.mileage import calculate_mileage_metrics
from missionlog.logic.metrics.efficiency import calculate_efficiency_metrics
from missionlog.logic.metrics.earnings import calculate_earnings
from missionlog.logic.metrics.timeline import generate_event_stream


class ReportService:
    @staticmethod
    def _base_queryset() -> QuerySet[Mission]:
        return Mission.objects.select_related("user").prefetch_related(
            "fuel_logs",
            Prefetch(
                "order_numbers__purchase_orders__loads",
                queryset=LoadDelivery.objects.select_related("fuel_type", "store"),
            ),
        )

    @staticmethod
    def generate(
        mission_id: int, user: Optional[AbstractBaseUser] = None
    ) -> Dict[str, Any]:
        queryset = ReportService._base_queryset()
        if user is not None:
            queryset = queryset.filter(user=user)

        mission = queryset.filter(pk=mission_id).first()
        if mission is None:
            raise Mission.DoesNotExist(f"Mission {mission_id} not found.")

        context = ReportContext(mission)

        # Run validations
        validator = MissionValidator(context)
        issues = validator.validate()

        timeline = generate_event_stream(context.shift)
        hourly_rate = Decimal(str(getattr(settings, "MISSION_HOURLY_RATE", "30.00")))

        # Aggregate metrics
        return {
            "metadata": {
                "mission_id": mission.id,
                "user": mission.user.email,
            },
            "metrics": {
                "fuel": calculate_fuel_metrics(context.shift),
                "mileage": calculate_mileage_metrics(context.shift),
                "efficiency": calculate_efficiency_metrics(context.shift),
                "earnings": calculate_earnings(context.shift, hourly_rate=hourly_rate),
            },
            "timeline": [
                {
                    "event_type": e.event_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "description": e.description,
                    "metadata": e.metadata,
                }
                for e in timeline
            ],
            "warnings": [
                {"code": i.code, "message": i.message, "severity": i.severity.value}
                for i in issues
            ],
        }
