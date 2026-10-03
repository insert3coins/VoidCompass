"""Semantic HTML renderer attachment for the Construction Needs overlay."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_colony_needs_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The width grows with the overlay text size, as Jump Info's does; the
    # height follows the page's measured content (one row per commodity).
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_colony_needs_bridge", template="colony_needs",
        snapshot_key="needs", model_attr="_html_render_model",
        log_name="Construction Needs", width=360,
        min_height=90, default_height=320, max_height=1100,
        bridge_class=HtmlJumpInfoBridge,
    )
