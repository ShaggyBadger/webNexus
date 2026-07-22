from datetime import UTC, datetime

from reportlab.platypus import Paragraph

from tankcharts.domain import StoreFieldChart


class StoreFooterRenderer:
    """Render concise footer metadata for store-wide chart pages."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: StoreFieldChart) -> list:
        generated_label = datetime.now(tz=UTC).strftime("Generated %Y-%m-%d %H:%M UTC")
        note_line = (
            f"Store-wide chart for {len(chart.tanks)} tanks | "
            f"{chart.total_veeder_observation_count} total Veeder observations"
        )
        return [
            Paragraph(generated_label, self.styles["footer"]),
            Paragraph(note_line, self.styles["footer"]),
        ]
