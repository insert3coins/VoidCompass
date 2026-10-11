"""Semantic HTML renderer attachment for the Galaxy Minimap (5.5.3.7)."""

from functools import lru_cache
import json

from voidcompass.exploration.galactic_regions import region_raster
from voidcompass.overlays.galaxy_minimap_hud import STRIP_PX, minimap_options, minimap_text_scale
from voidcompass.overlays.html_model_overlay import HtmlModelOverlayBridge, attach_html_model_overlay


@lru_cache(maxsize=1)
def _regions_json():
    """The Codex region raster, as the Galactic Atlas takes it (its page
    decodes it with the atlas's own regions.js). About 0.5 MB, asked for once
    when the minimap's page loads."""
    return json.dumps(region_raster(), separators=(",", ":")).encode("utf-8")


def minimap_file(name):
    if name == "regions":
        return _regions_json(), "application/json; charset=utf-8"
    return None


class HtmlGalaxyMinimapBridge(HtmlModelOverlayBridge):
    """A square map of the size chosen in Overlay Studio, with a strip under
    it for the region's name (the strip grows with the overlay text size)."""

    def set_enabled(self, enabled):
        live = super().set_enabled(enabled)
        register = getattr(getattr(self.surface, "server", None), "set_file_provider", None)
        if live and callable(register):
            register(self.overlay_id, minimap_file)
        return live

    def _text_scale(self):
        """Its own text size from Overlay Studio, or all overlays' (5.5.3.7):
        the strip and the region names. The snapshot carries it to the page."""
        return minimap_text_scale(getattr(self, "config", {}))

    def _dimensions(self):
        size = minimap_options(self.config)["size"]
        return size, size + int(round(STRIP_PX * self._text_scale()))


def attach_html_galaxy_minimap_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    size = minimap_options(getattr(overlay, "config", {}))["size"]
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_galaxy_minimap_bridge", template="galaxy_minimap",
        snapshot_key="minimap", model_attr="_html_render_model",
        log_name="Galaxy Minimap", width=size,
        min_height=size, default_height=size + STRIP_PX, max_height=size + STRIP_PX * 2,
        bridge_class=HtmlGalaxyMinimapBridge,
    )
