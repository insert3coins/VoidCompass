"""Dedicated semantic HTML renderer for the music player overlay."""

from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    attach_html_model_overlay,
)
from voidcompass.overlays.music_player_hud import music_overlay_size, music_text_scale


class HtmlMusicPlayerBridge(HtmlModelOverlayBridge):
    """Sized by its layout and text size, and hidden after a long pause.

    The visualizer's levels change many times a second, far faster than a
    snapshot should be republished, so the page reads them from the overlay
    server's live endpoint instead (`levels`, provided by the dashboard).
    """

    levels = None

    def _dimensions(self):
        return music_overlay_size(self.config)

    def _window_payload(self):
        payload = super()._window_payload()
        hidden = getattr(self.overlay, "hidden_while_idle", None)
        if callable(hidden) and hidden():
            payload["visible"] = False
        return payload

    def _snapshot(self):
        payload = super()._snapshot()
        # The overlay can have its own text size, not only the shared one.
        payload["effects"]["text_scale"] = music_text_scale(self.config)
        return payload

    def set_enabled(self, enabled):
        live = super().set_enabled(enabled)
        register = getattr(getattr(self.surface, "server", None), "set_live_provider", None)
        if live and callable(register):
            register(self.overlay_id, lambda: self.levels() if callable(self.levels) else {})
        return live


def attach_html_music_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key, levels=None):
    config = getattr(overlay, "config", {})
    width, height = music_overlay_size(config)
    attached = attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_music_bridge", template="music_player",
        snapshot_key="music", model_attr="_html_render_model",
        log_name="Music Player", width=width,
        min_height=height, default_height=height, max_height=height,
        bridge_class=HtmlMusicPlayerBridge,
    )
    bridge = getattr(overlay, "_html_music_bridge", None)
    if bridge is not None:
        bridge.levels = levels
    return attached
