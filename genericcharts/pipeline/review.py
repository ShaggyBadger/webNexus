"""Pure review graph data assembled from grouped tank curves."""

from __future__ import annotations

from dataclasses import dataclass

from .grouping import Bucket


@dataclass(frozen=True)
class ReviewGraphLayer:
    """One toggleable line layer for a review graph."""

    key: str
    label: str
    points: tuple[dict[str, float | int], ...]
    visible_by_default: bool


@dataclass(frozen=True)
class ReviewGraph:
    """All graph data needed to render one catalog bucket review."""

    bucket_name: str
    depth_inches: int
    nominal_volume_gallons: int
    tank_count: int
    layers: tuple[ReviewGraphLayer, ...]
    outliers: tuple[dict[str, float | int | bool], ...]

    def as_dict(self) -> dict:
        """Return a JSON-compatible payload for the admin review page."""

        return {
            "bucket_name": self.bucket_name,
            "depth_inches": self.depth_inches,
            "nominal_volume_gallons": self.nominal_volume_gallons,
            "tank_count": self.tank_count,
            "layers": [
                {
                    "key": layer.key,
                    "label": layer.label,
                    "points": list(layer.points),
                    "visible_by_default": layer.visible_by_default,
                }
                for layer in self.layers
            ],
            "outliers": list(self.outliers),
        }

    @property
    def svg_layers(self) -> tuple[dict[str, str | bool], ...]:
        """Return simple SVG polylines for the admin review page."""

        values = (
            value
            for layer in self.layers
            for point in layer.points
            for value in (
                point.get("gallons"),
                point.get("max"),
                point.get("upper"),
            )
            if value is not None
        )
        max_gallons = max(1, max(values, default=1))
        layers = []
        for layer in self.layers:
            points = []
            for point in layer.points:
                value = point.get("gallons") or point.get("max") or point.get("upper")
                if value is None:
                    continue
                x = float(point["inches"]) / self.depth_inches * 760
                y = 220 - (float(value) / max_gallons * 190)
                points.append(f"{x:.1f},{y:.1f}")
            layers.append(
                {
                    "key": layer.key,
                    "label": layer.label,
                    "points": " ".join(points),
                    "visible_by_default": layer.visible_by_default,
                }
            )
        return tuple(layers)


def build_review_graphs(
    catalog: dict[str, Bucket], outlier_multiplier: float = 2.0
) -> tuple[ReviewGraph, ...]:
    """Build toggleable original, envelope, statistics, and analytic layers."""

    if outlier_multiplier <= 0:
        raise ValueError("outlier_multiplier must be positive")

    graphs = []
    for name, bucket in sorted(catalog.items()):
        stats = bucket.per_inch_stats()
        layers = [
            ReviewGraphLayer(
                key="original",
                label="Original curves",
                points=tuple(
                    {
                        "inches": point.depth_inches,
                        "gallons": point.volume_gallons,
                    }
                    for tank in bucket.tanks
                    for point in tank.curve
                ),
                visible_by_default=True,
            ),
            ReviewGraphLayer(
                key="envelope",
                label="Min/max envelope",
                points=tuple(
                    {
                        "inches": inch,
                        "min": minimum,
                        "max": maximum,
                    }
                    for inch, minimum, maximum in zip(
                        stats["inches"], stats["min"], stats["max"]
                    )
                ),
                visible_by_default=True,
            ),
            ReviewGraphLayer(
                key="standard_deviation",
                label="Standard-deviation band",
                points=tuple(
                    {
                        "inches": inch,
                        "mean": mean,
                        "lower": mean - standard_deviation,
                        "upper": mean + standard_deviation,
                    }
                    for inch, mean, standard_deviation in zip(
                        stats["inches"], stats["mean"], stats["std"]
                    )
                ),
                visible_by_default=False,
            ),
            ReviewGraphLayer(
                key="median",
                label="Median",
                points=tuple(
                    {"inches": inch, "gallons": median}
                    for inch, median in zip(stats["inches"], stats["median"])
                ),
                visible_by_default=False,
            ),
            ReviewGraphLayer(
                key="analytic",
                label="Analytic curve",
                points=tuple(bucket.analytic_curve()),
                visible_by_default=True,
            ),
        ]
        outliers = tuple(
            {
                "store_id": tank.store_id,
                "tank_index": tank.tank_index or 0,
                "error": error,
                "is_outlier": is_outlier,
            }
            for tank, error, is_outlier in bucket.outlier_flags(outlier_multiplier)
        )
        graphs.append(
            ReviewGraph(
                bucket_name=name,
                depth_inches=bucket.depth_inches,
                nominal_volume_gallons=bucket.nominal_volume_gallons,
                tank_count=len(bucket.tanks),
                layers=tuple(layers),
                outliers=outliers,
            )
        )
    return tuple(graphs)
