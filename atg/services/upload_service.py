import logging
from django.db import transaction
from ..models import VeederTicket, VeederReading
from .auto_mapper import AutoMapperService
from .reading_quality import validate_readings_for_store

logger = logging.getLogger("webnexus")


class VeederUploadService:
    """
    OPERATIONAL SERVICE:
    Orchestrates the lifecycle of a Veeder Ticket acquisition.
    Handles the monolithic ingest of an image and its associated readings.
    """

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
