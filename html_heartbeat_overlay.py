"""Dedicated semantic HTML renderer for the journal heartbeat pulse."""

from html_model_overlay import attach_html_model_overlay


def attach_html_heartbeat_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_heartbeat_bridge", template="heartbeat",
        snapshot_key="heartbeat", model_attr="_html_render_model",
        log_name="Telemetry Heartbeat", width=132,
        min_height=48, default_height=48, max_height=48,
    )
