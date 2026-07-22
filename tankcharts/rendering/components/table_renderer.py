from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import Colors, PageLayout


class LookupTableRenderer:
    """Render inch-by-inch lookup table for field use."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        table_data = []

        header_row = []
        for _ in range(PageLayout.TABLE_GROUP_COUNT):
            header_row.extend(
                [
                    Paragraph("Inches", self.styles["heading"]),
                    Paragraph("Gallons", self.styles["heading"]),
                ]
            )
        table_data.append(header_row)

        group_count = PageLayout.TABLE_GROUP_COUNT
        rows_per_group = PageLayout.TABLE_ROWS_PER_GROUP

        for row_index in range(rows_per_group):
            row_cells = []
            for group_index in range(group_count):
                point_index = group_index * rows_per_group + row_index
                point = (
                    chart.table_rows[point_index]
                    if point_index < len(chart.table_rows)
                    else None
                )
                if point:
                    row_cells.extend(
                        [
                            Paragraph(str(point["inches"]), self.styles["body_right"]),
                            Paragraph(
                                self._format_number(point["gallons"]),
                                self.styles["body_right"],
                            ),
                        ]
                    )
                else:
                    row_cells.extend(
                        [
                            Paragraph("", self.styles["body_right"]),
                            Paragraph("", self.styles["body_right"]),
                        ]
                    )
            table_data.append(row_cells)

        inches_col_width = 52
        gallons_col_width = (
            PageLayout.CONTENT_WIDTH - (inches_col_width * group_count)
        ) / group_count
        col_widths = []
        for _ in range(group_count):
            col_widths.extend([inches_col_width, gallons_col_width])

        table = Table(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), Colors.HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, -1), Colors.TEXT_PRIMARY),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), PageLayout.TABLE_FONT_SIZE),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, 0),
                        PageLayout.TABLE_HEADER_FONT_SIZE,
                    ),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 0.5, Colors.BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, Colors.BORDER),
                    ("LINEAFTER", (1, 0), (1, -1), 1.2, Colors.ESTIMATED_CURVE),
                    ("LINEAFTER", (3, 0), (3, -1), 1.2, Colors.ESTIMATED_CURVE),
                    ("LINEAFTER", (5, 0), (5, -1), 1.2, Colors.ESTIMATED_CURVE),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, Colors.ROW_ALT],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
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
