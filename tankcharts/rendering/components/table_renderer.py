from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import PageLayout


class LookupTableRenderer:
    """Render inch-by-inch lookup table for field use."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        table_data = [
            [
                Paragraph("Inches", self.styles["heading"]),
                Paragraph("Official Gal", self.styles["heading"]),
                Paragraph("Est. Gal", self.styles["heading"]),
                Paragraph("Difference", self.styles["heading"]),
            ]
        ]

        for row in chart.table_rows:
            table_data.append(
                [
                    Paragraph(str(row["inches"]), self.styles["body_right"]),
                    Paragraph(
                        self._format_number(row["official_gallons"]),
                        self.styles["body_right"],
                    ),
                    Paragraph(
                        self._format_number(row["estimated_gallons"]),
                        self.styles["body_right"],
                    ),
                    Paragraph(
                        self._format_difference(row["difference"]),
                        self.styles["body_right"],
                    ),
                ]
            )

        table = Table(
            table_data,
            colWidths=[70, 130, 130, 130],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a2e33")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), PageLayout.TABLE_FONT_SIZE),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#a0aec0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#5b6168")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#1c1f23"), colors.HexColor("#202429")],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        return [table]

    def _format_number(self, value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:,.1f}"

    def _format_difference(self, value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:+.1f}"
