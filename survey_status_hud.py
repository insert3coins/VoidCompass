"""Compact native Void Compass system/body survey instrument."""

import textwrap
import tkinter as tk
import tkinter.font as tkfont

import bio_values
import themes
from config import save_config
import overlay_chrome
from notable_bodies import build_notable_body_rows

_CHROMA = "#ff00ff"
WIDTH = 420
SIGNAL_FONT = ("Courier", 10, "bold")
BIO_DETAIL_FONT = ("Courier", 9, "bold")
BIO_SYMBOL_FONT = ("Courier", 10, "bold")
BIO_DETAIL_H = 18
SAMPLE_CARD_H = 52


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _truncate(text, max_chars):
    text = str(text or "")
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


def _short_body_name(name, system_name):
    name = str(name or "Unknown body").strip()
    system = str(system_name or "").strip()
    prefix = system + " "
    if system and name.casefold().startswith(prefix.casefold()):
        return name[len(prefix):].strip() or name
    return name


def _planet_label(value):
    label = str(value or "").strip()
    if label.casefold().endswith(" body"):
        label = label[:-5]
    return label


def _body_display_name(name, system_name, planet_class=None, terraformable=False):
    designation = _short_body_name(name, system_name)
    planet = _planet_label(planet_class)
    label = f"{designation} · {planet}" if planet else designation
    if terraformable:
        label += " · TF"
    return label


def _body_matches(item, body_id, body_name):
    if body_id is not None and str(item.get("body_id")) == str(body_id):
        return True
    return bool(body_name and str(item.get("name") or "").casefold() == str(body_name).casefold())


def _signal_record(body_signals, body_id):
    """Find a body's latest signal record across restored int/string keys."""
    if body_id is None or not isinstance(body_signals, dict):
        return None
    for key in (body_id, str(body_id)):
        value = body_signals.get(key)
        if isinstance(value, dict):
            return value
    try:
        value = body_signals.get(int(body_id))
    except (TypeError, ValueError):
        value = None
    return value if isinstance(value, dict) else None


def _survey_bodies(scan_items, body_signals):
    """Merge journal scan rows with the newer surface-signal cache.

    FSS/SAASignalsFound can arrive before the matching detailed ``Scan`` row,
    and restored profiles may briefly hydrate the two caches in separate UI
    passes.  Work on copies so the overlay never mutates dashboard state.
    """
    bodies = [dict(row) for row in (scan_items or []) if not row.get("is_star")]
    represented = set()
    for body in bodies:
        body_id = body.get("body_id")
        if body_id is not None:
            represented.add(str(body_id))
        signals = _signal_record(body_signals, body_id)
        if not signals:
            continue
        body["bio_count"] = _safe_int(signals.get("bio"), _safe_int(body.get("bio_count")))
        body["geo_count"] = _safe_int(signals.get("geo"), _safe_int(body.get("geo_count")))
        body["dss_complete"] = bool(
            body.get("dss_complete") or signals.get("dss_complete")
        )
        if signals.get("genuses"):
            body["genuses"] = list(signals["genuses"])

    # Keep a signal-only body visible until its detailed Scan catches up.
    for body_id, signals in (body_signals or {}).items():
        if not isinstance(signals, dict) or str(body_id) in represented:
            continue
        bio_count = _safe_int(signals.get("bio"))
        geo_count = _safe_int(signals.get("geo"))
        if not bio_count and not geo_count:
            continue
        bodies.append({
            "body_id": body_id,
            "name": signals.get("body_name") or f"Body {body_id}",
            "bio_count": bio_count,
            "geo_count": geo_count,
            "genuses": list(signals.get("genuses") or []),
            "organic_scans": {},
            "organic_complete_count": 0,
            "dss_complete": bool(signals.get("dss_complete")),
        })
    return bodies


def _genus_name(value):
    if isinstance(value, dict):
        return (value.get("Genus_Localised") or value.get("Name_Localised")
                or value.get("name") or value.get("Genus") or value.get("Name"))
    return str(value) if value else ""


def _credits(value):
    value = _safe_int(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} M"
    if value >= 1_000:
        return f"{value / 1_000:.0f} K"
    return f"{value:,}" if value else "-"


def _bio_display_name(name, variant=None):
    """Prefer the localized variant without repeating its species prefix."""
    name = str(name or "Organic").strip()
    variant = str(variant or "").strip()
    if not variant:
        return name
    if variant.casefold().startswith(name.casefold()):
        return variant
    return f"{name} · {variant}"


def _surface_signal_state(bio_count=0, complete=0, geo_count=0, needs_dss=False,
                          palette=None):
    """Return the compact, truthful surface-signal label and colour."""
    palette = palette or themes.ACTIVE_PALETTE
    bio_count = _safe_int(bio_count)
    complete = _safe_int(complete)
    geo_count = _safe_int(geo_count)
    parts = []
    bio_finished = bool(bio_count and complete >= bio_count)
    if bio_count:
        parts.append("BIO COMPLETE" if bio_finished else f"BIO {complete}/{bio_count}")
    if geo_count:
        parts.append(f"GEO {geo_count}")
    if parts:
        if bio_count:
            color = palette["green"] if bio_finished else palette["orange"]
        else:
            color = palette["accent"]
        return " · ".join(parts), color
    return (("DSS REQUIRED", palette["dim"]) if needs_dss
            else ("NO SURFACE SIGNALS", palette["dim"]))


# Row kinds that are inferred rather than journal-confirmed. System mode must
# never show these, so they cannot be mistaken for DSS results.
PREDICTED_KINDS = frozenset({"predicted", "possible"})


def _predicted_display_name(genus, species):
    """Name the species behind a prediction while the row stays HUD-narrow."""
    epithets = []
    for entry in species:
        name = str(entry.get("name") or "").strip()
        if name.casefold().startswith(genus.casefold()):
            epithet = name[len(genus):].strip()
        elif name.casefold().endswith(genus.casefold()):
            # Legacy families are colour-first: Luteolum Anemone, Roseum
            # Brain Tree, and so on.
            epithet = name[:-len(genus)].strip()
        else:
            continue
        if epithet and epithet not in epithets:
            epithets.append(epithet)
    if not epithets or len(epithets) > 2:
        return genus if not epithets else f"{genus} ×{len(epithets)}"
    return f"{genus} {'/'.join(epithets)}"


def _body_value_range(item):
    scans = list((item.get("organic_scans") or {}).values())
    known = sum(_safe_int(bio_values.species_value(scan.get("species"))
                          or scan.get("species_value")) for scan in scans)
    bio_count = _safe_int(item.get("bio_count"))
    unknown = max(0, bio_count - len(scans))
    if not unknown:
        return known, known
    lows = []
    highs = []
    for row in (item.get("genuses") or item.get("predicted_genuses") or []):
        # A prediction now names the species that actually fit the body, so the
        # estimate spans those rather than everything the genus can contain.
        values = [
            _safe_int(entry.get("value"))
            for entry in (row.get("species") or () if isinstance(row, dict) else ())
            if entry.get("value")
        ]
        if not values:
            info = bio_values.genus_info(_genus_name(row))
            values = [
                _safe_int(info.get(bound))
                for bound in ("min_value", "max_value") if info.get(bound)
            ]
        if values:
            lows.append(min(values))
            highs.append(max(values))
    if not lows or not highs:
        return known, known
    return known + unknown * min(lows), known + unknown * max(highs)


def _body_detail_rows(item):
    rows = []
    represented = set()
    scans = list((item.get("organic_scans") or {}).values())
    scans.sort(key=lambda row: (not bool(row.get("is_complete")), str(row.get("species") or "")))
    for scan in scans:
        species = scan.get("species") or scan.get("genus") or "Organic"
        genus = scan.get("genus") or species.split(" ", 1)[0]
        represented.add(str(genus).casefold())
        sample = _safe_int(scan.get("sample_idx"))
        complete = bool(scan.get("is_complete"))
        rows.append({
            "status": "COMPLETE" if complete else (f"SAMPLE {sample}/3" if sample else "LOGGED"),
            "name": species,
            "variant": scan.get("variant") or "",
            "display_name": _bio_display_name(species, scan.get("variant")),
            "value": bio_values.species_value(species) or _safe_int(scan.get("species_value")),
            "kind": "complete" if complete else "sample",
            "progress": 3 if complete else sample,
        })

    for source, kind in ((item.get("genuses") or [], "detected"),
                         (item.get("predicted_genuses") or [], "predicted")):
        for raw in source:
            name = _genus_name(raw)
            key = name.casefold()
            if not name or key in represented:
                continue
            represented.add(key)
            info = bio_values.genus_info(name)
            low = info.get("min_value")
            high = info.get("max_value")
            display = name
            row_kind = kind
            status = "DETECTED" if kind == "detected" else "PREDICTED"
            species = list(raw.get("species") or ()) if isinstance(raw, dict) else []
            if kind == "predicted" and species:
                values = [_safe_int(entry.get("value")) for entry in species if entry.get("value")]
                if values:
                    low, high = min(values), max(values)
                # A candidate resting on a requirement this scan cannot test —
                # galactic region, star class, nearby bodies — is only possible.
                if not any(entry.get("confirmed") for entry in species):
                    row_kind = "possible"
                    status = "POSSIBLE"
                display = _predicted_display_name(name, species)
            rows.append({
                "status": status,
                "name": name,
                "variant": "",
                "display_name": display,
                "min_value": low,
                "max_value": high,
                "kind": row_kind,
                "progress": 0,
            })
    return rows


def _joined_lines(values, max_chars=62):
    """Pack every supplied label into compact lines without a hidden +more."""
    lines = []
    current = ""
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        segments = textwrap.wrap(
            value, width=max_chars, break_long_words=False,
            break_on_hyphens=False,
        ) or [value]
        for segment in segments:
            candidate = f"{current} · {segment}" if current else segment
            if current and len(candidate) > max_chars:
                lines.append(current)
                current = segment
            else:
                current = candidate
    if current:
        lines.append(current)
    return lines


def build_survey_model(system_name, scan_items, focused_body_id=None,
                       focused_body_name=None, sampling=None, scanned=0, total=0,
                       min_notable_value=50_000, palette=None, total_known=True,
                       body_signals=None, belt_clusters=None):
    """Build a renderer-neutral survey model for the overlay and tests."""
    bodies = _survey_bodies(scan_items, body_signals)
    notable_rows = build_notable_body_rows(scan_items, min_notable_value, palette)
    for row in notable_rows:
        row["display_name"] = _body_display_name(
            row.get("name"), system_name, row.get("planet_class"), row.get("terraformable")
        )
    notable_by_id = {
        str(row.get("body_id")): row for row in notable_rows if row.get("body_id") is not None
    }
    notable_by_name = {str(row.get("name") or "").casefold(): row for row in notable_rows}
    focused = next((row for row in bodies if _body_matches(
        row, focused_body_id, focused_body_name)), None)
    if focused and (
        _safe_int(focused.get("bio_count")) > 0
        or _safe_int(focused.get("geo_count")) > 0
        or sampling
    ):
        incomplete = _safe_int(focused.get("organic_complete_count")) < _safe_int(focused.get("bio_count"))
        if incomplete or _safe_int(focused.get("geo_count")) > 0 or sampling:
            lo, hi = _body_value_range(focused)
            focused_notable = (
                notable_by_id.get(str(focused.get("body_id")))
                if focused.get("body_id") is not None else None
            )
            focused_notable = focused_notable or notable_by_name.get(
                str(focused.get("name") or "").casefold()
            )
            focused_notable_key = None
            if focused_notable:
                focused_notable_key = (
                    str(focused_notable.get("body_id")),
                    str(focused_notable.get("name") or "").casefold(),
                )
            return {
                "mode": "body", "system": system_name or "", "body": focused,
                "body_display": _body_display_name(
                    focused.get("name"), system_name, focused.get("planet_class"),
                    focused.get("terraformable"),
                ),
                "rows": _body_detail_rows(focused), "sampling": sampling,
                "min_value": lo, "max_value": hi,
                "notable": focused_notable,
                "notable_rows": [
                    row for row in notable_rows
                    if (
                        str(row.get("body_id")),
                        str(row.get("name") or "").casefold(),
                    ) != focused_notable_key
                ],
                "scanned": _safe_int(scanned), "total": _safe_int(total),
                "total_known": bool(total_known),
            }

    rows = []
    represented_notable = set()
    for body in bodies:
        bio_count = _safe_int(body.get("bio_count"))
        geo_count = _safe_int(body.get("geo_count"))
        complete = _safe_int(body.get("organic_complete_count"))
        needs_dss = not bool(body.get("dss_complete"))
        # Keep every known non-stellar body in the compact system strip. A
        # quiet NO SIGNALS row is still useful survey context and makes the
        # system inventory complete rather than silently filtering planets.
        notable = notable_by_id.get(str(body.get("body_id"))) if body.get("body_id") is not None else None
        notable = notable or notable_by_name.get(str(body.get("name") or "").casefold())
        if notable:
            represented_notable.add((
                str(notable.get("body_id")), str(notable.get("name") or "").casefold(),
            ))
        lo, hi = _body_value_range(body)
        rows.append({
            "name": body.get("name") or "Unknown body",
            "display_name": _body_display_name(
                body.get("name"), system_name, body.get("planet_class"), body.get("terraformable")
            ),
            "planet_class": body.get("planet_class") or "",
            "terraformable": bool(body.get("terraformable")),
            "bio_count": bio_count,
            "geo_count": geo_count,
            "complete": complete,
            "bio_complete": bool(bio_count and complete >= bio_count),
            "needs_dss": needs_dss,
            "min_value": lo,
            "max_value": hi,
            "first_footfall": bool(body.get("first_footfall")),
            "landable": bool(body.get("landable")),
            "gravity_g": body.get("gravity_g"),
            "notable": notable,
            # System mode used to stop at BIO 0/N. Include only journal-
            # identified genera/species here; predictions remain exclusive to
            # the focused-body view so they cannot be mistaken for DSS facts.
            "bio_details": [
                detail for detail in _body_detail_rows(body)
                if detail.get("kind") not in PREDICTED_KINDS
            ],
        })
    rows.sort(key=lambda row: (
        bool(row["bio_complete"]),
        not bool(row["bio_count"] or row["geo_count"]),
        not bool(row["bio_count"]), row["name"],
    ))
    remaining_notable = [
        row for row in notable_rows
        if (str(row.get("body_id")), str(row.get("name") or "").casefold()) not in represented_notable
    ]
    scan_in_progress = bool(
        total_known and _safe_int(total) > 0 and _safe_int(scanned) < _safe_int(total)
    )
    if not rows and not remaining_notable and not sampling and not scan_in_progress:
        return None
    return {
        "mode": "system", "system": system_name or "", "rows": rows,
        "notable_rows": remaining_notable, "sampling": sampling,
        "scanned": _safe_int(scanned), "total": _safe_int(total),
        "total_known": bool(total_known),
        "notable_count": len(notable_rows),
        "scan_in_progress": scan_in_progress,
    }


def _survey_render_key(model):
    """Key only pixels the Survey Operations renderer can actually change."""
    model = model or {}
    sampling = model.get("sampling")
    sampling_key = None
    if sampling:
        minimum = sampling.get("min_distance_m")
        if minimum is not None:
            # Ten-metre steps stay useful in the cockpit without rebuilding
            # the whole overlay for every metre reported by Status.json.
            minimum = _safe_int(minimum)
            minimum = int(round(minimum / 10.0) * 10)
        sampling_key = (
            sampling.get("species"), _safe_int(sampling.get("progress"), 1),
            sampling.get("colony_m"), minimum, sampling.get("clear"),
        )

    def notable_key(row):
        row = row or {}
        return (
            row.get("display_name") or row.get("name"), row.get("icons"),
            row.get("name_color"), row.get("value_line"), row.get("value_color"),
        )

    def detail_key(row):
        row = row or {}
        return (
            row.get("kind"), row.get("status"),
            row.get("display_name") or row.get("name"),
            row.get("value"), row.get("min_value"), row.get("max_value"),
            _safe_int(row.get("progress")),
        )

    common = (
        model.get("mode"), model.get("system"), sampling_key,
        tuple(notable_key(row) for row in model.get("notable_rows") or ()),
    )
    if model.get("mode") == "body":
        body = model.get("body") or {}
        return common + (
            model.get("body_display") or body.get("name"),
            _safe_int(body.get("bio_count")),
            _safe_int(body.get("organic_complete_count")),
            _safe_int(body.get("geo_count")), bool(body.get("dss_complete")),
            bool(body.get("first_footfall")), bool(body.get("landable")),
            body.get("gravity_g"),
            notable_key(model.get("notable")) if model.get("notable") else None,
            tuple(detail_key(row) for row in model.get("rows") or ()),
            model.get("min_value"), model.get("max_value"),
        )

    row_keys = []
    for row in model.get("rows") or ():
        row_keys.append((
            row.get("display_name") or row.get("name"),
            _safe_int(row.get("bio_count")), _safe_int(row.get("geo_count")),
            _safe_int(row.get("complete")), bool(row.get("bio_complete")),
            bool(row.get("needs_dss")), row.get("min_value"), row.get("max_value"),
            notable_key(row.get("notable")) if row.get("notable") else None,
            tuple(detail_key(detail) for detail in row.get("bio_details") or ()),
        ))
    return common + (
        tuple(row_keys), _safe_int(model.get("notable_count")),
        bool(model.get("scan_in_progress")),
    )


def _signal_node_states(signal_count, details=None, complete_count=0):
    """Return one truthful visual state for each biological signal slot.

    Compact biological nodes keep the signal count readable at a glance and
    deliberately use only journal-backed
    states: analysed, currently sampled, DSS-detected, or unresolved.
    """
    signal_count = max(0, _safe_int(signal_count))
    details = list(details or ())
    complete = max(
        _safe_int(complete_count),
        sum(1 for row in details if row.get("kind") == "complete"),
    )
    sampled = sum(1 for row in details if row.get("kind") == "sample")
    detected = sum(1 for row in details if row.get("kind") == "detected")
    states = (
        ["complete"] * complete
        + ["sample"] * sampled
        + ["detected"] * detected
    )[:signal_count]
    states.extend(["unresolved"] * (signal_count - len(states)))
    return states


class SurveyStatusHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_update = None
        self._last_render_key = None
        self._last_height = None
        self._suppressed = False
        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)
        self.canvas = tk.Canvas(self.win, width=WIDTH, height=90, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        x = _safe_int(config.get("survey_status_hud_x"), 30)
        y = _safe_int(config.get("survey_status_hud_y"), 520)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._force_topmost()
        self.win.withdraw()
        self._visible = False

    def _force_topmost(self):
        """Set persistent topmost state once; show() reapplies it after hiding."""
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass

    def show(self):
        if self._visible or self._suppressed:
            return False
        try:
            x = _safe_int(self.config.get("survey_status_hud_x"), 30)
            y = _safe_int(self.config.get("survey_status_hud_y"), 520)
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self._visible = True
            return True
        except Exception:
            return False

    def hide(self):
        if not self._visible:
            return False
        try:
            self.win.withdraw()
        except Exception:
            return False
        self._visible = False
        return True

    def suppress(self):
        """Hide while retaining the current survey for a later undock."""
        if self._suppressed and not self._visible:
            return False
        self._suppressed = True
        return self.hide()

    def resume(self, refresh=True):
        """Permit survey display again, optionally repainting cached data."""
        self._suppressed = False
        if refresh and self._last_update is not None:
            self.update(*self._last_update)

    def update(self, system_name, scanned, total, scan_items, body_signals,
               sampling=None, focused_body_id=None, focused_body_name=None,
               total_known=True, belt_clusters=None):
        self._last_update = (
            system_name, scanned, total, scan_items, body_signals,
            sampling, focused_body_id, focused_body_name, total_known,
            belt_clusters,
        )
        if self._suppressed:
            return
        model = build_survey_model(system_name, scan_items, focused_body_id,
                                   focused_body_name, sampling, scanned, total,
                                   _safe_int(self.config.get("system_info_min_value"), 50_000),
                                   self._palette, total_known,
                                   body_signals=body_signals,
                                   belt_clusters=belt_clusters)
        if not model:
            self._last_render_key = None
            self.hide()
            return
        render_key = _survey_render_key(model)
        if render_key != self._last_render_key:
            self._last_render_key = render_key
            self._redraw(model)
        self.show()

    def apply_theme(self, palette=None):
        """Adopt the active profile palette and repaint the cached survey."""
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._last_render_key = None
        if self._last_update is not None:
            self.update(*self._last_update)

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + event.x - self._dx
        y = self.win.winfo_y() + event.y - self._dy
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._desired_pos = (x, y)
        self.config["survey_status_hud_x"] = x
        self.config["survey_status_hud_y"] = y

    def _drag_end(self, _event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
        self._desired_pos = (x, y)
        self.config["survey_status_hud_x"] = x
        self.config["survey_status_hud_y"] = y
        try:
            save_config(self.config)
        except Exception:
            pass

    def _text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)


    def _draw_completion_rail(self, x1, x2, y, complete, total, color):
        """Draw a quiet segmented bio-completion rail below the system line."""
        total = max(0, _safe_int(total))
        complete = max(0, min(total, _safe_int(complete)))
        if not total:
            return
        palette = self._palette
        self.canvas.create_line(x1, y, x2, y, fill=palette["border_soft"], width=3)
        if complete:
            finish = x1 + ((x2 - x1) * complete / total)
            self.canvas.create_line(x1, y, finish, y, fill=color, width=3)
        if total <= 12:
            for index in range(1, total):
                x = x1 + ((x2 - x1) * index / total)
                self.canvas.create_line(x, y - 2, x, y + 2, fill=palette["panel"], width=1)

    def _draw_signal_nodes(self, x, y, signal_count, details=None, complete_count=0):
        """Draw Void Compass biological nodes and return their right edge."""
        palette = self._palette
        states = _signal_node_states(signal_count, details, complete_count)
        if not states:
            return x
        spacing = 13
        self.canvas.create_line(
            x, y, x + ((len(states) - 1) * spacing), y,
            fill=palette["border_soft"], width=1,
        )
        for index, state in enumerate(states):
            cx = x + index * spacing
            colors = {
                "complete": (palette["green"], palette["green"]),
                "sample": (palette["orange"], palette["orange"]),
                "detected": (palette["panel"], palette["accent"]),
                "unresolved": (palette["panel"], palette["dim"]),
            }
            fill, outline = colors[state]
            self.canvas.create_oval(
                cx - 4, y - 4, cx + 4, y + 4,
                fill=fill, outline=outline,
                width=2 if state in {"complete", "sample"} else 1,
            )
            if state == "detected":
                self.canvas.create_oval(
                    cx - 1, y - 1, cx + 1, y + 1,
                    fill=palette["accent"], outline="",
                )
            elif state == "sample":
                self.canvas.create_oval(
                    cx - 1, y - 1, cx + 1, y + 1,
                    fill=palette["panel"], outline="",
                )
        return x + ((len(states) - 1) * spacing) + 5

    def _notable_row(self, row, y):
        label = row.get("display_name") or row["name"]
        name = f"{row['icons']} {label}" if row.get("icons") else label
        self._text(20, y, _truncate(name, 36), row["name_color"], ("Courier", 8, "bold"))
        self._text(28, y + 15, "SURVEY VALUE", self._palette["dim"], ("Courier", 7, "bold"))
        self._text(WIDTH - 18, y + 15, row["value_line"], row["value_color"], ("Courier", 7, "bold"), "e")
        return y + 34

    @staticmethod
    def _range_text(low, high):
        if not high:
            return ""
        return _credits(low) if low == high else f"{_credits(low)}–{_credits(high)}"

    def _resize(self, height):
        """Keep geometry stable when only survey text or progress changes."""
        if height == self._last_height:
            return
        self._last_height = height
        self.canvas.config(width=WIDTH, height=height)
        x, y_pos = self._desired_pos
        self.win.geometry(overlay_chrome.position_geometry(x, y_pos, WIDTH, height))

    @staticmethod
    def _compact_detail_text(detail):
        """Build the short evidence token used by the compact survey strip."""
        kind = str((detail or {}).get("kind") or "")
        symbol = {
            "complete": "✓", "sample": "●", "detected": "○",
            "predicted": "?", "possible": "·",
        }.get(kind, "·")
        label = _truncate(
            (detail or {}).get("display_name") or (detail or {}).get("name") or "Organic",
            31,
        )
        progress = max(0, min(3, _safe_int((detail or {}).get("progress"))))
        suffix = f" {progress}/3" if kind == "sample" and progress else ""
        return f"{symbol} {label}{suffix}"

    def _compact_detail_groups(self, details):
        """Flow organism names horizontally instead of building a table."""
        font = tkfont.Font(font=overlay_chrome.scaled_font(
            ("Courier", 8, "bold"), self.config,
        ))
        max_width = WIDTH - 48
        groups = []
        current = []
        used = 0.0
        for detail in details or ():
            token = self._compact_detail_text(detail)
            added = float(font.measure(token)) + (14 if current else 0)
            if current and used + added > max_width:
                groups.append(current)
                current = []
                used = 0.0
                added = float(font.measure(token))
            current.append(detail)
            used += added
        if current:
            groups.append(current)
        return groups

    def _compact_detail_color(self, detail):
        kind = str((detail or {}).get("kind") or "")
        if kind == "complete":
            return self._palette["green"]
        if kind == "sample":
            return self._palette["orange"]
        if kind == "detected":
            return self._palette["text"]
        return self._palette["dim"]

    def _draw_compact_detail_group(self, group, y):
        """Draw one individually coloured, horizontally flowing evidence row."""
        font_spec = ("Courier", 8, "bold")
        font = tkfont.Font(font=overlay_chrome.scaled_font(font_spec, self.config))
        x = 24.0
        for detail in group:
            token = self._compact_detail_text(detail)
            self._text(
                x, y, token, self._compact_detail_color(detail),
                font_spec,
            )
            x += font.measure(token) + 14

    def _draw_sample_sequence(self, sampling, y):
        """Render active sampling as a Void Compass genetic flightpath."""
        palette = self._palette
        progress = max(1, min(3, _safe_int((sampling or {}).get("progress"), 1)))
        colony = (sampling or {}).get("colony_m")
        minimum = (sampling or {}).get("min_distance_m")
        clear = bool((sampling or {}).get("clear"))
        centre_y = y + 16
        self.canvas.create_line(
            28, centre_y, 84, centre_y,
            fill=palette["border_soft"], width=2,
        )
        if progress > 1:
            self.canvas.create_line(
                28, centre_y, 28 + ((progress - 1) * 28), centre_y,
                fill=palette["orange"], width=2,
            )
        for index in range(3):
            x = 28 + index * 28
            done = index < progress
            self.canvas.create_oval(
                x - 9, centre_y - 9, x + 9, centre_y + 9,
                fill=palette["panel"] if not done else palette["panel_raised"],
                outline=palette["orange"] if done else palette["dim"],
                width=2 if done else 1,
            )
            if done:
                self.canvas.create_oval(
                    x - 2, centre_y - 2, x + 2, centre_y + 2,
                    fill=palette["orange"], outline="",
                )
        self._text(
            104, y + 6, _truncate((sampling or {}).get("species"), 42),
            palette["accent"], ("Courier", 10, "bold"),
        )
        status = (
            "CLEAR FOR NEXT" if clear
            else f"{_safe_int(minimum):,}/{_safe_int(colony):,} M"
            if minimum is not None and colony
            else "SEEK NEXT COLONY"
        )
        self._text(104, y + 31, f"SAMPLE {progress}/3", palette["muted"], ("Courier", 8, "bold"))
        self._text(
            WIDTH - 18, y + 31, status,
            palette["green"] if clear else palette["text"],
            ("Courier", 8, "bold"), "e",
        )
        if minimum is not None and colony:
            x1, x2, rail_y = 236, WIDTH - 18, y + 41
            ratio = max(0.0, min(1.0, float(minimum) / max(1.0, float(colony))))
            self.canvas.create_line(x1, rail_y, x2, rail_y, fill=palette["border_soft"], width=2)
            self.canvas.create_line(
                x1, rail_y, x1 + ((x2 - x1) * ratio), rail_y,
                fill=palette["green"] if clear else palette["accent"], width=2,
            )
        return y + SAMPLE_CARD_H

    @staticmethod
    def _sampling_matches_detail(sampling, detail):
        if not sampling or not detail:
            return False
        sample = str(sampling.get("species") or "").casefold()
        names = {
            str(detail.get(key) or "").casefold()
            for key in ("name", "display_name")
        }
        return bool(sample and any(name and (name in sample or sample in name) for name in names))

    def _redraw(self, model):
        """Draw the compact Void Compass biological instrument."""
        palette = self._palette
        is_body = model["mode"] == "body"
        rows = list(model.get("rows") or [])
        sampling = model.get("sampling")
        notable_rows = list(model.get("notable_rows") or [])

        if is_body:
            body = model.get("body") or {}
            body_bio_count = _safe_int(body.get("bio_count"))
            body_bio_done = _safe_int(body.get("organic_complete_count"))
            body_bio_complete = bool(
                body_bio_count and body_bio_done >= body_bio_count and not sampling
            )
            detail_rows = [
                row for row in rows
                if not self._sampling_matches_detail(sampling, row)
            ]
            # Once this surface's biology is finished, its BIO N/N header and
            # base-value footer are the useful cockpit receipt. The full
            # species manifest remains in Explore & Survey rather than keeping
            # this persistent overlay tall.
            detail_groups = (
                [] if body_bio_complete
                else self._compact_detail_groups(detail_rows)
            )
            geo_count = _safe_int(body.get("geo_count"))
            body_notable = model.get("notable")
            content_h = (
                (SAMPLE_CARD_H if sampling else 0)
                + len(detail_groups) * 18
                + (17 if geo_count else 0)
                + (16 if body_notable else 0)
            )
            height = max(96, 68 + content_h + 25)
        else:
            active_rows = [
                row for row in rows
                if _safe_int(row.get("bio_count")) and not row.get("bio_complete")
            ]
            completed_rows = [row for row in rows if row.get("bio_complete")]
            neutral_rows = [
                row for row in rows
                if row not in active_rows and row not in completed_rows
            ]
            ordered_rows = active_rows + neutral_rows + completed_rows
            row_layout = []
            content_h = 0
            for row in ordered_rows:
                groups = (
                    [] if row.get("bio_complete")
                    else self._compact_detail_groups(row.get("bio_details") or [])
                )
                row_h = 20 + len(groups) * 17
                if _safe_int(row.get("geo_count")):
                    row_h += 15
                if row.get("notable"):
                    row_h += 14
                row_layout.append((row, groups, row_h))
                content_h += row_h
            if completed_rows:
                content_h += 16
            notable_h = (18 + len(notable_rows) * 30) if notable_rows else 0
            height = max(92, 68 + content_h + notable_h + 25)

        self._resize(height)
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, height, accent=palette["accent"],
            bracket_len=9, scanlines=False,
        )

        self._text(16, 18, "SURVEY OPERATIONS", palette["accent"], ("Courier", 9, "bold"))
        self._text(
            WIDTH - 16, 18, _truncate(model.get("system", "").upper(), 30),
            palette["muted"], ("Courier", 8, "bold"), "e",
        )

        if is_body:
            body = model.get("body") or {}
            bio_count = _safe_int(body.get("bio_count"))
            bio_done = _safe_int(body.get("organic_complete_count"))
            geo_count = _safe_int(body.get("geo_count"))
            body_label = model.get("body_display") or body.get("name") or "SURFACE"
            self._text(16, 42, _truncate(body_label, 22), palette["orange"], ("Courier", 8, "bold"))
            bio_complete = bool(bio_count and bio_done >= bio_count and not sampling)
            summary = (
                f"BIO {bio_done}/{bio_count} ✓"
                if bio_complete else f"BIO {bio_done}/{bio_count}"
            )
            if geo_count:
                summary += f" · GEO {geo_count}"
            self._text(WIDTH - 16, 42, summary, palette["text"], ("Courier", 8, "bold"), "e")
            self._draw_completion_rail(16, WIDTH - 16, 56, bio_done, bio_count, palette["orange"])
            y = 72
            if sampling:
                y = self._draw_sample_sequence(sampling, y)
            for group in detail_groups:
                self._draw_compact_detail_group(group, y)
                y += 18
            if geo_count:
                self._text(24, y, f"◇ GEOLOGICAL SIGNALS ×{geo_count}", palette["accent"], ("Courier", 8, "bold"))
                y += 17
            if model.get("notable"):
                notable = model["notable"]
                label = f"{notable.get('icons', '')} NOTABLE BODY".strip()
                self._text(24, y, label, notable["name_color"], ("Courier", 7, "bold"))
                self._text(WIDTH - 16, y, notable["value_line"], notable["value_color"], ("Courier", 7, "bold"), "e")
            low, high = model.get("min_value"), model.get("max_value")
            value = self._range_text(low, high) or "-"
            exact_complete = bool(bio_complete and high and low == high)
            value_label = "BIO BASE" if exact_complete else "ESTIMATED BIO BASE"
            self._text(16, height - 14, value_label, palette["dim"], ("Courier", 7, "bold"))
            self._text(
                WIDTH - 16, height - 14, value,
                palette["green"] if exact_complete else palette["orange"],
                ("Courier", 8, "bold"), "e",
            )
            return

        active_rows = [
            row for row in rows
            if _safe_int(row.get("bio_count")) and not row.get("bio_complete")
        ]
        completed_rows = [row for row in rows if row.get("bio_complete")]
        neutral_rows = [
            row for row in rows
            if row not in active_rows and row not in completed_rows
        ]
        ordered_rows = active_rows + neutral_rows + completed_rows
        bio_total = sum(_safe_int(row.get("bio_count")) for row in rows)
        bio_done = sum(_safe_int(row.get("complete")) for row in rows)
        geo_total = sum(_safe_int(row.get("geo_count")) for row in rows)
        left_summary = f"BIO SIGNALS {bio_total} | ANALYSED {bio_done} | GEO {geo_total}"
        if not rows and model.get("scan_in_progress"):
            left_summary = "FSS INTAKE ACTIVE | TARGETS PENDING"
        self._text(16, 42, left_summary, palette["orange"], ("Courier", 8, "bold"))
        self._draw_completion_rail(16, WIDTH - 16, 56, bio_done, bio_total, palette["green"])
        y = 72
        short_names = [
            _truncate(_short_body_name(row.get("name"), model.get("system")), 14)
            for row in ordered_rows
        ]
        widest_name = max((len(name) for name in short_names), default=3)
        node_label_x = min(140, 24 + widest_name * 8)
        completed_start = len(active_rows) + len(neutral_rows)
        for row_index, (row, groups, _row_h) in enumerate(row_layout):
            if completed_rows and row_index == completed_start:
                self._text(
                    16, y, "COMPLETED BIOLOGY",
                    palette["dim"], ("Courier", 7, "bold"),
                )
                self._text(
                    WIDTH - 16, y,
                    f"{len(completed_rows)} SURFACE{'S' if len(completed_rows) != 1 else ''}",
                    palette["green"], ("Courier", 7, "bold"), "e",
                )
                y += 16
            bio_count = _safe_int(row.get("bio_count"))
            geo_count = _safe_int(row.get("geo_count"))
            complete = _safe_int(row.get("complete"))
            completed = bool(row.get("bio_complete"))
            has_signals = bool(bio_count or geo_count)
            row_color = palette["green"] if completed else (
                palette["muted"] if not has_signals else palette["orange"]
            )
            prefix = "✓ " if completed else ""
            self._text(
                16, y, prefix + short_names[row_index],
                row_color, ("Courier", 8, "bold"),
            )
            if bio_count:
                self._text(node_label_x, y, "BIO", palette["dim"], ("Courier", 7, "bold"))
                self._draw_signal_nodes(
                    node_label_x + 28, y, bio_count,
                    row.get("bio_details"), complete,
                )
            value = self._range_text(row.get("min_value"), row.get("max_value"))
            if completed and value:
                value = f"BASE {value}"
            if not value and row.get("needs_dss"):
                value = "DSS REQUIRED"
            elif not value and not has_signals:
                value = "NO SIGNALS"
            self._text(
                WIDTH - 16, y, value,
                palette["green"] if completed else palette["orange"] if has_signals else palette["dim"],
                ("Courier", 7, "bold"), "e",
            )
            y += 20
            for group in groups:
                self._draw_compact_detail_group(group, y)
                y += 17
            if geo_count:
                self._text(24, y, f"◇ GEO ×{geo_count}", palette["accent"], ("Courier", 7, "bold"))
                y += 15
            if row.get("notable"):
                notable = row["notable"]
                self._text(24, y, "NOTABLE BODY", palette["dim"], ("Courier", 7, "bold"))
                self._text(WIDTH - 16, y, notable["value_line"], notable["value_color"], ("Courier", 7, "bold"), "e")
                y += 14

        if notable_rows:
            self._text(16, y + 5, f"VALUABLE / NOTABLE {len(notable_rows)}", palette["dim"], ("Courier", 7, "bold"))
            y += 18
            for notable in notable_rows:
                y = self._notable_row(notable, y)

        total_low = sum(_safe_int(row.get("min_value")) for row in rows)
        total_high = sum(_safe_int(row.get("max_value")) for row in rows)
        footer = f"BODIES {len(rows)} · OPEN {len(active_rows)} · COMPLETE {len(completed_rows)}"
        value = self._range_text(total_low, total_high)
        self._text(16, height - 14, footer, palette["dim"], ("Courier", 7, "bold"))
        self._text(WIDTH - 16, height - 14, f"BIO BASE {value}" if value else "", palette["orange"], ("Courier", 7, "bold"), "e")
