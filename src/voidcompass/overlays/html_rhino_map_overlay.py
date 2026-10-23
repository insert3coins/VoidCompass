"""Semantic HTML renderer attachment for the Rhino Map (5.5.18)."""

from voidcompass.overlays.galaxy_minimap_hud import STRIP_PX
from voidcompass.overlays.html_model_overlay import HtmlModelOverlayBridge, _integer, attach_html_model_overlay
from voidcompass.overlays.rhino_map_hud import rhino_map_size

# The strip under the map: one line, up to three when its warnings wrap.
STRIP_LINES = 3


class HtmlRhinoMapBridge(HtmlModelOverlayBridge):
    """Sized as every overlay is (overlayfix.md): its square map's size from
    Overlay Studio times the text size, the height from what the page
    measures (the map and its strip), so a wrapped warning is never cut."""

    def _dimensions(self):
        scale = self._text_scale()
        size = rhino_map_size(self.config)
        low = int(round((size + STRIP_PX) * scale))
        high = int(round((size + STRIP_PX * STRIP_LINES) * scale))
        measured = _integer(self._browser_content_height, 0) or low
        return int(round(size * scale)), max(low, min(high, measured))


def attach_html_rhino_map_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    size = rhino_map_size(getattr(overlay, "config", {}))
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_rhino_map_bridge", template="rhino_map",
        snapshot_key="rhino", model_attr="_html_render_model",
        log_name="Rhino Map", width=size,
        min_height=size + STRIP_PX, default_height=size + STRIP_PX, max_height=size + STRIP_PX * STRIP_LINES,
        bridge_class=HtmlRhinoMapBridge,
    )
