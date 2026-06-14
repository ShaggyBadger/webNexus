import logging
from django.db import transaction
from ..models import VeederTicket, VeederReading

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
                    f"ATG_INGEST: Created Ticket {ticket.id} for Store {store.store_num if store else 'UNKNOWN'}"
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

                logger.info(
                    f"ATG_INGEST_COMPLETE: Ticket {ticket.id} processed successfully."
                )
                return ticket

        except Exception as e:
            logger.error(
                f"ATG_INGEST_FAILED: Critical failure during ticket ingest: {str(e)}"
            )
            raise e
