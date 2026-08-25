"""Dedicated semantic HTML renderer for Fleet and Squadron Carrier status."""

from html_model_overlay import attach_html_model_overlay


def attach_html_carrier_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_carrier_bridge", template="carrier",
        snapshot_key="carrier", model_attr="_html_render_model",
        log_name="Carrier Command", width=430,
        min_height=214, default_height=270, max_height=520,
    )
