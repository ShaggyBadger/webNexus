from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from tankcharts.domain import StoreFieldChart
from tankcharts.rendering.theme import Colors, PageLayout


class StoreLookupTableRenderer:
    """Render a multi-tank lookup table for one store table page."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: StoreFieldChart, *, tank_indices: list[int]) -> list:
        header_row = [Paragraph("INCHES", self.styles["heading"])]
        for tank in chart.tanks:
            if tank.tank_index in tank_indices:
                header_row.append(
                    Paragraph(
                        self._tank_header_label(
                            fuel_type=tank.fuel_type,
                            tank_index=tank.tank_index,
                            max_depth_inches=tank.max_depth_inches,
                        ),
                        self.styles["heading"],
                    )
                )

        table_data = [header_row]

        for row in chart.combined_table_rows:
            inches = int(row["inches"])
            row_cells = [Paragraph(str(inches), self.styles["body_right"])]
            for tank_index in tank_indices:
                value = row.get(f"tank_{tank_index}_gallons")
                row_cells.append(
                    Paragraph(self._format_number(value), self.styles["body_right"])
                )
            table_data.append(row_cells)

        col_widths = self._column_widths(tank_count=len(tank_indices))
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), Colors.HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, -1), Colors.TEXT_PRIMARY),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), PageLayout.TABLE_FONT_SIZE),
            ("FONTSIZE", (0, 0), (-1, 0), PageLayout.TABLE_HEADER_FONT_SIZE),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, Colors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, Colors.BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, Colors.ROW_ALT]),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]

        for row_number in range(51, len(table_data), 50):
            style_commands.append(
                (
                    "LINEABOVE",
                    (0, row_number),
                    (-1, row_number),
                    1.0,
                    Colors.ESTIMATED_CURVE,
                )
            )

        table.setStyle(TableStyle(style_commands))
        return [table]

    def _column_widths(self, *, tank_count: int) -> list[float]:
        inches_col_width = PageLayout.STORE_TABLE_COL_INCHES_WIDTH
        tank_col_width = (PageLayout.CONTENT_WIDTH - inches_col_width) / tank_count
        return [inches_col_width] + [tank_col_width] * tank_count

    def _tank_header_label(
        self,
        *,
        fuel_type: str,
        tank_index: int,
        max_depth_inches: int,
    ) -> str:
        fuel_abbreviation = (fuel_type or "UNK").upper()[:3]
        return f'{fuel_abbreviation} T{tank_index} ({max_depth_inches}")'

    def _format_number(self, value: float | None) -> str:
        if value is None:
            return ""
        return f"{int(round(value)):,}"
