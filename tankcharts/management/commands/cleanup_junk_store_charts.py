from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from dms.models import Document
from tankgauge.models import Store, TankEstimation, VirtualTankEstimation


class Command(BaseCommand):
    help = (
        "Delete store-chart DMS documents for stores with no active "
        "Veeder-derived estimations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report candidate documents without deleting.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        store_content_type = ContentType.objects.get_for_model(Store)

        store_chart_docs = Document.objects.filter(
            category__slug="tankchart",
            content_type=store_content_type,
            status="ACTIVE",
            original_filename__endswith="_STORE.pdf",
        ).order_by("uploaded_at")

        deleted_count = 0
        scanned_count = 0

        for document in store_chart_docs:
            scanned_count += 1
            if not document.object_id or not document.object_id.isdigit():
                continue

            store_id = int(document.object_id)
            has_mapped_estimation = TankEstimation.objects.filter(
                tank_mapping__store_id=store_id,
                is_active=True,
            ).exists()
            has_virtual_estimation = VirtualTankEstimation.objects.filter(
                store_id=store_id,
                is_active=True,
            ).exists()

            if has_mapped_estimation or has_virtual_estimation:
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] would delete document {document.id} "
                    f"for store_id={store_id}"
                )
                continue

            default_storage.delete(document.file_path)
            document.delete()
            deleted_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete. Scanned {scanned_count} store charts."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} junk store chart(s) "
                f"out of {scanned_count} scanned."
            )
        )
