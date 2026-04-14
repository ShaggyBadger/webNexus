def global_config(request):
    """
    Returns global configuration values available in all templates.
    """
    return {
        "SITE_NAME": "WebNexus",
        "VERSION": "2.3.1",
        "PRIMARY_COLOR": "#8da35d",
        "BG_COLOR": "#121417",
        "TEXT_COLOR": "#f8f9fa",
        "MUTED_TEXT_COLOR": "#adb5bd",
        "FONT_FAMILY": "'JetBrains Mono', monospace",
        "ACCENT_COLOR": "#e94560",
        "NAVBAR_BG": "#1c1f23",
        "NAVBAR_BORDER": "#2c3036",
    }
