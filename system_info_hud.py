import tkinter as tk
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome
from stellar_types import star_type_label

WIDTH = 460

_CHROMA = "#ff00ff"

_COL_DIM  = "#7a8a98"
_COL_GOLD = "#e8c97a"

_STARPORT_TYPES = {
    "Coriolis Starport", "Orbis Starport", "Ocellus Starport",
    "Asteroid base", "Planetary Port", "Planetary Outpost",
}

def _fmt_pop(n):
    try:
        n = int(n)
    except Exception:
        return ""
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


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
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)

        self.canvas = tk.Canvas(
            self.win, bg=overlay_bg, highlightthickness=0,
            width=WIDTH, height=100,
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>",        self._on_mouse_down)
        self.canvas.bind("<B1-Motion>",       self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        x = int(config.get("system_info_hud_x", 30))
        y = int(config.get("system_info_hud_y", 30))
        self.win.geometry(overlay_chrome.position_geometry(x, y))

        self._hide_job       = None
        self._save_job       = None
        self._mouse_down     = None
        self._mouse_dragging = False
        self._mx = self._my  = 0
        # Displayed data
        self._system        = ""
        self._star_class    = ""
        self._body_count    = 0
        self._scanned_count = 0
        self._bio_total     = 0
        self._edsm_info     = None
        self._spansh        = None  # parsed station/service summary

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
        self.win.geometry(overlay_chrome.position_geometry(x, y))
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

    def _apply_scan_progress(self, scan_items, body_signals, total_bodies,
                             scanned_bodies=None):
        self._body_count    = int(total_bodies or 0)
        if scanned_bodies is None:
            self._scanned_count = sum(
                1 for it in (scan_items or []) if not it.get("is_star")
            )
        else:
            self._scanned_count = max(0, int(scanned_bodies or 0))
        self._bio_total = sum(
            s.get("bio", 0) for s in (body_signals or {}).values()
        )

    def on_system_arrival(self, system_name, star_class,
                          scan_items, body_signals, total_bodies,
                          scanned_bodies=None):
        self._system        = system_name or "Unknown"
        self._star_class    = star_type_label(star_class)
        self._edsm_info     = None
        self._spansh        = None
        self._apply_scan_progress(
            scan_items, body_signals, total_bodies, scanned_bodies,
        )
        self.show()

    def update_scan_progress(self, scan_items, body_signals, total_bodies,
                             star_class=None, scanned_bodies=None):
        """Incremental refresh as the current system is surveyed further.

        Unlike on_system_arrival(), this never shows/repositions the window
        or resets its auto-hide timer — it only updates the content in
        place if the panel happens to already be visible.
        """
        self._apply_scan_progress(
            scan_items, body_signals, total_bodies, scanned_bodies,
        )
        if star_class:
            self._star_class = star_type_label(star_class)
        try:
            if self.win.state() != "withdrawn":
                self._redraw()
        except Exception:
            pass

    def update_traffic(self, traffic):
        # Traffic is shown in the Navigation HUD — nothing to do here.
        pass

    def update_edsm_details(self, details):
        # Always mark as arrived (even if empty) so the "EDSM ..." loading
        # line disappears. Use {} for "arrived but no data" (uninhabited systems).
        if details is None:
            self._edsm_info = {}
        else:
            self._edsm_info = details.get("information") or {}
        try:
            if self.win.state() != "withdrawn":
                self._redraw()
        except Exception:
            pass

    def update_spansh(self, data):
        if not data:
            return
        system = data.get("system") or {}
        bodies = system.get("bodies") or []

        # ── Bodies: stars & planets ───────────────────────────────────────
        star_classes = []   # spectral class strings, e.g. ["G", "M"]
        planet_count = 0
        landable_count = 0
        for body in bodies:
            btype = (body.get("type") or "").lower()
            if btype == "star":
                sc = (body.get("spectralClass") or body.get("subType") or "").strip()
                # Keep just the leading letter(s), e.g. "G" from "G (White-Yellow) Star"
                if sc:
                    sc = sc.split()[0]
                    if sc not in star_classes:
                        star_classes.append(sc)
            elif btype in ("planet", "moon"):
                planet_count += 1
                if body.get("isLandable"):
                    landable_count += 1

        # ── Stations ─────────────────────────────────────────────────────
        all_stations = list(system.get("stations") or [])
        for body in bodies:
            all_stations.extend(body.get("stations") or [])

        counts = {"starport": 0, "outpost": 0, "settlement": 0, "fc": 0}
        services = {"mat_trader": False, "tech_broker": False, "engineer": False}

        for st in all_stations:
            stype    = st.get("type") or ""
            svc_list = st.get("services") or []
            gov      = st.get("government") or ""

            if stype == "Drake-Class Carrier":
                counts["fc"] += 1
            elif stype == "Settlement":
                counts["settlement"] += 1
            elif stype == "Outpost":
                counts["outpost"] += 1
            elif stype in _STARPORT_TYPES or (st.get("landingPads") and "Mega ship" in stype):
                counts["starport"] += 1

            if "Material Trader" in svc_list:
                services["mat_trader"] = True
            if "Technology Broker" in svc_list:
                services["tech_broker"] = True
            if gov == "Engineer":
                services["engineer"] = True

        self._spansh = {
            "counts":         counts,
            "services":       services,
            "star_classes":   star_classes,
            "planet_count":   planet_count,
            "landable_count": landable_count,
        }
        try:
            if self.win.state() != "withdrawn":
                self._redraw()
        except Exception:
            pass

    # ── Rendering ─────────────────────────────────────────────────────────

    def _redraw(self):
        rows = self._build_rows()
        LINE_H  = 20
        total_h = 35 + len(rows) * LINE_H + 10

        total_h = max(total_h, 60)

        self.canvas.config(width=WIDTH, height=total_h)
        self.win.geometry(f"{WIDTH}x{total_h}")
        self.canvas.delete("all")

        overlay_chrome.draw_chrome(self.canvas, WIDTH, total_h)
        self.canvas.create_line(20, 35, WIDTH - 20, 35, fill="#1a2530", width=1)
        self._draw_text(20, 20, "SYSTEM INFO", COLOR_ACCENT, ("Courier", 10, "bold"))

        y = 44
        for i, (text, color) in enumerate(rows):
            self._draw_text(20, y, text, color, ("Courier", 10, "bold"))
            if i == 0 and self._star_class:
                self._draw_text(WIDTH - 20, y, f"[{self._star_class}]", _COL_GOLD,
                                ("Courier", 10, "bold"), anchor="e")
            y += LINE_H

    def _build_rows(self):
        rows = []

        sys_name = _truncate(self._system.upper(), 34)
        rows.append((sys_name, COLOR_ACCENT))

        if self._spansh:
            # Stars line: "2 STARS  G · M"
            sc = self._spansh["star_classes"]
            pc = self._spansh["planet_count"]
            lc = self._spansh["landable_count"]
            star_str = f"{len(sc)} STAR{'S' if len(sc) != 1 else ''}"
            if sc:
                star_str += "  " + "  ".join(sc)
            planet_str = f"{pc} PLANET{'S' if pc != 1 else ''}"
            if lc:
                planet_str += f"  {lc} Landable"
            rows.append((f"{star_str}  ·  {planet_str}", _COL_DIM))

            # Scanned / bio progress from local data
            prog_parts = []
            if self._scanned_count > 0:
                prog_parts.append(f"{self._scanned_count} Scanned")
            if self._bio_total > 0:
                prog_parts.append(f"{self._bio_total} Bio Signals")
            if prog_parts:
                rows.append(("  ·  ".join(prog_parts), _COL_DIM))
        else:
            # No Spansh yet — fall back to local DB counts
            scan_parts = []
            if self._body_count > 0:
                scan_parts.append(f"{self._body_count} Bodies")
            if self._scanned_count > 0:
                scan_parts.append(f"{self._scanned_count} Scanned")
            if self._bio_total > 0:
                scan_parts.append(f"{self._bio_total} Bio Signals")
            if scan_parts:
                rows.append(("  ·  ".join(scan_parts), _COL_DIM))

        if self._spansh:
            c = self._spansh["counts"]
            s = self._spansh["services"]
            port_parts = [p for p in [
                (f"×{c['starport']} Starport"   if c["starport"]   else ""),
                (f"×{c['outpost']} Outpost"     if c["outpost"]    else ""),
                (f"×{c['settlement']} Settlement" if c["settlement"] else ""),
                (f"×{c['fc']} Fleet Carrier"    if c["fc"]         else ""),
            ] if p]
            rows.append(("  ·  ".join(port_parts) if port_parts else "No Stations", _COL_DIM))
            svc_parts = [p for p in [
                ("Material Trader" if s["mat_trader"]  else ""),
                ("Tech Broker"     if s["tech_broker"] else ""),
                ("Engineer"        if s["engineer"]    else ""),
            ] if p]
            if svc_parts:
                rows.append(("  ·  ".join(svc_parts), COLOR_ORANGE))
        else:
            rows.append(("Stations  ...", _COL_DIM))

        if self._edsm_info is None:
            # Still waiting for EDSM response
            rows.append(("Faction info  ...", _COL_DIM))
        elif self._edsm_info:
            # Has faction/population data (inhabited system)
            info    = self._edsm_info
            pop     = _fmt_pop(info.get("population"))
            alleg   = (info.get("allegiance")   or "").upper()
            gov     = (info.get("government")   or "").upper()
            sec     = (info.get("security")     or "").upper()
            state   = (info.get("factionState") or info.get("state") or "").upper()
            faction = _truncate((info.get("faction") or "").upper(), 30)
            economy = (info.get("economy") or "").upper()

            pol_parts = [p for p in [
                (f"POP {pop}" if pop else ""), alleg, gov,
            ] if p]
            if pol_parts:
                rows.append(("  ·  ".join(pol_parts), _COL_DIM))

            fac_parts = [p for p in [
                faction,
                sec,
                (state  if state  and state  not in ("NONE", "") else ""),
                (economy if economy and economy not in ("NONE", "") else ""),
            ] if p]
            if fac_parts:
                rows.append(("  ·  ".join(fac_parts), _COL_DIM))
        # else: empty dict = arrived, uninhabited system — show nothing

        return rows

    def _draw_text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x+1, y+1, text=text, fill="black",
                                font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill,
                                font=font, anchor=anchor)

    # ── Drag-to-move ──────────────────────────────────────────────────────

    def _on_mouse_down(self, event):
        self._mouse_down     = (event.x, event.y)
        self._mouse_dragging = False
        self._mx = event.x
        self._my = event.y

    def _on_mouse_drag(self, event):
        if not self._mouse_down:
            return
        sx, sy = self._mouse_down
        if abs(event.x - sx) > 3 or abs(event.y - sy) > 3:
            self._mouse_dragging = True
        x = self.win.winfo_x() + (event.x - self._mx)
        y = self.win.winfo_y() + (event.y - self._my)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.config["system_info_hud_x"] = x
        self.config["system_info_hud_y"] = y
        self._schedule_config_save()

    def _on_mouse_up(self, event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
        if x != 0 or y != 0:
            self.config["system_info_hud_x"] = x
            self.config["system_info_hud_y"] = y
            self._write_config()
        self._mouse_down     = None
        self._mouse_dragging = False

    def _schedule_config_save(self):
        if self._save_job:
            try:
                self.win.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.win.after(250, self._flush_config_save)

    def _flush_config_save(self):
        self._save_job = None
        self._write_config()

    def _write_config(self):
        try:
            save_config(self.config)
        except Exception:
            pass
