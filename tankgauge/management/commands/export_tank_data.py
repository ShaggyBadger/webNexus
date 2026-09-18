import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models as db_models

from atg.models import VeederReading
from tankgauge.logic.capacity_resolution import CapacityResolutionService
from tankgauge.logic.curve_generator import generate_inch_gallon_curve
from tankgauge.logic.geometry import GeometryEngine
from tankgauge.logic.utils import canonicalize_fuel
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    VirtualTankEstimation,
)

DEFAULT_OUTPUT_DIR = os.path.join(
    str(settings.BASE_DIR), "instructions", "tank_data_exports"
)


class Command(BaseCommand):
    help = (
        "Export tank data to 5 JSON files for offline analysis "
        f"(default output: {DEFAULT_OUTPUT_DIR})."
    )

    @staticmethod
    def _clean_tank_type_name(name):
        """Hide abandoned auto-mapper placeholder names (AUTO_*) as unnamed."""
        if name and name.startswith("AUTO_"):
            return None
        return name

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=DEFAULT_OUTPUT_DIR,
            help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
        )
        parser.add_argument(
            "--store",
            type=int,
            help="Limit export to a single store number.",
        )
        parser.add_argument(
            "--compact",
            action="store_true",
            help="Compact JSON output (no indentation).",
        )

    def handle(self, *args, **options):
        output_dir = options["output"]
        store_num = options.get("store")
        indent = None if options["compact"] else 2

        os.makedirs(output_dir, exist_ok=True)

        stores = Store.objects.all()
        if store_num is not None:
            stores = stores.filter(store_num=store_num)

        self._export_store_map(stores, output_dir, indent)
        self._export_official_charts(stores, output_dir, indent)
        recovery_report = self._export_generated_charts(stores, output_dir, indent)
        self._export_tank_assignments(stores, output_dir, indent)
        self._write_json(
            os.path.join(output_dir, "tank_recovery_report.json"),
            recovery_report,
            indent,
        )
        if recovery_report["recovered_tanks"]:
            self.stdout.write(
                self.style.WARNING(
                    "Recovered geometry for "
                    f"{len(recovery_report['recovered_tanks'])} tank(s); "
                    "see tank_recovery_report.json."
                )
            )

    def _export_store_map(self, stores, output_dir, indent):
        store_map = {}
        for store in stores.order_by("store_num"):
            store_map[str(store.id)] = {
                "store_num": store.store_num,
                "riso_num": store.riso_num,
                "store_name": store.store_name,
                "store_type": store.store_type,
                "address": store.address,
                "city": store.city,
                "state": store.state,
                "zip_code": store.zip_code,
                "lat": store.lat,
                "lon": store.lon,
            }

        path = os.path.join(output_dir, "store_map.json")
        self._write_json(path, store_map, indent)
        self.stdout.write(self.style.SUCCESS(f"store_map: {len(store_map)} stores"))

    def _export_official_charts(self, stores, output_dir, indent):
        store_ids = list(stores.values_list("id", flat=True))

        tank_type_ids = (
            StoreTankMapping.objects.filter(store_id__in=store_ids)
            .values_list("tank_type_id", flat=True)
            .distinct()
        )

        charts = (
            TankChart.objects.filter(
                is_official=True,
            )
            .filter(
                db_models.Q(tank_type_id__in=tank_type_ids)
                | db_models.Q(store_id__in=store_ids)
            )
            .select_related("tank_type", "store")
            .order_by("tank_type__name", "inches")
        )

        rows = []
        for chart in charts:
            store_num = None
            if chart.store_id:
                store_num = chart.store.store_num if chart.store else None

            rows.append(
                {
                    "tank_type_id": chart.tank_type_id,
                    "tank_type_name": (
                        chart.tank_type.name if chart.tank_type else None
                    ),
                    "store_id": chart.store_id,
                    "store_num": store_num,
                    "tank_index": chart.tank_index,
                    "is_official": chart.is_official,
                    "inches": chart.inches,
                    "gallons": chart.gallons,
                    "tank_name": chart.tank_name,
                    "misc_info": chart.misc_info,
                }
            )

        path = os.path.join(output_dir, "official_tank_charts.json")
        self._write_json(path, rows, indent)
        self.stdout.write(self.style.SUCCESS(f"official_tank_charts: {len(rows)} rows"))

    def _export_generated_charts(self, stores, output_dir, indent):
        """Export one generated chart per physical tank (store_id, tank_index).

        A tank can have both a mapped TankEstimation and a VirtualTankEstimation
        (the auto-mapper creates a virtual estimate before linking the mapping).
        Candidates are deduped preferring the mapped record; ties break by
        confidence, then sample_count.
        """
        store_ids = list(stores.values_list("id", flat=True))
        candidates = {}
        recovered_tanks = []

        def add_candidate(record, source_priority):
            key = (record["store_id"], record["tank_index"])
            rank = (
                source_priority,
                -(record["confidence"] or 0.0),
                -(record["sample_count"] or 0),
            )
            existing = candidates.get(key)
            if existing is None or rank < existing[0]:
                candidates[key] = (rank, record)

        mappings = (
            StoreTankMapping.objects.filter(store_id__in=store_ids)
            .select_related("store", "tank_type")
            .order_by("store__store_num", "tank_index")
        )

        for mapping in mappings:
            estimation = (
                TankEstimation.objects.filter(
                    tank_mapping=mapping,
                    is_active=True,
                )
                .order_by("-created_at")
                .first()
            )
            if not estimation or not estimation.radius or not estimation.length:
                continue

            radius = float(estimation.radius)
            length = float(estimation.length)
            max_depth = int(radius * 2)

            try:
                chart = generate_inch_gallon_curve(radius, length, max_depth)
            except ValueError:
                continue

            add_candidate(
                {
                    "store_id": mapping.store_id,
                    "store_num": mapping.store.store_num,
                    "tank_index": mapping.tank_index,
                    "fuel_type": mapping.fuel_type,
                    "tank_type_id": (
                        mapping.tank_type_id if mapping.tank_type else None
                    ),
                    "tank_type_name": (
                        self._clean_tank_type_name(mapping.tank_type.name)
                        if mapping.tank_type
                        else None
                    ),
                    "radius": radius,
                    "length": length,
                    "max_depth": max_depth,
                    "confidence": estimation.confidence,
                    "sample_count": estimation.sample_count,
                    "estimation_method": estimation.estimation_method,
                    "algorithm_version": estimation.algorithm_version,
                    "chart": chart,
                },
                source_priority=0,
            )

        virtual_estimators = (
            VirtualTankEstimation.objects.filter(
                store_id__in=store_ids,
                is_active=True,
            )
            .select_related("store")
            .order_by("store__store_num", "tank_index")
        )

        for ve in virtual_estimators:
            radius = float(ve.radius)
            length = float(ve.length)
            max_depth = int(radius * 2)

            try:
                chart = generate_inch_gallon_curve(radius, length, max_depth)
            except ValueError:
                continue

            add_candidate(
                {
                    "store_id": ve.store_id,
                    "store_num": ve.store.store_num,
                    "tank_index": ve.tank_index,
                    "fuel_type": ve.fuel_type,
                    "tank_type_id": None,
                    "tank_type_name": None,
                    "radius": radius,
                    "length": length,
                    "max_depth": max_depth,
                    "confidence": ve.confidence,
                    "sample_count": ve.sample_count,
                    "estimation_method": ve.estimation_method,
                    "algorithm_version": ve.algorithm_version,
                    "chart": chart,
                },
                source_priority=1,
            )

        mappings_by_key = {
            (mapping.store_id, mapping.tank_index): mapping for mapping in mappings
        }
        readings = (
            VeederReading.objects.filter(
                ticket__store_id__in=store_ids,
                acceptance_status="ACCEPTED",
            )
            .select_related("ticket", "fuel_type")
            .order_by("ticket__uploaded_at", "id")
        )
        readings_by_key = {}
        for reading in readings:
            if (
                reading.volume is None
                or reading.ullage is None
                or reading.height is None
            ):
                continue
            try:
                total_capacity = float(reading.volume + reading.ullage)
                height = float(reading.height)
                volume = float(reading.volume)
            except (TypeError, ValueError):
                continue
            if total_capacity <= 0:
                continue
            key = (
                reading.ticket.store_id,
                reading.tank_index,
                canonicalize_fuel(reading.fuel_type.name),
            )
            readings_by_key.setdefault(key, []).append(
                (reading, total_capacity, height, volume)
            )

        geometry_engine = GeometryEngine()
        capacity_resolver = CapacityResolutionService()
        for reading_key, reading_group in readings_by_key.items():
            store_id, tank_index, fuel_type = reading_key
            candidate_key = (store_id, tank_index)
            if candidate_key in candidates:
                continue

            latest_reading, total_capacity, _, _ = reading_group[-1]
            if latest_reading.volume is None or latest_reading.ullage is None:
                continue
            resolution = capacity_resolver.resolve_virtual(
                total_capacity_gallons=latest_reading.volume + latest_reading.ullage,
                evidence_ids=(str(latest_reading.id),),
                basis_percent_exact=latest_reading.ullage_endpoint_percent_exact,
            )
            if not resolution.usable:
                continue
            total_capacity = float(resolution.physical_capacity_gallons)
            observations = [(height, volume) for _, _, height, volume in reading_group]
            result = geometry_engine.calculate_best_fit(total_capacity, observations)
            if result.get("status") != "SUCCESS":
                continue

            radius = float(result["radius"])
            length = float(result["length"])
            max_depth = int(radius * 2)
            try:
                chart = generate_inch_gallon_curve(radius, length, max_depth)
            except ValueError:
                continue

            mapping = mappings_by_key.get(candidate_key)
            recovered_record = {
                "store_id": store_id,
                "store_num": latest_reading.ticket.store.store_num,
                "tank_index": tank_index,
                "fuel_type": fuel_type,
                "tank_type_id": mapping.tank_type_id if mapping else None,
                "tank_type_name": (
                    self._clean_tank_type_name(mapping.tank_type.name)
                    if mapping and mapping.tank_type
                    else None
                ),
                "radius": radius,
                "length": length,
                "max_depth": max_depth,
                "confidence": result["confidence"],
                "sample_count": result["diagnostics"].get("sample_count"),
                "estimation_method": "HORIZONTAL_CYLINDER",
                "algorithm_version": result["algorithm_version"],
                "capacity_status": resolution.status,
                "capacity_warning_codes": list(resolution.warning_codes),
                "chart": chart,
            }
            candidates[candidate_key] = ((2, 0, 0), recovered_record)
            recovered_tanks.append(
                {
                    "store_id": store_id,
                    "store_num": latest_reading.ticket.store.store_num,
                    "tank_index": tank_index,
                    "fuel_type": fuel_type,
                    "reading_count": len(reading_group),
                    "latest_reading_id": latest_reading.id,
                    "reason": "no_active_estimation",
                    "capacity_status": resolution.status,
                }
            )

        generated = [
            record
            for _, record in sorted(
                candidates.values(),
                key=lambda item: (
                    item[1]["store_num"] is None,
                    item[1]["store_num"] or 0,
                    item[1]["tank_index"] is None,
                    item[1]["tank_index"] or 0,
                ),
            )
        ]

        path = os.path.join(output_dir, "generated_tank_charts.json")
        self._write_json(path, generated, indent)
        self.stdout.write(
            self.style.SUCCESS(f"generated_tank_charts: {len(generated)} tanks")
        )
        return {"recovered_tanks": recovered_tanks}

    def _export_tank_assignments(self, stores, output_dir, indent):
        """Export one row per physical tank slot at every store.

        Rows come from StoreTankMapping (the store -> tank -> TankType
        assignment table) plus virtual-only tanks that were estimated but never
        mapped (tank_type_name: null). Abandoned auto-mapper placeholder types
        (AUTO_*) are exported as unnamed. Stores with no tank data simply
        produce no rows. Mappings are the current assignment, so they export
        as active; a virtual-only slot is active only if any estimate is.
        """
        stores_by_id = {store.id: store for store in stores}
        store_ids = list(stores_by_id)
        rows_by_key = {}

        mappings = (
            StoreTankMapping.objects.filter(store_id__in=store_ids)
            .select_related("store", "tank_type")
            .order_by("store__store_num", "tank_index")
        )

        for mapping in mappings:
            key = (
                mapping.store_id,
                canonicalize_fuel(mapping.fuel_type),
                mapping.tank_index,
            )
            rows_by_key[key] = {
                "store_num": mapping.store.store_num,
                "tank_index": mapping.tank_index,
                "tank_type_name": (
                    self._clean_tank_type_name(mapping.tank_type.name)
                    if mapping.tank_type
                    else None
                ),
                "fuel_type": mapping.fuel_type,
                "is_active": True,
            }

        virtual_groups = {}
        virtuals = VirtualTankEstimation.objects.filter(store_id__in=store_ids).only(
            "store_id", "fuel_type", "tank_index", "is_active"
        )

        for ve in virtuals:
            key = (
                ve.store_id,
                canonicalize_fuel(ve.fuel_type),
                ve.tank_index,
            )
            group = virtual_groups.setdefault(
                key, {"fuel_type": ve.fuel_type, "is_active": False}
            )
            group["is_active"] = group["is_active"] or ve.is_active

        for key, group in virtual_groups.items():
            if key in rows_by_key:
                continue
            store_id, _, tank_index = key
            rows_by_key[key] = {
                "store_num": stores_by_id[store_id].store_num,
                "tank_index": tank_index,
                "tank_type_name": None,
                "fuel_type": group["fuel_type"],
                "is_active": group["is_active"],
            }

        rows = sorted(
            rows_by_key.values(),
            key=lambda row: (
                row["store_num"] is None,
                row["store_num"] or 0,
                row["tank_index"] is None,
                row["tank_index"] or 0,
            ),
        )

        path = os.path.join(output_dir, "tank_assignments.json")
        self._write_json(path, rows, indent)
        self.stdout.write(self.style.SUCCESS(f"tank_assignments: {len(rows)} tanks"))

    def _write_json(self, path, data, indent):
        with open(path, "w") as f:
            json.dump(data, f, indent=indent, default=str)
