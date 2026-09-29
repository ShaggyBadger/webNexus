import re
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

from genericcharts.pdf import CoreStarterPackPDFRenderer
from genericcharts.pdf.renderer import (
    _Chart,
    _NumberedCanvas,
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


def make_package(*, store_count=1, with_chart=True):
    generated_tanks = (make_tank(),) if with_chart else ()
    catalog, collisions = build_new_catalog(generated_tanks)
    store_map, coverage = build_store_tank_map(generated_tanks, catalog)
    stores = tuple(
        SelectedStore(
            store_id=store_id,
            store_number=100 + store_id,
            riso_number=None,
            store_name=f"Test Store {store_id}",
            state="NC",
            store_type="Travel Center",
            city="Raleigh",
            tanks=(
                (
                    SelectedTank(
                        mapping_id=store_id,
                        tank_index=1,
                        fuel_type="Regular",
                        tank_type_id=None,
                        tank_type_name="",
                        capacity_gallons=None,
                        max_depth_inches=None,
                    ),
                )
                if with_chart and store_id == 1
                else ()
            ),
        )
        for store_id in range(1, store_count + 1)
    )
    return PackageData(
        selection=SelectionSpec(state="NC"),
        stores=stores,
        generated_tanks=generated_tanks,
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


class CoreStarterPackPDFTests(SimpleTestCase):
    def test_map_sort_normalizes_state_aliases_before_city(self):
        package = SimpleNamespace(
            stores=(
                SimpleNamespace(
                    state="North Carolina", city="Charlotte", store_number=2
                ),
                SimpleNamespace(state="NC", city="Raleigh", store_number=1),
                SimpleNamespace(state="NC", city="Charlotte", store_number=3),
                SimpleNamespace(
                    state="South Carolina", city="Anderson", store_number=4
                ),
            )
        )

        ordered = CoreStarterPackPDFRenderer._sorted_stores(package, "FULL")

        self.assertEqual(
            [(store.state, store.city) for store in ordered],
            [
                ("North Carolina", "Charlotte"),
                ("NC", "Charlotte"),
                ("NC", "Raleigh"),
                ("South Carolina", "Anderson"),
            ],
        )

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
        package = make_package()
        renderer = CoreStarterPackPDFRenderer()
        footer_texts = []
        generated_at = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        draw_centred_string = _NumberedCanvas.drawCentredString

        def capture_footer(canvas, x, y, text):
            if " | Generated " in text:
                footer_texts.append(text)
            draw_centred_string(canvas, x, y, text)

        with (
            patch("genericcharts.pdf.renderer.datetime") as datetime_class,
            patch.object(_NumberedCanvas, "drawCentredString", capture_footer),
            patch.object(
                renderer,
                "_duplex_blank_page",
                wraps=renderer._duplex_blank_page,
            ) as blank_page,
        ):
            datetime_class.now.return_value = generated_at
            pdf_bytes = renderer.render(package)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        page_count = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
        self.assertEqual(page_count, 5)
        self.assertEqual(len(footer_texts), page_count)
        self.assertTrue(
            all("Generated 2026-09-29" in footer for footer in footer_texts)
        )
        self.assertEqual(
            [call.args[1] for call in blank_page.call_args_list],
            ["STORE-TANK MAP", "GENERIC TANK CHARTS"],
        )

    def test_odd_chart_section_is_padded_when_map_is_even(self):
        package = make_package(store_count=60)
        renderer = CoreStarterPackPDFRenderer()
        styles = renderer._styles()
        map_story = renderer._store_map(package, styles, "NC")
        page_count = renderer._store_map_page_count(
            map_story, letter[0] - inch, letter[1] - 0.9 * inch
        )
        self.assertEqual(page_count, 2)

        with patch.object(
            renderer,
            "_duplex_blank_page",
            wraps=renderer._duplex_blank_page,
        ) as blank_page:
            pdf_bytes = renderer.render(package)

        self.assertEqual(
            [call.args[1] for call in blank_page.call_args_list],
            ["GENERIC TANK CHARTS"],
        )
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf_bytes)), 5)

    def test_chart_page_count_combines_depth_groups_before_padding(self):
        package = make_package(with_chart=False)

        def make_bucket(depth):
            return SimpleNamespace(
                depth_inches=depth,
                analytic_curve=lambda: (
                    {"inches": 1, "gallons": 100},
                    {"inches": depth, "gallons": 10_000},
                ),
                median_radius_inches=48,
                median_length_inches=100,
                tanks=(),
            )

        package = replace(
            package,
            catalog={"depth-96": make_bucket(96), "depth-98": make_bucket(98)},
        )
        renderer = CoreStarterPackPDFRenderer()
        self.assertEqual(renderer._generic_chart_page_count(package), 2)

        with patch.object(
            renderer,
            "_duplex_blank_page",
            wraps=renderer._duplex_blank_page,
        ) as blank_page:
            pdf_bytes = renderer.render(package)

        self.assertEqual(
            [call.args[1] for call in blank_page.call_args_list],
            ["STORE-TANK MAP"],
        )
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf_bytes)), 5)

    def test_odd_map_gets_blank_even_when_no_generic_charts_are_selected(self):
        package = make_package(with_chart=False)
        renderer = CoreStarterPackPDFRenderer()
        styles = renderer._styles()
        map_story = renderer._store_map(package, styles, "NC")
        self.assertEqual(
            renderer._store_map_page_count(
                map_story, letter[0] - inch, letter[1] - 0.9 * inch
            ),
            1,
        )
        self.assertEqual(
            renderer._duplex_blank_page(styles, "STORE-TANK MAP")[1].getPlainText(),
            "STORE-TANK MAP SECTION",
        )

        with patch.object(
            renderer,
            "_duplex_blank_page",
            wraps=renderer._duplex_blank_page,
        ) as blank_page:
            pdf_bytes = renderer.render(package)

        blank_page.assert_called_once()
        self.assertEqual(blank_page.call_args.args[1], "STORE-TANK MAP")
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf_bytes)), 4)
