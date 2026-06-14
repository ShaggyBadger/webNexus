import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.storage import default_storage

from dms.models import Document, TemporaryUpload


class Command(BaseCommand):
    """
    Management command to purge expired temporary uploads, soft-deleted documents,
    and orphaned files, and verify the integrity of the DMS.
    """

    help = "Purge expired temporary uploads, old soft-deleted documents, and orphaned storage files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Purge archived/soft-deleted documents older than this number of days (default: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be purged/deleted without executing any changes.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "--- DRY RUN MODE: No modifications will be made ---"
                )
            )

        # 1. Purge Expired Temporary Uploads
        self.stdout.write("Checking for expired temporary uploads...")
        now = timezone.now()
        expired_temps = TemporaryUpload.objects.filter(expires_at__lt=now)
        expired_temp_count = expired_temps.count()

        for temp in expired_temps:
            file_name = temp.file.name
            self.stdout.write(f"  Expired Temp Upload: ID {temp.id}, File: {file_name}")
            if not dry_run:
                if default_storage.exists(file_name):
                    default_storage.delete(file_name)
                temp.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {expired_temp_count} expired temporary upload record(s)."
            )
        )

        # 2. Purge Soft-Deleted (Archived) Documents
        cutoff_date = now - timedelta(days=days)
        self.stdout.write(
            f"Checking for archived documents soft-deleted before {cutoff_date}..."
        )
        archived_docs = Document.objects.filter(
            status="ARCHIVED", updated_at__lt=cutoff_date
        )
        archived_count = archived_docs.count()

        for doc in archived_docs:
            self.stdout.write(
                f"  Archived Document: ID {doc.id}, Title: {doc.title}, Path: {doc.file_path}"
            )
            if not dry_run:
                if default_storage.exists(doc.file_path):
                    default_storage.delete(doc.file_path)
                doc.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Purged {archived_count} archived document record(s).")
        )

        # 3. Verify Integrity (check missing active files)
        self.stdout.write("Verifying database document integrity...")
        active_docs = Document.objects.filter(
            status__in=["ACTIVE", "SUPERSEDED", "DRAFT"]
        )
        missing_file_count = 0
        for doc in active_docs:
            if not default_storage.exists(doc.file_path):
                self.stdout.write(
                    self.style.ERROR(
                        f"  INTEGRITY FAILURE: Document {doc.id} ({doc.title}) has file_path '{doc.file_path}' but file is missing from storage!"
                    )
                )
                missing_file_count += 1

        if missing_file_count == 0:
            self.stdout.write(
                self.style.SUCCESS("  All active/draft documents verified in storage.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  Found {missing_file_count} missing document files."
                )
            )

        # 4. Remove Orphaned Files
        self.stdout.write("Searching for orphaned files in storage...")
        # Get all valid files registered in database
        valid_paths = set(Document.objects.values_list("file_path", flat=True))
        valid_paths.update(TemporaryUpload.objects.values_list("file", flat=True))

        # Helper to recursively list files in storage folders
        def get_all_files_in_dir(directory: str) -> list:
            if not default_storage.exists(directory):
                return []
            try:
                dirs, files = default_storage.listdir(directory)
            except Exception:
                return []

            all_files = [os.path.join(directory, f) for f in files]
            for d in dirs:
                # Skip double dots and special dirs
                if d in [".", ".."]:
                    continue
                all_files.extend(get_all_files_in_dir(os.path.join(directory, d)))
            return all_files

        # Scan documents, temp, and trash folders
        scan_dirs = ["documents", "temp", "trash"]
        storage_files = []
        for sdir in scan_dirs:
            storage_files.extend(get_all_files_in_dir(sdir))

        orphaned_count = 0
        for file_path in storage_files:
            # Normalize path delimiters for direct lookup comparisons
            normalized_path = file_path.replace("\\", "/")

            # Check if this file is in our valid paths
            if normalized_path not in valid_paths:
                self.stdout.write(f"  Orphaned File: {normalized_path}")
                orphaned_count += 1
                if not dry_run:
                    default_storage.delete(file_path)

        self.stdout.write(
            self.style.SUCCESS(f"Purged {orphaned_count} orphaned storage file(s).")
        )
