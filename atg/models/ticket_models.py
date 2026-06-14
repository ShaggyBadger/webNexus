from django.db import models
from django.contrib.auth.models import User
from atg.utils.storage import generate_ulid, veeder_ticket_upload_path


class VeederTicket(models.Model):
    """
    DATA ACQUISITION:
    Represents a physical Veeder-Root / ATG printout.
    This is the 'Primary Evidence' for the system.
    """

    id = models.CharField(
        primary_key=True,
        max_length=26,
        default=generate_ulid,
        editable=False,
        help_text="Globally unique ULID.",
    )
    store = models.ForeignKey(
        "tankgauge.Store",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veeder_tickets",
        help_text="The physical store location where the ticket was printed.",
    )
    image = models.ImageField(
        upload_to=veeder_ticket_upload_path,
        null=True,
        blank=True,
        help_text="Photographic evidence of the physical ticket.",
    )
    ocr_text = models.TextField(
        blank=True,
        null=True,
        help_text="Preserved raw OCR output for future machine learning processing.",
    )
    ocr_status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending Processing"),
            ("PROCESSING", "Processing in Progress"),
            ("COMPLETED", "Completed"),
            ("FAILED", "Failed"),
        ],
        default="PENDING",
        help_text="Remote OCR workflow status.",
    )
    parsed_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Snapshot of the parser's structured output. Preserved for debugging and re-processing.",
    )
    ocr_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when OCR processing finished. Used for latency tracking.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Field observations regarding ticket condition or acquisition.",
    )
    ticket_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The exact time printed on the physical ticket (Manual entry).",
    )

    # Audit Trail
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_veeder_tickets",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Veeder Ticket"
        verbose_name_plural = "Veeder Tickets"
        ordering = ["-uploaded_at"]

    def __str__(self):
        store_lbl = self.store.store_num if self.store else "UNKNOWN"
        return f"Ticket {self.id} - Store {store_lbl}"
