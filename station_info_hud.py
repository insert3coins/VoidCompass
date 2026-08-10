"""Exploration-first station overlay built from Elite journal evidence.

The renderer consumes the station state captured by :mod:`dashboard` from
``Docked``/``Location`` events.  The model builder is intentionally independent
of Tk so journal examples can be validated without constructing a window.
"""

import re
import tkinter as tk

from config import save_config
import overlay_chrome
import themes


_CHROMA = "#ff00ff"
WIDTH = 520

_CORE_SERVICES = (
    ("REFUEL", ("refuel",)),
    ("REPAIR", ("repair",)),
    ("REARM", ("rearm",)),
    ("OUTFITTING", ("outfitting",)),
)
_EXPLORATION_SERVICES = (
    ("UNIVERSAL CARTOGRAPHICS", ("exploration",)),
    ("VISTA GENOMICS", ("vistagenomics",)),
    ("SEARCH & RESCUE", ("searchrescue",)),
    ("COLONISATION", ("registeringcolonisation", "colonisationconstruction")),
)
_SPECIAL_SERVICES = (
    ("SHIPYARD", ("shipyard",)),
    ("TECH BROKER", ("techbroker",)),
    ("MATERIAL TRADER", ("materialtrader",)),
    ("BLACK MARKET", ("blackmarket",)),
    ("ENGINEER", ("engineer",)),
)
_STATION_TYPE_LABELS = {
    "asteroidbase": "ASTEROID BASE",
    "coriolis": "CORIOLIS STARPORT",
    "fleetcarrier": "FLEET CARRIER",
    "megaship": "MEGASHIP",
    "ocellus": "OCELLUS STARPORT",
    "orbis": "ORBIS STARPORT",
    "outpost": "OUTPOST",
    "planetaryconstructiondepot": "SURFACE DEPOT",
    "spaceconstructiondepot": "ORBITAL DEPOT",
    "surfacestation": "SURFACE PORT",
}


def _truncate(text, max_chars):
    text = str(text or "")
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _display_name(value):
    """Turn a localised label or Frontier token into compact readable text."""
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1]
        text = re.sub(r"^(economy|government|stationtype)_", "", text, flags=re.I)
    text = text.replace("_", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return " ".join(text.split()).strip()


def _credits(value):
    value = max(0, _safe_int(value))
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} B CR"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} M CR"
    if value >= 1_000:
        return f"{value / 1_000:.0f} K CR"
    return f"{value:,} CR"


def _service_keys(services):
    return {
        str(service or "").strip().casefold().replace("_", "")
        for service in (services or ()) if service
    }


def _has_service(service_keys, aliases):
    return any(alias.casefold().replace("_", "") in service_keys for alias in aliases)


def _service_rows(definitions, service_keys):
    return [
        {"label": label, "available": _has_service(service_keys, aliases)}
        for label, aliases in definitions
    ]


def _economy_summary(economies, fallback=None):
    rows = []
    for economy in economies or ():
        if not isinstance(economy, dict):
            continue
        name = _display_name(economy.get("Name_Localised") or economy.get("Name"))
        if not name:
            continue
        proportion = economy.get("Proportion")
        try:
            proportion = float(proportion)
        except (TypeError, ValueError):
            proportion = None
        rows.append((name, proportion))
    rows.sort(key=lambda item: item[1] if item[1] is not None else -1, reverse=True)
    rows = rows[:3]
    # Frontier journal examples can report economy weights whose total exceeds
    # one (including individual values over one).  Those values are ordering
    # weights, not safe percentages, so only render percentages when the whole
    # set is demonstrably fractional.
    valid_percentages = bool(rows) and all(
        value is not None and 0 <= value <= 1 for _, value in rows
    ) and sum(value for _, value in rows) <= 1.05
    if valid_percentages:
        return " · ".join(f"{name} {value * 100:.0f}%" for name, value in rows)
    if rows:
        return " · ".join(name for name, _ in rows)
    return _display_name(fallback)


def _station_type_label(station_type):
    raw = str(station_type or "").strip()
    key = raw.casefold().replace(" ", "").replace("_", "")
    return _STATION_TYPE_LABELS.get(key) or _display_name(raw).upper() or "STATION"


def _same_market_id(left, right):
    if left in (None, "") or right in (None, ""):
        return False
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left).strip().casefold() == str(right).strip().casefold()


def build_station_model(dash):
    """Return a truthful, renderer-neutral station status card."""
    service_keys = _service_keys(getattr(dash, "current_station_services", None))
    carrier = getattr(getattr(dash, "carrier_tracker", None), "carrier_data", None) or {}
    market_id = getattr(dash, "current_station_market_id", None)
    is_personal_carrier = _same_market_id(market_id, carrier.get("carrier_id"))
    station_type = _station_type_label(getattr(dash, "current_station_type", None))

    pads = getattr(dash, "current_station_landing_pads", None) or {}
    pad_parts = []
    for key, short in (("Large", "L"), ("Medium", "M"), ("Small", "S")):
        value = _safe_int(pads.get(key))
        if value:
            pad_parts.append(f"{short} {value}")

    distance = getattr(dash, "current_station_dist_ls", None)
    try:
        distance_text = f"{float(distance):,.0f} Ls" if distance is not None else ""
    except (TypeError, ValueError):
        distance_text = ""

    faction = getattr(dash, "current_station_faction", None) or {}
    authority_parts = []
    for value in (
        faction.get("name"),
        getattr(dash, "current_station_government", None),
        getattr(dash, "current_station_allegiance", None),
        faction.get("state"),
    ):
        label = _display_name(value)
        if label and label.casefold() != "none" and label.casefold() not in {
            item.casefold() for item in authority_parts
        }:
            authority_parts.append(label)

    state = getattr(dash, "companion_state", None) or {}
    exploration_value = max(0, _safe_int(state.get("unsold_exploration_cr")))
    bio_value = max(0, _safe_int(state.get("unsold_bio_cr")))
    bio_bonus = max(0, _safe_int(state.get("unsold_bio_bonus_potential_cr")))
    bio_samples = max(0, _safe_int(state.get("unsold_bio_samples")))
    data_rows = []
    if exploration_value:
        data_rows.append({
            "label": "EXPLORATION",
            "value": _credits(exploration_value),
            "available": "exploration" in service_keys,
            "service": "CARTOGRAPHICS",
        })
    if bio_value:
        value = _credits(bio_value)
        if bio_bonus:
            value = f"{value.removesuffix(' CR')}–{_credits(bio_value + bio_bonus)}"
        data_rows.append({
            "label": f"BIOLOGY · {bio_samples} ANALYSES" if bio_samples else "BIOLOGY",
            "value": value,
            "available": "vistagenomics" in service_keys,
            "service": "VISTA",
        })

    station_state = _display_name(getattr(dash, "current_station_state", None))
    type_parts = [station_type]
    if station_state and station_state.casefold() not in ("none", "normal"):
        type_parts.append(station_state.upper())

    return {
        "station": getattr(dash, "current_station_name", None) or "UNKNOWN STATION",
        "system": getattr(dash, "current_sys", None) or "UNKNOWN SYSTEM",
        "type": " · ".join(type_parts),
        "badge": "PERSONAL CARRIER" if is_personal_carrier else "DOCKED",
        "is_personal_carrier": is_personal_carrier,
        "distance": distance_text,
        "pads": " · ".join(pad_parts),
        "core_services": _service_rows(_CORE_SERVICES, service_keys),
        "exploration_services": _service_rows(_EXPLORATION_SERVICES, service_keys),
        "special_services": [
            row["label"] for row in _service_rows(_SPECIAL_SERVICES, service_keys)
            if row["available"]
        ],
        "data_rows": data_rows,
        "economies": _economy_summary(
            getattr(dash, "current_station_economies", None),
            getattr(dash, "current_station_economy", None),
        ),
        "authority": " · ".join(authority_parts),
    }


class StationInfoHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_model = None
        self._hide_job = None
        self._visible = False

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)
        self.canvas = tk.Canvas(
            self.win, width=WIDTH, height=100, bg=overlay_bg, highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        x = _safe_int(config.get("station_info_hud_x"), 30)
        y = _safe_int(config.get("station_info_hud_y"), 380)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._force_topmost()
        self.win.withdraw()

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, _safe_int(
            self.config.get("overlay_topmost_refresh_ms"), 12000,
        ))
        self.win.after(refresh_ms, self._force_topmost)

    def show(self):
        try:
            x = _safe_int(self.config.get("station_info_hud_x"), 30)
            y = _safe_int(self.config.get("station_info_hud_y"), 380)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self._visible = True
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
        self._visible = False

    def _schedule_hide(self):
        if self._hide_job:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        if not self.config.get("station_info_auto_hide_enabled", False):
            return
        timeout_s = max(5, _safe_int(self.config.get("station_info_timeout_s"), 30))
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def on_docked(self, dash):
        self.reconcile(dash, present=True)

    def reconcile(self, dash, present=False):
        """Bring the overlay into line with the settled journal dock state.

        ``present`` is reserved for a real docking/login transition.  Ordinary
        batches may refresh an already-visible card, but must not resurrect a
        card the commander deliberately auto-hid or restart its hide timer.
        """
        docked = bool(getattr(dash, "current_docked", False))
        station = getattr(dash, "current_station_name", None)
        if not docked or not station:
            self.hide()
            return False
        self.refresh(dash)
        if present:
            self.show()
            self._schedule_hide()
        return bool(self._visible)

    def refresh(self, dash):
        """Repaint live docked data without restarting the auto-hide timer."""
        model = build_station_model(dash)
        if model == self._last_model:
            return
        self._last_model = model
        self._redraw(model)

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        if self._last_model is not None:
            self._redraw(self._last_model)

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + event.x - self._dx
        y = self.win.winfo_y() + event.y - self._dy
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    def _drag_end(self, _event):
        self.config["station_info_hud_x"] = self.win.winfo_x()
        self.config["station_info_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    def _text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(
            x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor,
        )
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _status_beacon(self, text, color):
        """Draw the compact chamfered state plate shared by refined overlays."""
        palette = self._palette
        right, left = WIDTH - 18, WIDTH - 176
        top, bottom, chamfer = 10, 32, 7
        plate = (
            left + chamfer, top, right - chamfer, top,
            right, (top + bottom) / 2,
            right - chamfer, bottom, left + chamfer, bottom,
            left, (top + bottom) / 2,
        )
        self.canvas.create_polygon(
            plate, fill=palette["inset"], outline=palette["border_soft"], width=2,
        )
        self.canvas.create_polygon(plate, fill="", outline=color, width=1)
        self._text(
            (left + right) / 2, 21, _truncate(text, 20), color,
            ("Courier", 9, "bold"), "center",
        )

    def _instrument(self, x, y, width, label, value, tone="text"):
        palette = self._palette
        color = palette.get(tone, palette["text"])
        self.canvas.create_rectangle(
            x, y, x + width, y + 49,
            fill=palette["panel"], outline=palette["border_soft"], width=1,
        )
        self.canvas.create_line(x + 1, y + 1, x + 42, y + 1, fill=color, width=2)
        self._text(x + 8, y + 14, label, palette["dim"], ("Courier", 8, "bold"))
        self._text(
            x + 8, y + 34, _truncate(value or "NOT REPORTED", 16), color,
            ("Courier", 9, "bold"),
        )

    def _panel(self, x, y, width, height, label, state="", tone="accent"):
        palette = self._palette
        color = palette.get(tone, palette["accent"])
        self.canvas.create_rectangle(
            x, y, x + width, y + height,
            fill=palette["panel"], outline=palette["border_soft"], width=1,
        )
        self.canvas.create_line(x + 1, y + 1, x + 58, y + 1, fill=color, width=2)
        self._text(x + 9, y + 15, label, color, ("Courier", 8, "bold"))
        if state:
            self._text(
                x + width - 9, y + 15, _truncate(state, 19), palette["dim"],
                ("Courier", 8, "bold"), "e",
            )

    def _service_grid(self, x, y, width, rows):
        """Draw a quiet two-column availability grid without row dividers."""
        column_width = width / 2
        compact_labels = {
            "UNIVERSAL CARTOGRAPHICS": "CARTOGRAPHICS",
            "VISTA GENOMICS": "VISTA GENOMICS",
            "SEARCH & RESCUE": "SEARCH/RESCUE",
        }
        for index, row in enumerate(rows[:4]):
            column = index % 2
            line = index // 2
            item_x = x + column * column_width
            item_y = y + line * 21
            available = bool(row.get("available"))
            color = self._palette["green"] if available else self._palette["dim"]
            symbol = "●" if available else "○"
            label = compact_labels.get(row.get("label"), row.get("label"))
            self._text(
                item_x, item_y,
                f"{symbol} {_truncate(label, 13)}",
                color, ("Courier", 8, "bold"),
            )

    def _redraw(self, model):
        palette = self._palette
        special = model.get("special_services") or []
        data_rows = model.get("data_rows") or []
        core_rows = model.get("core_services") or []
        explorer_rows = model.get("exploration_services") or []
        core_online = sum(bool(row.get("available")) for row in core_rows)
        explorer_online = sum(bool(row.get("available")) for row in explorer_rows)

        data_h = 58 if not data_rows else 39 + min(2, len(data_rows)) * 23
        local_rows = [
            value for value in (
                model.get("economies"), model.get("authority"),
                " · ".join(special) if special else "",
            ) if value
        ]
        local_h = 39 + max(1, min(3, len(local_rows))) * 18
        data_y = 241
        local_y = data_y + data_h + 9
        h = local_y + local_h + 14

        self.canvas.config(width=WIDTH, height=h)
        self.win.geometry(f"{WIDTH}x{h}")
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, h, accent=palette["accent"], bracket_len=12,
            scanlines=True, scanline_step=5,
        )

        self._text(18, 20, "STATION LINK", palette["accent"], ("Courier", 10, "bold"))
        badge_color = (
            palette["orange"] if model.get("is_personal_carrier") else palette["green"]
        )
        self._status_beacon(model["badge"], badge_color)
        self._text(
            18, 51, _truncate(model["station"].upper(), 47), palette["text"],
            ("Courier", 13, "bold"),
        )
        identity = f"{model['system'].upper()} · {model['type']}"
        self._text(
            18, 74, _truncate(identity, 67), palette["muted"],
            ("Courier", 8, "bold"),
        )

        gap = 6
        instrument_w = (WIDTH - 36 - gap * 3) / 4
        pad_grid = " / ".join(
            part.replace(" ", "") for part in str(model.get("pads") or "").split(" · ")
            if part
        )
        metrics = (
            ("CONNECTION", "CARRIER" if model.get("is_personal_carrier") else "LINKED", "orange" if model.get("is_personal_carrier") else "green"),
            ("ARRIVAL", model.get("distance") or "LOCAL", "text"),
            ("PAD GRID", pad_grid or "NOT REPORTED", "text"),
            ("SUPPORT", f"{core_online} CORE · {explorer_online} EXP", "accent"),
        )
        for index, (label, value, tone) in enumerate(metrics):
            self._instrument(
                18 + index * (instrument_w + gap), 89, instrument_w,
                label, value, tone,
            )

        panel_gap = 8
        panel_w = (WIDTH - 36 - panel_gap) / 2
        core_tone = "green" if core_online == len(core_rows) else "orange"
        explorer_tone = "green" if explorer_online else "orange"
        self._panel(
            18, 147, panel_w, 85, "CORE SERVICES",
            f"{core_online}/{len(core_rows)} ONLINE", core_tone,
        )
        self._service_grid(28, 181, panel_w - 20, core_rows)
        self._panel(
            18 + panel_w + panel_gap, 147, panel_w, 85, "EXPLORER SUPPORT",
            f"{explorer_online}/{len(explorer_rows)} ONLINE", explorer_tone,
        )
        self._service_grid(
            28 + panel_w + panel_gap, 181, panel_w - 20, explorer_rows,
        )

        data_ready = sum(bool(row.get("available")) for row in data_rows)
        data_tone = "green" if data_rows and data_ready == len(data_rows) else (
            "orange" if data_rows else "muted"
        )
        data_state = (
            f"{data_ready}/{len(data_rows)} READY" if data_rows else "NONE REPORTED"
        )
        self._panel(18, data_y, WIDTH - 36, data_h, "DATA ONBOARD", data_state, data_tone)
        if data_rows:
            for index, row in enumerate(data_rows[:2]):
                color = palette["green"] if row.get("available") else palette["yellow"]
                readiness = "SALE READY" if row.get("available") else "SERVICE UNAVAILABLE"
                label = f"{row['label']} · {readiness}"
                row_y = data_y + 42 + index * 23
                self._text(28, row_y, _truncate(label, 45), color, ("Courier", 8, "bold"))
                self._text(
                    WIDTH - 28, row_y, row.get("value") or "-", color,
                    ("Courier", 8, "bold"), "e",
                )
        else:
            self._text(
                28, data_y + 42, "NO UNSOLD EXPLORATION OR BIOLOGY DATA REPORTED",
                palette["muted"], ("Courier", 8, "bold"),
            )

        profile_state = f"{len(special)} SPECIALIST" + ("S" if len(special) != 1 else "")
        self._panel(
            18, local_y, WIDTH - 36, local_h, "LOCAL PROFILE",
            profile_state if special else "PORT DOSSIER", "accent",
        )
        if not local_rows:
            local_rows = ["NO ECONOMY OR AUTHORITY DETAILS REPORTED"]
        for index, value in enumerate(local_rows[:3]):
            label = ("SPECIALISTS · " + value) if special and value == " · ".join(special) else value
            self._text(
                28, local_y + 41 + index * 18, _truncate(str(label).upper(), 66),
                palette["text"] if index == 0 else palette["muted"],
                ("Courier", 8, "bold"),
            )
