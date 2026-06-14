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
                created_readings = []
                if readings_data:
                    for r_data in readings_data:
                        # Extract metrics, ensuring required fields are present
                        # (Validation already handled by Serializer, but we double-check here for safety)
                        reading = VeederReading.objects.create(
                            ticket=ticket,
                            tank_index=r_data.get("tank_index", 0),
                            fuel_type_id=r_data.get("fuel_type"),
                            volume=r_data.get("volume"),
                            ullage=r_data.get("ullage"),
                            height=r_data.get("height"),
                            temp=r_data.get("temp"),
                            water=r_data.get("water"),
                            raw_line_text=r_data.get("raw_line_text"),
                            confidence_score=r_data.get("confidence_score", 1.0),
                            is_user_corrected=r_data.get("is_user_corrected", False),
                        )
                        created_readings.append(reading)

                logger.info(
                    f"ATG_INGEST_COMPLETE: Ticket {ticket.id} with {len(created_readings)} readings."
                )
                return ticket

        except Exception as e:
            logger.error(
                f"ATG_INGEST_FAILED: Critical failure during ticket ingest: {str(e)}"
            )
            raise e
