from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import Colors, Spacing


class ConfidenceRenderer:
    """Render confidence summary panel."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        rows = [
            [
                Paragraph(
                    f"CONFIDENCE: {chart.confidence_level}",
                    self.styles["heading"],
                )
            ],
            [Paragraph(self._official_label(chart), self.styles["body"])],
            [
                Paragraph(
                    f"Coverage: {chart.coverage_percent:.1f}%", self.styles["body"]
                )
            ],
            [
                Paragraph(
                    f"Observations: {chart.veeder_observation_count}",
                    self.styles["body"],
                )
            ],
            [
                Paragraph(
                    f"Avg Difference: {chart.avg_difference_gallons:.1f} gallons",
                    self.styles["body"],
                )
            ],
            [
                Paragraph(
                    f"Max Difference: {chart.max_difference_gallons:.1f} gallons",
                    self.styles["body"],
                )
            ],
        ]

        table = Table(rows, colWidths=[480])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), Colors.PANEL_BG),
                    ("BOX", (0, 0), (-1, -1), 1, Colors.BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, Colors.BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), Spacing.TABLE_CELL_PADDING),
                    ("RIGHTPADDING", (0, 0), (-1, -1), Spacing.TABLE_CELL_PADDING),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ]
            )
        )
        return [table]

    def _official_label(self, chart: TankFieldChart) -> str:
        if chart.has_official_chart:
            return "Official Chart: Available"
        return "Official Chart: Not Available"
