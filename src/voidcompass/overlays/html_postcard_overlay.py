"""Semantic HTML renderer attachment for Postcards (5.5.3.7)."""

from voidcompass.overlays.html_model_overlay import HtmlModelOverlayBridge, attach_html_model_overlay
from voidcompass.overlays.postcards import SIZES, postcard_options


class HtmlPostcardBridge(HtmlModelOverlayBridge):
    """As wide as Overlay Studio's card size (grown with the overlay text
    size), as tall as the page measures; each card's photo is served by id
    at /api/file?name=photo-<id>."""

    def set_enabled(self, enabled):
        live = super().set_enabled(enabled)
        register = getattr(getattr(self.surface, "server", None), "set_file_provider", None)
        if live and callable(register):
            register(self.overlay_id, self._file)
        return live

    def _file(self, name):
        if not str(name).startswith("photo-"):
            return None
        photo = getattr(self.overlay, "photo", None)
        found = photo(str(name)[6:]) if callable(photo) else None
        return (found, "image/jpeg") if found else None

    def _dimensions(self):
        self.width = SIZES[postcard_options(self.config)["size"]] + 40  # room for the tilt and the stack
        return super()._dimensions()


def attach_html_postcard_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_postcard_bridge", template="postcards",
        snapshot_key="postcards", model_attr="_html_render_model",
        log_name="Postcards", width=SIZES["standard"] + 40,
        min_height=120, default_height=330, max_height=760,
        bridge_class=HtmlPostcardBridge,
    )
