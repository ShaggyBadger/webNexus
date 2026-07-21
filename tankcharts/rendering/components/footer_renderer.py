from datetime import UTC, datetime

from reportlab.platypus import Paragraph

from tankcharts.domain import TankFieldChart


class FooterRenderer:
    """Render concise footer metadata for field trust."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        generated_label = datetime.now(tz=UTC).strftime("Generated %Y-%m-%d %H:%M UTC")
        trust_line = f"Estimated curve derived from {chart.veeder_observation_count} Veeder observations."
        return [
            Paragraph(generated_label, self.styles["footer"]),
            Paragraph(trust_line, self.styles["footer"]),
        ]
