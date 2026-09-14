"""Pure grouping and review statistics for generated tank curves."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, median, pstdev

from tankgauge.logic.curve_generator import generate_inch_gallon_curve

from .dataclasses import GeneratedTank


@dataclass(frozen=True)
class Bucket:
    """One volume bucket within an exact maximum-depth group."""

    depth_inches: int
    tanks: tuple[GeneratedTank, ...]

    @property
    def nominal_volume_gallons(self) -> int:
        return round(median(_max_volume(tank) for tank in self.tanks))

    @property
    def median_radius_inches(self) -> float:
        return float(median(tank.radius_inches for tank in self.tanks))

    @property
    def mean_radius_inches(self) -> float:
        return fmean(tank.radius_inches for tank in self.tanks)

    @property
    def median_length_inches(self) -> float:
        return float(median(tank.length_inches for tank in self.tanks))

    @property
    def mean_length_inches(self) -> float:
        return fmean(tank.length_inches for tank in self.tanks)

    @property
    def label(self) -> str:
        return (
            f"{self.depth_inches}in / {self.nominal_volume_gallons:,}gal "
            f"({len(self.tanks)})"
        )

    def analytic_curve(self) -> tuple[dict[str, float | int], ...]:
        """Build the representative curve from median bucket geometry."""

        points = generate_inch_gallon_curve(
            self.median_radius_inches,
            self.median_length_inches,
            self.depth_inches,
        )
        return tuple(
            {"inches": int(point["inches"]), "gallons": float(point["gallons"])}
            for point in points
        )

    def per_inch_stats(self) -> dict[str, list[float | int]]:
        """Return distribution statistics for every depth in the bucket."""

        values_by_depth = {depth: [] for depth in range(1, self.depth_inches + 1)}
        for tank in self.tanks:
            for point in tank.curve:
                values_by_depth[point.depth_inches].append(point.volume_gallons)

        stats = {
            key: []
            for key in ("inches", "mean", "median", "std", "min", "max", "count")
        }
        for depth in range(1, self.depth_inches + 1):
            values = values_by_depth[depth]
            stats["inches"].append(depth)
            stats["mean"].append(float(fmean(values)))
            stats["median"].append(float(median(values)))
            stats["std"].append(float(pstdev(values)))
            stats["min"].append(float(min(values)))
            stats["max"].append(float(max(values)))
            stats["count"].append(len(values))
        return stats

    def tank_errors(self) -> tuple[tuple[GeneratedTank, float], ...]:
        """Return each tank's RMS error from the representative curve."""

        reference = {
            point["inches"]: point["gallons"] for point in self.analytic_curve()
        }
        errors = []
        for tank in self.tanks:
            squared = [
                (point.volume_gallons - reference[point.depth_inches]) ** 2
                for point in tank.curve
            ]
            errors.append((tank, math.sqrt(fmean(squared))))
        return tuple(errors)

    def outlier_flags(self, multiplier: float = 2.0):
        """Flag review outliers without excluding them from the bucket."""

        errors = self.tank_errors()
        median_error = median(error for _, error in errors) if errors else 0.0
        return tuple(
            (tank, error, bool(median_error and error > multiplier * median_error))
            for tank, error in errors
        )

    def widest_spread(self) -> dict[str, float | int]:
        """Return the depth with the widest observed min/max envelope."""

        stats = self.per_inch_stats()
        index = max(
            range(len(stats["inches"])),
            key=lambda position: stats["max"][position] - stats["min"][position],
        )
        analytic = self.analytic_curve()[index]["gallons"]
        return {
            "inch": stats["inches"][index],
            "width": stats["max"][index] - stats["min"][index],
            "min": stats["min"][index],
            "max": stats["max"][index],
            "mean": stats["mean"][index],
            "median": stats["median"][index],
            "std": stats["std"][index],
            "analytic": analytic,
        }

    def generic_payload(self) -> dict:
        """Return the geometry-only payload used by catalog and PDF stages."""

        return {
            "max_depth": self.depth_inches,
            "radius": round(self.median_radius_inches, 2),
            "length": round(self.median_length_inches, 2),
            "sample_count": len(self.tanks),
            "chart": list(self.analytic_curve()),
        }


def group_by_depth(tanks: tuple[GeneratedTank, ...] | list[GeneratedTank]):
    """Group generated tanks by exact maximum depth."""

    groups: dict[int, list[GeneratedTank]] = {}
    for tank in tanks:
        groups.setdefault(tank.max_depth_inches, []).append(tank)
    return groups


def cluster_volumes(tanks, gap_fraction: float = 0.03):
    """Cluster tanks when consecutive capacities exceed a relative gap."""

    if gap_fraction < 0:
        raise ValueError("gap_fraction must be non-negative")
    ordered = sorted(tanks, key=_max_volume)
    buckets: list[list[GeneratedTank]] = []
    current: list[GeneratedTank] = []
    previous_volume = None
    for tank in ordered:
        volume = _max_volume(tank)
        if current and previous_volume is not None:
            if previous_volume <= 0:
                raise ValueError("tank capacity must be positive")
            if (volume - previous_volume) / previous_volume > gap_fraction:
                buckets.append(current)
                current = []
        current.append(tank)
        previous_volume = volume
    if current:
        buckets.append(current)
    return tuple(tuple(bucket) for bucket in buckets)


def build_groups(tanks, gap_fraction: float = 0.03):
    """Build sorted depth groups containing volume buckets."""

    return {
        depth: tuple(
            Bucket(depth, tuple(cluster))
            for cluster in cluster_volumes(depth_tanks, gap_fraction)
        )
        for depth, depth_tanks in sorted(group_by_depth(tanks).items())
    }


def _max_volume(tank: GeneratedTank) -> float:
    return float(tank.curve[-1].volume_gallons)
