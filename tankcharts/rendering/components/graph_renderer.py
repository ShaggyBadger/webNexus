import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from reportlab.platypus import Image

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.theme import GraphConfig, PageLayout


class GraphRenderer:
    """Render official/estimated curves and veeder points as a static chart image."""

    def render(self, chart: TankFieldChart) -> list:
        figure, axis = plt.subplots(figsize=GraphConfig.FIGSIZE)
        figure.patch.set_facecolor("white")
        axis.set_facecolor("white")

        for curve in chart.curves:
            inches = [point["inches"] for point in curve["points"]]
            gallons = [point["gallons"] for point in curve["points"]]
            is_generated_curve = curve["label"] == "Generated Curve (Math)"
            axis.plot(
                inches,
                gallons,
                label=curve["label"],
                color=curve["color"],
                linewidth=(
                    GraphConfig.GENERATED_LINE_WIDTH
                    if is_generated_curve
                    else GraphConfig.OFFICIAL_LINE_WIDTH
                ),
                linestyle=(
                    (0, GraphConfig.GENERATED_LINE_DASH)
                    if is_generated_curve
                    else "solid"
                ),
            )

        if chart.veeder_points:
            axis.scatter(
                [point["inches"] for point in chart.veeder_points],
                [point["gallons"] for point in chart.veeder_points],
                label="Veeder-Root Readings",
                s=GraphConfig.VEEDER_MARKER_SIZE,
                color="#d63050",
                edgecolors=GraphConfig.VEEDER_EDGE_COLOR,
                linewidths=GraphConfig.VEEDER_EDGE_WIDTH,
            )

        axis.grid(True, alpha=0.5, color=GraphConfig.GRID_COLOR)
        axis.set_xlabel("Depth (Inches)", fontsize=GraphConfig.FONT_SIZE)
        axis.set_ylabel("Volume (Gallons)", fontsize=GraphConfig.FONT_SIZE)
        axis.tick_params(axis="both", labelsize=GraphConfig.FONT_SIZE)
        axis.legend(fontsize=9, loc="upper left")
        axis.set_xlim(0, chart.max_depth_inches)
        axis.set_ylim(bottom=0)

        image_buffer = io.BytesIO()
        figure.tight_layout()
        figure.savefig(image_buffer, format="png", dpi=180)
        plt.close(figure)

        image_buffer.seek(0)
        image = Image(
            image_buffer, width=PageLayout.CONTENT_WIDTH, height=PageLayout.GRAPH_HEIGHT
        )
        return [image]
