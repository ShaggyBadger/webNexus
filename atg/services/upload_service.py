import logging

import magic
from django.db import transaction

from ..models import VeederTicket, VeederReading
from .auto_mapper import AutoMapperService
from .reading_quality import validate_readings_for_store

logger = logging.getLogger("webnexus")


class VeederUploadService:
    """OPERATIONAL SERVICE:
    Orchestrates the lifecycle of a Veeder Ticket acquisition.
    Handles the monolithic ingest of an image and its associated readings.
    """

    QUICK_CAPTURE_MAX_UPLOAD_SIZE_BYTES = 12 * 1024 * 1024
    QUICK_CAPTURE_ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
    }

    @classmethod
    def validate_quick_capture_image(cls, uploaded_file) -> str:
        """Validate quick-capture ticket image size and MIME type."""
        if not uploaded_file:
            raise ValueError("Ticket image is required.")

        if uploaded_file.size > cls.QUICK_CAPTURE_MAX_UPLOAD_SIZE_BYTES:
            raise ValueError("Ticket image exceeds maximum allowed size of 12MB.")

        uploaded_file.seek(0)
        header_data = uploaded_file.read(2048)
        uploaded_file.seek(0)
        detected_mime = magic.from_buffer(header_data, mime=True)

        if detected_mime not in cls.QUICK_CAPTURE_ALLOWED_MIME_TYPES:
            raise ValueError(
                "Unsupported ticket image type. Allowed types: JPEG, PNG, WEBP, HEIC."
            )

        return detected_mime

    @staticmethod
    def process_ticket_submission(
        user, store, image, ticket_timestamp=None, notes=None, readings_data=None
    ):
        """
        Ingests a new ticket and creates its associated readings in an atomic transaction.
        """
        from ..serializers.reading_serializers import VeederReadingSerializer

        if not store:
            raise ValueError("Store selection is required.")

        try:
            with transaction.atomic():
                # 1. Create the Ticket (The Evidence)
                ticket = VeederTicket.objects.create(
                    store=store,
                    image=image,
                    ticket_timestamp=ticket_timestamp,
                    notes=notes,
                    uploaded_by=user,
                )

                logger.info(
                    f"ATG_INGEST: Created Ticket {ticket.id} for Store {store.store_num}"
                )

                # 2. Process Readings (The Dataset)
                if readings_data:
                    # Validate readings using the Serializer for consistency
                    serializer = VeederReadingSerializer(data=readings_data, many=True)
                    if not serializer.is_valid():
                        logger.error(
                            f"ATG_INGEST_VALIDATION_FAILED: {serializer.errors}"
                        )
                        raise ValueError(f"Invalid readings data: {serializer.errors}")

                    # Enforce unique tank_index per ticket
                    tank_indices = [
                        r.get("tank_index") for r in serializer.validated_data
                    ]
                    if len(tank_indices) != len(set(tank_indices)):
                        raise ValueError(
                            "Duplicate tank indices are not allowed on a single ticket."
                        )

                    quality_errors = validate_readings_for_store(
                        store,
                        serializer.validated_data,
                    )
                    if quality_errors:
                        raise ValueError(
                            "Invalid readings data: " + " | ".join(quality_errors)
                        )

                    # Bulk create readings associated with the ticket
                    readings_to_create = []
                    for validated_reading in serializer.validated_data:
                        readings_to_create.append(
                            VeederReading(
                                ticket=ticket,
                                tank_index=validated_reading.get("tank_index", 0),
                                fuel_type=validated_reading.get("fuel_type"),
                                volume=validated_reading.get("volume"),
                                ullage=validated_reading.get("ullage"),
                                height=validated_reading.get("height"),
                                temp=validated_reading.get("temp"),
                                water=validated_reading.get("water"),
                                raw_line_text=validated_reading.get("raw_line_text"),
                                confidence_score=validated_reading.get(
                                    "confidence_score", 1.0
                                ),
                                is_user_corrected=validated_reading.get(
                                    "is_user_corrected", False
                                ),
                            )
                        )

                    VeederReading.objects.bulk_create(readings_to_create)

                    # 3. Auto-Map Tanks (after successful commit)
                    mapping_targets = {
                        (
                            validated_reading.get("tank_index", 0),
                            validated_reading.get("fuel_type").name,
                        )
                        for validated_reading in serializer.validated_data
                        if validated_reading.get("fuel_type") is not None
                    }

                    def run_auto_mapping() -> None:
                        if store is None:
                            logger.info(
                                "AUTO_MAPPER: Skipping post-ingest auto-map for Ticket %s because store is missing.",
                                ticket.id,
                            )
                            return

                        for tank_index, fuel_name in sorted(mapping_targets):
                            try:
                                AutoMapperService.trigger_updates(
                                    store,
                                    fuel_name,
                                    tank_index,
                                )
                            except Exception:
                                logger.exception(
                                    "AUTO_MAPPER: Failed for Ticket %s Store %s Tank %s Fuel %s",
                                    ticket.id,
                                    store.store_num,
                                    tank_index,
                                    fuel_name,
                                )

                    transaction.on_commit(run_auto_mapping)

                logger.info(
                    f"ATG_INGEST_COMPLETE: Ticket {ticket.id} processed successfully."
                )
                return ticket

        except Exception as e:
            logger.error(
                f"ATG_INGEST_FAILED: Critical failure during ticket ingest: {str(e)}"
            )
            raise

    @classmethod
    def process_quick_capture_submission(
        cls,
        *,
        user,
        store,
        image,
        ticket_timestamp=None,
        notes=None,
    ):
        """Create an image-first Veeder ticket for later structured review."""
        cls.validate_quick_capture_image(image)

        uploaded_by = user if getattr(user, "is_authenticated", False) else None

        try:
            with transaction.atomic():
                ticket = VeederTicket.objects.create(
                    store=store,
                    image=image,
                    ticket_timestamp=ticket_timestamp,
                    notes=notes,
                    uploaded_by=uploaded_by,
                )

            logger.info(
                "ATG_QUICK_CAPTURE_ACCEPTED ticket_id=%s store_num=%s uploaded_by_id=%s",
                ticket.id,
                ticket.store.store_num if ticket.store else None,
                uploaded_by.id if uploaded_by else None,
            )
            return ticket
        except Exception as exc:
            logger.error(
                "ATG_QUICK_CAPTURE_FAILED store_num=%s uploaded_by_id=%s error=%s",
                store.store_num if store else None,
                uploaded_by.id if uploaded_by else None,
                str(exc),
            )
            raise
