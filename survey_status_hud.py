"""Native system/body survey strip inspired by SrvSurvey's bio plotter."""

import tkinter as tk

import bio_values
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome
from notable_bodies import build_notable_body_rows

_CHROMA = "#ff00ff"
_DIM = "#7a8a98"
_GREEN = "#21d189"
WIDTH = 560
FONT_TITLE = ("Courier", 11, "bold")
FONT_MAIN = ("Courier", 10, "bold")
FONT_DETAIL = ("Courier", 9, "bold")
FONT_SYMBOL = ("Courier", 11, "bold")
ROW_H = 22
DETAIL_ROW_H = 18
NOTABLE_ROW_H = 40


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


def _surface_signal_state(bio_count=0, complete=0, geo_count=0, needs_dss=False):
    """Return the compact, truthful surface-signal label and colour."""
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
            color = _GREEN if bio_finished else COLOR_ORANGE
        else:
            color = COLOR_ACCENT
        return " · ".join(parts), color
    return ("DSS REQUIRED", _DIM) if needs_dss else ("NO SURFACE SIGNALS", _DIM)


def _body_value_range(item):
    scans = list((item.get("organic_scans") or {}).values())
    known = sum(_safe_int(bio_values.species_value(scan.get("species"))
                          or scan.get("species_value")) for scan in scans)
    bio_count = _safe_int(item.get("bio_count"))
    unknown = max(0, bio_count - len(scans))
    genera = [_genus_name(row) for row in (item.get("genuses") or item.get("predicted_genuses") or [])]
    ranges = [bio_values.genus_info(name) for name in genera if name]
    lows = [_safe_int(row.get("min_value")) for row in ranges if row.get("min_value")]
    highs = [_safe_int(row.get("max_value")) for row in ranges if row.get("max_value")]
    if not unknown:
        return known, known
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
            rows.append({
                "status": "DETECTED" if kind == "detected" else "PREDICTED",
                "name": name,
                "variant": "",
                "display_name": name,
                "min_value": info.get("min_value"),
                "max_value": info.get("max_value"),
                "kind": kind,
            })
    return rows


def build_survey_model(system_name, scan_items, focused_body_id=None,
                       focused_body_name=None, sampling=None, scanned=0, total=0,
                       min_notable_value=50_000):
    """Build a renderer-neutral survey model for the overlay and tests."""
    bodies = [row for row in (scan_items or []) if not row.get("is_star")]
    notable_rows = build_notable_body_rows(scan_items, min_notable_value)
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
            "needs_dss": needs_dss,
            "min_value": lo,
            "max_value": hi,
            "first_footfall": bool(body.get("first_footfall")),
            # System mode used to stop at BIO 0/N. Include only journal-
            # identified genera/species here; predictions remain exclusive to
            # the focused-body view so they cannot be mistaken for DSS facts.
            "bio_details": [
                detail for detail in _body_detail_rows(body)
                if detail.get("kind") != "predicted"
            ],
        })
    rows.sort(key=lambda row: (
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
        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", True, "-transparentcolor", _CHROMA, "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg=_CHROMA)
        self.canvas = tk.Canvas(self.win, width=WIDTH, height=90, bg=_CHROMA, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        x = _safe_int(config.get("survey_status_hud_x"), 30)
        y = _safe_int(config.get("survey_status_hud_y"), 520)
        self.win.geometry(f"+{x}+{y}")
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

    def update(self, system_name, scanned, total, scan_items, body_signals,
               sampling=None, focused_body_id=None, focused_body_name=None):
        model = build_survey_model(system_name, scan_items, focused_body_id,
                                   focused_body_name, sampling, scanned, total,
                                   _safe_int(self.config.get("system_info_min_value"), 50_000))
        if not model:
            self.hide()
            return
        self._redraw(model)
        self.show()

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        self.win.geometry(f"+{self.win.winfo_x() + event.x - self._dx}+{self.win.winfo_y() + event.y - self._dy}")

    def _drag_end(self, event):
        self.config["survey_status_hud_x"] = self.win.winfo_x()
        self.config["survey_status_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    def _text(self, x, y, text, fill, font, anchor="w"):
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
        self._text(18, y, f"SAMPLE {progress}/3 · {_truncate(sampling.get('species'), 31)}", COLOR_ORANGE, FONT_MAIN)
        self._text(WIDTH - 18, y, status, _GREEN if clear else COLOR_TEXT, FONT_MAIN, "e")
        return y + ROW_H

    def _notable_row(self, row, y):
        label = row.get("display_name") or row["name"]
        name = f"{row['icons']} {label}" if row.get("icons") else label
        self._text(20, y, _truncate(name, 42), row["name_color"], FONT_MAIN)
        self._text(28, y + DETAIL_ROW_H, "SURVEY VALUE", _DIM, FONT_DETAIL)
        self._text(WIDTH - 18, y + DETAIL_ROW_H, row["value_line"], row["value_color"], FONT_DETAIL, "e")
        return y + NOTABLE_ROW_H

    def _redraw(self, model):
        is_body = model["mode"] == "body"
        rows = model["rows"]
        notable_rows = model.get("notable_rows") or []
        sample_h = ROW_H if model.get("sampling") else 0
        if is_body:
            content_h = 24 + max(1, len(rows)) * ROW_H
        else:
            content_h = (
                24 + sum(
                    ROW_H + len(row.get("bio_details") or []) * DETAIL_ROW_H
                    + (DETAIL_ROW_H if row.get("notable") else 0)
                    for row in rows
                )
            ) if rows else 0
        notable_h = (28 + len(notable_rows) * NOTABLE_ROW_H) if notable_rows else 0
        h = 52 + sample_h + content_h + notable_h + 32
        self.canvas.config(width=WIDTH, height=h)
        self.win.geometry(f"{WIDTH}x{h}")
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(self.canvas, WIDTH, h, bracket_len=10)
        title = "BIO SURVEY" if is_body else "SURVEY STATUS"
        self._text(18, 20, title, COLOR_ACCENT, FONT_TITLE)
        self._text(WIDTH - 18, 20, _truncate(model["system"].upper(), 34), COLOR_TEXT, FONT_TITLE, "e")
        self.canvas.create_line(18, 33, WIDTH - 18, 33, fill="#1a2530", width=1)
        y = self._sample_row(model.get("sampling"), 49)

        if is_body:
            body = model["body"]
            count = _safe_int(body.get("bio_count"))
            geo = _safe_int(body.get("geo_count"))
            done = _safe_int(body.get("organic_complete_count"))
            signal_state, signal_color = _surface_signal_state(
                count, done, geo, needs_dss=not bool(body.get("dss_complete")),
            )
            self._text(18, y, _truncate(model.get("body_display") or body.get("name"), 43), COLOR_ORANGE, FONT_MAIN)
            self._text(WIDTH - 18, y, signal_state, signal_color, FONT_MAIN, "e")
            y += 24
            for row in rows:
                symbol = {"complete": "✓", "sample": "●", "detected": "○", "predicted": "?"}.get(row["kind"], "·")
                color = _GREEN if row["kind"] == "complete" else (COLOR_ORANGE if row["kind"] == "sample" else COLOR_TEXT if row["kind"] == "detected" else _DIM)
                label = row.get("display_name") or row["name"]
                value = row.get("value")
                if value:
                    value_text = _credits(value)
                else:
                    lo, hi = row.get("min_value"), row.get("max_value")
                    value_text = _credits(lo) if lo == hi else f"{_credits(lo)}–{_credits(hi)}"
                self._text(20, y, symbol, color, FONT_SYMBOL)
                self._text(40, y, _truncate(label, 39), color, FONT_MAIN)
                self._text(WIDTH - 18, y, value_text, color, FONT_MAIN, "e")
                y += ROW_H
        else:
            if rows:
                self._text(18, y, "SURVEY TARGETS", _DIM, FONT_DETAIL)
                self._text(WIDTH - 18, y, "STATUS / EST. VALUE", _DIM, FONT_DETAIL, "e")
                y += 24
            for row in rows:
                bio = row["bio_count"]
                geo = row["geo_count"]
                state, color = _surface_signal_state(
                    bio, row["complete"], geo, needs_dss=row["needs_dss"],
                )
                lo, hi = row["min_value"], row["max_value"]
                estimate = "" if not hi else (f" · {_credits(lo)}" if lo == hi else f" · {_credits(lo)}–{_credits(hi)}")
                notable = row.get("notable")
                label = row.get("display_name") or row["name"]
                name = f"{notable['icons']} {label}" if notable and notable.get("icons") else label
                self._text(20, y, _truncate(name, 39), color, FONT_MAIN)
                self._text(WIDTH - 18, y, state + estimate, color, FONT_MAIN, "e")
                y += ROW_H
                for detail in row.get("bio_details") or []:
                    kind = detail.get("kind")
                    symbol = {"complete": "✓", "sample": "●", "detected": "○"}.get(kind, "·")
                    detail_color = (
                        _GREEN if kind == "complete"
                        else COLOR_ORANGE if kind == "sample"
                        else COLOR_TEXT
                    )
                    self._text(30, y, symbol, detail_color, FONT_MAIN)
                    self._text(
                        48, y, _truncate(detail.get("display_name") or detail.get("name"), 42),
                        detail_color, FONT_DETAIL,
                    )
                    self._text(
                        WIDTH - 18, y, detail.get("status") or "DETECTED",
                        detail_color, FONT_DETAIL, "e",
                    )
                    y += DETAIL_ROW_H
                if notable:
                    self._text(28, y, "NOTABLE BODY", _DIM, FONT_DETAIL)
                    self._text(WIDTH - 18, y, notable["value_line"], notable["value_color"], FONT_DETAIL, "e")
                    y += DETAIL_ROW_H

        if notable_rows:
            self.canvas.create_line(18, y - 2, WIDTH - 18, y - 2, fill="#26313a", width=1)
            self._text(18, y + 10, f"NOTABLE BODIES ({len(notable_rows)})", _DIM, FONT_DETAIL)
            y += 28
            for row in notable_rows:
                y = self._notable_row(row, y)

        if is_body:
            lo, hi = model["min_value"], model["max_value"]
            total = _credits(lo) if lo == hi else f"{_credits(lo)}–{_credits(hi)}"
            self._text(18, h - 18, "ESTIMATED BASE", _DIM, FONT_DETAIL)
            self._text(WIDTH - 18, h - 18, total, COLOR_ORANGE, FONT_MAIN, "e")
        else:
            progress = f"SCAN {model.get('scanned', 0)}/{model.get('total', 0)}"
            self._text(18, h - 18, progress, _DIM, FONT_DETAIL)
            self._text(WIDTH - 18, h - 18, f"NOTABLE {model.get('notable_count', 0)}", COLOR_ORANGE, FONT_DETAIL, "e")
