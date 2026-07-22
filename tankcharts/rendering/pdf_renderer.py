import io

from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

from tankcharts.domain import StoreFieldChart, TankFieldChart
from tankcharts.rendering.components import (
    FooterRenderer,
    GraphRenderer,
    HeaderRenderer,
    LookupTableRenderer,
    SiteConfigurationRenderer,
    StoreFooterRenderer,
    StoreHeaderRenderer,
    StoreLookupTableRenderer,
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
        self.store_header_renderer = StoreHeaderRenderer(self.styles)
        self.store_table_renderer = StoreLookupTableRenderer(self.styles)
        self.store_footer_renderer = StoreFooterRenderer(self.styles)

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

    def render_store(
        self,
        chart: StoreFieldChart,
        *,
        tank_chunks: list[list[int]],
    ) -> bytes:
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
        for index, tank_indices in enumerate(tank_chunks, start=1):
            elements.extend(
                self.store_header_renderer.render(
                    chart,
                    page_label=f"TABLE PAGE {index}/{len(tank_chunks)}",
                )
            )
            elements.extend(
                self.store_table_renderer.render(chart, tank_indices=tank_indices)
            )
            elements.append(Spacer(1, Spacing.SECTION_GAP))
            elements.extend(self.store_footer_renderer.render(chart))
            elements.append(PageBreak())

        elements.extend(
            self.store_header_renderer.render(chart, page_label="COMBINED GRAPH")
        )
        elements.extend(self.graph_renderer.render(chart))
        elements.append(Spacer(1, Spacing.SECTION_GAP))
        elements.extend(self.store_footer_renderer.render(chart))

        doc.build(elements)
        return buffer.getvalue()
