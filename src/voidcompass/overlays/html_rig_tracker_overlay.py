"""Semantic HTML renderer attachment for the Rig Tracker overlay."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_rig_tracker_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The height follows the page's measured content (the collection order adds a line).
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_rig_tracker_bridge", template="rig_tracker",
        snapshot_key="rigs", model_attr="_html_render_model",
        log_name="Rig Tracker", width=420,
        min_height=130, default_height=155, max_height=420,
        bridge_class=HtmlJumpInfoBridge,
    )
