from types import SimpleNamespace

from django.test import SimpleTestCase

from genericcharts.pdf import CoreStarterPackPDFRenderer
from genericcharts.pdf.renderer import (
    _Chart,
    _compact_label,
    _display_tank_label,
    _store_identifier,
    _store_type_markup,
)
from genericcharts.pipeline.catalog import build_new_catalog
from genericcharts.pipeline.coverage import build_store_tank_map
from genericcharts.pipeline.dataclasses import (
    CurvePoint,
    GeneratedTank,
    SelectedStore,
    SelectedTank,
    SelectionSpec,
)
from genericcharts.pipeline.package import PackageData
from genericcharts.pipeline.review import build_review_graphs


def make_tank():
    return GeneratedTank(
        store_id=1,
        store_number=101,
        tank_index=1,
        fuel_type="Regular",
        tank_type_id=None,
        tank_type_name="",
        radius_inches=48,
        length_inches=100,
        max_depth_inches=96,
        confidence=0.9,
        sample_count=10,
        source="mapped_estimation",
        algorithm_version="test",
        curve=tuple(
            CurvePoint(depth_inches=depth, volume_gallons=depth * 100)
            for depth in range(1, 97)
        ),
    )


class CoreStarterPackPDFTests(SimpleTestCase):
    def test_store_identifier_includes_riso_when_present(self):
        store = SimpleNamespace(store_id=1, store_number=6947, riso_number=44643)

        self.assertEqual(_store_identifier(store), "6947/44643")

    def test_store_identifier_omits_matching_riso(self):
        store = SimpleNamespace(store_id=1, store_number=6947, riso_number=6947)

        self.assertEqual(_store_identifier(store), "6947")

    def test_long_store_type_wraps_at_word_boundary(self):
        self.assertEqual(_store_type_markup("Exxon Wholesale"), "Exxon<br/>Wholesale")
        self.assertEqual(_store_type_markup("Speedway"), "Speedway")

    def test_chart_headers_mark_legacy_charts(self):
        generated = _Chart("10k91", 91, 10_000, "generated_geometry", ((1, 1),))
        legacy = _Chart("10k91", 91, 10_000, "official_chart", ((1, 1),))

        self.assertEqual(_compact_label(generated), "10k")
        self.assertEqual(_compact_label(legacy), "10k-L")

    def test_map_labels_include_source_markers(self):
        self.assertEqual(
            _display_tank_label(
                name="8k96",
                count=1,
                source_markers=set(),
                no_chart=False,
            ),
            "8k96",
        )
        self.assertEqual(
            _display_tank_label(
                name="8k115a",
                count=2,
                source_markers=set(),
                no_chart=False,
            ),
            "8k115a(x2)",
        )
        self.assertEqual(
            _display_tank_label(
                name="8k96",
                count=1,
                source_markers={"L"},
                no_chart=False,
            ),
            "8k96-L",
        )
        self.assertEqual(
            _display_tank_label(
                name="12k",
                count=1,
                source_markers=set(),
                no_chart=True,
            ),
            "12k",
        )

    def test_renderer_returns_one_numbered_pdf(self):
        tank = make_tank()
        catalog, collisions = build_new_catalog((tank,))
        store_map, coverage = build_store_tank_map((tank,), catalog)
        package = PackageData(
            selection=SelectionSpec(state="NC"),
            stores=(
                SelectedStore(
                    store_id=1,
                    store_number=101,
                    riso_number=None,
                    store_name="Test Store",
                    state="NC",
                    store_type="Travel Center",
                    city="Raleigh",
                    tanks=(
                        SelectedTank(
                            mapping_id=1,
                            tank_index=1,
                            fuel_type="Regular",
                            tank_type_id=None,
                            tank_type_name="",
                            capacity_gallons=None,
                            max_depth_inches=None,
                        ),
                    ),
                ),
            ),
            generated_tanks=(tank,),
            catalog=catalog,
            collisions=collisions,
            official_charts={},
            official_aliases={},
            store_map=store_map,
            coverage_report=coverage,
            review_graphs=build_review_graphs(catalog),
            options={
                "volume_gap_percent": 3.0,
                "near_duplicate_tolerance_percent": 1.0,
                "outlier_multiplier": 2.0,
            },
        )

        pdf_bytes = CoreStarterPackPDFRenderer().render(package)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(pdf_bytes.count(b"/Type /Page"), 2)
