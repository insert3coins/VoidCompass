"""Semantic HTML renderer attachment for the Hatchling overlay."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_hatchling_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The height follows the page: a log line comes and goes under the bars.
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_hatchling_bridge", template="hatchling",
        snapshot_key="hatchling", model_attr="_html_render_model",
        log_name="Hatchling", width=250,
        min_height=110, default_height=132, max_height=260,
        bridge_class=HtmlJumpInfoBridge,
    )
