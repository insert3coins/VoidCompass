"""Semantic HTML renderer attachment for the Crew Orders overlay (5.7.7)."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_orders_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The height follows the page's measured content (objectives add lines).
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_orders_bridge", template="crew_orders",
        snapshot_key="orders", model_attr="_html_render_model",
        log_name="Crew Orders", width=360,
        min_height=90, default_height=170, max_height=900,
        bridge_class=HtmlJumpInfoBridge,
    )
