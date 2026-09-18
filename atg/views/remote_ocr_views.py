import logging
from uuid import uuid4
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import VeederTicket, VeederReading
from ..serializers import VeederTicketSerializer
from ..serializers.reading_serializers import VeederReadingSerializer
from ..services.auto_mapper import AutoMapperService
from ..services.reading_quality import validate_readings_for_store
from ..utils.permissions import IsRemoteOCRClient

logger = logging.getLogger("webnexus")


def _remote_ocr_disabled_response():
    return Response(
        {
            "status": "disabled",
            "message": "Remote OCR endpoints are disabled. Upload images are still retained for audit.",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _is_remote_ocr_enabled():
    return getattr(settings, "ATG_REMOTE_OCR_ENABLED", False)


def _remote_error(*, code: str, message: str, status_code: int, details=None):
    """Return the canonical error while retaining a transitional string field."""

    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "trace_id": str(uuid4()),
            },
            "legacy_error": message,
        },
        status=status_code,
    )


class RemoteOCRInstructionsView(APIView):
    """
    ENDPOINT 1: INSTRUCTIONS
    Provides the manual and documentation for the Remote OCR Desktop client.
    """

    permission_classes = [IsRemoteOCRClient]

    def get(self, request):
        if not _is_remote_ocr_enabled():
            return _remote_ocr_disabled_response()

        instructions = {
            "mission": "Offload OCR processing from Linode (4GB) to Desktop (GPU/12GB).",
            "protocol": "Fetch-Process-Resolve",
            "endpoints": {
                "GET /atg/api/v1/remote-ocr/instructions/": "This document.",
                "GET /atg/api/v1/remote-ocr/fetch-job/": "Acquire the oldest PENDING ticket and its image URL.",
                "POST /atg/api/v1/remote-ocr/resolve-job/": "Upload extracted JSON data for a ticket.",
            },
            "resolve_payload_format": {
                "ticket_id": "ULID_STRING",
                "ocr_text": "FULL_RAW_TEXT_BLOCK",
                "readings": [
                    {
                        "tank_index": 1,
                        "fuel_type_id": 5,
                        "volume": 5000,
                        "ullage": 1200,
                        "height": 92.5,
                        "temp": 68.4,
                        "raw_line_text": "1 REGULAR 5000 1200 92.5",
                    }
                ],
            },
            "security": "Requires 'X-ATG-Remote-Key' header.",
        }
        return Response(instructions)


class RemoteOCRFetchJobView(APIView):
    """
    ENDPOINT 2: FETCH_JOB
    Returns the oldest ticket with 'PENDING' status.
    Marks it as 'PROCESSING' to avoid race conditions.
    """

    permission_classes = [IsRemoteOCRClient]

    def get(self, request):
        if not _is_remote_ocr_enabled():
            return _remote_ocr_disabled_response()

        with transaction.atomic():
            ticket = (
                VeederTicket.objects.filter(ocr_status="PENDING")
                .order_by("uploaded_at")
                .first()
            )
            if not ticket:
                return Response(
                    {"status": "idle", "message": "No pending jobs found."},
                    status=status.HTTP_200_OK,
                )

            ticket.ocr_status = "PROCESSING"
            ticket.save()

            serializer = VeederTicketSerializer(ticket)
            return Response(serializer.data)


class RemoteOCRResolveJobView(APIView):
    """
    ENDPOINT 3: RESOLVE_JOB
    Accepts extracted data, creates readings, and marks ticket as COMPLETED.
    """

    permission_classes = [IsRemoteOCRClient]

    def post(self, request):
        if not _is_remote_ocr_enabled():
            return _remote_ocr_disabled_response()

        ticket_id = request.data.get("ticket_id")
        readings_data = request.data.get("readings", [])
        ocr_text = request.data.get("ocr_text", "")

        if not ticket_id:
            return _remote_error(
                code="ticket_id_required",
                message="ticket_id required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce tank_index >= 1 and uniqueness within ticket
        seen_indices = set()
        for r_data in readings_data:
            t_idx = r_data.get("tank_index")
            if t_idx is None:
                return _remote_error(
                    code="tank_index_required",
                    message="tank_index is required for all readings.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            try:
                t_idx_int = int(t_idx)
                if t_idx_int < 1:
                    raise ValueError()
            except (ValueError, TypeError):
                return _remote_error(
                    code="invalid_tank_index",
                    message=f"tank_index '{t_idx}' must be a positive integer (>= 1).",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if t_idx_int in seen_indices:
                return _remote_error(
                    code="duplicate_tank_index",
                    message=f"Duplicate tank_index {t_idx_int} detected in submission.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            seen_indices.add(t_idx_int)

        try:
            with transaction.atomic():
                ticket = VeederTicket.objects.select_for_update().get(id=ticket_id)

                # 1. Update Ticket Metadata
                ticket.ocr_text = ocr_text
                ticket.ocr_status = "COMPLETED"
                ticket.save()

                # 2. Create Readings (Standardized via established Service pattern)
                # We clear any partial readings first to ensure a clean slate
                ticket.readings.all().delete()

                serializer_payload = [
                    {
                        "tank_index": r_data.get("tank_index"),
                        "fuel_type": r_data.get("fuel_type_id"),
                        "volume": r_data.get("volume"),
                        "ullage": r_data.get("ullage"),
                        "height": r_data.get("height"),
                        "printed_physical_capacity_gallons": r_data.get(
                            "printed_physical_capacity_gallons"
                        ),
                        "printed_capacity_text": r_data.get("printed_capacity_text"),
                        "temp": r_data.get("temp"),
                        "water": r_data.get("water"),
                        "raw_line_text": r_data.get("raw_line_text"),
                        "confidence_score": r_data.get("confidence_score", 1.0),
                        "is_user_corrected": True,
                    }
                    for r_data in readings_data
                ]

                serializer = VeederReadingSerializer(data=serializer_payload, many=True)
                if not serializer.is_valid():
                    return _remote_error(
                        code="reading_validation_error",
                        message="One or more readings are invalid.",
                        details=serializer.errors,
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                quality_errors = validate_readings_for_store(
                    ticket.store,
                    serializer.validated_data,
                )
                if quality_errors:
                    return _remote_error(
                        code="reading_quality_error",
                        message="Submitted readings failed quality checks.",
                        details={"errors": quality_errors},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                mapping_targets = {
                    (r["tank_index"], r["fuel_type"].name)
                    for r in serializer.validated_data
                }

                for validated_reading in serializer.validated_data:
                    VeederReading.objects.create(
                        ticket=ticket,
                        tank_index=validated_reading.get("tank_index"),
                        fuel_type=validated_reading.get("fuel_type"),
                        volume=validated_reading.get("volume"),
                        ullage=validated_reading.get("ullage"),
                        height=validated_reading.get("height"),
                        printed_physical_capacity_gallons=validated_reading.get(
                            "printed_physical_capacity_gallons"
                        ),
                        printed_capacity_text=validated_reading.get(
                            "printed_capacity_text"
                        ),
                        ullage_endpoint_gallons=validated_reading.get(
                            "ullage_endpoint_gallons"
                        ),
                        ullage_endpoint_percent_exact=validated_reading.get(
                            "ullage_endpoint_percent_exact"
                        ),
                        basis_status=validated_reading.get("basis_status", "UNKNOWN"),
                        temp=validated_reading.get("temp"),
                        water=validated_reading.get("water"),
                        raw_line_text=validated_reading.get("raw_line_text"),
                        confidence_score=validated_reading.get("confidence_score", 1.0),
                        is_user_corrected=True,
                        acceptance_status="ACCEPTED",
                        accepted_at=timezone.now(),
                    )

                def run_auto_mapping() -> None:
                    for tank_index, fuel_name in sorted(mapping_targets):
                        try:
                            AutoMapperService.trigger_updates(
                                ticket.store,
                                fuel_name,
                                tank_index,
                            )
                        except Exception:
                            logger.exception(
                                "REMOTE_OCR_AUTO_MAPPER_FAILED: Ticket %s Store %s Tank %s Fuel %s",
                                ticket_id,
                                ticket.store.store_num if ticket.store else None,
                                tank_index,
                                fuel_name,
                            )

                transaction.on_commit(run_auto_mapping)

                logger.info(
                    f"REMOTE_OCR_RESOLVE: Ticket {ticket_id} resolved with {len(readings_data)} readings."
                )
                return Response({"status": "success", "ticket_id": ticket_id})

        except VeederTicket.DoesNotExist:
            return _remote_error(
                code="ticket_not_found",
                message="Ticket not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"REMOTE_OCR_RESOLVE_FAILED: {str(e)}")
            return _remote_error(
                code="remote_ocr_resolve_failed",
                message="Unable to resolve remote OCR ticket.",
                details={"error": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
