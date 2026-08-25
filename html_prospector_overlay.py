"""Dedicated semantic HTML renderer for live prospector analysis."""

from html_model_overlay import attach_html_model_overlay


def attach_html_prospector_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_prospector_bridge", template="prospector",
        snapshot_key="prospector", model_attr="_html_render_model",
        log_name="Prospector Analysis", width=400,
        min_height=180, default_height=250, max_height=560,
    )
