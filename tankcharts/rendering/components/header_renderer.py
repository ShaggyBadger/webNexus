from reportlab.platypus import Paragraph, Spacer

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import Spacing


class HeaderRenderer:
    """Render tank and store identifying information."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        location_line = (
            f"{chart.store_num} - {chart.store_name} | {chart.city}, {chart.state}"
        )
        tank_line = (
            f"Tank {chart.tank_index} - {chart.fuel_type.upper()} | "
            f"Type: {chart.tank_type_name} | "
            f"Capacity: {chart.capacity_gallons:,} gal | "
            f"Max Depth: {chart.max_depth_inches} in"
        )
        return [
            Paragraph("TANK FIELD CHART", self.styles["title"]),
            Paragraph(location_line, self.styles["body"]),
            Paragraph(chart.address, self.styles["body"]),
            Paragraph(tank_line, self.styles["body"]),
            Spacer(1, Spacing.SECTION_GAP),
        ]
