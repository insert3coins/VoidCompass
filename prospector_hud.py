"""
ProspectorHUD — transparent canvas overlay that pops up on ProspectedAsteroid.

Shows material proportions, content level, core status, and a running
refined-since-prospect counter.  Auto-hides after a configurable timeout.
Follows the same pattern as ScanHUD and CargoHUD.
"""

import tkinter as tk
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome

# Chroma-key colour used for window transparency (must never appear in content)
_CHROMA = "#ff00ff"

# Content level → (display label, bar/text colour)
_CONTENT = {
    "high":   ("HIGH",   "#57F287"),
    "medium": ("MED",    "#FEE75C"),
    "med":    ("MED",    "#FEE75C"),
    "low":    ("LOW",    "#888888"),
}

_BAR_BG   = "#1c2830"   # unfilled bar track colour
_DARK_SEP = "#1a2228"   # subtle separator colour


def _content_info(raw):
    """Return (label, colour) for Content field, handling both raw tokens and localised."""
    s = (raw.get("Content_Localised") or raw.get("Content") or "").lower()
    s = s.replace("$asteroidmaterialcontent_", "").replace(";", "").strip()
    if "high" in s:
        return _CONTENT["high"]
    if "med" in s:
        return _CONTENT["medium"]
    if "low" in s:
        return _CONTENT["low"]
    return (s.upper() or "?", COLOR_TEXT)


def _mining_type(raw):
    """Return human-readable mining type (Metallic / Rocky / Icy …)."""
    s = (raw.get("MiningType_Localised") or raw.get("MiningType") or "").lower()
    s = s.replace("$asteroidtype_", "").replace(";", "").strip()
    return s.title() or "Asteroid"


def _mat_name(item):
    """Return cleaned material name from a Materials list entry."""
    s = item.get("Name_Localised") or item.get("Name") or ""
    # strip game token formatting: $Alexandrite; → Alexandrite
    s = s.strip()
    if s.startswith("$"):
        s = s[1:]
    if s.endswith(";"):
        s = s[:-1]
    return s.title()


def _core_name(raw):
    """Return cleaned motherlode/core material name, or None."""
    s = raw.get("MotherlodeMaterial_Localised") or raw.get("MotherlodeMaterial")
    if not s:
        return None
    s = s.strip()
    if s.startswith("$"):
        s = s[1:]
    if s.endswith(";"):
        s = s[:-1]
    return s.title() or None


class ProspectorHUD:
    WIDTH = 340         # fixed overlay width in pixels
    MAX_MATERIALS = 10  # max material rows rendered

    # Layout constants
    _HEADER_H  = 52     # height of header section (title + subtitle + separator)
    _CORE_H    = 26     # extra height for core row when present
    _MAT_H     = 20     # height per material row
    _FOOTER_H  = 34     # height for refined footer
    _MIN_H     = 110    # minimum overlay height

    def __init__(self, root, config):
        self.root    = root
        self.config  = config

        self._last_raw  = None   # last ProspectedAsteroid raw dict
        self._refined   = {}     # material → ton count since last prospect
        self._hide_job  = None
        self._timeout_ms = max(
            5000,
            int((config.get("prospector_hud_timeout_s") or 45)) * 1000
        )

        # ── Transparent topmost window ────────────────────────────────────
        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)

        self.canvas = tk.Canvas(
            self.win,
            width=self.WIDTH, height=self._MIN_H,
            bg=overlay_bg, highlightthickness=0,
        )
        self.canvas.pack()

        # Drag bindings
        self.canvas.bind("<Button-1>",        self._drag_start)
        self.canvas.bind("<B1-Motion>",        self._drag_move)
        self.canvas.bind("<ButtonRelease-1>",  self._drag_end)

        # Restore saved position (default: bottom-left area)
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        default_x = 30
        default_y = max(30, screen_h - 320)
        x = int(config.get("prospector_hud_x", default_x))
        y = int(config.get("prospector_hud_y", default_y))
        self.win.geometry(overlay_chrome.position_geometry(x, y))

        self._force_topmost()
        self.win.withdraw()  # start hidden; shown on first ProspectedAsteroid

    # ── Overlay lifecycle ─────────────────────────────────────────────────

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self._force_topmost)

    def show(self):
        try:
            # Restore saved position before making the window visible.
            # winfo_x()/winfo_y() return 0 on withdrawn windows, so we
            # always drive position from config rather than the live geometry.
            x = int(self.config.get("prospector_hud_x", 30))
            y = int(self.config.get("prospector_hud_y", 600))
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def hide(self):
        """Hide immediately and cancel any pending auto-hide timer."""
        if self._hide_job:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        try:
            self.win.withdraw()
        except Exception:
            pass

    def _schedule_hide(self):
        if self._hide_job:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
        # Read timeout dynamically so settings changes take effect without restart.
        timeout_s = max(5, int(self.config.get("prospector_hud_timeout_s") or 45))
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    # ── Data interface ────────────────────────────────────────────────────

    def update(self, raw):
        """Process a ProspectedAsteroid journal event dict.

        Resets the refined counter, redraws, shows the overlay and starts
        the auto-hide countdown.
        """
        self._last_raw = raw
        self._refined  = {}
        self._redraw()
        self.show()
        self._schedule_hide()

    def add_refined(self, material):
        """Increment the refined-since-prospect counter for *material*.

        Called for every MiningRefined event that arrives after the last
        ProspectedAsteroid.  Redraws the footer immediately if visible.
        """
        if not material or not self._last_raw:
            return
        self._refined[material] = self._refined.get(material, 0) + 1
        self._redraw()

    # ── Drag-to-move ──────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    def _drag_end(self, event):
        self.config["prospector_hud_x"] = self.win.winfo_x()
        self.config["prospector_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ─────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        """Draw text with a 1-px drop-shadow for on-screen readability."""
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000",
                                font=font, anchor=anchor)
        self.canvas.create_text(x,     y,     text=text, fill=fill,
                                font=font, anchor=anchor)

    def _redraw(self):
        if not self._last_raw:
            return

        raw = self._last_raw
        w   = self.WIDTH

        # ── Parse journal data ────────────────────────────────────────────

        materials = []
        for item in raw.get("Materials") or []:
            name = _mat_name(item)
            if not name:
                continue
            prop = item.get("Proportion") or 0.0
            # journal reports 0.0–1.0; convert to percent
            if prop <= 1.0:
                prop = round(prop * 100.0, 1)
            else:
                prop = round(float(prop), 1)
            materials.append((name, prop))

        # Sort largest proportion first
        materials.sort(key=lambda m: m[1], reverse=True)
        shown = materials[:self.MAX_MATERIALS]

        core_mat  = _core_name(raw)
        remaining = raw.get("Remaining")
        remaining_txt = f"{remaining:.1f}%" if remaining is not None else "?"

        content_lbl, content_col = _content_info(raw)
        m_type = _mining_type(raw)

        # ── Calculate dynamic height ──────────────────────────────────────

        core_extra = self._CORE_H if core_mat else 0
        height = max(
            self._MIN_H,
            self._HEADER_H + core_extra + len(shown) * self._MAT_H + self._FOOTER_H,
        )

        self.canvas.config(width=w, height=height)
        # Only resize — never set position here.  winfo_x()/winfo_y() return 0
        # when the window is withdrawn, which would silently reset the overlay
        # to the top-left corner on every new prospect.  Position is set once
        # in show() from config, and live during drag via _drag_move().
        self.win.geometry(f"{w}x{height}")
        self.canvas.delete("all")

        # ── Background & border ───────────────────────────────────────────

        border_col = COLOR_ORANGE if core_mat else COLOR_ACCENT
        overlay_chrome.draw_chrome(self.canvas, w, height, accent=border_col, bracket_len=10)

        # ── Header ───────────────────────────────────────────────────────

        header_lbl = "◆  CORE ASTEROID  ◆" if core_mat else "⛏  PROSPECTOR RESULT"
        header_col = COLOR_ORANGE if core_mat else COLOR_ACCENT
        self._text(16, 16, header_lbl, header_col, ("Courier", 10, "bold"))

        subtitle = f"{m_type}  ·  {content_lbl}  ·  {remaining_txt} remaining"
        self._text(16, 33, subtitle, content_col, ("Courier", 9))

        sep_y = self._HEADER_H - 2
        self.canvas.create_line(16, sep_y, w - 16, sep_y, fill="#1a2530", width=1)

        y = self._HEADER_H + 2

        # ── Core material row ─────────────────────────────────────────────

        if core_mat:
            self._text(16, y + 9, f"★  Motherlode:  {core_mat}", COLOR_ORANGE,
                       ("Courier", 10, "bold"))
            y += self._CORE_H
            self.canvas.create_line(4, y - 2, w - 4, y - 2, fill=_DARK_SEP, width=1)

        # ── Material bars ─────────────────────────────────────────────────

        BAR_X   = 132          # label column ends here, bar starts
        BAR_END = w - 55       # bar ends here, percent label begins after
        BAR_W   = BAR_END - BAR_X
        BAR_H   = 8
        PCT_X   = BAR_END + 6

        max_prop = max((m[1] for m in shown), default=1.0) or 1.0

        for name, prop in shown:
            row_y    = y + 4
            is_core  = bool(core_mat and name.lower() == core_mat.lower())
            name_col = COLOR_ORANGE if is_core else COLOR_TEXT
            bar_col  = COLOR_ORANGE if is_core else COLOR_ACCENT

            # Truncate long names
            display = name if len(name) <= 17 else name[:16] + "…"
            self._text(16, row_y + 4, display, name_col, ("Courier", 9))

            # Bar track (background)
            self.canvas.create_rectangle(
                BAR_X, row_y + 1, BAR_END, row_y + BAR_H,
                fill=_BAR_BG, outline="",
            )
            # Bar fill
            fill_px = max(2, int(BAR_W * (prop / max_prop)))
            self.canvas.create_rectangle(
                BAR_X, row_y + 1, BAR_X + fill_px, row_y + BAR_H,
                fill=bar_col, outline="",
            )

            # Percentage
            self._text(PCT_X, row_y + 4, f"{prop:.1f}%", name_col, ("Courier", 8))

            y += self._MAT_H

        # ── Refined footer ────────────────────────────────────────────────

        self.canvas.create_line(4, y + 4, w - 4, y + 4, fill=_DARK_SEP, width=1)

        refined_total = sum(self._refined.values())
        if refined_total > 0:
            parts = "  ".join(f"{v}t {k}" for k, v in self._refined.items())
            self._text(16, y + 18, f"~{refined_total} t refined:  {parts}",
                       COLOR_ORANGE, ("Courier", 8))
        else:
            self._text(16, y + 18, "Awaiting refinement…",
                       "#444444", ("Courier", 8))
