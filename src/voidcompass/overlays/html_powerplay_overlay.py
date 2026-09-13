"""Dedicated semantic HTML renderer bridge for Powerplay operations."""

from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_powerplay_overlay(
    overlay, overlay_id, title, enabled_key, x_key, y_key,
):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_powerplay_bridge",
        template="powerplay-overlay",
        snapshot_key="powerplay",
        model_attr="_html_render_model",
        log_name="Powerplay Operations",
        width=430, min_height=180, default_height=310, max_height=520,
    )
