"""Semantic HTML renderer attachment for Jump Info."""

from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    _integer,
    attach_html_model_overlay,
)


class HtmlJumpInfoBridge(HtmlModelOverlayBridge):
    """The page sets its type by the overlay text size, so the window widens
    with it rather than wrapping every line."""

    def _dimensions(self):
        width, height = super()._dimensions()
        scale = max(75, min(200, _integer(self.config.get("overlay_text_scale_percent"), 100))) / 100.0
        return int(round(width * scale)), height


def attach_html_jump_info_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_jump_info_bridge", template="jump_info",
        snapshot_key="jump", model_attr="_html_render_model",
        log_name="Jump Info", width=560,
        min_height=96, default_height=180, max_height=640,
        bridge_class=HtmlJumpInfoBridge,
    )
