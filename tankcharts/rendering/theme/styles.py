from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle

from tankcharts.rendering.theme.colors import Colors
from tankcharts.rendering.theme.fonts import Fonts


def build_styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            name="title",
            fontName=Fonts.PRIMARY_BOLD,
            fontSize=13,
            textColor=Colors.AMBER,
            leading=15,
            alignment=TA_LEFT,
        ),
        "heading": ParagraphStyle(
            name="heading",
            fontName=Fonts.PRIMARY_BOLD,
            fontSize=9,
            textColor=Colors.TEXT_PRIMARY,
            leading=11,
            alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            name="body",
            fontName=Fonts.PRIMARY,
            fontSize=8,
            textColor=Colors.TEXT_PRIMARY,
            leading=10,
            alignment=TA_LEFT,
        ),
        "body_right": ParagraphStyle(
            name="body_right",
            fontName=Fonts.PRIMARY,
            fontSize=8,
            textColor=Colors.TEXT_PRIMARY,
            leading=10,
            alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            name="footer",
            fontName=Fonts.PRIMARY,
            fontSize=7,
            textColor=Colors.TEXT_SECONDARY,
            leading=9,
            alignment=TA_LEFT,
        ),
    }
