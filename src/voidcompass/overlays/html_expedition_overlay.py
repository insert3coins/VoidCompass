"""Semantic HTML renderer attachment for the Expedition overlay."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_expedition_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The height follows the page's measured content (a compass, warnings).
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_expedition_bridge", template="expedition",
        snapshot_key="expedition", model_attr="_html_render_model",
        log_name="Expedition", width=380,
        min_height=120, default_height=220, max_height=640,
        bridge_class=HtmlJumpInfoBridge,
    )
