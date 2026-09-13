"""Dedicated HTML renderer bridge for the Rhino coverage minimap."""

from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_rhino_minimap_overlay(
    overlay, overlay_id, title, enabled_key, x_key, y_key,
):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_rhino_minimap_bridge",
        template="rhino-minimap-overlay",
        snapshot_key="rhino_minimap",
        model_attr="_html_render_model",
        log_name="Rhino Minimap",
        width=360, min_height=430, default_height=470, max_height=560,
    )
