"""Prototype-faithful single-document CoreStarterPack PDF renderer."""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from genericcharts.pipeline.package import PackageData
from genericcharts.version import PACKAGE_VERSION

MAX_CHARTS_PER_PAGE = 6
STORE_TYPE_SINGLE_LINE_LIMIT = len("SPEEDWAY")
CONTENT_WIDTH = letter[0] - inch
SEPARATOR_WIDTH = 0.06 * inch
INCHES_COLUMN_WIDTH = 0.55 * inch
CHART_COLUMN_WIDTH = (
    (CONTENT_WIDTH - SEPARATOR_WIDTH) / 2 - INCHES_COLUMN_WIDTH
) / MAX_CHARTS_PER_PAGE
TEXT = HexColor("#111111")
SECONDARY = HexColor("#4a5568")
BORDER = HexColor("#cbd5e0")
HEADER = HexColor("#e2e8f0")
ALTERNATE = HexColor("#e4ead8")
GENERATED_ACCENT = HexColor("#d4943a")
LEGACY_ACCENT = HexColor("#a94442")
TITLE_ACCENT = HexColor("#2b6cb0")
FUEL_COLUMNS = ("RUL", "PREM", "PLUS", "DSL", "KERO")
FUEL_NAMES = {
    "regular": "RUL",
    "premium": "PREM",
    "plus": "PLUS",
    "diesel": "DSL",
    "kerosene": "KERO",
    "def": "OTHER",
}


def _register_fonts() -> tuple[str, str]:
    font_dir = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tankcharts"
        / "assets"
        / "fonts"
    )
    regular = font_dir / "JetBrainsMono-Regular.ttf"
    bold = font_dir / "JetBrainsMono-Bold.ttf"
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("CoreStarterMono", str(regular)))
        pdfmetrics.registerFont(TTFont("CoreStarterMono-Bold", str(bold)))
        return "CoreStarterMono", "CoreStarterMono-Bold"
    return "Helvetica", "Helvetica-Bold"


BODY_FONT, BOLD_FONT = _register_fonts()


@dataclass(frozen=True)
class _Chart:
    name: str
    depth: int
    capacity: float
    source: str
    curve: tuple[tuple[int, float], ...]
    radius: float | None = None
    length: float | None = None
    samples: int | None = None


class _NumberedCanvas(canvas.Canvas):
    """Add final Page X/Y numbering after ReportLab has laid out all pages."""

    def __init__(self, *args, package_title: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.package_title = package_title
        self._page_states = []

    def showPage(self):
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._page_states)
        for state in self._page_states:
            self.__dict__.update(state)
            self.saveState()
            self.setFont(BODY_FONT, 7)
            self.setFillColor(SECONDARY)
            self.drawCentredString(
                self._pagesize[0] / 2,
                0.22 * inch,
                f"{self.package_title} | Generator {PACKAGE_VERSION} | "
                f"Page {self._pageNumber}/{total}",
            )
            self.restoreState()
            super().showPage()
        super().save()


class CoreStarterPackPDFRenderer:
    """Render the prototype's map, lookup charts, and datasheet in one PDF."""

    def render(self, package: PackageData) -> bytes:
        state_label = "FULL" if package.selection.is_full else package.selection.state
        package_title = f"CoreStarterPack [ {state_label} ] version {PACKAGE_VERSION}"
        document = BaseDocTemplate(
            io.BytesIO(),
            pagesize=letter,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.45 * inch,
            bottomMargin=0.45 * inch,
        )
        portrait = Frame(
            document.leftMargin,
            document.bottomMargin,
            document.width,
            document.height,
            id="portrait",
        )
        landscape_size = landscape(letter)
        landscape_frame = Frame(
            0.35 * inch,
            0.35 * inch,
            landscape_size[0] - 0.7 * inch,
            landscape_size[1] - 0.65 * inch,
            id="landscape",
        )
        document.addPageTemplates(
            [
                PageTemplate(id="portrait", frames=[portrait], pagesize=letter),
                PageTemplate(
                    id="landscape", frames=[landscape_frame], pagesize=landscape_size
                ),
            ]
        )
        styles = self._styles()
        story = self._store_map(package, styles, state_label)
        story.extend(self._generic_chart_pages(package, styles, state_label))
        if self._chart_page_count(package) % 2:
            story.extend(self._duplex_blank_page(styles))
        story.extend([NextPageTemplate("landscape"), PageBreak()])
        story.extend(self._datasheet(package, styles, state_label))
        buffer = document.filename
        document.build(
            story,
            canvasmaker=lambda *args, **kwargs: _NumberedCanvas(
                *args, package_title=package_title, **kwargs
            ),
        )
        return buffer.getvalue()

    @staticmethod
    def _styles():
        sample = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "CoreTitle",
                parent=sample["Normal"],
                fontName=BOLD_FONT,
                fontSize=17,
                leading=19,
                textColor=TITLE_ACCENT,
                alignment=TA_CENTER,
            ),
            "subtitle": ParagraphStyle(
                "CoreSubtitle",
                parent=sample["Normal"],
                fontName=BODY_FONT,
                fontSize=8,
                leading=10,
                textColor=SECONDARY,
                alignment=TA_CENTER,
            ),
            "heading": ParagraphStyle(
                "CoreHeading",
                parent=sample["Normal"],
                fontName=BOLD_FONT,
                fontSize=18,
                leading=20,
                textColor=TITLE_ACCENT,
                alignment=TA_LEFT,
            ),
            "blank_title": ParagraphStyle(
                "CoreBlankTitle",
                parent=sample["Normal"],
                fontName=BOLD_FONT,
                fontSize=16,
                leading=18,
                textColor=TEXT,
                alignment=TA_CENTER,
            ),
            "blank_body": ParagraphStyle(
                "CoreBlankBody",
                parent=sample["Normal"],
                fontName=BODY_FONT,
                fontSize=10,
                leading=12,
                textColor=TEXT,
                alignment=TA_CENTER,
            ),
            "map_heading": ParagraphStyle(
                "CoreMapHeading",
                parent=sample["Normal"],
                fontName=BOLD_FONT,
                fontSize=17,
                leading=19,
                textColor=TITLE_ACCENT,
                alignment=TA_CENTER,
            ),
            "table_header": ParagraphStyle(
                "CoreTableHeader",
                parent=sample["Normal"],
                fontName=BOLD_FONT,
                fontSize=9,
                leading=9,
                textColor=TEXT,
                alignment=TA_CENTER,
            ),
            "cell": ParagraphStyle(
                "CoreCell",
                parent=sample["Normal"],
                fontName=BODY_FONT,
                fontSize=8,
                leading=9,
                textColor=TEXT,
                alignment=TA_CENTER,
            ),
            "small": ParagraphStyle(
                "CoreSmall",
                parent=sample["Normal"],
                fontName=BODY_FONT,
                fontSize=7,
                leading=8,
                textColor=SECONDARY,
                alignment=TA_CENTER,
            ),
            "map_legend": ParagraphStyle(
                "CoreMapLegend",
                parent=sample["Normal"],
                fontName=BODY_FONT,
                fontSize=7,
                leading=8,
                textColor=SECONDARY,
                alignment=TA_LEFT,
            ),
        }

    def _store_map(self, package, styles, state_label):
        map_state_label = (
            "ALL STATES" if package.selection.is_full else state_label.upper()
        )
        title = Table(
            [
                [Paragraph("STORE-TANK MAP", styles["map_heading"])],
                [
                    Paragraph(
                        f"PRINTABLE TANK LOOKUP | {map_state_label} | "
                        f"{len(package.stores)} STORES",
                        styles["subtitle"],
                    )
                ],
            ],
            colWidths=[4.7 * inch],
            style=self._padding_style(),
        )
        legend = Table(
            [
                [Paragraph("<b>LEGEND</b>", styles["small"])],
                [
                    Paragraph(
                        '<font color="#a94442"><b>L</b> - Legacy Chart</font>',
                        styles["map_legend"],
                    )
                ],
                [
                    Paragraph(
                        '<font color="#a94442"><b>[!]</b> - No Chart Available</font>',
                        styles["map_legend"],
                    )
                ],
            ],
            colWidths=[2.8 * inch],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            ),
        )
        header = Table(
            [[title, legend]],
            colWidths=[4.7 * inch, 2.8 * inch],
            style=self._padding_style(),
        )
        rows = [["STORE", "CITY", "STATE", "TYPE", *FUEL_COLUMNS]]
        for store in self._sorted_stores(package, state_label):
            entries = package.store_map.get(store.store_id, {})
            fuel_values = {column: {} for column in (*FUEL_COLUMNS, "OTHER")}
            for tank_index, entry in entries.items():
                name = entry.display_name or entry.legacy_name or "UNKNOWN TANK TYPE"
                if entry.source == "no_chart":
                    name = entry.legacy_name or "UNKNOWN TANK TYPE"
                fuels = (entry.fuel_type or "other").split("+")
                for fuel in fuels:
                    column = FUEL_NAMES.get(fuel.strip().casefold(), "OTHER")
                    grouped = fuel_values[column].setdefault(
                        name,
                        {
                            "count": 0,
                            "legacy": False,
                            "no_chart": False,
                            "source_markers": set(),
                        },
                    )
                    grouped["count"] += 1
                    grouped["legacy"] |= entry.source in {"official_chart", "no_chart"}
                    grouped["no_chart"] |= entry.source == "no_chart"
                    if marker := _source_marker(entry.source):
                        grouped["source_markers"].add(marker)
            cells = []
            for column in FUEL_COLUMNS:
                parts = []
                for name, info in fuel_values[column].items():
                    label = _display_tank_label(
                        name=name,
                        count=info["count"],
                        source_markers=info["source_markers"],
                        no_chart=info["no_chart"],
                    )
                    color = LEGACY_ACCENT.hexval() if info["legacy"] else TEXT.hexval()
                    marker = (
                        '<font color="#a94442"><b>[!]</b> </font>'
                        if info["no_chart"]
                        else ""
                    )
                    parts.append(
                        f'{marker}<font color="{color}">{escape(label)}</font>'
                    )
                cells.append(Paragraph(", ".join(parts) or "-", styles["cell"]))
            rows.append(
                [
                    _store_identifier(store),
                    escape(store.city),
                    escape(_state_abbreviation(store.state)),
                    Paragraph(_store_type_markup(store.store_type), styles["cell"]),
                    *cells,
                ]
            )
        if len(rows) == 1:
            rows.append(["", "No selected stores", "", "", "", "", "", "", ""])
        table = Table(
            rows,
            colWidths=[
                width * inch for width in [1.15, 1.49, 0.35, 0.62, *([0.77] * 5)]
            ],
            repeatRows=1,
            hAlign="CENTER",
        )
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER),
            ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
            ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("LEADING", (0, 0), (-1, -1), 10.8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
        ]
        for row in range(1, len(rows)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), ALTERNATE))
        table.setStyle(TableStyle(commands))
        return [header, Spacer(1, 7), table]

    def _generic_chart_pages(self, package, styles, state_label):
        charts = self._charts(package)
        groups = {}
        for chart in charts:
            groups.setdefault(chart.depth, []).append(chart)
        story = []
        for depth in sorted(groups):
            depth_charts = sorted(groups[depth], key=self._chart_sort_key)
            chunks = [
                depth_charts[i : i + MAX_CHARTS_PER_PAGE]
                for i in range(0, len(depth_charts), MAX_CHARTS_PER_PAGE)
            ]
            for page_number, chunk in enumerate(chunks, 1):
                story.append(PageBreak())
                story.extend(
                    self._chart_page(
                        chunk, depth, page_number, len(chunks), state_label, styles
                    )
                )
        if not charts:
            story.extend(
                [
                    Paragraph("GENERIC TANK CHARTS", styles["heading"]),
                    Paragraph("No charts selected.", styles["small"]),
                ]
            )
        return story

    def _chart_page_count(self, package):
        groups = {}
        for chart in self._charts(package):
            groups.setdefault(chart.depth, 0)
            groups[chart.depth] += 1
        return sum(
            math.ceil(chart_count / MAX_CHARTS_PER_PAGE)
            for chart_count in groups.values()
        )

    @staticmethod
    def _duplex_blank_page(styles):
        return [
            PageBreak(),
            Paragraph("GENERIC CHART SECTION", styles["subtitle"]),
            Spacer(1, 3.0 * inch),
            Paragraph("INTENTIONALLY BLANK", styles["blank_title"]),
            Spacer(1, 0.12 * inch),
            Paragraph(
                "This page is reserved for double-sided section alignment.",
                styles["blank_body"],
            ),
        ]

    def _chart_page(self, charts, depth, page_number, page_total, state_label, styles):
        title = Table(
            [
                [Paragraph(f"{depth}-INCH TANK // GENERIC", styles["heading"])],
                [
                    Paragraph(
                        f"GENERIC TANK CHARTS | PAGE {page_number}/{page_total}",
                        styles["subtitle"],
                    )
                ],
            ],
            colWidths=[3.84 * inch],
            style=self._padding_style(),
        )
        legend = Table(
            [
                [Paragraph("L - Legacy Chart", styles["map_legend"])],
            ],
            colWidths=[2.5 * inch],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            ),
        )
        header = Table(
            [[title, legend]],
            colWidths=[3.84 * inch, 3.66 * inch],
            style=self._padding_style(),
        )
        rows = self._lookup_rows(charts, depth, styles["table_header"])
        chart_count = len(charts)
        widths = [INCHES_COLUMN_WIDTH] + [CHART_COLUMN_WIDTH] * chart_count
        widths += [SEPARATOR_WIDTH, INCHES_COLUMN_WIDTH]
        widths += [CHART_COLUMN_WIDTH] * chart_count
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="CENTER")
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
            ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
            ("FONTSIZE", (0, 1), (-1, -1), 7.5),
            ("LEADING", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            (
                "BACKGROUND",
                (chart_count + 1, 0),
                (chart_count + 1, -1),
                GENERATED_ACCENT,
            ),
        ]
        for row in range(1, len(rows)):
            if row % 2 == 0:
                commands.extend(
                    [
                        ("BACKGROUND", (0, row), (chart_count, row), ALTERNATE),
                        ("BACKGROUND", (chart_count + 2, row), (-1, row), ALTERNATE),
                    ]
                )
        for index, chart in enumerate(charts):
            if chart.source == "official_chart":
                commands.extend(
                    [
                        ("TEXTCOLOR", (index + 1, 1), (index + 1, -1), LEGACY_ACCENT),
                        (
                            "TEXTCOLOR",
                            (chart_count + 3 + index, 1),
                            (chart_count + 3 + index, -1),
                            LEGACY_ACCENT,
                        ),
                    ]
                )
            accent = (
                LEGACY_ACCENT if chart.source == "official_chart" else GENERATED_ACCENT
            )
            commands.extend(
                [
                    ("LINEABOVE", (index + 1, 0), (index + 1, 0), 2.5, accent),
                    (
                        "LINEABOVE",
                        (chart_count + 3 + index, 0),
                        (chart_count + 3 + index, 0),
                        2.5,
                        accent,
                    ),
                ]
            )
        table.setStyle(TableStyle(commands))
        return [header, Spacer(1, 6), table]

    def _datasheet(self, package, styles, state_label):
        charts = self._charts(package)

        def make_table(table_charts):
            rows = [
                ["CHART", "SOURCE", "DEPTH", "CAPACITY", "RADIUS", "LENGTH", "SAMPLES"]
            ]
            for chart in table_charts:
                rows.append(
                    [
                        chart.name,
                        (
                            "Generated geometry"
                            if chart.source == "generated_geometry"
                            else "Legacy"
                        ),
                        str(chart.depth),
                        f"{round(chart.capacity):,}",
                        f"{chart.radius:.2f}" if chart.radius is not None else "",
                        f"{chart.length:.2f}" if chart.length is not None else "",
                        str(chart.samples) if chart.samples is not None else "",
                    ]
                )
            table = Table(
                rows,
                colWidths=[
                    width * inch for width in [0.92, 1.12, 0.35, 0.68, 0.53, 0.53, 0.45]
                ],
                repeatRows=1,
                hAlign="CENTER",
            )
            commands = [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
                ("FONTNAME", (0, 0), (-1, -1), BODY_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 5.2),
                ("LEADING", (0, 0), (-1, -1), 5.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ]
            for row, chart in enumerate(table_charts, start=1):
                if row % 2 == 0:
                    commands.append(("BACKGROUND", (0, row), (-1, row), ALTERNATE))
                if chart.source == "official_chart":
                    commands.append(("TEXTCOLOR", (1, row), (1, row), LEGACY_ACCENT))
            table.setStyle(TableStyle(commands))
            return table

        split = math.ceil(len(charts) / 2)
        tables = Table(
            [[make_table(charts[:split]), make_table(charts[split:])]],
            colWidths=[4.58 * inch, 4.58 * inch],
            hAlign="CENTER",
        )
        tables.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [
            Paragraph("GENERIC TANK CHARTS // DATASHEET", styles["heading"]),
            Paragraph(
                f"{state_label} | {len(charts)} chart definitions", styles["subtitle"]
            ),
            Spacer(1, 5),
            tables,
        ]

    def _charts(self, package):
        charts = []
        for name, bucket in package.catalog.items():
            curve = tuple(
                (int(point["inches"]), float(point["gallons"]))
                for point in bucket.analytic_curve()
            )
            charts.append(
                _Chart(
                    name,
                    bucket.depth_inches,
                    curve[-1][1],
                    "generated_geometry",
                    curve,
                    bucket.median_radius_inches,
                    bucket.median_length_inches,
                    len(bucket.tanks),
                )
            )
        used_official = {}
        for entries in package.store_map.values():
            for entry in entries.values():
                if entry.source == "official_chart" and entry.legacy_name:
                    used_official.setdefault(entry.display_name, entry.legacy_name)
        for display_name, legacy_name in used_official.items():
            points = package.official_charts.get(legacy_name, ())
            if points:
                curve = tuple(
                    (int(point["inches"]), float(point["gallons"])) for point in points
                )
                charts.append(
                    _Chart(
                        display_name,
                        curve[-1][0],
                        curve[-1][1],
                        "official_chart",
                        curve,
                    )
                )
        return sorted(
            charts, key=lambda chart: (chart.depth, self._chart_sort_key(chart))
        )

    @staticmethod
    def _chart_sort_key(chart):
        suffix_match = re.search(r"\([a-z]+\)$", chart.name)
        return (
            -round(chart.capacity / 1000),
            bool(suffix_match),
            -chart.capacity,
            chart.name,
        )

    @staticmethod
    def _lookup_rows(charts, depth, header_style):
        split = math.ceil(depth / 2)
        curves = [dict(chart.curve) for chart in charts]
        header = [Paragraph("<b>INCHES</b>", header_style)]
        header.extend(
            Paragraph(f"<b>{_compact_label(chart)}</b>", header_style)
            for chart in charts
        )
        header.append("")
        header.append(Paragraph("<b>INCHES</b>", header_style))
        header.extend(
            Paragraph(f"<b>{_compact_label(chart)}</b>", header_style)
            for chart in charts
        )
        rows = [header]
        for number in range(split):
            left = number + 1
            right = left + split
            row = [left]
            row.extend(_format_gallons(curve.get(left)) for curve in curves)
            row.append("")
            if right <= depth:
                row.append(right)
                row.extend(_format_gallons(curve.get(right)) for curve in curves)
            else:
                row.extend([""] * (1 + len(charts)))
            rows.append(row)
        return rows

    @staticmethod
    def _sorted_stores(package, state_label):
        return sorted(
            package.stores,
            key=lambda store: (
                "" if state_label != "FULL" else _state_abbreviation(store.state),
                store.city.casefold(),
                store.store_number or 0,
            ),
        )

    @staticmethod
    def _padding_style():
        return TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )


def _compact_label(chart: _Chart) -> str:
    suffix = re.search(r"(\([a-z]+\))$", chart.name)
    label = f"{round(chart.capacity / 1000)}k{suffix.group(1) if suffix else ''}"
    return f"{label}-L" if chart.source == "official_chart" else label


def _source_marker(source: str) -> str | None:
    if source == "official_chart":
        return "L"
    return None


def _store_identifier(store) -> str:
    store_number = store.store_number or store.store_id
    if store.riso_number and store.riso_number != store_number:
        return f"{store_number}/{store.riso_number}"
    return str(store_number)


def _store_type_markup(store_type: str) -> str:
    """Wrap longer store types at a word boundary for the printable map."""

    words = (store_type or "").strip().split()
    if len(" ".join(words)) <= STORE_TYPE_SINGLE_LINE_LIMIT or len(words) < 2:
        return escape(" ".join(words))
    split_at = min(
        range(1, len(words)),
        key=lambda index: abs(
            len(" ".join(words[:index])) - len(" ".join(words[index:]))
        ),
    )
    return "<br/>".join(
        escape(" ".join(words[start:end]))
        for start, end in ((0, split_at), (split_at, len(words)))
    )


def _display_tank_label(*, name, count, source_markers, no_chart) -> str:
    if no_chart:
        label = name
    else:
        marker = "/".join(sorted(source_markers))
        label = f"{name}-{marker}" if marker else name
    return label if count == 1 else f"{label}(x{count})"


def _format_gallons(value: float | None) -> str:
    return "" if value is None else f"{round(value):,}"


def _state_abbreviation(state: str) -> str:
    aliases = {
        "nc": "NC",
        "no": "NC",
        "north carolina": "NC",
        "va": "VA",
        "virginia": "VA",
        "sc": "SC",
        "south carolina": "SC",
    }
    return aliases.get((state or "").strip().casefold(), state or "")
