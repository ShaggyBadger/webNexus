import logging

# Tactical Logger for Global Context
logger = logging.getLogger('webnexus')

def global_config(request):
    """
    TACTICAL_CONTEXT_PROCESSOR:
    Injects global configuration parameters and user preferences into every template context.
    Provides consistent access to tactical UI themes and profile-driven settings.
    """
    # 1. RESOLVE_MAP_PREFERENCE: Default to STANDARD if anonymous or unavailable
    map_preference = 'STANDARD'
    if request.user.is_authenticated:
        try:
            map_preference = request.user.profile.map_preference
        except Exception as e:
            logger.error(f"CONTEXT_ERROR: Failed to resolve map preference for {request.user.username}: {str(e)}")
            pass

    # 2. COMPILE_OPERATIONAL_PARAMETERS: Centralized UI and System configurations
    return {
        # Core Identity
        "SITE_NAME": "WebNexus",
        "VERSION": "2.7.0",
        
        # Tactical Color Palette (Profile-neutral constants)
        "PRIMARY_COLOR": "#8da35d",
        "BG_COLOR": "#121417",
        "TEXT_COLOR": "#f8f9fa",
        "MUTED_TEXT_COLOR": "#adb5bd",
        "FONT_FAMILY": "'JetBrains Mono', monospace",
        "ACCENT_COLOR": "#ffb86c",
        "NAVBAR_BG": "#1c1f23",
        "NAVBAR_BORDER": "#2c3036",
        
        # Dynamic User Settings
        "USER_MAP_PREFERENCE": map_preference,
    }
