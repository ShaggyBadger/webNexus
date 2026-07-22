from datetime import datetime

from atg.models import VeederReading
from tankgauge.logic.curve_generator import generate_inch_gallon_curve
from tankgauge.models import StoreTankMapping, TankChart, TankEstimation

from tankcharts.domain import StoreFieldChart, StoreTankSummary, TankFieldChart
from tankcharts.rendering.theme.colors import Colors


class TankFieldChartService:
    """Builds field chart data for a specific store tank."""

    def build(self, store_num: int, tank_index: int) -> TankFieldChart:
        """Build a complete field chart payload for rendering."""
        collected = self._collect_data(store_num=store_num, tank_index=tank_index)
        mapping = collected["mapping"]
        official_curve = collected["official_curve"]
        veeder_points = collected["veeder_points"]
        estimation = collected["estimation"]
        max_depth_inches = collected["max_depth_inches"]

        generated_curve = self._generate_estimated_curve(
            estimation=estimation,
            max_depth_inches=max_depth_inches,
        )

        if not official_curve and not generated_curve:
            raise ValueError(
                "Cannot generate chart: no official chart rows and no active estimation."
            )

        table_rows = self._build_lookup_table(
            official_curve=official_curve,
            generated_curve=generated_curve,
        )

        coverage_percent = self._compute_coverage(
            veeder_points=veeder_points,
            max_depth_inches=max_depth_inches,
        )
        curves = []
        if official_curve:
            curves.append(
                {
                    "label": "Official Tank Chart",
                    "color": "#a0aec0",
                    "points": official_curve,
                }
            )
        if generated_curve:
            curves.append(
                {
                    "label": "Generated Curve (Math)",
                    "color": "#d4943a",
                    "points": generated_curve,
                }
            )

        fallback_capacity = int(round(table_rows[-1]["gallons"])) if table_rows else 0

        return TankFieldChart(
            store_num=mapping.store.store_num,
            riso_num=mapping.store.riso_num,
            store_name=mapping.store.store_name or "",
            store_type=mapping.store.store_type or "",
            address=mapping.store.address or "",
            city=mapping.store.city or "",
            state=mapping.store.state or "",
            zip_code=mapping.store.zip_code or "",
            latitude=mapping.store.lat,
            longitude=mapping.store.lon,
            tank_index=mapping.tank_index or tank_index,
            fuel_type=(mapping.fuel_type or "unknown").lower(),
            tank_type_name=mapping.tank_type.name if mapping.tank_type else "Unknown",
            capacity_gallons=(
                int(mapping.tank_type.capacity)
                if mapping.tank_type and mapping.tank_type.capacity
                else fallback_capacity
            ),
            max_depth_inches=max_depth_inches,
            table_rows=table_rows,
            has_official_chart=bool(official_curve),
            official_chart_source=collected["official_chart_source"],
            coverage_percent=coverage_percent,
            veeder_observation_count=len(veeder_points),
            curves=curves,
            veeder_points=veeder_points,
            official_row_count=len(official_curve),
            estimation_id=estimation.id if estimation else None,
            estimation_radius_inches=(
                float(estimation.radius)
                if estimation and estimation.radius is not None
                else None
            ),
            estimation_length_inches=(
                float(estimation.length)
                if estimation and estimation.length is not None
                else None
            ),
            generated_at=datetime.utcnow(),
        )

    def build_store(self, store_num: int) -> StoreFieldChart:
        """Build a store-wide chart payload with all store tank mappings."""
        mappings = list(
            StoreTankMapping.objects.select_related("store", "tank_type")
            .filter(store__store_num=store_num)
            .order_by("tank_index", "id")
        )
        if not mappings:
            raise StoreTankMapping.DoesNotExist(
                f"Store {store_num} has no mapped tanks for store-wide chart generation."
            )

        store = mappings[0].store
        tank_payloads: list[dict] = []
        curves: list[dict] = []
        summaries: list[StoreTankSummary] = []
        total_veeder_observation_count = 0

        for mapping in mappings:
            official_curve = self._get_official_curve(mapping=mapping)
            veeder_points = self._get_veeder_points(mapping=mapping)
            estimation = (
                TankEstimation.objects.filter(tank_mapping=mapping, is_active=True)
                .order_by("-created_at")
                .first()
            )
            max_depth_inches = self._resolve_max_depth(
                mapping=mapping,
                official_curve=official_curve,
                estimation=estimation,
            )
            generated_curve = self._generate_estimated_curve(
                estimation=estimation,
                max_depth_inches=max_depth_inches,
            )
            table_rows = self._build_lookup_table(
                official_curve=official_curve,
                generated_curve=generated_curve,
            )
            if not table_rows:
                continue

            fuel_label = (mapping.fuel_type or "UNK").upper()[:3]
            tank_label = f'{fuel_label} T{mapping.tank_index} ({max_depth_inches}")'
            tank_color = self._color_for_tank_index(mapping.tank_index)

            if official_curve:
                curves.append(
                    {
                        "label": f"{tank_label} - Official Tank Chart",
                        "color": "#a0aec0",
                        "points": official_curve,
                    }
                )
            if generated_curve:
                curves.append(
                    {
                        "label": f"{tank_label} - Generated Curve (Math)",
                        "color": tank_color,
                        "points": generated_curve,
                    }
                )

            tank_payloads.append(
                {
                    "tank_index": mapping.tank_index,
                    "header_label": tank_label,
                    "max_depth_inches": max_depth_inches,
                    "table_rows": table_rows,
                }
            )

            capacity_gallons = (
                int(mapping.tank_type.capacity)
                if mapping.tank_type and mapping.tank_type.capacity
                else int(round(table_rows[-1]["gallons"]))
            )
            veeder_count = len(veeder_points)
            total_veeder_observation_count += veeder_count
            summaries.append(
                StoreTankSummary(
                    tank_index=mapping.tank_index,
                    fuel_type=(mapping.fuel_type or "unknown").lower(),
                    tank_type_name=(
                        mapping.tank_type.name if mapping.tank_type else "Unknown"
                    ),
                    capacity_gallons=capacity_gallons,
                    max_depth_inches=max_depth_inches,
                    has_official_chart=bool(official_curve),
                    veeder_observation_count=veeder_count,
                    official_row_count=len(official_curve),
                )
            )

        if not tank_payloads:
            raise ValueError(
                "Cannot generate store chart: no tanks have official rows or active estimations."
            )

        combined_table_rows = self._build_combined_table(tank_payloads=tank_payloads)
        max_depth_inches_global = max(
            payload["max_depth_inches"] for payload in tank_payloads
        )

        return StoreFieldChart(
            store_num=store.store_num,
            riso_num=store.riso_num,
            store_name=store.store_name or "",
            store_type=store.store_type or "",
            address=store.address or "",
            city=store.city or "",
            state=store.state or "",
            zip_code=store.zip_code or "",
            latitude=store.lat,
            longitude=store.lon,
            tanks=sorted(summaries, key=lambda summary: summary.tank_index),
            combined_table_rows=combined_table_rows,
            curves=curves,
            max_depth_inches_global=max_depth_inches_global,
            total_veeder_observation_count=total_veeder_observation_count,
            generated_at=datetime.utcnow(),
        )

    def _collect_data(self, *, store_num: int, tank_index: int) -> dict:
        mapping = (
            StoreTankMapping.objects.select_related("store", "tank_type")
            .filter(store__store_num=store_num, tank_index=tank_index)
            .first()
        )
        if not mapping:
            raise StoreTankMapping.DoesNotExist(
                f"Store {store_num} has no tank index {tank_index}."
            )

        official_curve = self._get_official_curve(mapping=mapping)
        veeder_points = self._get_veeder_points(mapping=mapping)
        estimation = (
            TankEstimation.objects.filter(tank_mapping=mapping, is_active=True)
            .order_by("-created_at")
            .first()
        )

        max_depth_inches = self._resolve_max_depth(
            mapping=mapping,
            official_curve=official_curve,
            estimation=estimation,
        )

        official_chart_source = None
        if official_curve and mapping.tank_type:
            has_store_specific = TankChart.objects.filter(
                store=mapping.store,
                tank_index=mapping.tank_index,
                is_official=True,
            ).exists()
            official_chart_source = (
                "store_specific_official"
                if has_store_specific
                else f"tank_type:{mapping.tank_type.name}"
            )

        return {
            "mapping": mapping,
            "official_curve": official_curve,
            "veeder_points": veeder_points,
            "estimation": estimation,
            "max_depth_inches": max_depth_inches,
            "official_chart_source": official_chart_source,
        }

    def _resolve_max_depth(
        self,
        *,
        mapping: StoreTankMapping,
        official_curve: list[dict],
        estimation: TankEstimation | None,
    ) -> int:
        if mapping.tank_type and mapping.tank_type.max_depth:
            return int(mapping.tank_type.max_depth)

        if official_curve:
            return int(max(point["inches"] for point in official_curve))

        if estimation:
            return max(1, int(round(2 * estimation.radius)))

        return 120

    def _get_official_curve(self, *, mapping: StoreTankMapping) -> list[dict]:
        store_curve = list(
            TankChart.objects.filter(
                store=mapping.store,
                tank_index=mapping.tank_index,
                is_official=True,
            )
            .order_by("inches")
            .values("inches", "gallons")
        )
        if store_curve:
            return store_curve

        if not mapping.tank_type:
            return []

        return list(
            TankChart.objects.filter(
                tank_type=mapping.tank_type,
                is_official=True,
            )
            .order_by("inches")
            .values("inches", "gallons")
        )

    def _get_veeder_points(self, *, mapping: StoreTankMapping) -> list[dict]:
        readings = VeederReading.objects.filter(
            ticket__store=mapping.store,
            tank_index=mapping.tank_index,
            height__isnull=False,
            volume__isnull=False,
        )
        if mapping.fuel_type:
            readings = readings.filter(fuel_type__name__iexact=mapping.fuel_type)

        points = []
        for reading in readings.order_by("ticket__uploaded_at", "id"):
            points.append(
                {
                    "inches": float(reading.height),
                    "gallons": float(reading.volume),
                }
            )
        return points

    def _generate_estimated_curve(
        self,
        *,
        estimation: TankEstimation | None,
        max_depth_inches: int,
    ) -> list[dict]:
        if not estimation:
            return []
        if not estimation.radius or not estimation.length:
            return []

        try:
            return generate_inch_gallon_curve(
                radius_inches=float(estimation.radius),
                length_inches=float(estimation.length),
                max_depth=max_depth_inches,
            )
        except ValueError:
            return []

    def _build_lookup_table(
        self,
        *,
        official_curve: list[dict],
        generated_curve: list[dict],
    ) -> list[dict]:
        if generated_curve:
            return generated_curve
        return official_curve

    def _build_combined_table(self, *, tank_payloads: list[dict]) -> list[dict]:
        """Merge per-tank inch curves into one row set keyed by tank index."""
        if not tank_payloads:
            return []

        max_depth_inches = max(payload["max_depth_inches"] for payload in tank_payloads)
        index_maps: dict[int, dict[int, float]] = {}

        for payload in tank_payloads:
            tank_index = payload["tank_index"]
            by_inches = {
                int(row["inches"]): float(row["gallons"])
                for row in payload["table_rows"]
            }
            index_maps[tank_index] = by_inches

        rows: list[dict] = []
        for inches in range(1, max_depth_inches + 1):
            row: dict[str, int | float | None] = {"inches": inches}
            for payload in tank_payloads:
                tank_index = payload["tank_index"]
                row[f"tank_{tank_index}_gallons"] = index_maps[tank_index].get(inches)
            rows.append(row)

        return rows

    def _color_for_tank_index(self, tank_index: int) -> str:
        palette = Colors.TANK_COLORS
        if not tank_index:
            return palette[0]
        return palette[(int(tank_index) - 1) % len(palette)]

    def chunk_store_tanks(
        self, chart: StoreFieldChart, page_size: int = 4
    ) -> list[list[int]]:
        """Return tank index groups for deterministic multi-page store table rendering."""
        ordered_indices = [tank.tank_index for tank in chart.tanks]
        return [
            ordered_indices[start : start + page_size]
            for start in range(0, len(ordered_indices), page_size)
        ]

    def _compute_coverage(
        self,
        *,
        veeder_points: list[dict],
        max_depth_inches: int,
        band_width_inches: int = 5,
    ) -> float:
        if not veeder_points or max_depth_inches <= 0:
            return 0.0

        covered_inches: set[int] = set()
        for point in veeder_points:
            center_inch = int(round(float(point["inches"])))
            start_inch = max(1, center_inch - band_width_inches)
            end_inch = min(max_depth_inches, center_inch + band_width_inches)
            covered_inches.update(range(start_inch, end_inch + 1))

        return round((len(covered_inches) / max_depth_inches) * 100.0, 1)
