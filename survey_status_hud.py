"""Native system/body survey strip inspired by SrvSurvey's bio plotter."""

import textwrap
import tkinter as tk

import bio_values
import themes
from config import save_config
import overlay_chrome
from notable_bodies import build_notable_body_rows

_CHROMA = "#ff00ff"
WIDTH = 520
SIGNAL_FONT = ("Courier", 10, "bold")
BIO_DETAIL_FONT = ("Courier", 9, "bold")
BIO_SYMBOL_FONT = ("Courier", 10, "bold")
BIO_DETAIL_H = 18


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


def _distance_ls(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if value < 10:
        return f"{value:.2f} LS"
    if value < 1_000:
        return f"{value:.1f} LS"
    return f"{value:,.0f} LS"


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


def _belt_cluster_rows(system_name, belt_clusters):
    """Normalise journal belt contacts without treating them as FSS bodies."""
    rows = []
    seen = set()
    for raw in belt_clusters or ():
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or raw.get("body_name") or "").strip()
        body_id = raw.get("body_id")
        key = str(body_id) if body_id is not None else name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        rows.append({
            "body_id": body_id,
            "name": name,
            "display_name": _short_body_name(name, system_name),
            "distance": _distance_ls(raw.get("distance_ls")),
            "new_discovery": raw.get("was_discovered") is False,
        })
    rows.sort(key=lambda row: (
        _safe_int(row.get("body_id"), 999_999), row.get("display_name", ""),
    ))
    return rows


def build_survey_model(system_name, scan_items, focused_body_id=None,
                       focused_body_name=None, sampling=None, scanned=0, total=0,
                       min_notable_value=50_000, palette=None, total_known=True,
                       body_signals=None, belt_clusters=None):
    """Build a renderer-neutral survey model for the overlay and tests."""
    bodies = _survey_bodies(scan_items, body_signals)
    notable_rows = build_notable_body_rows(scan_items, min_notable_value, palette)
    belt_rows = _belt_cluster_rows(system_name, belt_clusters)
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
                "belt_clusters": belt_rows,
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
        # Bodies resolved by FSS remain actionable until DSS assessment. This
        # keeps Survey Operations alive while the commander is actively tuning
        # bodies without duplicating Navigation's system percentage.
        if not needs_dss and not bio_count and not geo_count:
            continue
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
    if not rows and not remaining_notable and not belt_rows and not sampling and not scan_in_progress:
        return None
    return {
        "mode": "system", "system": system_name or "", "rows": rows,
        "notable_rows": remaining_notable, "sampling": sampling,
        "scanned": _safe_int(scanned), "total": _safe_int(total),
        "total_known": bool(total_known),
        "notable_count": len(notable_rows),
        "scan_in_progress": scan_in_progress,
        "belt_clusters": belt_rows,
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
    belt_keys = tuple(
        (
            row.get("body_id"), row.get("display_name"), row.get("distance"),
            bool(row.get("new_discovery")),
        )
        for row in model.get("belt_clusters") or ()
    )
    return common + (
        tuple(row_keys), _safe_int(model.get("notable_count")),
        bool(model.get("scan_in_progress")), belt_keys,
    )


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

    def _sample_row(self, sampling, y):
        if not sampling:
            return y
        progress = max(1, min(3, _safe_int(sampling.get("progress"), 1)))
        colony = sampling.get("colony_m")
        minimum = sampling.get("min_distance_m")
        clear = sampling.get("clear")
        status = (
            "CLEAR FOR NEXT" if clear
            else f"SPACE {_safe_int(minimum):,}/{_safe_int(colony):,} M"
            if minimum is not None and colony
            else "SEEK NEXT COLONY"
        )
        pips = "".join("●" if index <= progress else "○" for index in range(1, 4))
        palette = self._palette
        self.canvas.create_rectangle(
            16, y - 11, WIDTH - 16, y + 12,
            fill=palette["panel_alt"], outline=palette["border_soft"],
        )
        self._text(24, y, f"{pips} {progress}/3 · {_truncate(sampling.get('species'), 31)}", palette["orange"], ("Courier", 8, "bold"))
        self._text(WIDTH - 24, y, status, palette["green"] if clear else palette["text"], ("Courier", 8, "bold"), "e")
        return y + 28

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

    def _redraw(self, model):
        palette = self._palette
        is_body = model["mode"] == "body"
        rows = model["rows"]
        active_rows = rows if is_body else [row for row in rows if not row.get("bio_complete")]
        completed_rows = [] if is_body else [row for row in rows if row.get("bio_complete")]
        notable_rows = model.get("notable_rows") or []
        belt_rows = [] if is_body else (model.get("belt_clusters") or [])
        sample_h = 28 if model.get("sampling") else 0

        if is_body:
            body = model["body"]
            bio_count = _safe_int(body.get("bio_count"))
            geo_count = _safe_int(body.get("geo_count"))
            bio_h = (20 + max(1, len(rows)) * 19) if bio_count or rows else 0
            geo_h = 19 if geo_count else 0
            content_h = 52 + bio_h + geo_h
        else:
            content_h = (
                20 + sum(
                    (21 if row.get("bio_count") or row.get("geo_count") else 19)
                    + len(row.get("bio_details") or []) * BIO_DETAIL_H
                    + (15 if row.get("notable") else 0)
                    for row in active_rows
                )
            ) if active_rows else 0
        completed_h = (
            24 + sum(
                19 + 15 * len(_joined_lines(
                    [
                        detail.get("display_name") or detail.get("name") or "Organic"
                        for detail in (row.get("bio_details") or [])
                    ]
                ))
                for row in completed_rows
            )
        ) if completed_rows else 0
        notable_h = (20 + len(notable_rows) * 34) if notable_rows else 0
        belt_h = (24 + len(belt_rows) * 18) if belt_rows else 0
        h = 89 + sample_h + content_h + belt_h + notable_h + completed_h + 29
        self._resize(h)
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, h, accent=palette["accent"], bracket_len=10,
            scanlines=False,
        )
        title = "SURVEY OPERATIONS"
        self._text(18, 18, title, palette["accent"], ("Courier", 10, "bold"))
        if is_body:
            self._text(WIDTH - 18, 18, "FIELD FOCUS", palette["orange"], ("Courier", 8, "bold"), "e")
        self._text(18, 48, _truncate(model["system"].upper(), 58), palette["text"], ("Courier", 10, "bold"))
        if is_body:
            body = model["body"]
            bio_count = _safe_int(body.get("bio_count"))
            bio_done = _safe_int(body.get("organic_complete_count"))
            geo_count = _safe_int(body.get("geo_count"))
            dss_state = "DSS MAPPED" if body.get("dss_complete") else "DSS PENDING"
            header_summary = f"FOCUSED SURFACE · BIO {bio_done}/{bio_count} · GEO {geo_count}"
        else:
            bio_total = sum(_safe_int(row.get("bio_count")) for row in rows)
            geo_total = sum(_safe_int(row.get("geo_count")) for row in rows)
            if not rows and model.get("scan_in_progress"):
                header_summary = "FSS INTAKE ACTIVE · SURVEY TARGETS PENDING"
            else:
                header_summary = f"{len(active_rows)} OPEN · {len(completed_rows)} BIO COMPLETE · BIO {bio_total} · GEO {geo_total}"
        self._text(18, 66, header_summary, palette["muted"], ("Courier", 8, "bold"))
        y = 93

        if is_body:
            body = model["body"]
            count = _safe_int(body.get("bio_count"))
            geo = _safe_int(body.get("geo_count"))
            done = _safe_int(body.get("organic_complete_count"))
            signal_state, signal_color = _surface_signal_state(
                count, done, geo, needs_dss=not bool(body.get("dss_complete")),
                palette=palette,
            )
            notable = model.get("notable")
            tags = []
            if notable:
                tags.append("NOTABLE")
            if body.get("first_footfall"):
                tags.append("FIRST FOOTFALL")
            elif body.get("landable"):
                tags.append("LANDABLE")
            gravity = body.get("gravity_g")
            try:
                if gravity is not None:
                    tags.append(f"{float(gravity):.2f} G")
            except (TypeError, ValueError):
                pass
            tag_text = " · ".join(tags) or "SURFACE TARGET"
            body_label = model.get("body_display") or body.get("name")
            if notable and notable.get("icons"):
                body_label = f"{notable['icons']} {body_label}"
            self.canvas.create_rectangle(
                14, y - 11, WIDTH - 14, y + 35,
                fill=palette["panel_alt"], outline=palette["border_soft"],
            )
            self._text(24, y, _truncate(body_label, 35), palette["orange"], ("Courier", 8, "bold"))
            self._text(WIDTH - 24, y, tag_text, palette["muted"], ("Courier", 7, "bold"), "e")
            self._text(24, y + 20, signal_state, signal_color, SIGNAL_FONT)
            self._text(WIDTH - 24, y + 20, dss_state, palette["green"] if body.get("dss_complete") else palette["dim"], ("Courier", 8, "bold"), "e")
            y += 52
            y = self._sample_row(model.get("sampling"), y)

            if count or rows:
                self._text(18, y, "BIOLOGICAL EVIDENCE", palette["dim"], ("Courier", 7, "bold"))
                self._text(WIDTH - 18, y, "STATE / BASE VALUE", palette["dim"], ("Courier", 7, "bold"), "e")
                y += 20
                if not rows:
                    self._text(30, y, "○", palette["dim"], BIO_SYMBOL_FONT)
                    self._text(46, y, "Awaiting DSS identification", palette["dim"], BIO_DETAIL_FONT)
                    y += 19
                for row in rows:
                    symbol = {
                        "complete": "✓", "sample": "●", "detected": "○",
                        "predicted": "?", "possible": "·",
                    }.get(row["kind"], "·")
                    color = (
                        palette["green"] if row["kind"] == "complete"
                        else palette["orange"] if row["kind"] == "sample"
                        else palette["text"] if row["kind"] == "detected"
                        else palette["dim"]
                    )
                    label = row.get("display_name") or row["name"]
                    value = row.get("value")
                    if value:
                        value_text = _credits(value)
                    else:
                        value_text = self._range_text(row.get("min_value"), row.get("max_value")) or "-"
                    state_value = f"{row.get('status') or 'LOGGED'} · {value_text}"
                    self._text(20, y, symbol, color, ("Courier", 9, "bold"))
                    self._text(38, y, _truncate(label, 34), color, ("Courier", 8, "bold"))
                    self._text(WIDTH - 18, y, state_value, color, ("Courier", 8, "bold"), "e")
                    y += 19

            if geo:
                self._text(20, y, "◇", palette["accent"], BIO_SYMBOL_FONT)
                self._text(38, y, "GEOLOGICAL SIGNALS", palette["text"], BIO_DETAIL_FONT)
                self._text(WIDTH - 18, y, f"{geo} CONFIRMED", palette["accent"], BIO_DETAIL_FONT, "e")
                y += 19
        else:
            if active_rows:
                self._text(18, y, "OPEN SURVEY WORK", palette["dim"], ("Courier", 7, "bold"))
                self._text(WIDTH - 18, y, "STATUS / BASE VALUE", palette["dim"], ("Courier", 7, "bold"), "e")
                y += 20
            for row in active_rows:
                bio = row["bio_count"]
                geo = row["geo_count"]
                state, color = _surface_signal_state(
                    bio, row["complete"], geo, needs_dss=row["needs_dss"],
                    palette=palette,
                )
                lo, hi = row["min_value"], row["max_value"]
                value_text = self._range_text(lo, hi)
                estimate = f" · {value_text}" if value_text else ""
                notable = row.get("notable")
                label = row.get("display_name") or row["name"]
                name = f"{notable['icons']} {label}" if notable and notable.get("icons") else label
                self._text(20, y, _truncate(name, 34), color, ("Courier", 8, "bold"))
                status_font = SIGNAL_FONT if bio or geo else ("Courier", 8, "bold")
                self._text(WIDTH - 18, y, state + estimate, color, status_font, "e")
                y += 21 if bio or geo else 19
                for detail in row.get("bio_details") or []:
                    kind = detail.get("kind")
                    symbol = {"complete": "✓", "sample": "●", "detected": "○"}.get(kind, "·")
                    detail_color = (
                        palette["green"] if kind == "complete"
                        else palette["orange"] if kind == "sample"
                        else palette["text"]
                    )
                    self._text(30, y, symbol, detail_color, BIO_SYMBOL_FONT)
                    self._text(
                        46, y, _truncate(detail.get("display_name") or detail.get("name"), 38),
                        detail_color, BIO_DETAIL_FONT,
                    )
                    self._text(
                        WIDTH - 18, y, detail.get("status") or "DETECTED",
                        detail_color, BIO_DETAIL_FONT, "e",
                    )
                    y += BIO_DETAIL_H
                if notable:
                    self._text(28, y, "NOTABLE BODY", palette["dim"], ("Courier", 7, "bold"))
                    self._text(WIDTH - 18, y, notable["value_line"], notable["value_color"], ("Courier", 7, "bold"), "e")
                    y += 15

        if belt_rows:
            self._text(
                18, y + 8, f"ASTEROID BELT CLUSTERS ({len(belt_rows)})",
                palette["accent"], ("Courier", 7, "bold"),
            )
            self._text(WIDTH - 18, y + 8, "FSS CONTACTS", palette["dim"], ("Courier", 7, "bold"), "e")
            y += 24
            for row in belt_rows:
                color = palette["orange"] if row.get("new_discovery") else palette["text"]
                self._text(20, y, "◆", color, BIO_SYMBOL_FONT)
                self._text(38, y, _truncate(row.get("display_name"), 54), color, BIO_DETAIL_FONT)
                distance = row.get("distance") or ("NEW" if row.get("new_discovery") else "FOUND")
                self._text(WIDTH - 18, y, distance, palette["muted"], BIO_DETAIL_FONT, "e")
                y += 18

        if notable_rows:
            self._text(18, y + 8, f"VALUABLE / NOTABLE ({len(notable_rows)})", palette["dim"], ("Courier", 7, "bold"))
            y += 24
            for row in notable_rows:
                y = self._notable_row(row, y)

        if completed_rows:
            self._text(
                18, y + 8, f"SURVEYED BIOLOGY ({len(completed_rows)})",
                palette["green"], ("Courier", 7, "bold"),
            )
            y += 24
            for row in completed_rows:
                state, _color = _surface_signal_state(
                    row["bio_count"], row["complete"], row["geo_count"],
                    needs_dss=row["needs_dss"], palette=palette,
                )
                lo, hi = row["min_value"], row["max_value"]
                value_text = self._range_text(lo, hi)
                estimate = f" · {value_text}" if value_text else ""
                notable = row.get("notable")
                label = row.get("display_name") or row["name"]
                name = f"{notable['icons']} {label}" if notable and notable.get("icons") else label
                self._text(20, y, f"✓ {_truncate(name, 34)}", palette["green"], ("Courier", 8, "bold"))
                self._text(
                    WIDTH - 18, y, state + estimate,
                    palette["green"], BIO_DETAIL_FONT, "e",
                )
                y += 19
                species_lines = _joined_lines(
                    [
                        detail.get("display_name") or detail.get("name") or "Organic"
                        for detail in (row.get("bio_details") or [])
                    ]
                )
                for species in species_lines:
                    self._text(
                        30, y, species,
                        palette["text"], ("Courier", 7, "bold"),
                    )
                    y += 15

        if is_body:
            lo, hi = model["min_value"], model["max_value"]
            if _safe_int(model.get("body", {}).get("bio_count")) or rows:
                total = _credits(lo) if lo == hi else f"{_credits(lo)}–{_credits(hi)}"
                footer_label = "ESTIMATED BIO BASE"
                footer_value = total
            else:
                footer_label = "GEOLOGICAL EVIDENCE"
                footer_value = f"{_safe_int(model.get('body', {}).get('geo_count'))} SIGNALS"
            self._text(18, h - 15, footer_label, palette["dim"], ("Courier", 7, "bold"))
            self._text(WIDTH - 18, h - 15, footer_value, palette["orange"], ("Courier", 8, "bold"), "e")
        else:
            footer = f"OPEN {len(active_rows)} · BIO COMPLETE {len(completed_rows)}"
            self._text(18, h - 15, footer, palette["dim"], ("Courier", 7, "bold"))
            right_footer = f"BELTS {len(belt_rows)} · NOTABLE {model.get('notable_count', 0)}"
            self._text(WIDTH - 18, h - 15, right_footer, palette["orange"], ("Courier", 7, "bold"), "e")
