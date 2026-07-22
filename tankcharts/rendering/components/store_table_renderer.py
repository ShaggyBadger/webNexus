from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

from tankcharts.domain import StoreFieldChart
from tankcharts.rendering.theme import Colors, PageLayout


class StoreLookupTableRenderer:
    """Render a multi-tank lookup table for one store table page."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: StoreFieldChart, *, tank_indices: list[int]) -> list:
        left_headers = ["INCHES"]
        for tank in chart.tanks:
            if tank.tank_index in tank_indices:
                left_headers.append(
                    self._tank_header_label(
                        fuel_type=tank.fuel_type,
                        tank_index=tank.tank_index,
                        max_depth_inches=tank.max_depth_inches,
                    )
                )
        right_headers = list(left_headers)

        table_data = [left_headers + [""] + right_headers]

        max_depth_inches = len(chart.combined_table_rows)
        split_point = (max_depth_inches + 1) // 2

        for row_number in range(1, split_point + 1):
            left_row = chart.combined_table_rows[row_number - 1]
            right_index = row_number + split_point
            right_row = (
                chart.combined_table_rows[right_index - 1]
                if right_index <= max_depth_inches
                else None
            )

            row_cells = [str(int(left_row["inches"]))]
            for tank_index in tank_indices:
                row_cells.append(
                    self._format_number(left_row.get(f"tank_{tank_index}_gallons"))
                )

            row_cells.append("")
            row_cells.append(str(int(right_row["inches"])) if right_row else "")
            for tank_index in tank_indices:
                row_cells.append(
                    self._format_number(
                        right_row.get(f"tank_{tank_index}_gallons")
                        if right_row
                        else None
                    )
                )

            table_data.append(row_cells)

        col_widths, separator_col_index = self._column_widths(
            tank_count=len(tank_indices)
        )
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), Colors.HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, -1), Colors.TEXT_PRIMARY),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.0),
            ("FONTSIZE", (0, 0), (-1, 0), 7.5),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, Colors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, Colors.BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, Colors.ROW_ALT]),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 1), (-1, -1), 0.5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 0.5),
            ("TOPPADDING", (0, 0), (-1, 0), 1),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
            ("LEADING", (0, 0), (-1, -1), 7),
            (
                "BACKGROUND",
                (separator_col_index, 0),
                (separator_col_index, -1),
                Colors.ESTIMATED_CURVE,
            ),
            (
                "LINEBEFORE",
                (separator_col_index, 0),
                (separator_col_index, -1),
                0.3,
                Colors.ESTIMATED_CURVE,
            ),
            (
                "LINEAFTER",
                (separator_col_index, 0),
                (separator_col_index, -1),
                0.3,
                Colors.ESTIMATED_CURVE,
            ),
        ]

        table.setStyle(TableStyle(style_commands))
        return [table]

    def _column_widths(self, *, tank_count: int) -> tuple[list[float], int]:
        separator_width = PageLayout.STORE_TABLE_SEPARATOR_WIDTH
        block_width = (PageLayout.CONTENT_WIDTH - separator_width) / 2
        inches_col_width = PageLayout.STORE_TABLE_COL_INCHES_WIDTH / 2
        tank_col_width = (block_width - inches_col_width) / tank_count

        left_block = [inches_col_width] + [tank_col_width] * tank_count
        separator_col_index = len(left_block)
        widths = left_block + [separator_width] + left_block
        return widths, separator_col_index

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
