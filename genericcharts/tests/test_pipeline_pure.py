from django.test import SimpleTestCase

from genericcharts.pipeline.catalog import build_new_catalog, bucket_name
from genericcharts.pipeline.coverage import build_store_tank_map
from genericcharts.pipeline.dataclasses import CurvePoint, GeneratedTank
from genericcharts.pipeline.grouping import build_groups, cluster_volumes
from genericcharts.pipeline.review import build_review_graphs


def make_tank(*, store_id=1, tank_index=1, capacity=10000, length=100):
    return GeneratedTank(
        store_id=store_id,
        store_number=store_id,
        tank_index=tank_index,
        fuel_type="Regular",
        tank_type_id=None,
        tank_type_name="",
        radius_inches=48,
        length_inches=length,
        max_depth_inches=96,
        confidence=0.9,
        sample_count=10,
        source="mapped_estimation",
        algorithm_version="test",
        curve=tuple(
            CurvePoint(depth_inches=depth, volume_gallons=capacity * depth / 96)
            for depth in range(1, 97)
        ),
    )


class PurePipelineTests(SimpleTestCase):
    def test_volume_clustering_uses_strict_relative_gap(self):
        tanks = [
            make_tank(capacity=10000),
            make_tank(store_id=2, capacity=10200),
            make_tank(store_id=3, capacity=11000),
        ]

        buckets = cluster_volumes(tanks, gap_fraction=0.03)

        self.assertEqual(
            [[tank.store_id for tank in bucket] for bucket in buckets], [[1, 2], [3]]
        )

    def test_grouping_keeps_depths_exact_and_builds_bucket_statistics(self):
        tanks = [make_tank(), make_tank(store_id=2, capacity=10200)]

        groups = build_groups(tanks)
        bucket = groups[96][0]

        self.assertEqual(bucket.label, "96in / 10,100gal (2)")
        self.assertEqual(bucket.generic_payload()["sample_count"], 2)
        self.assertEqual(len(bucket.per_inch_stats()["inches"]), 96)

    def test_catalog_and_coverage_preserve_generated_tank_identity(self):
        tank = make_tank()
        catalog, collisions = build_new_catalog((tank,))

        self.assertFalse(collisions)
        self.assertEqual(bucket_name(next(iter(catalog.values()))), "10k96")
        store_map, report = build_store_tank_map((tank,), catalog)

        self.assertEqual(store_map[1][1].display_name, "10k96")
        self.assertEqual(report["tier_counts"], {1: 1, 2: 0, 3: 0, 4: 0})

    def test_coverage_retains_unmatched_legacy_inventory(self):
        store_map, report = build_store_tank_map(
            (),
            {},
            legacy_assignments={
                (9, 3): {"tank_type_name": None, "fuel_type": "Diesel"}
            },
        )

        entry = store_map[9][3]
        self.assertEqual(entry.source, "no_chart")
        self.assertEqual(entry.display_name, "NO CHART:UNKNOWN TANK TYPE")
        self.assertEqual(report["review_counts"]["missing_legacy_name"], 1)

    def test_coverage_orders_unindexed_tanks_without_comparing_none(self):
        store_map, report = build_store_tank_map(
            (),
            {},
            legacy_assignments={
                (9, None): {"tank_type_name": None, "fuel_type": "Regular"},
                (9, 1): {"tank_type_name": None, "fuel_type": "Diesel"},
            },
        )

        self.assertEqual(list(store_map[9]), [1, None])
        self.assertEqual(report["review_counts"]["missing_legacy_name"], 2)

    def test_review_graph_contains_expected_toggleable_layers_and_outliers(self):
        tank = make_tank()
        catalog, _ = build_new_catalog((tank,))

        graph = build_review_graphs(catalog)[0]

        self.assertEqual(
            [layer.key for layer in graph.layers],
            ["original", "envelope", "standard_deviation", "median", "analytic"],
        )
        self.assertEqual(graph.layers[0].points[0]["inches"], 1)
        self.assertEqual(graph.layers[-1].points[-1]["inches"], 96)
        self.assertGreater(graph.layers[-1].points[-1]["gallons"], 0)
        self.assertEqual(len(graph.svg_layers), 5)
        self.assertTrue(graph.svg_layers[-1]["points"])
        self.assertFalse(graph.outliers[0]["is_outlier"])
        self.assertEqual(graph.as_dict()["bucket_name"], "10k96")


from django.test import SimpleTestCase
