"""Semantic HTML renderer attachment for the Trade Route overlay."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_trade_route_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The height follows the page's measured content (warnings add lines).
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_trade_route_bridge", template="trade_route",
        snapshot_key="route", model_attr="_html_render_model",
        log_name="Trade Route", width=360,
        min_height=90, default_height=150, max_height=600,
        bridge_class=HtmlJumpInfoBridge,
    )
