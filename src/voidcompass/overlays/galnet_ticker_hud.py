"""GalnetTickerHUD — a scrolling Galnet news bar for the cockpit.

A GALNET badge, then each dispatch's headline followed by its story,
scrolling right to left like a news channel's ticker. The articles come from
the Galnet relay (services/galnet.py); this class keeps only the ticker's
model: which stories, how much of each, and the options chosen in Overlay
Studio. web/galnet_ticker draws and scrolls it.
"""
import re
import time

from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.core import themes
from voidcompass.overlays import overlay_chrome

TICKER_HEIGHT = 34
TICKER_WIDTH_RANGE = (360, 2560)
DEFAULT_TICKER_WIDTH = 860
# Scroll speeds in px per second at 100% text size.
TICKER_SPEEDS = {"slow": 45, "standard": 75, "fast": 115}
TICKER_CONTENT = ("headlines", "summary", "full")
TICKER_STORIES = (3, 5, 8, 16)
SUMMARY_CHARS = 280
FULL_CHARS = 1600


def _integer(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def ticker_options(config):
    """The ticker's Overlay Studio options, each within its allowed values."""
    config = config or {}
    speed = str(config.get("galnet_ticker_speed") or "standard").casefold()
    content = str(config.get("galnet_ticker_content") or "summary").casefold()
    stories = _integer(config.get("galnet_ticker_stories"), 5)
    # The ticker's own text size; 0 follows the size set for all overlays.
    text_scale = _integer(config.get("galnet_ticker_text_scale_percent"), 0)
    low, high = TICKER_WIDTH_RANGE
    return {
        "width": max(low, min(high, _integer(config.get("galnet_ticker_width"), DEFAULT_TICKER_WIDTH))),
        "speed": speed if speed in TICKER_SPEEDS else "standard",
        "content": content if content in TICKER_CONTENT else "summary",
        "stories": stories if stories in TICKER_STORIES else 5,
        "show_date": bool(config.get("galnet_ticker_show_date", True)),
        "text_scale_percent": 0 if text_scale <= 0 else max(75, min(200, text_scale)),
    }


def ticker_text_scale(config):
    """The ticker's text size as a factor: its own, else all overlays' size."""
    own = ticker_options(config)["text_scale_percent"]
    chosen = own if own > 0 else _integer((config or {}).get("overlay_text_scale_percent"), 100)
    return max(75, min(200, chosen)) / 100.0


def ticker_text(body, content):
    """The part of a story the ticker reads after its headline."""
    text = re.sub(r"\s+", " ", str(body or "")).strip()
    if content == "headlines" or not text:
        return ""
    limit = SUMMARY_CHARS if content == "summary" else FULL_CHARS
    if len(text) <= limit:
        return text
    # Whole sentences where they fit, otherwise a clean word break.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = ""
    for sentence in sentences:
        candidate = f"{kept} {sentence}".strip()
        if len(candidate) > limit:
            break
        kept = candidate
    if kept:
        return kept
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


class GalnetTickerHUD:

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._feed = {}
        self._feed_enabled = True
        self._seen_ids = None
        self._new_ids = {}
        self._signature = None
        self._html_render_model = {}
        self._rebuild()
        self.win = OverlayWindowState(root)
        x = self._safe_int(config.get("galnet_ticker_hud_x"), 360)
        y = self._safe_int(config.get("galnet_ticker_hud_y"), 12)
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass

    def update_feed(self, galnet, enabled=True):
        """Take the relay's latest snapshot (the dashboard's Galnet model)."""
        self._feed = dict(galnet or {})
        self._feed_enabled = bool(enabled)
        self._rebuild()

    def apply_settings(self):
        """Overlay Studio changed the ticker's options."""
        self._rebuild()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

    def _rebuild(self):
        options = ticker_options(self.config)
        articles = [row for row in (self._feed.get("articles") or []) if isinstance(row, dict) and row.get("title")]
        signature = (
            tuple((row.get("id"), row.get("title")) for row in articles[: options["stories"]]),
            self._feed.get("status"), self._feed.get("busy"), self._feed_enabled,
            tuple(sorted(options.items())),
        )
        if signature == self._signature:
            return
        self._signature = signature
        ids = [str(row.get("id") or row.get("title")) for row in articles]
        # Dispatches that arrive while the ticker is up are marked new for a
        # while; whatever was already there when it started is not news.
        now = time.time()
        if self._seen_ids is None:
            if ids:
                self._seen_ids = set(ids)
        else:
            for identifier in ids:
                if identifier not in self._seen_ids:
                    self._seen_ids.add(identifier)
                    self._new_ids[identifier] = now
        self._new_ids = {key: at for key, at in self._new_ids.items() if now - at < 1800}
        stories = []
        for row, identifier in zip(articles, ids):
            if len(stories) >= options["stories"]:
                break
            stories.append({
                "id": identifier[:300],
                "title": str(row.get("title") or "")[:300],
                "text": ticker_text(row.get("body"), options["content"]),
                "stamp": str(row.get("stamp") or row.get("published") or "")[:40],
                "new": identifier in self._new_ids,
            })
        if not self._feed_enabled:
            status = "off"
        elif self._feed.get("busy") and not stories:
            status = "receiving"
        elif stories:
            status = "live"
        elif str(self._feed.get("status") or "") == "error":
            status = "error"
        else:
            status = "waiting"
        self._html_render_model = {
            "status": status,
            "busy": bool(self._feed.get("busy")),
            "detail": str(self._feed.get("detail") or "")[:180],
            "stories": stories,
            "options": {**options, "px_per_second": TICKER_SPEEDS[options["speed"]]},
        }
