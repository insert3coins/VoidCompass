"""Dedicated semantic HTML renderer for the journal watcher orb."""

import math
import textwrap

from voidcompass.core.display_scale import monitor_scale
from voidcompass.overlays.heartbeat_hud import orb_size
from voidcompass.overlays.watcher_mind import THOUGHT_SIZES
from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    attach_html_model_overlay,
)


# Room for one of the Watcher's thoughts beside the orb (design px).
THOUGHT_WIDTH = 330
# The thought's type (heartbeat/styles.css), by Studio's thought size: the
# font in px, and a monospaced character's advance (0.6em of Cascadia Mono
# plus its .02em letter spacing). Monospaced, so the wrapped height can be
# worked out here, before the page draws it.
THOUGHT_FONT_PX = {"small": 10.0, "standard": 11.5, "large": 13.5}
THOUGHT_ADVANCE_EM = .62
THOUGHT_LINE_EM = 1.3
# Around the words: the box's side padding and the line to the eye (34px),
# and the backdrop's padding and border (16px across, 8px down).
THOUGHT_SIDE_PX, THOUGHT_BACKDROP_PX = 50, 8


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

    def _thought_height(self, thought):
        """How tall the thought is once typed out (design px): its words
        wrapped to the box, line by line. The long lore passages (5.5.3.5)
        run to five or six lines, more on a small orb at large text."""
        size_name = (thought.get("style") or {}).get("size") or "standard"
        font = THOUGHT_FONT_PX.get(size_name, THOUGHT_FONT_PX["standard"]) * self._text_scale()
        text_width = self._thought_width(thought) - THOUGHT_SIDE_PX
        per_line = max(8, int(text_width // (font * THOUGHT_ADVANCE_EM)))
        # One more character for the typing caret at the end.
        lines = max(1, len(textwrap.wrap(str(thought.get("text") or "") + "_", per_line)))
        return int(math.ceil(lines * font * THOUGHT_LINE_EM + THOUGHT_BACKDROP_PX + 6))

    def _dimensions(self):
        size = orb_size(self.config)
        thought = self._thought()
        if thought:
            # A large thought on a small orb needs a little more height too,
            # and a long one (the lore) as many lines as it takes.
            scale = THOUGHT_SIZES.get((thought.get("style") or {}).get("size"), 1.0)
            height = max(size, int(round(54 * scale * self._text_scale())), self._thought_height(thought))
            return size + self._thought_width(thought), height
        return size, size

    def _window_payload(self):
        payload = super()._window_payload()
        thought = self._thought()
        # The orb alone is a round window (5.5.3.3): the host clips it to a
        # circle, so its corners never show, whatever the graphics card does
        # with transparent pixels. A thought beside it needs the rectangle.
        payload["shape"] = "rect" if thought else "circle"
        if thought:
            # The window grows in screen pixels (the host scales it to the
            # monitor), around the orb, which stays where it is: to the left
            # for a thought on that side, and up and down alike for a thought
            # taller than the orb (the page centres the orb in the window).
            size = orb_size(getattr(self, "config", {}))
            scale = monitor_scale(int(payload["x"]) + size // 2, int(payload["y"]) + size // 2)
            if thought.get("side") == "left":
                payload["x"] = int(payload["x"]) - int(round(self._thought_width(thought) * scale))
            height = int(payload.get("height") or size)  # from _dimensions, just now
            if height > size:
                payload["y"] = int(payload["y"]) - int(round((height - size) / 2 * scale))
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
