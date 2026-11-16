"""Semantic HTML renderer attachment for the Stream Chat overlay (5.8.3)."""

from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_stream_chat_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    # The height follows the page: a strip when it's quiet, taller for a game
    # or the credits.
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_stream_chat_bridge", template="stream_chat",
        snapshot_key="stream", model_attr="_html_render_model",
        log_name="Stream Chat", width=420,
        min_height=48, default_height=240, max_height=1100,
        bridge_class=HtmlJumpInfoBridge,
    )
