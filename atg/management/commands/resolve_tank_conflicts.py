import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from atg.models import VeederReading
from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import Store, StoreTankMapping

logger = logging.getLogger("webnexus")


class Command(BaseCommand):
    """
    Management command to find and resolve duplicate StoreTankMapping records
    caused by manual SiteIntel entries being superseded by Veeder-Root ATG
    uploads with authoritative tank_index values.

    Resolution logic (mirrors AutoMapperService.ensure_mapping merge step):
      - For each store, group mappings by fuel_type.
      - If a fuel_type has more than one mapping at different tank_indices,
        determine which index is confirmed by VeederReading records.
      - The mapping whose tank_index has NO supporting readings is the stale
        manual entry. Update it to match the confirmed ATG index and delete
        the now-redundant AUTO_ duplicate.
      - If BOTH indices have readings (a genuine two-tank store), skip and report.

    Usage:
      python manage.py resolve_tank_conflicts           # dry run (safe preview)
      python manage.py resolve_tank_conflicts --commit  # apply changes
    """

    help = "Resolve duplicate StoreTankMapping records caused by conflicting manual and ATG-auto entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            default=False,
            help="Apply changes to the database. Without this flag, only a dry-run preview is shown.",
        )
        parser.add_argument(
            "--store",
            type=int,
            default=None,
            help="Limit resolution to a single store number.",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        target_store_num = options.get("store")

        mode = "COMMIT" if commit else "DRY-RUN"
        self.stdout.write(
            self.style.WARNING(f"\n[{mode}] Resolving Tank Mapping Conflicts\n")
        )
        if not commit:
            self.stdout.write(
                "  Run with --commit to apply changes. No data will be modified.\n"
            )

        stores_qs = Store.objects.all()
        if target_store_num:
            stores_qs = stores_qs.filter(store_num=target_store_num)

        total_fixed = 0
        total_skipped = 0
        total_already_clean = 0

        for store in stores_qs.prefetch_related("tank_mappings__tank_type"):
            mappings = list(store.tank_mappings.select_related("tank_type").all())
            if not mappings:
                continue

            # Group by fuel_type
            by_fuel = {}
            for m in mappings:
                fuel_key = canonicalize_fuel(m.fuel_type)
                by_fuel.setdefault(fuel_key, []).append(m)

            for fuel_type, fuel_mappings in by_fuel.items():
                if len(fuel_mappings) <= 1:
                    total_already_clean += 1
                    continue

                # Multiple mappings for same fuel — analyse each index
                self.stdout.write(
                    f"\n  Store {store.store_num} | {fuel_type.upper()} — "
                    f"{len(fuel_mappings)} mappings found:"
                )
                for m in fuel_mappings:
                    is_auto = m.tank_type and m.tank_type.name.startswith("AUTO_")
                    tag = "[AUTO]  " if is_auto else "[MANUAL]"
                    self.stdout.write(
                        f"    {tag} ID:{m.id} | idx:{m.tank_index} | type:{m.tank_type.name if m.tank_type else 'None'}"
                    )

                # Find which indices have real ATG readings
                readings_by_index = {}
                for m in fuel_mappings:
                    count = VeederReading.objects.filter(
                        ticket__store=store,
                        tank_index=m.tank_index,
                        fuel_type__name__iexact=fuel_type,
                    ).count()
                    readings_by_index[m.id] = (m.tank_index, count)
                    self.stdout.write(
                        f"           → index {m.tank_index}: {count} Veeder reading(s)"
                    )

                # Separate confirmed (has readings) from stale (no readings)
                confirmed = [m for m in fuel_mappings if readings_by_index[m.id][1] > 0]
                stale = [m for m in fuel_mappings if readings_by_index[m.id][1] == 0]

                if len(confirmed) == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ⚠  SKIP: No Veeder readings for ANY mapping. Cannot determine ground truth."
                        )
                    )
                    total_skipped += 1
                    continue

                if len(confirmed) > 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ⚠  SKIP: Multiple indices have readings — likely a genuine multi-tank setup."
                        )
                    )
                    total_skipped += 1
                    continue

                if len(stale) == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ⚠  SKIP: All mappings have readings — cannot safely determine which to remove."
                        )
                    )
                    total_skipped += 1
                    continue

                # Exactly one confirmed, one or more stale — safe to resolve
                ground_truth = confirmed[0]
                ground_truth_is_auto = bool(
                    ground_truth.tank_type
                ) and ground_truth.tank_type.name.startswith("AUTO_")

                if ground_truth_is_auto and len(stale) > 1:
                    self.stdout.write(
                        self.style.WARNING(
                            "    ⚠  SKIP: confirmed mapping is AUTO_ but multiple stale mappings exist. "
                            "Cannot safely collapse to one manual mapping."
                        )
                    )
                    total_skipped += 1
                    continue

                resolved_for_fuel = 0
                with transaction.atomic():
                    for stale_mapping in stale:
                        stale_is_auto = bool(
                            stale_mapping.tank_type
                        ) and stale_mapping.tank_type.name.startswith("AUTO_")

                        if stale_is_auto:
                            action = "DELETE (stale AUTO_ duplicate)"
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"    ✓  RESOLVE: Mapping ID:{stale_mapping.id} [{action}]"
                                )
                            )
                            if commit:
                                stale_mapping.delete()
                            resolved_for_fuel += 1
                            continue

                        if ground_truth_is_auto:
                            action = (
                                "DELETE confirmed AUTO_ + "
                                f"UPDATE stale MANUAL index {stale_mapping.tank_index} → {ground_truth.tank_index}"
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"    ✓  RESOLVE: Mapping ID:{stale_mapping.id} [{action}]"
                                )
                            )
                            if commit:
                                ground_truth.delete()
                                stale_mapping.tank_index = ground_truth.tank_index
                                stale_mapping.save(update_fields=["tank_index"])
                            resolved_for_fuel += 1
                            continue

                        self.stdout.write(
                            self.style.WARNING(
                                "    ⚠  SKIP: stale mapping is MANUAL but confirmed mapping is not AUTO_. "
                                "Cannot safely resolve without risking duplicate/manual conflict."
                            )
                        )
                        total_skipped += 1
                        continue

                if resolved_for_fuel > 0:
                    total_fixed += 1

        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(f"  Fixed:         {total_fixed}")
        self.stdout.write(f"  Skipped:       {total_skipped}")
        self.stdout.write(f"  Already clean: {total_already_clean}")
        if not commit:
            self.stdout.write(
                self.style.WARNING(
                    "\n  [DRY-RUN] No changes were written. Re-run with --commit to apply.\n"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  [COMMIT] Done. {total_fixed} conflict(s) resolved.\n"
                )
            )
