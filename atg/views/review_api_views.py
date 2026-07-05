import json
from uuid import uuid4

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from missionlog.models import FuelType
from tankgauge.models import Store

from ..models import VeederReading, VeederTicket
from ..serializers.reading_serializers import VeederReadingSerializer
from ..services.auto_mapper import AutoMapperService
from ..services.reading_quality import validate_readings_for_store


class VeederReviewQueueListAPIView(APIView):
    """Staff review queue listing endpoint for image-first quick captures."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        status_filter = f"{request.query_params.get('status', '')}".strip().upper()
        store_num_filter = f"{request.query_params.get('store_num', '')}".strip()
        uploader_filter = f"{request.query_params.get('uploaded_by', '')}".strip()

        queryset = (
            VeederTicket.objects.select_related("store", "uploaded_by")
            .annotate(readings_count=Count("readings"))
            .order_by("-uploaded_at")
        )

        if status_filter == "COMPLETED":
            queryset = queryset.filter(readings_count__gt=0)
        elif status_filter == "PENDING":
            queryset = queryset.filter(readings_count=0)
        elif status_filter in {"", "ALL"}:
            pass
        else:
            queryset = queryset.filter(readings_count=0)

        if store_num_filter:
            if store_num_filter.isdigit():
                queryset = queryset.filter(store__store_num=int(store_num_filter))
            else:
                queryset = queryset.none()

        if uploader_filter:
            queryset = queryset.filter(uploaded_by__username__icontains=uploader_filter)

        tickets = [
            {
                "id": ticket.id,
                "uploaded_at": (
                    ticket.uploaded_at.isoformat() if ticket.uploaded_at else None
                ),
                "store_num": ticket.store.store_num if ticket.store else None,
                "store_name": ticket.store.store_name if ticket.store else None,
                "uploaded_by": (
                    ticket.uploaded_by.username if ticket.uploaded_by else "ANONYMOUS"
                ),
                "has_image": bool(ticket.image),
                "readings_count": ticket.readings_count,
                "status": "COMPLETED" if ticket.readings_count > 0 else "PENDING",
            }
            for ticket in queryset[:200]
        ]

        return Response({"status": "success", "data": {"tickets": tickets}})


class VeederReviewQueueDetailAPIView(APIView):
    """Staff review queue detail endpoint for single ticket review work."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, ticket_id):
        try:
            ticket = VeederTicket.objects.select_related("store", "uploaded_by").get(
                id=ticket_id
            )
        except VeederTicket.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "ticket_not_found",
                        "message": "Ticket not found.",
                        "details": {"ticket_id": ticket_id},
                        "trace_id": str(uuid4()),
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        readings = list(
            ticket.readings.select_related("fuel_type")
            .order_by("tank_index")
            .values(
                "id",
                "tank_index",
                "fuel_type_id",
                "fuel_type__name",
                "volume",
                "ullage",
                "height",
                "temp",
                "water",
                "raw_line_text",
                "confidence_score",
                "is_user_corrected",
            )
        )
        for item in readings:
            item["fuel_type_name"] = item.pop("fuel_type__name")

        return Response(
            {
                "status": "success",
                "data": {
                    "ticket": {
                        "id": ticket.id,
                        "store_pk": ticket.store.id if ticket.store else None,
                        "store_num": ticket.store.store_num if ticket.store else None,
                        "store_name": ticket.store.store_name if ticket.store else None,
                        "uploaded_by": (
                            ticket.uploaded_by.username
                            if ticket.uploaded_by
                            else "ANONYMOUS"
                        ),
                        "uploaded_at": (
                            ticket.uploaded_at.isoformat()
                            if ticket.uploaded_at
                            else None
                        ),
                        "ticket_timestamp": (
                            ticket.ticket_timestamp.isoformat()
                            if ticket.ticket_timestamp
                            else None
                        ),
                        "notes": ticket.notes or "",
                        "image_url": ticket.image.url if ticket.image else None,
                    },
                    "readings": readings,
                },
            }
        )


class VeederReviewQueueFinalizeAPIView(APIView):
    """Finalize a review ticket by writing structured readings."""

    permission_classes = [permissions.IsAdminUser]

    def _error(self, *, code: str, message: str, details=None, status_code=400):
        return Response(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                    "trace_id": str(uuid4()),
                }
            },
            status=status_code,
        )

    def post(self, request, ticket_id):
        try:
            ticket = (
                VeederTicket.objects.select_for_update()
                .select_related("store")
                .get(id=ticket_id)
            )
        except VeederTicket.DoesNotExist:
            return self._error(
                code="ticket_not_found",
                message="Ticket not found.",
                details={"ticket_id": ticket_id},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        store_num_raw = f"{request.data.get('store_num', '')}".strip()
        if store_num_raw:
            if not store_num_raw.isdigit():
                return self._error(
                    code="invalid_store_num",
                    message="Store number must be numeric.",
                )
            store = Store.objects.filter(store_num=int(store_num_raw)).first()
            if not store:
                return self._error(
                    code="store_not_found",
                    message="Store not found.",
                    details={"store_num": store_num_raw},
                )
            ticket.store = store

        if not ticket.store:
            return self._error(
                code="store_required",
                message="Store assignment is required before finalize.",
            )

        ticket_timestamp_raw = f"{request.data.get('ticket_timestamp', '')}".strip()
        if ticket_timestamp_raw:
            parsed_timestamp = parse_datetime(ticket_timestamp_raw)
            if parsed_timestamp is None:
                return self._error(
                    code="invalid_ticket_timestamp",
                    message="Ticket timestamp is invalid.",
                    details={"ticket_timestamp": ticket_timestamp_raw},
                )
            if timezone.is_naive(parsed_timestamp):
                parsed_timestamp = timezone.make_aware(
                    parsed_timestamp,
                    timezone.get_current_timezone(),
                )
            ticket.ticket_timestamp = parsed_timestamp

        notes_raw = request.data.get("notes")
        if notes_raw is not None:
            ticket.notes = f"{notes_raw}".strip()

        readings_raw = request.data.get("readings")
        if isinstance(readings_raw, str):
            try:
                readings_raw = json.loads(readings_raw)
            except (TypeError, ValueError):
                readings_raw = None

        if not isinstance(readings_raw, list) or not readings_raw:
            return self._error(
                code="readings_required",
                message="At least one reading is required to finalize.",
            )

        serializer = VeederReadingSerializer(data=readings_raw, many=True)
        if not serializer.is_valid():
            return self._error(
                code="reading_validation_error",
                message="One or more readings are invalid.",
                details=serializer.errors,
            )

        tank_indices = [row.get("tank_index") for row in serializer.validated_data]
        if len(tank_indices) != len(set(tank_indices)):
            return self._error(
                code="duplicate_tank_index",
                message="Duplicate tank indices are not allowed.",
            )

        quality_errors = validate_readings_for_store(
            ticket.store, serializer.validated_data
        )
        if quality_errors:
            return self._error(
                code="reading_quality_error",
                message="Submitted readings failed store quality checks.",
                details={"errors": quality_errors},
            )

        with transaction.atomic():
            ticket.save()
            ticket.readings.all().delete()

            mappings = set()
            for validated in serializer.validated_data:
                VeederReading.objects.create(
                    ticket=ticket,
                    tank_index=validated.get("tank_index"),
                    fuel_type=validated.get("fuel_type"),
                    volume=validated.get("volume"),
                    ullage=validated.get("ullage"),
                    height=validated.get("height"),
                    temp=validated.get("temp"),
                    water=validated.get("water"),
                    raw_line_text=validated.get("raw_line_text"),
                    confidence_score=validated.get("confidence_score", 1.0),
                    is_user_corrected=True,
                )
                mappings.add(
                    (validated.get("tank_index"), validated.get("fuel_type").name)
                )

            def run_auto_mapping() -> None:
                for tank_index, fuel_name in sorted(mappings):
                    try:
                        AutoMapperService.trigger_updates(
                            ticket.store, fuel_name, tank_index
                        )
                    except Exception:
                        pass

            transaction.on_commit(run_auto_mapping)

        return Response(
            {
                "status": "success",
                "data": {
                    "ticket_id": ticket.id,
                    "readings_count": ticket.readings.count(),
                    "store_num": ticket.store.store_num,
                },
            }
        )


class FuelTypeListAPIView(APIView):
    """Return fuel type list for staff review UI form controls."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = list(FuelType.objects.all().order_by("name").values("id", "name"))
        return Response({"status": "success", "data": {"fuel_types": data}})
