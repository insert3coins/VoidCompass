"""Transient exploration-first system intelligence overlay.

Navigation HUD owns scan progress and Survey Status owns individual bodies;
this card instead summarises composition, signals, facilities and authority.
The model builder remains independent of Tk for journal-shaped validation.
"""

import tkinter as tk

from config import save_config
import overlay_chrome
from stellar_types import star_type_label
import themes

WIDTH = 520

_CHROMA = "#ff00ff"

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


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _truncate(text, max_chars):
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


def _count_label(value, singular, plural=None):
    value = max(0, _safe_int(value))
    return f"{value} {singular if value == 1 else (plural or singular + 'S')}"


def _local_stellar_profile(scan_items):
    stars = 0
    planets = 0
    landable = 0
    classes = []
    for row in scan_items or ():
        if not isinstance(row, dict):
            continue
        if row.get("is_star"):
            stars += 1
            raw_class = row.get("star_type") or row.get("class") or ""
            label = star_type_label(raw_class) or str(raw_class).strip()
            if label and label not in classes:
                classes.append(label)
        else:
            planets += 1
            if row.get("landable"):
                landable += 1
    if not (stars or planets):
        return None
    return {
        "star_count": stars,
        "star_classes": classes,
        "planet_count": planets,
        "landable_count": landable,
    }


def build_system_model(system_name, star_class, body_count,
                       bio_total=0, geo_total=0, total_known=False,
                       local_profile=None, edsm_info=None, spansh=None,
                       scanned_count=0):
    """Return a renderer-neutral exploration summary for one system."""
    total = max(0, _safe_int(body_count))
    known = bool(total_known and total > 0)

    signals = []
    if _safe_int(bio_total) > 0:
        signals.append(f"BIO {_safe_int(bio_total)}")
    if _safe_int(geo_total) > 0:
        signals.append(f"GEO {_safe_int(geo_total)}")

    profile = spansh or local_profile
    profile_rows = []
    profile_source = "RESOLVING"
    if profile:
        profile_source = "SYSTEM RECORD" if spansh else "LOCAL SCANS"
        star_count = max(0, _safe_int(profile.get("star_count")))
        planet_count = max(0, _safe_int(profile.get("planet_count")))
        landable_count = max(0, _safe_int(profile.get("landable_count")))
        parts = [
            _count_label(star_count, "STAR"),
            _count_label(planet_count, "PLANET"),
        ]
        if landable_count:
            parts.append(_count_label(landable_count, "LANDABLE BODY", "LANDABLE BODIES"))
        if signals:
            parts.extend(signals)
        profile_rows.append(" · ".join(parts))
        classes = [str(value).strip() for value in profile.get("star_classes") or () if value]
        if len(classes) > 1:
            profile_rows.append("STELLAR CLASSES · " + " / ".join(classes))

        # Spansh supplies useful whole-system context, but it must not hide the
        # commander's live journal discoveries. Keep this as a compact catalogue
        # readout rather than duplicating the Navigation HUD's progress bar.
        if spansh and local_profile:
            local_parts = [
                _count_label(local_profile.get("star_count"), "STAR"),
                _count_label(local_profile.get("planet_count"), "PLANET"),
            ]
            local_landable = max(0, _safe_int(local_profile.get("landable_count")))
            if local_landable:
                local_parts.append(
                    _count_label(local_landable, "LANDABLE BODY", "LANDABLE BODIES")
                )
            profile_rows.append("LOCAL CATALOGUE · " + " · ".join(local_parts))
    else:
        profile_rows.append("STELLAR PROFILE DATA RESOLVING")
        if signals:
            profile_rows.append("SURFACE SIGNALS · " + " · ".join(signals))

    scanned = max(0, _safe_int(scanned_count))
    if scanned:
        profile_source = (
            f"RECORD + LIVE · {scanned} CATALOGUED"
            if spansh else f"LIVE SURVEY · {scanned} CATALOGUED"
        )

    facility_rows = []
    facility_state = "RESOLVING"
    facility_detected = False
    if spansh:
        counts = spansh.get("counts") or {}
        count_parts = []
        for key, singular in (
            ("starport", "STARPORT"),
            ("outpost", "OUTPOST"),
            ("settlement", "SETTLEMENT"),
            ("fc", "CARRIER"),
        ):
            value = max(0, _safe_int(counts.get(key)))
            if value:
                count_parts.append(_count_label(value, singular))
        facility_detected = bool(count_parts)
        facility_state = "DETECTED" if facility_detected else "NONE REPORTED"
        facility_rows.append(" · ".join(count_parts) if count_parts else "NO STATIONS OR CARRIERS REPORTED")
        services = spansh.get("services") or {}
        service_parts = [
            label for key, label in (
                ("mat_trader", "MATERIAL TRADER"),
                ("tech_broker", "TECH BROKER"),
                ("engineer", "ENGINEER"),
            ) if services.get(key)
        ]
        if service_parts:
            facility_rows.append("SPECIALISTS · " + " · ".join(service_parts))
    else:
        facility_rows.append("FACILITY DATA RESOLVING")

    authority_rows = []
    authority_state = "RESOLVING"
    if edsm_info is None:
        authority_rows.append("LOCAL AUTHORITY DATA RESOLVING")
    elif not edsm_info:
        authority_state = "UNINHABITED"
        authority_rows.append("NO POPULATION OR LOCAL AUTHORITY REPORTED")
    else:
        info = edsm_info
        population = _fmt_pop(info.get("population"))
        authority_state = f"POP {population}" if population else "INHABITED"
        civic = []
        for value in (
            info.get("allegiance"), info.get("government"),
            info.get("security"), info.get("economy"),
        ):
            label = str(value or "").strip().upper()
            if label and label != "NONE" and label not in civic:
                civic.append(label)
        if civic:
            authority_rows.append(" · ".join(civic))
        faction = str(info.get("faction") or "").strip().upper()
        state = str(info.get("factionState") or info.get("state") or "").strip().upper()
        faction_parts = [value for value in (faction, state) if value and value != "NONE"]
        if faction_parts:
            authority_rows.append(" · ".join(faction_parts))
        if not authority_rows:
            authority_rows.append("NO LOCAL AUTHORITY DETAILS REPORTED")

    if edsm_info:
        badge = "INHABITED"
        badge_tone = "green"
    elif facility_detected:
        badge = "HUMAN PRESENCE"
        badge_tone = "orange"
    elif edsm_info is not None and spansh is not None:
        badge = "UNINHABITED"
        badge_tone = "muted"
    else:
        badge = "SYSTEM PROFILE"
        badge_tone = "accent"

    return {
        "system": str(system_name or "Unknown").strip(),
        "primary_star": str(star_class or "").strip(),
        "badge": badge,
        "badge_tone": badge_tone,
        "body_total": total if known else None,
        "profile_source": profile_source,
        "profile_rows": profile_rows,
        "facility_state": facility_state,
        "facility_rows": facility_rows,
        "authority_state": authority_state,
        "authority_rows": authority_rows,
    }


class SystemInfoHUD:
    def __init__(self, root, config):
        self.root   = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)

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
        self._geo_total     = 0
        self._total_known   = False
        self._local_profile = None
        self._edsm_info     = None
        self._spansh        = None  # parsed station/service summary
        self._last_model    = None

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
                             scanned_bodies=None, total_known=None):
        self._body_count = max(0, _safe_int(total_bodies))
        if scanned_bodies is None:
            self._scanned_count = sum(
                1 for item in (scan_items or ())
                if isinstance(item, dict) and item.get("body_id") is not None
            )
        else:
            self._scanned_count = max(0, _safe_int(scanned_bodies))
        self._total_known = (
            self._body_count > 0 if total_known is None else bool(total_known)
        )
        self._bio_total = sum(
            max(0, _safe_int(signals.get("bio")))
            for signals in (body_signals or {}).values() if isinstance(signals, dict)
        )
        self._geo_total = sum(
            max(0, _safe_int(signals.get("geo")))
            for signals in (body_signals or {}).values() if isinstance(signals, dict)
        )
        self._local_profile = _local_stellar_profile(scan_items)

    def on_system_arrival(self, system_name, star_class,
                          scan_items, body_signals, total_bodies,
                          scanned_bodies=None, total_known=None):
        self._system        = system_name or "Unknown"
        self._star_class    = star_type_label(star_class)
        self._edsm_info     = None
        self._spansh        = None
        self._last_model    = None
        self._apply_scan_progress(
            scan_items, body_signals, total_bodies, scanned_bodies, total_known,
        )
        self.show()

    def update_scan_progress(self, scan_items, body_signals, total_bodies,
                             star_class=None, scanned_bodies=None, total_known=None):
        """Incremental refresh as the current system is surveyed further.

        Unlike on_system_arrival(), this never shows/repositions the window
        or resets its auto-hide timer — it only updates the content in
        place if the panel happens to already be visible.
        """
        self._apply_scan_progress(
            scan_items, body_signals, total_bodies, scanned_bodies, total_known,
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
        star_count = 0
        planet_count = 0
        landable_count = 0
        for body in bodies:
            btype = (body.get("type") or "").lower()
            if btype == "star":
                star_count += 1
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
            type_key = str(stype).strip().casefold()
            service_keys = {str(value).strip().casefold() for value in svc_list if value}

            if "carrier" in type_key:
                counts["fc"] += 1
            elif "settlement" in type_key:
                counts["settlement"] += 1
            elif stype in _STARPORT_TYPES or (st.get("landingPads") and "mega ship" in type_key):
                counts["starport"] += 1
            elif "outpost" in type_key:
                counts["outpost"] += 1

            if "material trader" in service_keys:
                services["mat_trader"] = True
            if "technology broker" in service_keys:
                services["tech_broker"] = True
            if str(gov).strip().casefold() == "engineer":
                services["engineer"] = True

        self._spansh = {
            "counts":         counts,
            "services":       services,
            "star_count":     star_count,
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

    def _build_model(self):
        return build_system_model(
            self._system,
            self._star_class,
            self._body_count,
            self._bio_total,
            self._geo_total,
            self._total_known,
            self._local_profile,
            self._edsm_info,
            self._spansh,
            self._scanned_count,
        )

    def _section(self, y, label, right=""):
        palette = self._palette
        self._draw_text(18, y, label, palette["dim"], ("Courier", 7, "bold"))
        if right:
            self._draw_text(
                WIDTH - 18, y, _truncate(right, 34), palette["dim"],
                ("Courier", 7, "bold"), anchor="e",
            )
        return y + 16

    def _separator(self, y):
        """Separate sections with whitespace rather than decorative rules."""
        return y + 12

    def _redraw(self, force=False):
        palette = self._palette
        model = self._build_model()
        if not force and model == self._last_model:
            return
        self._last_model = model

        sections = (
            model["profile_rows"], model["facility_rows"], model["authority_rows"],
        )
        total_h = 89 + sum(28 + len(rows) * 17 for rows in sections) + 8

        self.canvas.config(width=WIDTH, height=total_h)
        self.win.geometry(f"{WIDTH}x{total_h}")
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, total_h, accent=palette["accent"], bracket_len=10,
            scanlines=False,
        )

        self._draw_text(
            18, 18, "SYSTEM INTELLIGENCE", palette["accent"],
            ("Courier", 9, "bold"),
        )
        badge_color = palette.get(model["badge_tone"], palette["accent"])
        self._draw_text(
            WIDTH - 18, 18, model["badge"], badge_color,
            ("Courier", 8, "bold"), anchor="e",
        )
        self._draw_text(
            18, 45, _truncate(model["system"].upper(), 49), palette["text"],
            ("Courier", 11, "bold"),
        )
        primary = model["primary_star"].upper() or "CLASSIFICATION PENDING"
        self._draw_text(
            18, 64, _truncate(f"PRIMARY · {primary}", 43), palette["muted"],
            ("Courier", 8, "bold"),
        )
        body_total = model.get("body_total")
        total_label = _count_label(body_total, "BODY", "BODIES") if body_total else "BODY COUNT PENDING"
        self._draw_text(
            WIDTH - 18, 64, total_label, palette["muted"],
            ("Courier", 8, "bold"), anchor="e",
        )
        y = self._section(89, "SYSTEM PROFILE", model["profile_source"])
        for row in model["profile_rows"]:
            color = palette["text"] if model["profile_source"] != "RESOLVING" else palette["dim"]
            self._draw_text(18, y, _truncate(row, 65), color, ("Courier", 8, "bold"))
            y += 17
        y = self._separator(y)

        y = self._section(y, "HUMAN FOOTPRINT", model["facility_state"])
        for index, row in enumerate(model["facility_rows"]):
            color = palette["orange"] if index > 0 else (
                palette["text"] if model["facility_state"] != "RESOLVING" else palette["dim"]
            )
            self._draw_text(18, y, _truncate(row, 65), color, ("Courier", 8, "bold"))
            y += 17
        y = self._separator(y)

        y = self._section(y, "LOCAL AUTHORITY", model["authority_state"])
        for index, row in enumerate(model["authority_rows"]):
            color = palette["text"] if index == 0 and model["authority_state"] != "RESOLVING" else palette["muted"]
            if model["authority_state"] == "RESOLVING":
                color = palette["dim"]
            self._draw_text(18, y, _truncate(row, 65), color, ("Courier", 8, "bold"))
            y += 17
        self._separator(y)

    def apply_theme(self, palette=None):
        """Apply the active commander palette without resetting visibility."""
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        try:
            if self.win.state() != "withdrawn":
                self._redraw(force=True)
        except (AttributeError, tk.TclError):
            pass

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
