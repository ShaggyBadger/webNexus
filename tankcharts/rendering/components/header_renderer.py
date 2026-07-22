from reportlab.platypus import Paragraph, Spacer

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import Spacing


class HeaderRenderer:
    """Render tank and store identifying information."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        title_line = (
            f"{chart.store_num} {chart.store_name} | "
            f"Tank {chart.tank_index} {chart.fuel_type.upper()} | "
            f"{chart.capacity_gallons:,} gal | {chart.max_depth_inches} in"
        )
        return [
            Paragraph(title_line, self.styles["title"]),
            Spacer(1, Spacing.SECTION_GAP),
        ]
