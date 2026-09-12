"""Dedicated semantic HTML renderer for live planetary materials."""

from html_model_overlay import attach_html_model_overlay


def attach_html_planet_materials_overlay(
    overlay, overlay_id, title, enabled_key, x_key, y_key,
):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_planet_materials_bridge",
        template="planet-materials-overlay",
        snapshot_key="planet_materials",
        model_attr="_html_render_model",
        log_name="Planet Materials",
        width=440, min_height=190, default_height=390, max_height=680,
    )
