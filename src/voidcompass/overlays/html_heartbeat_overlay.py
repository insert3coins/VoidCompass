"""Dedicated semantic HTML renderer for the journal watcher orb."""

import math
import textwrap

from voidcompass.core.display_scale import monitor_bounds, monitor_scale
from voidcompass.overlays.heartbeat_hud import (
    heartbeat_text_scale, orb_size, place_thought, thought_side_setting,
)
from voidcompass.overlays.watcher_mind import THOUGHT_SIZES, thought_style
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
# The heading above the words (5.5.3.5): one line at .78 of the thought's
# font, and a 3px gap below it.
THOUGHT_HEADING_EM, THOUGHT_HEADING_GAP_PX = .78, 3
# A passage of its story is set off by a rule beside it: 2px and 6px clear.
RULED_KINDS, THOUGHT_RULE_PX = ("memory", "afterword", "recall"), 8


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

    def _text_scale(self):
        """The Watcher's own text size from Overlay Studio, or all overlays'
        (5.5.3.5). The page reads it from the snapshot's effects too."""
        return heartbeat_text_scale(getattr(self, "config", {}))

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
        if thought.get("kind") in RULED_KINDS:
            text_width -= THOUGHT_RULE_PX
        per_line = max(8, int(text_width // (font * THOUGHT_ADVANCE_EM)))
        # One more character for the typing caret at the end.
        lines = max(1, len(textwrap.wrap(str(thought.get("text") or "") + "_", per_line)))
        height = lines * font * THOUGHT_LINE_EM + THOUGHT_BACKDROP_PX + 6
        if (thought.get("style") or {}).get("heading", True):
            height += font * THOUGHT_HEADING_EM * THOUGHT_LINE_EM + THOUGHT_HEADING_GAP_PX
        return int(math.ceil(height))

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
        self._thought_layout = None
        if thought:
            # The window grows in screen pixels (the host scales it to the
            # monitor) around the orb, which stays where it is: the words on
            # the side asked for if they fit on its monitor, else the other;
            # up and down alike, or away from a screen edge (5.5.3.5).
            size = orb_size(getattr(self, "config", {}))
            orb_x, orb_y = int(payload["x"]), int(payload["y"])
            scale = monitor_scale(orb_x + size // 2, orb_y + size // 2)
            height = int(payload.get("height") or size)  # from _dimensions, just now
            side, payload["x"], payload["y"] = place_thought(
                "left" if thought.get("side") == "left" else "right",
                orb_x, orb_y, size * scale, self._thought_width(thought) * scale, height * scale,
                monitor_bounds(orb_x + size * scale / 2, orb_y + size * scale / 2))
            # Where the page puts the orb: its top, in the page's own px.
            self._thought_layout = {"side": side, "orb_top": max(0, int(round((orb_y - payload["y"]) / scale)))}
        return payload

    def _snapshot(self):
        payload = super()._snapshot()  # the window (and the layout) first
        thought = (payload.get(self.snapshot_key) or {}).get("thought")
        layout = getattr(self, "_thought_layout", None)
        if isinstance(thought, dict) and layout:
            thought.update(layout)
        return payload


def thought_zone(config, x, y):
    """Where the Watcher's words go beside the orb, for its Overlay Studio card
    (5.5.3.5): {"side", "x", "y", "width", "height"}, the words' own area in
    screen px, for a three-line thought. The card is the orb alone with this
    beside it; it used to take the window a thought had stretched, which ran
    off the display."""
    size = orb_size(config)
    text = heartbeat_text_scale(config)
    style = thought_style(config)
    width = int(round(THOUGHT_WIDTH * THOUGHT_SIZES.get(style["size"], 1.0) * text))
    font = THOUGHT_FONT_PX.get(style["size"], THOUGHT_FONT_PX["standard"]) * text
    height = 3 * font * THOUGHT_LINE_EM + THOUGHT_BACKDROP_PX + 6
    if style["heading"]:
        height += font * THOUGHT_HEADING_EM * THOUGHT_LINE_EM + THOUGHT_HEADING_GAP_PX
    height = max(size, int(math.ceil(height)))
    scale = monitor_scale(x + size // 2, y + size // 2)
    bounds = monitor_bounds(x + size * scale / 2, y + size * scale / 2)
    side = thought_side_setting(config)
    if side == "auto":
        side = "left" if bounds and x + size * scale / 2 > (bounds[0] + bounds[2]) / 2 else "right"
    words_px, height_px = int(round(width * scale)), int(round(height * scale))
    side, left, top = place_thought(side, x, y, size * scale, words_px, height_px, bounds)
    if side == "right":
        left = x + int(round(size * scale))
    return {"side": side, "x": left, "y": top, "width": words_px, "height": height_px}


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
