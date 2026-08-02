import time

from django.core.management.base import BaseCommand

from tankcharts.services.chart_service import TankChartService
from tankgauge.models import Store, TankEstimation, VirtualTankEstimation


class Command(BaseCommand):
    help = "Batch generate tank chart PDFs for stores with Veeder-derived data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate charts even if cached and fresh.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5,
            help="Number of stores to process per batch (default: 5).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=2.0,
            help="Pause in seconds between batches (default: 2.0).",
        )
        parser.add_argument(
            "--store",
            type=int,
            help="Target a specific store number.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report stores to process without performing generation.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        batch_size = options["batch_size"]
        sleep_secs = options["sleep"]
        store_num = options.get("store")
        dry_run = options["dry_run"]

        if store_num:
            stores = Store.objects.filter(store_num=store_num)
        else:
            estimation_store_ids = (
                TankEstimation.objects.filter(is_active=True)
                .values_list("tank_mapping__store_id", flat=True)
                .distinct()
            )
            virtual_store_ids = VirtualTankEstimation.objects.filter(
                is_active=True
            ).values_list("store_id", flat=True)
            stores = Store.objects.filter(
                id__in=estimation_store_ids.union(virtual_store_ids)
            ).order_by("store_num")

        total_stores = stores.count()
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Starting tank chart batch generation for {total_stores} store(s)..."
            )
        )

        if dry_run:
            for store in stores:
                self.stdout.write(f"[DRY-RUN] Store {store.store_num} queued.")
            self.stdout.write(self.style.SUCCESS("Dry run complete."))
            return

        orchestrator = TankChartService()
        processed = 0
        success_count = 0
        fail_count = 0

        store_list = list(stores)
        for i in range(0, total_stores, batch_size):
            batch = store_list[i : i + batch_size]
            for store in batch:
                processed += 1
                result = orchestrator.get_store_chart(
                    store_num=store.store_num, force=force
                )
                if result["success"]:
                    success_count += 1
                    source = result.get("source", "cached")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{processed}/{total_stores}] Store {store.store_num}: OK ({source})"
                        )
                    )
                else:
                    fail_count += 1
                    msg = result.get("message", "Unknown error")
                    self.stdout.write(
                        self.style.ERROR(
                            f"[{processed}/{total_stores}] Store {store.store_num}: FAILED ({msg})"
                        )
                    )

            if i + batch_size < total_stores and sleep_secs > 0:
                time.sleep(sleep_secs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Batch generation completed: {success_count} succeeded, {fail_count} failed out of {total_stores} total."
            )
        )
