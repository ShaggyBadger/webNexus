import io

from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

from tankcharts.domain import TankFieldChart
from tankcharts.rendering.components import (
    FooterRenderer,
    GraphRenderer,
    HeaderRenderer,
    LookupTableRenderer,
    SiteConfigurationRenderer,
)
from tankcharts.rendering.theme import PageLayout, Spacing, build_styles, register_fonts


class PDFRenderer:
    """Render a tank field chart dataclass into PDF bytes."""

    def __init__(self) -> None:
        register_fonts()
        self.styles = build_styles()
        self.header_renderer = HeaderRenderer(self.styles)
        self.graph_renderer = GraphRenderer()
        self.table_renderer = LookupTableRenderer(self.styles)
        self.site_configuration_renderer = SiteConfigurationRenderer(self.styles)
        self.footer_renderer = FooterRenderer(self.styles)

    def render(self, chart: TankFieldChart) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=PageLayout.PAGE_SIZE,
            leftMargin=Spacing.PAGE_MARGIN_LEFT,
            rightMargin=Spacing.PAGE_MARGIN_RIGHT,
            topMargin=Spacing.PAGE_MARGIN_TOP,
            bottomMargin=Spacing.PAGE_MARGIN_BOTTOM,
        )

        elements = []
        elements.extend(self.header_renderer.render(chart))
        elements.extend(self.table_renderer.render(chart))
        elements.append(PageBreak())
        elements.extend(self.site_configuration_renderer.render(chart))
        elements.append(Spacer(1, Spacing.SECTION_GAP * 2))
        elements.extend(self.graph_renderer.render(chart))
        elements.append(Spacer(1, Spacing.SECTION_GAP))
        elements.extend(self.footer_renderer.render(chart))

        doc.build(elements)
        return buffer.getvalue()
