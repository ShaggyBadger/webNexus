from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch


class PageLayout:
    PAGE_SIZE = letter
    CONTENT_WIDTH = letter[0] - (1.0 * inch)
    GRAPH_HEIGHT = 3.0 * inch

    TABLE_GROUP_COUNT = 4
    TABLE_ROWS_PER_GROUP = 50
    TABLE_TOTAL_COLUMNS = TABLE_GROUP_COUNT * 2
    TABLE_FONT_SIZE = 7.0
    TABLE_HEADER_FONT_SIZE = 7.5
    STORE_TABLE_COL_INCHES_WIDTH = 0.9 * inch
