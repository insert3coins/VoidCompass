"""BioStripHUD — transient overlay showing bio-signal genus/species value info
for the body currently being scanned.

Follows a confirmed > detected > predicted priority, same as
exploration_window.py's _bio_value_text/_bio_spacing_text:
  1. organic_scans (from ScanOrganic) — real species, sample progress, real value.
  2. genuses (from SAASignalsFound/FSSBodySignals) — genus names only, no value yet.
  3. predicted_genuses (from Scan/DSS heuristics) — pre-scan value-range estimate.

Auto-hides after a timeout, same pattern as ProspectorHUD.
"""

import tkinter as tk
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import bio_values
import overlay_chrome

_CHROMA = "#ff00ff"
_DIM = "#7a8a98"
_GREEN = "#54e39a"


def _fmt_credits(n):
    try:
        n = int(n or 0)
    except Exception:
        return "--"
    for suffix, div in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if n >= div:
            return f"{n/div:.1f}{suffix}"
    return f"{n:,}"


class BioStripHUD:
    WIDTH = 440
    MAX_ROWS = 6
    _HEADER_H = 40
    _ROW_H = 18
    _MIN_H = 70

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._hide_job = None
        self._body_name = None
        self._rows = []  # list of (name, detail, color)

        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", True, "-transparentcolor", _CHROMA, "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg=_CHROMA)

        self.canvas = tk.Canvas(self.win, width=self.WIDTH, height=self._MIN_H, bg=_CHROMA, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        # Right side by default — gravity_warning_hud shares this column
        # below it, keeping both clear of the left-edge overlay stack
        # (system info / carrier / station info / survey status).
        screen_w = root.winfo_screenwidth()
        default_x = max(30, screen_w - self.WIDTH - 30)
        x = self._safe_int(config.get("bio_strip_hud_x"), default_x)
        y = self._safe_int(config.get("bio_strip_hud_y"), 320)
        self.win.geometry(f"+{x}+{y}")

        self._force_topmost()
        self.win.withdraw()

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
        try:
            x = self._safe_int(self.config.get("bio_strip_hud_x"), 30)
            y = self._safe_int(self.config.get("bio_strip_hud_y"), 320)
            self.win.geometry(f"+{x}+{y}")
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def hide(self):
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
        timeout_s = max(5, int(self.config.get("bio_strip_hud_timeout_s") or 30))
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    # ── Data interface ───────────────────────────────────────────────────

    def update_from_item(self, body_name, item):
        """item is a dashboard scan_items entry (see dashboard_scan_mixin.py)."""
        if not item:
            return
        organic_scans = item.get("organic_scans") or {}
        genuses = item.get("genuses") or []
        predicted = item.get("predicted_genuses") or []
        if not (organic_scans or genuses or predicted):
            return

        rows = []
        confirmed_names = set()
        for scan in organic_scans.values():
            species = scan.get("species") or "Organic"
            confirmed_names.add((scan.get("genus") or species))
            sample_idx = scan.get("sample_idx")
            max_samples = scan.get("max_samples") or 3
            if scan.get("is_complete"):
                value = scan.get("species_value")
                detail = f"{_fmt_credits(value)} CR  ✓ complete" if value else "complete"
                color = _GREEN
            else:
                progress = f"{sample_idx}/{max_samples}" if sample_idx is not None else "scanning"
                detail = f"sample {progress}"
                color = COLOR_ACCENT
            rows.append((species, detail, color))

        for genus in genuses:
            if genus in confirmed_names:
                continue
            info = bio_values.genus_info(genus)
            lo, hi = info.get("min_value"), info.get("max_value")
            value_txt = "value unknown"
            if lo and hi:
                value_txt = _fmt_credits(lo) if lo == hi else f"{_fmt_credits(lo)}-{_fmt_credits(hi)}"
            spacing = info.get("colony_m")
            spacing_txt = f"{int(spacing):,}m spacing" if spacing else ""
            detail = "  ·  ".join(p for p in (value_txt + " CR", spacing_txt) if p)
            rows.append((genus, detail, COLOR_ORANGE))

        if not rows:
            for pred in predicted[:self.MAX_ROWS]:
                lo, hi = pred.get("min_value"), pred.get("max_value")
                value_txt = "?"
                if lo and hi:
                    value_txt = _fmt_credits(lo) if lo == hi else f"{_fmt_credits(lo)}-{_fmt_credits(hi)}"
                spacing = pred.get("colony_m")
                spacing_txt = f"{int(spacing):,}m" if spacing else ""
                detail = "  ·  ".join(p for p in (f"~{value_txt} CR", spacing_txt) if p)
                rows.append((pred.get("name") or "Organic", detail, _DIM))
            if rows:
                rows.insert(0, ("(predicted, not yet detected)", "", _DIM))

        if not rows:
            return

        self._body_name = body_name
        self._rows = rows[:self.MAX_ROWS]
        self._redraw()
        self.show()
        self._schedule_hide()

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        self.config["bio_strip_hud_x"] = self.win.winfo_x()
        self.config["bio_strip_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _redraw(self):
        w = self.WIDTH
        h = max(self._MIN_H, self._HEADER_H + len(self._rows) * self._ROW_H + 10)
        self.canvas.config(width=w, height=h)
        self.win.geometry(f"{w}x{h}")
        self.canvas.delete("all")

        overlay_chrome.draw_chrome(self.canvas, w, h, bracket_len=10)
        self._text(16, 16, "☘  BIO SIGNALS", COLOR_ACCENT, ("Courier", 10, "bold"))
        body_label = (self._body_name or "").upper()
        self._text(w - 16, 16, body_label if len(body_label) <= 22 else body_label[:21] + "…",
                    COLOR_TEXT, ("Courier", 8, "bold"), anchor="e")
        self.canvas.create_line(16, 28, w - 16, 28, fill="#1a2530", width=1)

        y = self._HEADER_H
        for name, detail, color in self._rows:
            self._text(16, y, name, color, ("Courier", 9, "bold"))
            self._text(w - 16, y, detail, color, ("Courier", 8, "bold"), anchor="e")
            y += self._ROW_H
