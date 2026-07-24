import json
import os

from django.core.management.base import BaseCommand
from django.db import models as db_models

from tankgauge.logic.curve_generator import generate_inch_gallon_curve
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    VirtualTankEstimation,
)


class Command(BaseCommand):
    help = "Export tank data to 3 JSON files for offline analysis."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=".",
            help="Output directory (default: current directory).",
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
        self._export_generated_charts(stores, output_dir, indent)

    def _export_store_map(self, stores, output_dir, indent):
        store_map = {}
        for store in stores.order_by("store_num"):
            store_map[str(store.id)] = {
                "store_num": store.store_num,
                "riso_num": store.riso_num,
                "store_name": store.store_name,
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
        store_ids = list(stores.values_list("id", flat=True))
        generated = []

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

            generated.append(
                {
                    "store_id": mapping.store_id,
                    "store_num": mapping.store.store_num,
                    "tank_index": mapping.tank_index,
                    "fuel_type": mapping.fuel_type,
                    "tank_type_id": (
                        mapping.tank_type_id if mapping.tank_type else None
                    ),
                    "tank_type_name": (
                        mapping.tank_type.name if mapping.tank_type else None
                    ),
                    "radius": radius,
                    "length": length,
                    "max_depth": max_depth,
                    "confidence": estimation.confidence,
                    "sample_count": estimation.sample_count,
                    "estimation_method": estimation.estimation_method,
                    "algorithm_version": estimation.algorithm_version,
                    "chart": chart,
                }
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

            generated.append(
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
                }
            )

        path = os.path.join(output_dir, "generated_tank_charts.json")
        self._write_json(path, generated, indent)
        self.stdout.write(
            self.style.SUCCESS(f"generated_tank_charts: {len(generated)} tanks")
        )

    def _write_json(self, path, data, indent):
        with open(path, "w") as f:
            json.dump(data, f, indent=indent, default=str)
