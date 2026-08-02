from datetime import UTC, datetime

from django.conf import settings
from reportlab.platypus import Paragraph

from tankcharts.domain import StoreFieldChart


class StoreFooterRenderer:
    """Render concise footer metadata for store-wide chart pages."""

    def __init__(self, styles: dict):
        self.styles = styles

    def render(self, chart: StoreFieldChart) -> list:
        generated_label = datetime.now(tz=UTC).strftime("Generated %Y-%m-%d %H:%M UTC")
        minimum_readings = int(getattr(settings, "CHART_MIN_READINGS", 10))
        confidence_flags = []
        for tank in chart.tanks:
            observed_count = tank.veeder_observation_count or tank.sample_count
            if observed_count < minimum_readings:
                tank_label = tank.tank_index if tank.tank_index is not None else "?"
                confidence_flags.append(f"T{tank_label}={observed_count}")

        omitted_line = ""
        if chart.omitted_tanks:
            omitted_labels = []
            for omitted in chart.omitted_tanks:
                tank_label = omitted.tank_index if omitted.tank_index is not None else "?"
                omitted_labels.append(
                    f"T{tank_label} ({omitted.reason_code}, N={omitted.veeder_observation_count})"
                )
            omitted_line = f" | Omitted tanks: {', '.join(omitted_labels)}"

        note_line = (
            f"Store-wide chart for {len(chart.tanks)} tanks | "
            f"{chart.total_veeder_observation_count} total Veeder observations"
            f" | Trust threshold N>={minimum_readings}"
        )
        if confidence_flags:
            note_line += (
                " | LOW CONFIDENCE "
                + ", ".join(confidence_flags)
            )
        return [
            Paragraph(f"{generated_label} | {note_line}{omitted_line}", self.styles["footer"])
        ]
