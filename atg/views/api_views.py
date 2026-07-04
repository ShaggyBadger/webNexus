import json
from statistics import median
from uuid import uuid4

from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.views import APIView
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from missionlog.models import FuelType
from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankEstimation,
    VirtualTankEstimation,
)
from ..models import VeederTicket, VeederReading
from ..serializers import (
    VeederTicketSerializer,
    VeederReadingSerializer,
    StoreSerializer,
)
from ..services import VeederUploadService


class StoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    TACTICAL API:
    Retrieve stores or search stores by store number or RISO number.
    GET /atg/api/v1/stores/?search=
    """

    queryset = Store.objects.all().select_related("location")
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.query_params.get("search", "").strip()

        if search_query:
            if search_query.isdigit():
                search_value = int(search_query)
                queryset = queryset.filter(
                    Q(store_num=search_value)
                    | Q(riso_num=search_value)
                    | Q(id=search_value)
                )
            else:
                queryset = queryset.filter(store_name__icontains=search_query)

        return queryset.order_by("store_num", "id")[:10]


class VeederQuickCaptureAPIView(APIView):
    """Accept image-first Veeder ticket capture from TankGauge without full ingest."""

    permission_classes = [permissions.AllowAny]

    @staticmethod
    def _trace_id() -> str:
        return str(uuid4())

    def _error(self, *, code: str, message: str, status_code: int, details=None):
        return Response(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                    "trace_id": self._trace_id(),
                }
            },
            status=status_code,
        )

    @staticmethod
    def _resolve_store(*, store_num_raw: str, riso_num_raw: str):
        if store_num_raw and store_num_raw.isdigit():
            store = Store.objects.filter(store_num=int(store_num_raw)).first()
            if store:
                return store

        if riso_num_raw and riso_num_raw.isdigit():
            store = Store.objects.filter(riso_num=int(riso_num_raw)).first()
            if store:
                return store

        return None

    def post(self, request):
        image = request.FILES.get("image")
        if not image:
            return self._error(
                code="missing_image",
                message="Ticket image is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        store_num_raw = f"{request.data.get('store_num', '')}".strip()
        riso_num_raw = f"{request.data.get('riso_num', '')}".strip()
        store = self._resolve_store(
            store_num_raw=store_num_raw, riso_num_raw=riso_num_raw
        )

        ticket_timestamp_raw = f"{request.data.get('ticket_timestamp', '')}".strip()
        ticket_timestamp = None
        if ticket_timestamp_raw:
            ticket_timestamp = parse_datetime(ticket_timestamp_raw)
            if ticket_timestamp is None:
                return self._error(
                    code="invalid_ticket_timestamp",
                    message="Ticket timestamp is invalid.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={"ticket_timestamp": ticket_timestamp_raw},
                )
            if timezone.is_naive(ticket_timestamp):
                ticket_timestamp = timezone.make_aware(
                    ticket_timestamp,
                    timezone.get_current_timezone(),
                )

        notes = f"{request.data.get('notes', '')}".strip()

        try:
            ticket = VeederUploadService.process_quick_capture_submission(
                user=request.user,
                store=store,
                image=image,
                ticket_timestamp=ticket_timestamp,
                notes=notes,
            )
        except ValueError as exc:
            message = str(exc)
            if "maximum allowed size" in message:
                return self._error(
                    code="file_too_large",
                    message=message,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={
                        "max_upload_size_bytes": VeederUploadService.QUICK_CAPTURE_MAX_UPLOAD_SIZE_BYTES
                    },
                )
            if "Unsupported ticket image type" in message:
                return self._error(
                    code="unsupported_mime_type",
                    message=message,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={
                        "allowed_mime_types": sorted(
                            VeederUploadService.QUICK_CAPTURE_ALLOWED_MIME_TYPES
                        )
                    },
                )
            return self._error(
                code="quick_capture_validation_error",
                message=message,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return self._error(
                code="quick_capture_failed",
                message="Unable to submit ticket image right now.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "status": "success",
                "data": {
                    "ticket_id": ticket.id,
                    "store": {
                        "store_pk": ticket.store.id if ticket.store else None,
                        "store_num": ticket.store.store_num if ticket.store else None,
                        "name": ticket.store.store_name if ticket.store else None,
                    },
                    "uploaded_at": (
                        ticket.uploaded_at.isoformat() if ticket.uploaded_at else None
                    ),
                    "requires_review": True,
                },
                "meta": {"trace_id": self._trace_id()},
            },
            status=status.HTTP_201_CREATED,
        )


class VeederTicketViewSet(viewsets.ModelViewSet):
    """
    TACTICAL API:
    Manage Veeder Tickets and their associated readings.
    Supports monolithic creation via the Service Layer.
    """

    queryset = VeederTicket.objects.all().prefetch_related("readings")
    serializer_class = VeederTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Redirect creation to the Service Layer for monolithic processing.
        """
        # We try to get readings from JSON string first (preferred for multipart)
        # then fallback to direct list (standard JSON API).
        readings_json = self.request.data.get("readings_json")
        if readings_json:
            try:
                readings_data = json.loads(readings_json)
            except (ValueError, TypeError):
                readings_data = []
        else:
            readings_data = self.request.data.get("readings", [])

        # We handle the creation manually via service to maintain strict atomicity
        # across the ticket and its multiple readings.
        try:
            ticket = VeederUploadService.process_ticket_submission(
                user=self.request.user,
                store=serializer.validated_data.get("store"),
                image=serializer.validated_data.get("image"),
                ticket_timestamp=serializer.validated_data.get("ticket_timestamp"),
                notes=serializer.validated_data.get("notes"),
                readings_data=readings_data,
            )
        except Exception as e:
            # Catching at view level to return 400 instead of 500
            raise serializers.ValidationError({"error": str(e)})

        # Update the serializer instance so the response contains the new ID
        serializer.instance = ticket


class VeederReadingViewSet(viewsets.ModelViewSet):
    """
    TACTICAL API:
    Manage individual tank readings.
    Used for granular corrections or analysis.
    """

    queryset = VeederReading.objects.all()
    serializer_class = VeederReadingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["fuel_type", "ticket__store"]


class VeederStatsView(APIView):
    """
    ML DATA EXPORT:
    Returns a flattened dataset of all tank readings across the fleet.
    Optimized for JSON/CSV consumption in Machine Learning environments.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        readings = VeederReading.objects.select_related(
            "ticket__store", "fuel_type"
        ).all()

        data = []
        for r in readings:
            store_num = r.ticket.store.store_num if r.ticket.store else None
            data.append(
                {
                    "ticket_id": r.ticket.id,
                    "store_num": store_num,
                    "tank_index": r.tank_index,
                    "fuel_type": r.fuel_type.name,
                    "volume_gal": r.volume,
                    "ullage_gal": r.ullage,
                    "height_in": r.height,
                    "temp_f": r.temp,
                    "water_in": r.water,
                    "timestamp": r.ticket.ticket_timestamp or r.ticket.uploaded_at,
                    "is_verified": r.is_user_corrected,
                }
            )

        return Response({"status": "success", "count": len(data), "data": data})


class StoreTankProfileAPIView(APIView):
    """
    Returns a normalized tank profile for ingest UI prefill/locking.
    """

    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _capacity_from_estimation(estimation):
        if not estimation:
            return None

        diagnostics = estimation.diagnostics or {}
        if diagnostics.get("capacity"):
            return float(diagnostics["capacity"])

        radius_inches = float(estimation.radius or 0)
        length_inches = float(estimation.length or 0)
        if radius_inches <= 0 or length_inches <= 0:
            return None

        return (3.141592653589793 * (radius_inches**2) * length_inches) / 231.0

    def get(self, request, store_num):
        try:
            store = Store.objects.get(store_num=store_num)
        except Store.DoesNotExist:
            return Response(
                {"error": "Store not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        fuel_lookup = {
            canonicalize_fuel(fuel.name): fuel
            for fuel in FuelType.objects.all().only("id", "name")
        }

        known_tanks = []
        covered_keys = set()
        mappings = (
            StoreTankMapping.objects.filter(store=store)
            .select_related("tank_type")
            .order_by("tank_index", "fuel_type", "id")
        )

        for mapping in mappings:
            if mapping.tank_index is None:
                continue

            fuel_key = canonicalize_fuel(mapping.fuel_type)
            if not fuel_key:
                continue

            readings_qs = VeederReading.objects.filter(
                ticket__store=store,
                tank_index=mapping.tank_index,
                fuel_type__name__iexact=fuel_key,
            )
            implied_caps = [
                float(volume + ullage)
                for volume, ullage in readings_qs.values_list("volume", "ullage")
                if volume is not None and ullage is not None
            ]

            mapped_capacity = (
                float(mapping.tank_type.capacity)
                if mapping.tank_type and mapping.tank_type.capacity
                else None
            )
            history_capacity = median(implied_caps) if implied_caps else None
            active_estimation = TankEstimation.objects.filter(
                tank_mapping=mapping,
                is_active=True,
            ).first()
            estimation_capacity = self._capacity_from_estimation(active_estimation)

            baseline_capacity = (
                estimation_capacity or history_capacity or mapped_capacity
            )
            if estimation_capacity:
                baseline_source = "veeder_estimation"
            elif history_capacity:
                baseline_source = "veeder_history"
            elif mapped_capacity:
                baseline_source = "mapped_capacity"
            else:
                baseline_source = None
            fuel_obj = fuel_lookup.get(fuel_key)

            known_tanks.append(
                {
                    "mapping_id": mapping.id,
                    "tank_index": mapping.tank_index,
                    "fuel_key": fuel_key,
                    "fuel_type_id": fuel_obj.id if fuel_obj else None,
                    "fuel_type_name": fuel_obj.name if fuel_obj else mapping.fuel_type,
                    "tank_type_name": (
                        mapping.tank_type.name if mapping.tank_type else None
                    ),
                    "max_depth": (
                        mapping.tank_type.max_depth
                        if mapping.tank_type and mapping.tank_type.max_depth
                        else None
                    ),
                    "baseline_capacity": (
                        int(round(baseline_capacity)) if baseline_capacity else None
                    ),
                    "baseline_source": baseline_source,
                    "readings_count": len(implied_caps),
                    "locked_identity": len(implied_caps) > 0,
                    "verification_status": (
                        "confirmed" if len(implied_caps) > 0 else "unverified_mapping"
                    ),
                    "source": "mapping",
                }
            )
            covered_keys.add((fuel_key, mapping.tank_index))

        history_only_groups = (
            VeederReading.objects.filter(ticket__store=store)
            .values("fuel_type__name", "tank_index")
            .annotate(
                reading_count=Count("id"),
                avg_capacity=Avg(
                    ExpressionWrapper(
                        F("volume") + F("ullage"),
                        output_field=FloatField(),
                    )
                ),
            )
            .order_by("tank_index", "fuel_type__name")
        )

        for group in history_only_groups:
            tank_index = group["tank_index"]
            if tank_index is None:
                continue

            fuel_key = canonicalize_fuel(group["fuel_type__name"])
            if not fuel_key or (fuel_key, tank_index) in covered_keys:
                continue

            fuel_obj = fuel_lookup.get(fuel_key)
            active_virtual_estimation = VirtualTankEstimation.objects.filter(
                store=store,
                fuel_type=fuel_key,
                tank_index=tank_index,
                is_active=True,
            ).first()
            estimation_capacity = self._capacity_from_estimation(
                active_virtual_estimation
            )
            history_capacity = group["avg_capacity"]
            baseline_capacity = estimation_capacity or history_capacity
            known_tanks.append(
                {
                    "mapping_id": None,
                    "tank_index": tank_index,
                    "fuel_key": fuel_key,
                    "fuel_type_id": fuel_obj.id if fuel_obj else None,
                    "fuel_type_name": (
                        fuel_obj.name if fuel_obj else group["fuel_type__name"]
                    ),
                    "tank_type_name": None,
                    "max_depth": None,
                    "baseline_capacity": (
                        int(round(baseline_capacity)) if baseline_capacity else None
                    ),
                    "baseline_source": (
                        "veeder_estimation" if estimation_capacity else "veeder_history"
                    ),
                    "readings_count": group["reading_count"],
                    "locked_identity": True,
                    "verification_status": "confirmed_from_history",
                    "source": "history_only",
                }
            )

        known_tanks.sort(
            key=lambda item: (
                item["tank_index"] if item["tank_index"] is not None else 999,
                item["fuel_key"],
                item["source"],
            )
        )

        return Response(
            {
                "store": {
                    "store_pk": store.id,
                    "store_num": store.store_num,
                    "name": store.store_name,
                    "city": store.city,
                    "state": store.state,
                },
                "known_tanks": known_tanks,
            }
        )
