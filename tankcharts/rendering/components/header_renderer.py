from reportlab.platypus import Paragraph, Spacer

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import Spacing


class HeaderRenderer:
    """Render tank and store identifying information."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        city_state_zip = ", ".join(
            [part for part in [chart.city, chart.state, chart.zip_code] if part]
        )
        title_line = (
            f"STORE {chart.store_num}"
            f" | RISO {chart.riso_num or 'Unknown'}"
            f" | TANK {chart.tank_index} {chart.fuel_type.upper()}"
            f" | {chart.capacity_gallons:,} gal"
            f" | {chart.max_depth_inches} in"
        )
        location_line = (
            f"{chart.address or 'Unknown address'}"
            f" | {city_state_zip or 'Unknown city/state/zip'}"
            f" | {chart.store_name or 'Unknown brand'}"
        )
        return [
            Paragraph(title_line, self.styles["title"]),
            Paragraph(location_line, self.styles["body"]),
            Spacer(1, Spacing.SECTION_GAP),
        ]
