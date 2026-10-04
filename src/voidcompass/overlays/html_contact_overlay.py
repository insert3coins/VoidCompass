"""Semantic HTML renderer attachment for Deep Space Contact Scope."""

from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


def attach_html_contact_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_contact_bridge", template="contact_scope",
        snapshot_key="contacts", model_attr="_html_render_model",
        log_name="Deep Space Contacts", width=420,
        min_height=90, default_height=220, max_height=720,
    )
