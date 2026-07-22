from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import Colors, PageLayout


class SiteConfigurationRenderer:
    """Render Page 2 site and tank configuration summary details."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        section_title = Paragraph("[ SITE_CONFIGURATION ]", self.styles["heading"])

        city_state_zip = self._format_city_state_zip(chart)
        coordinates = self._format_coordinates(chart)
        max_depth_label = f"{chart.max_depth_inches} in"
        ninety_percent_gallons = int(round(chart.capacity_gallons * 0.9))

        rows = [
            [
                "// GEOSPATIAL_DATA",
                "",
                "// STORE_IDENTIFIERS",
                "",
            ],
            ["Address", chart.address or "Unknown", "Store #", str(chart.store_num)],
            [
                "City/State/ZIP",
                city_state_zip,
                "RISO",
                str(chart.riso_num or "Unknown"),
            ],
            [
                "Type",
                chart.store_type or "Unknown",
                "Brand",
                chart.store_name or "Unknown",
            ],
            ["Coordinates", coordinates, "Tank Index", str(chart.tank_index)],
            ["", "", "Fuel Type", chart.fuel_type.upper()],
            [
                "// TANK_CONFIGURATION",
                "",
                "// DATA_COVERAGE",
                "",
            ],
            [
                "Max Depth (Diameter)",
                max_depth_label,
                "Veeder Readings",
                str(chart.veeder_observation_count),
            ],
            [
                "Tank Length",
                self._format_inches(chart.estimation_length_inches),
                "Coverage",
                f"{chart.coverage_percent:.1f}%",
            ],
            [
                "Tank Radius",
                self._format_inches(chart.estimation_radius_inches),
                "Official Rows",
                str(chart.official_row_count),
            ],
            [
                "Max Gallons",
                f"{chart.capacity_gallons:,} gal",
                "Curve Source",
                self._curve_source_label(chart),
            ],
            [
                "90% Max Gallons",
                f"{ninety_percent_gallons:,} gal",
                "Official Chart",
                "YES" if chart.has_official_chart else "NO",
            ],
        ]

        table = Table(
            rows,
            colWidths=[95, 175, 95, PageLayout.CONTENT_WIDTH - 365],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, Colors.BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, Colors.BORDER),
                    ("TEXTCOLOR", (0, 0), (-1, -1), Colors.TEXT_PRIMARY),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("BACKGROUND", (0, 0), (-1, 0), Colors.HEADER_BG),
                    ("BACKGROUND", (0, 6), (-1, 6), Colors.HEADER_BG),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
                    ("SPAN", (0, 0), (1, 0)),
                    ("SPAN", (2, 0), (3, 0)),
                    ("SPAN", (0, 6), (1, 6)),
                    ("SPAN", (2, 6), (3, 6)),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, 5), [colors.white, Colors.ROW_ALT]),
                    (
                        "ROWBACKGROUNDS",
                        (0, 7),
                        (-1, -1),
                        [colors.white, Colors.ROW_ALT],
                    ),
                ]
            )
        )

        return [section_title, table]

    def _format_city_state_zip(self, chart: TankFieldChart) -> str:
        parts = [part for part in [chart.city, chart.state, chart.zip_code] if part]
        return ", ".join(parts) if parts else "Unknown"

    def _format_coordinates(self, chart: TankFieldChart) -> str:
        if chart.latitude is None or chart.longitude is None:
            return "Unknown"
        return f"{chart.latitude:.6f}, {chart.longitude:.6f}"

    def _curve_source_label(self, chart: TankFieldChart) -> str:
        if any(curve["label"] == "Generated Curve (Math)" for curve in chart.curves):
            return "GENERATED"
        return "OFFICIAL"

    def _format_inches(self, value: float | None) -> str:
        if value is None:
            return "Unknown"
        return f"{value:.1f} in"
