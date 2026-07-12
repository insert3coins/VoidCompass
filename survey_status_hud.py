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

    def update(self, system_name, scanned, total, scan_items, body_signals, sampling=None):
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

        if not remaining and not sampling:
            # Nothing left to map — the nav HUD's own progress readout
            # already communicates "100%"; no unique info left to show here.
            self.hide()
            return

        self._redraw(system_name, remaining, bio_remaining, sampling=sampling)
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

    _MAX_LINES = 4
    _MAX_CONSIDERED = 30

    def _wrap_names(self, shown):
        """Greedily packs (name, has_bio) tuples into up to _MAX_LINES lines
        that each fit WIDTH, returning (lines, extra_count) where lines is a
        list of lists of (name, has_bio, display_text)."""
        measurer = tkfont.Font(family="Courier", size=8, weight="bold")
        max_x = WIDTH - 36
        lines = []
        current = []
        cur_w = 0
        i = 0
        n = len(shown)
        while i < n and len(lines) < self._MAX_LINES:
            name, has_bio = shown[i]
            text = name if i == n - 1 else f"{name},"
            w = measurer.measure(text + " ")
            if current and cur_w + w > max_x:
                lines.append(current)
                current = []
                cur_w = 0
                continue
            current.append((name, has_bio, text))
            cur_w += w
            i += 1
        if current:
            lines.append(current)
        return lines, n - i

    def _redraw(self, system_name, remaining, bio_remaining, sampling=None):
        w = WIDTH
        shown = remaining[:self._MAX_CONSIDERED]
        lines, extra_from_wrap = self._wrap_names(shown)
        extra_count = extra_from_wrap + (len(remaining) - len(shown))

        if extra_count and lines:
            measurer = tkfont.Font(family="Courier", size=8, weight="bold")
            max_x = WIDTH - 36
            last_line = lines[-1]

            def _line_w(line):
                return sum(measurer.measure(t + " ") for _, _, t in line)

            while last_line and _line_w(last_line) + measurer.measure(f"+{extra_count} more") > max_x:
                last_line.pop()
                extra_count += 1
            if not last_line:
                lines.pop()

        header_h, label_h, line_h, bottom_pad = 30, 16, 16, 10
        sample_h = 18 if sampling else 0
        remaining_h = (label_h + max(1, len(lines)) * line_h) if remaining else 0
        h = header_h + sample_h + remaining_h + bottom_pad

        self.canvas.config(width=w, height=h)
        self.win.geometry(f"{w}x{h}")
        self.canvas.delete("all")

        overlay_chrome.draw_chrome(self.canvas, w, h, bracket_len=10)
        self._text(18, 18, "SURVEY STATUS", COLOR_ACCENT, ("Courier", 9, "bold"))
        self._text(w - 18, 18, _truncate((system_name or "").upper(), 30), COLOR_TEXT, ("Courier", 9, "bold"), anchor="e")
        self.canvas.create_line(18, 28, w - 18, 28, fill="#1a2530", width=1)

        label_y = 42
        if sampling:
            progress = int(sampling.get("progress") or 1)
            colony = sampling.get("colony_m")
            minimum = sampling.get("min_distance_m")
            clear = sampling.get("clear")
            status = "CLEAR" if clear else (f"{minimum:,}/{colony:,} M" if minimum is not None and colony else "MOVE TO NEXT SAMPLE")
            self._text(18, label_y, f"SAMPLE {progress}/3 · {_truncate(sampling.get('species'), 28)}", COLOR_ORANGE, ("Courier", 8, "bold"))
            self._text(w - 18, label_y, status, "#21d189" if clear else COLOR_TEXT,
                       ("Courier", 8, "bold"), anchor="e")
            label_y += 18

        if remaining:
            label = f"DSS REMAINING ({len(remaining)})"
            self._text(18, label_y, label, _DIM, ("Courier", 7, "bold"))
            if bio_remaining:
                self._text(w - 18, label_y, f"BIO REMAINING {bio_remaining}", COLOR_ORANGE, ("Courier", 7, "bold"), anchor="e")

        font = ("Courier", 8, "bold")
        measurer = tkfont.Font(family="Courier", size=8, weight="bold")
        y = label_y + line_h
        for line_idx, line in enumerate(lines):
            x = 18
            for name, has_bio, text in line:
                color = COLOR_ORANGE if has_bio else _DIM
                self._text(x, y, text, color, font)
                x += measurer.measure(text + " ")
            if line_idx == len(lines) - 1 and extra_count:
                self._text(x, y, f"+{extra_count} more", _DIM, font)
            y += line_h
