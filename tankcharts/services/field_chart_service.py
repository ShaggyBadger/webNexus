import math
from datetime import datetime

from atg.models import VeederReading
from tankgauge.models import StoreTankMapping, TankChart, TankEstimation

from tankcharts.domain import TankFieldChart


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

        estimated_curve = self._generate_estimated_curve(
            estimation=estimation,
            max_depth_inches=max_depth_inches,
        )

        if not official_curve and not estimated_curve:
            raise ValueError(
                "Cannot generate chart: no official chart rows and no active estimation."
            )

        table_rows = self._build_lookup_table(
            official_curve=official_curve,
            estimated_curve=estimated_curve,
            max_depth_inches=max_depth_inches,
        )

        coverage_percent = self._compute_coverage(
            veeder_points=veeder_points,
            max_depth_inches=max_depth_inches,
        )
        confidence = self._compute_confidence(
            has_official_chart=bool(official_curve),
            coverage_percent=coverage_percent,
            veeder_count=len(veeder_points),
            table_rows=table_rows,
            capacity_gallons=mapping.tank_type.capacity if mapping.tank_type else None,
        )

        curves = []
        if official_curve:
            curves.append(
                {
                    "label": "Official Chart",
                    "color": "#3b82f6",
                    "points": official_curve,
                }
            )
        if estimated_curve:
            curves.append(
                {
                    "label": "Estimated Curve",
                    "color": "#f97316",
                    "points": estimated_curve,
                }
            )

        return TankFieldChart(
            store_num=mapping.store.store_num,
            store_name=mapping.store.store_name or "",
            address=mapping.store.address or "",
            city=mapping.store.city or "",
            state=mapping.store.state or "",
            tank_index=mapping.tank_index or tank_index,
            fuel_type=(mapping.fuel_type or "unknown").lower(),
            tank_type_name=mapping.tank_type.name if mapping.tank_type else "Unknown",
            capacity_gallons=(
                int(mapping.tank_type.capacity)
                if mapping.tank_type and mapping.tank_type.capacity
                else int(round(table_rows[-1]["official_gallons"] or 0))
            ),
            max_depth_inches=max_depth_inches,
            table_rows=table_rows,
            has_official_chart=bool(official_curve),
            official_chart_source=collected["official_chart_source"],
            coverage_percent=coverage_percent,
            veeder_observation_count=len(veeder_points),
            confidence_level=confidence["confidence_level"],
            avg_difference_gallons=confidence["avg_difference_gallons"],
            max_difference_gallons=confidence["max_difference_gallons"],
            curves=curves,
            veeder_points=veeder_points,
            official_row_count=len(official_curve),
            estimation_id=estimation.id if estimation else None,
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

        radius_inches = float(estimation.radius)
        length_inches = float(estimation.length)
        points: list[dict] = []

        for inches in range(1, max_depth_inches + 1):
            fluid_height_inches = min(float(inches), 2 * radius_inches)
            gallons = self._horizontal_cylinder_volume_gallons(
                radius_inches=radius_inches,
                length_inches=length_inches,
                fluid_height_inches=fluid_height_inches,
            )
            points.append({"inches": inches, "gallons": round(gallons, 1)})

        return points

    def _horizontal_cylinder_volume_gallons(
        self,
        *,
        radius_inches: float,
        length_inches: float,
        fluid_height_inches: float,
    ) -> float:
        if fluid_height_inches <= 0:
            return 0.0

        full_volume_gallons = (math.pi * (radius_inches**2) * length_inches) / 231.0
        if fluid_height_inches >= 2 * radius_inches:
            return full_volume_gallons

        segment_theta_radians = 2 * math.acos(
            max(
                -1.0,
                min(1.0, (radius_inches - fluid_height_inches) / radius_inches),
            )
        )
        sector_area_square_inches = (radius_inches**2 * segment_theta_radians) / 2.0
        triangle_area_square_inches = (
            0.5 * (radius_inches**2) * math.sin(segment_theta_radians)
        )
        segment_area_square_inches = (
            sector_area_square_inches - triangle_area_square_inches
        )

        return (segment_area_square_inches * length_inches) / 231.0

    def _build_lookup_table(
        self,
        *,
        official_curve: list[dict],
        estimated_curve: list[dict],
        max_depth_inches: int,
    ) -> list[dict]:
        official_by_inches = {
            row["inches"]: float(row["gallons"]) for row in official_curve
        }
        estimated_by_inches = {
            row["inches"]: float(row["gallons"]) for row in estimated_curve
        }

        rows = []
        for inches in range(1, max_depth_inches + 1):
            official_gallons = official_by_inches.get(inches)
            estimated_gallons = estimated_by_inches.get(inches)

            difference = None
            if official_gallons is not None and estimated_gallons is not None:
                difference = round(estimated_gallons - official_gallons, 1)

            rows.append(
                {
                    "inches": inches,
                    "official_gallons": official_gallons,
                    "estimated_gallons": estimated_gallons,
                    "difference": difference,
                }
            )

        return rows

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

    def _compute_confidence(
        self,
        *,
        has_official_chart: bool,
        coverage_percent: float,
        veeder_count: int,
        table_rows: list[dict],
        capacity_gallons: int | None,
    ) -> dict:
        comparable_differences = [
            abs(row["difference"])
            for row in table_rows
            if row["difference"] is not None
        ]
        avg_difference_gallons = (
            round(sum(comparable_differences) / len(comparable_differences), 1)
            if comparable_differences
            else 0.0
        )
        max_difference_gallons = (
            round(max(comparable_differences), 1) if comparable_differences else 0.0
        )

        maturity_max_difference = 0.0
        if capacity_gallons:
            maturity_max_difference = capacity_gallons * 0.02

        if (
            coverage_percent >= 90
            and has_official_chart
            and (
                maturity_max_difference <= 0
                or max_difference_gallons <= maturity_max_difference
            )
        ):
            confidence_level = "MATURE"
        elif coverage_percent >= 75 and veeder_count >= 5:
            confidence_level = "HIGH"
        elif coverage_percent >= 50 and veeder_count >= 3:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        if not has_official_chart and confidence_level in {"HIGH", "MATURE"}:
            confidence_level = "MEDIUM"

        return {
            "confidence_level": confidence_level,
            "avg_difference_gallons": avg_difference_gallons,
            "max_difference_gallons": max_difference_gallons,
        }
