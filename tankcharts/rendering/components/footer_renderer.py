from datetime import UTC, datetime

from django.conf import settings
from reportlab.platypus import Paragraph

from tankcharts.domain import TankFieldChart


class FooterRenderer:
    """Render concise footer metadata for field trust."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: TankFieldChart) -> list:
        generated_label = datetime.now(tz=UTC).strftime("Generated %Y-%m-%d %H:%M UTC")
        minimum_readings = int(getattr(settings, "CHART_MIN_READINGS", 10))
        observation_count = (
            chart.veeder_observation_count or chart.estimation_sample_count
        )
        trust_line = (
            f"Veeder-derived curve based on N={observation_count} readings "
            f"(threshold N>={minimum_readings})."
        )
        if observation_count < minimum_readings:
            trust_line += " LOW CONFIDENCE."
        return [
            Paragraph(generated_label, self.styles["footer"]),
            Paragraph(trust_line, self.styles["footer"]),
        ]
