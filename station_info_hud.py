"""StationInfoHUD — transient overlay showing economy/government/faction/
services info for the station the commander just docked at.

All data comes from the raw Docked journal event (dashboard.py captures it
into self.current_station_* attributes) — no network calls needed.
"""

import tkinter as tk
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome

_CHROMA = "#ff00ff"
_DIM = "#7a8a98"

WIDTH = 480


def _truncate(text, max_chars):
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


class StationInfoHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._hide_job = None

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)

        self.canvas = tk.Canvas(self.win, width=WIDTH, height=100, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        x = self._safe_int(config.get("station_info_hud_x"), 30)
        y = self._safe_int(config.get("station_info_hud_y"), 380)
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
            x = self._safe_int(self.config.get("station_info_hud_x"), 30)
            y = self._safe_int(self.config.get("station_info_hud_y"), 380)
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
        timeout_s = max(5, int(self.config.get("station_info_timeout_s") or 25))
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    # ── Data interface ───────────────────────────────────────────────────

    def on_docked(self, dash):
        """dash is the MainDashboard instance — reads its current_station_* attrs."""
        rows = self._build_rows(dash)
        self._redraw(dash.current_station_name or "UNKNOWN STATION", rows)
        self.show()
        self._schedule_hide()

    def _build_rows(self, dash):
        rows = []

        stype = dash.current_station_type
        pads = dash.current_station_landing_pads or {}
        pad_txt = ""
        if pads:
            parts = [f"{v}×{k[0]}" for k, v in (("Large", pads.get("Large")), ("Medium", pads.get("Medium")), ("Small", pads.get("Small"))) if v]
            pad_txt = "  ·  ".join(parts)
        dist = dash.current_station_dist_ls
        dist_txt = f"{dist:,.0f} Ls" if isinstance(dist, (int, float)) else ""
        line1 = "  ·  ".join(p for p in (stype, pad_txt, dist_txt) if p)
        if line1:
            rows.append((line1, _DIM))

        economies = dash.current_station_economies or []
        if economies:
            parts = []
            for econ in sorted(economies, key=lambda e: e.get("Proportion") or 0, reverse=True)[:3]:
                name = econ.get("Name_Localised") or econ.get("Name") or ""
                pct = econ.get("Proportion")
                if name and isinstance(pct, (int, float)):
                    parts.append(f"{name} {pct*100:.0f}%")
                elif name:
                    parts.append(name)
            if parts:
                rows.append(("  ·  ".join(parts), COLOR_TEXT))
        elif dash.current_station_economy:
            rows.append((dash.current_station_economy, COLOR_TEXT))

        gov = dash.current_station_government
        alleg = dash.current_station_allegiance
        gov_parts = [p for p in (gov, alleg) if p]
        if gov_parts:
            rows.append(("  ·  ".join(gov_parts), _DIM))

        faction = dash.current_station_faction
        if faction and faction.get("name"):
            state = faction.get("state")
            txt = faction["name"] if not state or state == "None" else f"{faction['name']} ({state})"
            rows.append((_truncate(txt, 46), COLOR_ORANGE))

        services = dash.current_station_services or []
        notable = [s for s in services if s in (
            "Refuel", "Repair", "Rearm", "Outfitting", "Shipyard", "BlackMarket",
            "Contacts", "Missions", "Market", "TechBroker", "MaterialTrader",
            "Engineer", "Crew", "Dock",
        ) and s not in ("Dock", "Contacts", "Crew")]
        if notable:
            rows.append((", ".join(notable[:8]), _DIM))

        return rows

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        self.config["station_info_hud_x"] = self.win.winfo_x()
        self.config["station_info_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _redraw(self, station_name, rows):
        LINE_H = 20
        total_h = max(60, 35 + len(rows) * LINE_H + 10)
        self.canvas.config(width=WIDTH, height=total_h)
        self.win.geometry(f"{WIDTH}x{total_h}")
        self.canvas.delete("all")

        overlay_chrome.draw_chrome(self.canvas, WIDTH, total_h)
        self.canvas.create_line(20, 35, WIDTH - 20, 35, fill="#1a2530", width=1)
        self._text(20, 20, _truncate(station_name.upper(), 40), COLOR_ACCENT, ("Courier", 10, "bold"))

        y = 44
        for text, color in rows:
            self._text(20, y, _truncate(text, 64), color, ("Courier", 9, "bold"))
            y += LINE_H
