from reportlab.platypus import Paragraph, Spacer

from tankcharts.domain import StoreFieldChart
from tankcharts.rendering.theme import Spacing


class StoreHeaderRenderer:
    """Render compact store-level header for store chart table/graph pages."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: StoreFieldChart, *, page_label: str) -> list:
        city_state_zip = ", ".join(
            [part for part in [chart.city, chart.state, chart.zip_code] if part]
        )
        tank_summaries = " | ".join(
            [
                f'{tank.fuel_type.upper()[:3]} T{tank.tank_index} {tank.max_depth_inches}"'
                for tank in chart.tanks
            ]
        )
        title_line = (
            f"STORE {chart.store_num} | RISO {chart.riso_num or 'Unknown'}"
            f" | {chart.store_name or 'Unknown brand'} | {page_label}"
        )
        location_line = (
            f"{chart.address or 'Unknown address'} | "
            f"{city_state_zip or 'Unknown city/state/zip'} | "
            f"TANKS {len(chart.tanks)}"
        )
        return [
            Paragraph(title_line, self.styles["title"]),
            Paragraph(location_line, self.styles["body"]),
            Paragraph(tank_summaries, self.styles["footer"]),
            Spacer(1, Spacing.SECTION_GAP),
        ]
