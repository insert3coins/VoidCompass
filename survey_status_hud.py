"""Native system/body survey strip inspired by SrvSurvey's bio plotter."""

import tkinter as tk

import bio_values
import themes
from config import save_config
import overlay_chrome
from notable_bodies import build_notable_body_rows

_CHROMA = "#ff00ff"
WIDTH = 480
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


def _body_matches(item, body_id, body_name):
    if body_id is not None and str(item.get("body_id")) == str(body_id):
        return True
    return bool(body_name and str(item.get("name") or "").casefold() == str(body_name).casefold())


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
        if not name.startswith(genus):
            continue
        epithet = name[len(genus):].strip()
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


def build_survey_model(system_name, scan_items, focused_body_id=None,
                       focused_body_name=None, sampling=None, scanned=0, total=0,
                       min_notable_value=50_000, palette=None):
    """Build a renderer-neutral survey model for the overlay and tests."""
    bodies = [row for row in (scan_items or []) if not row.get("is_star")]
    notable_rows = build_notable_body_rows(scan_items, min_notable_value, palette)
    for row in notable_rows:
        row["display_name"] = _body_display_name(
            row.get("name"), system_name, row.get("planet_class"), row.get("terraformable")
        )
    focused = next((row for row in bodies if _body_matches(
        row, focused_body_id, focused_body_name)), None)
    if focused and (_safe_int(focused.get("bio_count")) > 0 or sampling):
        incomplete = _safe_int(focused.get("organic_complete_count")) < _safe_int(focused.get("bio_count"))
        if incomplete or sampling:
            lo, hi = _body_value_range(focused)
            return {
                "mode": "body", "system": system_name or "", "body": focused,
                "body_display": _body_display_name(
                    focused.get("name"), system_name, focused.get("planet_class"),
                    focused.get("terraformable"),
                ),
                "rows": _body_detail_rows(focused), "sampling": sampling,
                "min_value": lo, "max_value": hi,
                "notable_rows": notable_rows,
                "scanned": _safe_int(scanned), "total": _safe_int(total),
            }

    rows = []
    for body in bodies:
        bio_count = _safe_int(body.get("bio_count"))
        geo_count = _safe_int(body.get("geo_count"))
        complete = _safe_int(body.get("organic_complete_count"))
        needs_dss = not bool(body.get("dss_complete"))
        # Keep mapped biological bodies visible through completion. Survey
        # Status is the persistent system record until StartJump, so removing
        # the row after the final analysis would also remove the identification
        # the commander just earned.
        if not needs_dss and not bio_count and not geo_count:
            continue
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
    notable_by_id = {
        str(row.get("body_id")): row for row in notable_rows if row.get("body_id") is not None
    }
    notable_by_name = {str(row.get("name") or "").casefold(): row for row in notable_rows}
    represented = set()
    for row in rows:
        body = next((item for item in bodies if str(item.get("name") or "").casefold()
                     == str(row["name"]).casefold()), {})
        notable = notable_by_id.get(str(body.get("body_id"))) if body.get("body_id") is not None else None
        notable = notable or notable_by_name.get(str(row["name"]).casefold())
        if notable:
            row["notable"] = notable
            represented.add((str(notable.get("body_id")), str(notable.get("name") or "").casefold()))
    remaining_notable = [
        row for row in notable_rows
        if (str(row.get("body_id")), str(row.get("name") or "").casefold()) not in represented
    ]
    if not rows and not remaining_notable and not sampling:
        return None
    return {
        "mode": "system", "system": system_name or "", "rows": rows,
        "notable_rows": remaining_notable, "sampling": sampling,
        "scanned": _safe_int(scanned), "total": _safe_int(total),
        "notable_count": len(notable_rows),
    }


class SurveyStatusHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_update = None
        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)
        self.canvas = tk.Canvas(self.win, width=WIDTH, height=90, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        x = _safe_int(config.get("survey_status_hud_x"), 30)
        y = _safe_int(config.get("survey_status_hud_y"), 520)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._force_topmost()
        self.win.withdraw()
        self._visible = False

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, _safe_int(self.config.get("overlay_topmost_refresh_ms"), 12000))
        self.win.after(refresh_ms, self._force_topmost)

    def show(self):
        if self._visible:
            return
        try:
            x = _safe_int(self.config.get("survey_status_hud_x"), 30)
            y = _safe_int(self.config.get("survey_status_hud_y"), 520)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
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

    def update(self, system_name, scanned, total, scan_items, body_signals,
               sampling=None, focused_body_id=None, focused_body_name=None):
        self._last_update = (
            system_name, scanned, total, scan_items, body_signals,
            sampling, focused_body_id, focused_body_name,
        )
        model = build_survey_model(system_name, scan_items, focused_body_id,
                                   focused_body_name, sampling, scanned, total,
                                   _safe_int(self.config.get("system_info_min_value"), 50_000),
                                   self._palette)
        if not model:
            self.hide()
            return
        self._redraw(model)
        self.show()

    def apply_theme(self, palette=None):
        """Adopt the active profile palette and repaint the cached survey."""
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        if self._last_update is not None:
            self.update(*self._last_update)

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + event.x - self._dx
        y = self.win.winfo_y() + event.y - self._dy
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    def _drag_end(self, event):
        self.config["survey_status_hud_x"] = self.win.winfo_x()
        self.config["survey_status_hud_y"] = self.win.winfo_y()
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
        progress = _safe_int(sampling.get("progress"), 1)
        colony = sampling.get("colony_m")
        minimum = sampling.get("min_distance_m")
        clear = sampling.get("clear")
        status = "CLEAR" if clear else (f"{_safe_int(minimum):,}/{_safe_int(colony):,} M" if minimum is not None and colony else "MOVE TO NEXT SAMPLE")
        palette = self._palette
        self._text(18, y, f"SAMPLE {progress}/3 · {_truncate(sampling.get('species'), 27)}", palette["orange"], ("Courier", 8, "bold"))
        self._text(WIDTH - 18, y, status, palette["green"] if clear else palette["text"], ("Courier", 8, "bold"), "e")
        return y + 19

    def _notable_row(self, row, y):
        label = row.get("display_name") or row["name"]
        name = f"{row['icons']} {label}" if row.get("icons") else label
        self._text(20, y, _truncate(name, 36), row["name_color"], ("Courier", 8, "bold"))
        self._text(28, y + 15, "SURVEY VALUE", self._palette["dim"], ("Courier", 7, "bold"))
        self._text(WIDTH - 18, y + 15, row["value_line"], row["value_color"], ("Courier", 7, "bold"), "e")
        return y + 34

    def _redraw(self, model):
        palette = self._palette
        is_body = model["mode"] == "body"
        rows = model["rows"]
        active_rows = rows if is_body else [row for row in rows if not row.get("bio_complete")]
        completed_rows = [] if is_body else [row for row in rows if row.get("bio_complete")]
        notable_rows = model.get("notable_rows") or []
        sample_h = 19 if model.get("sampling") else 0
        if is_body:
            content_h = 20 + max(1, len(rows)) * 19
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
                19 + (15 if row.get("bio_details") else 0)
                for row in completed_rows
            )
        ) if completed_rows else 0
        notable_h = (20 + len(notable_rows) * 34) if notable_rows else 0
        h = 48 + sample_h + content_h + notable_h + completed_h + 27
        self.canvas.config(width=WIDTH, height=h)
        self.win.geometry(f"{WIDTH}x{h}")
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, h, accent=palette["accent"], bracket_len=10,
        )
        title = "BIO SURVEY" if is_body else "SURVEY STATUS"
        self._text(18, 18, title, palette["accent"], ("Courier", 9, "bold"))
        self._text(WIDTH - 18, 18, _truncate(model["system"].upper(), 30), palette["text"], ("Courier", 9, "bold"), "e")
        self.canvas.create_line(18, 28, WIDTH - 18, 28, fill=palette["border_soft"], width=1)
        y = self._sample_row(model.get("sampling"), 42)

        if is_body:
            body = model["body"]
            count = _safe_int(body.get("bio_count"))
            geo = _safe_int(body.get("geo_count"))
            done = _safe_int(body.get("organic_complete_count"))
            signal_state, signal_color = _surface_signal_state(
                count, done, geo, needs_dss=not bool(body.get("dss_complete")),
                palette=palette,
            )
            self._text(18, y, _truncate(model.get("body_display") or body.get("name"), 38), palette["orange"], ("Courier", 8, "bold"))
            self._text(WIDTH - 18, y, signal_state, signal_color, SIGNAL_FONT, "e")
            y += 20
            for row in rows:
                # '?' is a prediction whose every published requirement was
                # tested; '·' rests on something this scan could not check.
                symbol = {
                    "complete": "✓", "sample": "●", "detected": "○",
                    "predicted": "?", "possible": "·",
                }.get(row["kind"], "·")
                color = palette["green"] if row["kind"] == "complete" else (palette["orange"] if row["kind"] == "sample" else palette["text"] if row["kind"] == "detected" else palette["dim"])
                label = row.get("display_name") or row["name"]
                value = row.get("value")
                if value:
                    value_text = _credits(value)
                else:
                    lo, hi = row.get("min_value"), row.get("max_value")
                    value_text = _credits(lo) if lo == hi else f"{_credits(lo)}–{_credits(hi)}"
                self._text(20, y, symbol, color, ("Courier", 9, "bold"))
                self._text(38, y, _truncate(label, 34), color, ("Courier", 8, "bold"))
                self._text(WIDTH - 18, y, value_text, color, ("Courier", 8, "bold"), "e")
                y += 19
        else:
            if active_rows:
                self._text(18, y, "SURVEY TARGETS", palette["dim"], ("Courier", 7, "bold"))
                self._text(WIDTH - 18, y, "STATUS / EST. VALUE", palette["dim"], ("Courier", 7, "bold"), "e")
                y += 20
            for row in active_rows:
                bio = row["bio_count"]
                geo = row["geo_count"]
                state, color = _surface_signal_state(
                    bio, row["complete"], geo, needs_dss=row["needs_dss"],
                    palette=palette,
                )
                lo, hi = row["min_value"], row["max_value"]
                estimate = "" if not hi else (f" · {_credits(lo)}" if lo == hi else f" · {_credits(lo)}–{_credits(hi)}")
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

        if notable_rows:
            self.canvas.create_line(18, y - 2, WIDTH - 18, y - 2, fill=palette["border"], width=1)
            self._text(18, y + 8, f"NOTABLE BODIES ({len(notable_rows)})", palette["dim"], ("Courier", 7, "bold"))
            y += 24
            for row in notable_rows:
                y = self._notable_row(row, y)

        if completed_rows:
            self.canvas.create_line(18, y - 2, WIDTH - 18, y - 2, fill=palette["border"], width=1)
            self._text(
                18, y + 8, f"COMPLETED BIO ({len(completed_rows)})",
                palette["green"], ("Courier", 7, "bold"),
            )
            y += 24
            for row in completed_rows:
                state, _color = _surface_signal_state(
                    row["bio_count"], row["complete"], row["geo_count"],
                    needs_dss=row["needs_dss"], palette=palette,
                )
                lo, hi = row["min_value"], row["max_value"]
                estimate = "" if not hi else (
                    f" · {_credits(lo)}" if lo == hi
                    else f" · {_credits(lo)}–{_credits(hi)}"
                )
                notable = row.get("notable")
                label = row.get("display_name") or row["name"]
                name = f"{notable['icons']} {label}" if notable and notable.get("icons") else label
                self._text(20, y, f"✓ {_truncate(name, 34)}", palette["green"], ("Courier", 8, "bold"))
                self._text(
                    WIDTH - 18, y, state + estimate,
                    palette["green"], BIO_DETAIL_FONT, "e",
                )
                y += 19
                details = row.get("bio_details") or []
                if details:
                    species = " · ".join(
                        detail.get("display_name") or detail.get("name") or "Organic"
                        for detail in details
                    )
                    self._text(
                        30, y, _truncate(species, 62),
                        palette["text"], ("Courier", 7, "bold"),
                    )
                    y += 15

        if is_body:
            lo, hi = model["min_value"], model["max_value"]
            total = _credits(lo) if lo == hi else f"{_credits(lo)}–{_credits(hi)}"
            self._text(18, h - 15, "ESTIMATED BASE", palette["dim"], ("Courier", 7, "bold"))
            self._text(WIDTH - 18, h - 15, total, palette["orange"], ("Courier", 8, "bold"), "e")
        else:
            progress = f"SCAN {model.get('scanned', 0)}/{model.get('total', 0)}"
            self._text(18, h - 15, progress, palette["dim"], ("Courier", 7, "bold"))
            self._text(WIDTH - 18, h - 15, f"NOTABLE {model.get('notable_count', 0)}", palette["orange"], ("Courier", 7, "bold"), "e")
