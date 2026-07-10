"""SurveyStatusHUD — persistent (non-auto-hiding) "what's left to survey"
strip for the current system, modeled on SrvSurvey's PlotSysStatus.

Unlike the other chroma-key overlays in this app, this one stays visible
for the whole time a system has un-DSS-mapped bodies rather than
auto-hiding. It deliberately does NOT repeat the scanned/total percentage
already shown on the navigation HUD's SCAN PROGRESS row — its only job is
to name which specific bodies still need mapping and flag the bio-bearing
ones, so it hides itself once nothing is left to add.
"""

import tkinter as tk
import tkinter.font as tkfont
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome

_CHROMA = "#ff00ff"
_DIM = "#7a8a98"

WIDTH = 460


def _truncate(text, max_chars):
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


class SurveyStatusHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config

        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", True, "-transparentcolor", _CHROMA, "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg=_CHROMA)

        self.canvas = tk.Canvas(self.win, width=WIDTH, height=90, bg=_CHROMA, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        x = self._safe_int(config.get("survey_status_hud_x"), 30)
        y = self._safe_int(config.get("survey_status_hud_y"), 520)
        self.win.geometry(f"+{x}+{y}")

        self._force_topmost()
        self.win.withdraw()
        self._visible = False

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self._force_topmost)

    def show(self):
        if self._visible:
            return
        try:
            x = self._safe_int(self.config.get("survey_status_hud_x"), 30)
            y = self._safe_int(self.config.get("survey_status_hud_y"), 500)
            self.win.geometry(f"+{x}+{y}")
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self._visible = True
        except Exception:
            pass

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass
        self._visible = False

    # ── Data interface ───────────────────────────────────────────────────

    def update(self, system_name, scanned, total, scan_items, body_signals):
        if int(total or 0) <= 0:
            self.hide()
            return

        remaining = []
        bio_remaining = 0
        for item in (scan_items or []):
            if item.get("is_star"):
                continue
            bio_count = int(item.get("bio_count") or 0)
            complete = int(item.get("organic_complete_count") or 0)
            if bio_count > complete:
                bio_remaining += 1
            if not item.get("dss_complete"):
                remaining.append((item.get("name") or "?", bio_count > 0))

        if not remaining:
            # Nothing left to map — the nav HUD's own progress readout
            # already communicates "100%"; no unique info left to show here.
            self.hide()
            return

        self._redraw(system_name, remaining, bio_remaining)
        self.show()

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        self.config["survey_status_hud_x"] = self.win.winfo_x()
        self.config["survey_status_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _redraw(self, system_name, remaining, bio_remaining):
        w = WIDTH
        h = 66
        self.canvas.config(width=w, height=h)
        self.win.geometry(f"{w}x{h}")
        self.canvas.delete("all")

        overlay_chrome.draw_chrome(self.canvas, w, h, bracket_len=10)
        self._text(18, 18, "SURVEY STATUS", COLOR_ACCENT, ("Courier", 9, "bold"))
        self._text(w - 18, 18, _truncate((system_name or "").upper(), 30), COLOR_TEXT, ("Courier", 9, "bold"), anchor="e")
        self.canvas.create_line(18, 28, w - 18, 28, fill="#1a2530", width=1)

        names_y = 42
        label = f"DSS REMAINING ({len(remaining)})"
        self._text(18, names_y, label, _DIM, ("Courier", 7, "bold"))
        if bio_remaining:
            self._text(w - 18, names_y, f"BIO REMAINING {bio_remaining}", COLOR_ORANGE, ("Courier", 7, "bold"), anchor="e")

        shown = remaining[:10]
        self._draw_name_list(18, 56, shown, len(remaining) - len(shown))

    def _draw_name_list(self, x, y, shown, extra_count):
        cur_x = x
        max_x = WIDTH - 18
        font = ("Courier", 8, "bold")
        measurer = tkfont.Font(family="Courier", size=8, weight="bold")
        for i, (name, has_bio) in enumerate(shown):
            color = COLOR_ORANGE if has_bio else _DIM
            text = name if i == len(shown) - 1 and not extra_count else f"{name},"
            width = measurer.measure(text + " ")
            if cur_x + width > max_x:
                break
            self._text(cur_x, y, text, color, font)
            cur_x += width
        if extra_count:
            self._text(min(cur_x, max_x), y, f" +{extra_count} more", _DIM, font)
