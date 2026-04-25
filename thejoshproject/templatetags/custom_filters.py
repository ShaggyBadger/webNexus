from django import template
from django.utils.safestring import mark_safe
import markdown

register = template.Library()


@register.filter(name="split")
def split(value, key):
    """
    Returns the string split by the given key.
    """
    return value.split(key)

@register.filter(name="markdown")
def markdown_filter(value):
    """
    Converts markdown text to safe HTML.
    """
    if not value:
        return ""
    # Render markdown with common extensions
    html = markdown.markdown(value, extensions=['extra', 'sane_lists', 'nl2br'])
    return mark_safe(html)
