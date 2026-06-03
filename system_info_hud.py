import json
import tkinter as tk
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_BG, COLOR_TEXT

WIDTH   = 460
PAD     = 12
ROW_H   = 22
HDR_H   = 44

_CHROMA = "#ff00ff"

_COL_DIM    = "#5a6a78"
_COL_STAR   = "#e8c97a"
_COL_BIO    = "#7ec89a"
_COL_WARN   = "#e07040"
_COL_POP    = "#8ab4cc"

_ICONS = {
    "Earthlike body":        "ELW",
    "Water world":           "WW",
    "Ammonia world":         "AMM",
    "terraformable":         "TF",
}

def _fmt_pop(n):
    try:
        n = int(n)
    except Exception:
        return ""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)

def _fmt_traffic(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return "-"

def _truncate(text, max_chars):
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


class SystemInfoHUD:
    def __init__(self, root, config):
        self.root   = root
        self.config = config

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", _CHROMA)
        self.win.configure(bg=_CHROMA)
        self.win.resizable(False, False)

        self.canvas = tk.Canvas(
            self.win, bg=_CHROMA, highlightthickness=0,
            width=WIDTH, height=HDR_H,
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>",      self._drag_start)
        self.canvas.bind("<B1-Motion>",     self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        x = int(config.get("system_info_hud_x", 30))
        y = int(config.get("system_info_hud_y", 30))
        self.win.geometry(f"+{x}+{y}")

        self._hide_job    = None
        self._save_job    = None
        self._dx = self._dy = 0

        # Current data
        self._system      = ""
        self._star_class  = ""
        self._body_count  = 0          # total expected bodies
        self._scanned_count = 0        # bodies scanned so far
        self._bio_total   = 0          # total bio signals across all bodies
        self._notable     = []         # list of (tag, name) e.g. ("ELW", "A 1")
        self._traffic     = None       # dict day/week/total (EDSM async)
        self._edsm_info   = None       # dict from EDSM system details (async)

        self._force_topmost()
        self.win.withdraw()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(ms, self._force_topmost)

    def show(self):
        x = int(self.config.get("system_info_hud_x", 30))
        y = int(self.config.get("system_info_hud_y", 30))
        self.win.geometry(f"+{x}+{y}")
        self._redraw()
        self.win.deiconify()
        self.win.attributes("-topmost", True)
        self.win.lift()
        self._schedule_hide()

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
        timeout_s = int(self.config.get("system_info_timeout_s", 30) or 30)
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    # ── Data interface ────────────────────────────────────────────────────

    def on_system_arrival(self, system_name, star_class,
                          scan_items, body_signals, total_bodies):
        """Called on FSDJump / Location with whatever we know immediately."""
        self._system      = system_name or "Unknown"
        self._star_class  = star_class or ""
        self._body_count  = int(total_bodies or 0)
        self._traffic     = None
        self._edsm_info   = None

        # Count scanned bodies and bio signals from in-memory state
        self._scanned_count = sum(
            1 for it in (scan_items or [])
            if not it.get("is_star")
        )
        self._bio_total = sum(
            s.get("bio", 0) for s in (body_signals or {}).values()
        )

        # Notable bodies from restored scan items
        self._notable = []
        for item in (scan_items or []):
            if item.get("is_star"):
                continue
            pc = (item.get("planet_class") or "").lower()
            name = item.get("name") or ""
            if "earthlike" in pc:
                self._notable.append(("ELW", name))
            elif "water world" in pc:
                self._notable.append(("WW", name))
            elif "ammonia world" in pc:
                self._notable.append(("AMM", name))
            elif item.get("terraform_state") in ("Terraformable", "Candidate for terraforming"):
                self._notable.append(("TF", name))

        self.show()

    def update_traffic(self, traffic):
        """Called when EDSM traffic fetch returns."""
        self._traffic = traffic
        self._redraw_if_visible()

    def update_edsm_details(self, details):
        """Called when EDSM system details fetch returns."""
        if not details:
            return
        self._edsm_info = details.get("information") or {}
        self._redraw_if_visible()

    def _redraw_if_visible(self):
        try:
            if self.win.state() != "withdrawn":
                self._redraw()
        except Exception:
            pass

    # ── Rendering ─────────────────────────────────────────────────────────

    def _redraw(self):
        rows = self._build_rows()
        height = HDR_H + len(rows) * ROW_H + PAD
        self.canvas.config(width=WIDTH, height=height)
        self.win.geometry(f"{WIDTH}x{height}")
        self.canvas.delete("all")

        # Background panel
        r = 6
        self.canvas.create_rectangle(0, 0, WIDTH, height,
                                     fill="#080d11", outline=COLOR_ACCENT, width=1)

        # Header
        # System name
        sys_text = _truncate(self._system.upper(), 30)
        self._text(PAD, 14, sys_text, COLOR_ACCENT,
                   ("Segoe UI", 14, "bold"), anchor="w")

        # Star class badge (right side)
        if self._star_class:
            badge = f"  {self._star_class}-TYPE  "
            self._text(WIDTH - PAD, 14, badge, _COL_STAR,
                       ("Consolas", 9, "bold"), anchor="e")

        # Divider
        self.canvas.create_line(PAD, HDR_H - 2, WIDTH - PAD, HDR_H - 2,
                                fill=COLOR_ACCENT, width=1)

        # Body rows
        y = HDR_H + ROW_H // 2
        for label, value, color in rows:
            if label:
                self._text(PAD, y, label, _COL_DIM,
                           ("Segoe UI", 8, "bold"), anchor="w")
                self._text(PAD + 80, y, value, color,
                           ("Consolas", 10), anchor="w")
            else:
                # Full-width value (no label)
                self._text(PAD, y, value, color,
                           ("Consolas", 10), anchor="w")
            y += ROW_H

    def _build_rows(self):
        rows = []  # (label, value, color)

        # Bodies line
        if self._body_count > 0:
            body_str = f"{self._body_count} bodies"
        else:
            body_str = "? bodies"
        if self._scanned_count > 0:
            body_str += f"  ·  {self._scanned_count} scanned"
        if self._bio_total > 0:
            body_str += f"  ·  {self._bio_total} bio"
        rows.append(("BODIES", body_str, COLOR_TEXT))

        # Notable bodies (max 4, formatted as tags)
        if self._notable:
            chunks = [f"[{tag}] {_truncate(name, 14)}" for tag, name in self._notable[:4]]
            rows.append(("NOTABLE", "  ".join(chunks), _COL_WARN))

        # EDSM info block
        if self._edsm_info:
            info = self._edsm_info
            pop = _fmt_pop(info.get("population"))
            faction = _truncate(info.get("faction") or "", 24)
            gov = info.get("government") or ""
            alleg = info.get("allegiance") or ""
            security = info.get("security") or ""
            state = info.get("state") or ""

            # Population + allegiance / government
            if pop or alleg:
                line = "  ·  ".join(p for p in [
                    (f"Pop {pop}" if pop else ""),
                    alleg,
                    gov,
                ] if p)
                rows.append(("FACTION", line, _COL_POP))

            # Faction + security + state
            if faction or security:
                line2 = "  ·  ".join(p for p in [
                    faction,
                    security,
                    (state if state and state.lower() not in ("none", "") else ""),
                ] if p)
                if line2:
                    rows.append(("", line2, _COL_DIM))

        # Traffic
        if self._traffic:
            t = self._traffic
            d = _fmt_traffic(t.get("day", 0))
            w = _fmt_traffic(t.get("week", 0))
            total = _fmt_traffic(t.get("total", 0))
            rows.append(("TRAFFIC", f"Today {d}  ·  Week {w}  ·  All-time {total}", _COL_DIM))
        else:
            rows.append(("TRAFFIC", "fetching…", _COL_DIM))

        return rows

    def _text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000",
                                font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill,
                                font=font, anchor=anchor)

    # ── Drag-to-move ──────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
        if x != 0 or y != 0:
            self.config["system_info_hud_x"] = x
            self.config["system_info_hud_y"] = y
            self._write_config()

    def _write_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass
