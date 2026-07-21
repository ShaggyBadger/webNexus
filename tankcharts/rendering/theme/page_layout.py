from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch


class PageLayout:
    PAGE_SIZE = letter
    CONTENT_WIDTH = letter[0] - (1.0 * inch)
    GRAPH_HEIGHT = 2.0 * inch
    TABLE_FONT_SIZE = 6.8
