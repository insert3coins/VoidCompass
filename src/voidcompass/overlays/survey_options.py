"""Profile presentation choices for the Survey Operations overlay.

Shared by the overlay bridge (which publishes them to the page) and Overlay
Studio (which edits them), without either importing the other.
"""

SPOTLIGHT_ROTATION_MODES = ("auto", "always", "off")
DEFAULT_SPOTLIGHT_THRESHOLD = 8


def _integer(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def survey_overlay_options(config):
    """How Survey Operations rotates its spotlight.

    ``auto`` rotates only when the system has more biology worlds than the
    threshold; ``always`` rotates whenever there are two or more; ``off``
    keeps the spotlight on the latest journal activity.
    """
    mode = str(config.get("survey_spotlight_rotation") or "auto").strip().casefold()
    threshold = _integer(config.get("survey_spotlight_threshold"), DEFAULT_SPOTLIGHT_THRESHOLD)
    return {
        "spotlight_rotation": mode if mode in SPOTLIGHT_ROTATION_MODES else "auto",
        "spotlight_threshold": max(2, min(40, threshold)),
    }


def survey_text_scale(config):
    """Survey's own text size when set (percent), else the overlay-wide scale."""
    from voidcompass.core.overlay_registry import overlay_text_scale
    return overlay_text_scale(config, "survey_status_hud")
