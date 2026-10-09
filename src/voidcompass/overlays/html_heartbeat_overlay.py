"""Dedicated semantic HTML renderer for the journal watcher orb."""

from voidcompass.overlays.heartbeat_hud import orb_size
from voidcompass.overlays.watcher_mind import THOUGHT_SIZES
from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    attach_html_model_overlay,
)


# Room for one of the Watcher's thoughts beside the orb (design px).
THOUGHT_WIDTH = 330


class HtmlHeartbeatBridge(HtmlModelOverlayBridge):
    """The orb is a square window of the size chosen in Overlay Studio,
    wider only while the Watcher shares a thought beside it. The Music
    player's live levels reach it at /api/live, so the eye moves with the
    music (5.5.3.2)."""

    levels = None

    def set_enabled(self, enabled):
        live = super().set_enabled(enabled)
        register = getattr(getattr(self.surface, "server", None), "set_live_provider", None)
        if live and callable(register):
            register(self.overlay_id, lambda: self.levels() if callable(self.levels) else {})
        return live

    def _thought(self):
        if getattr(self, "overlay", None) is None:
            return None
        return (self._model() or {}).get("thought")

    def _thought_width(self, thought):
        size = THOUGHT_SIZES.get(((thought or {}).get("style") or {}).get("size"), 1.0)
        return int(round(THOUGHT_WIDTH * size * self._text_scale()))

    def _dimensions(self):
        size = orb_size(self.config)
        thought = self._thought()
        if thought:
            # A large thought on a small orb needs a little more height too.
            scale = THOUGHT_SIZES.get((thought.get("style") or {}).get("size"), 1.0)
            return size + self._thought_width(thought), max(size, int(round(54 * scale * self._text_scale())))
        return size, size

    def _window_payload(self):
        payload = super()._window_payload()
        thought = self._thought()
        # The orb alone is a round window (5.5.3.3): the host clips it to a
        # circle, so its corners never show, whatever the graphics card does
        # with transparent pixels. A thought beside it needs the rectangle.
        payload["shape"] = "rect" if thought else "circle"
        if thought and thought.get("side") == "left":
            # Grow to the left, keeping the orb where it is.
            payload["x"] = int(payload["x"]) - self._thought_width(thought)
        return payload


def attach_html_heartbeat_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key, levels=None):
    size = orb_size(getattr(overlay, "config", {}))
    attached = attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_heartbeat_bridge", template="heartbeat",
        snapshot_key="heartbeat", model_attr="_html_render_model",
        log_name="Journal Heartbeat", width=size,
        min_height=size, default_height=size, max_height=size,
        bridge_class=HtmlHeartbeatBridge,
    )
    bridge = getattr(overlay, "_html_heartbeat_bridge", None)
    if bridge is not None:
        bridge.levels = levels
    return attached
