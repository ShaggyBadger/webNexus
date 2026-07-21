from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"


class Fonts:
    PRIMARY = "Helvetica"
    PRIMARY_BOLD = "Helvetica-Bold"


def register_fonts() -> None:
    """Register JetBrains Mono if bundled font files are available."""
    regular_path = FONT_DIR / "JetBrainsMono-Regular.ttf"
    bold_path = FONT_DIR / "JetBrainsMono-Bold.ttf"
    if regular_path.exists() and bold_path.exists():
        pdfmetrics.registerFont(TTFont("JetBrainsMono", regular_path))
        pdfmetrics.registerFont(TTFont("JetBrainsMono-Bold", bold_path))
        Fonts.PRIMARY = "JetBrainsMono"
        Fonts.PRIMARY_BOLD = "JetBrainsMono-Bold"
