"""Native system/body survey strip inspired by SrvSurvey's bio plotter."""

import tkinter as tk

import bio_values
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome

_CHROMA = "#ff00ff"
_DIM = "#7a8a98"
_GREEN = "#21d189"
WIDTH = 480


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _truncate(text, max_chars):
    text = str(text or "")
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


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
                "min_value": info.get("min_value"),
                "max_value": info.get("max_value"),
                "kind": kind,
            })
    return rows


def build_survey_model(system_name, scan_items, focused_body_id=None,
                       focused_body_name=None, sampling=None):
    """Build a renderer-neutral survey model for the overlay and tests."""
    bodies = [row for row in (scan_items or []) if not row.get("is_star")]
    focused = next((row for row in bodies if _body_matches(
        row, focused_body_id, focused_body_name)), None)
    if focused and (_safe_int(focused.get("bio_count")) > 0 or sampling):
        incomplete = _safe_int(focused.get("organic_complete_count")) < _safe_int(focused.get("bio_count"))
        if incomplete or sampling:
            lo, hi = _body_value_range(focused)
            return {
                "mode": "body", "system": system_name or "", "body": focused,
                "rows": _body_detail_rows(focused), "sampling": sampling,
                "min_value": lo, "max_value": hi,
            }

    rows = []
    for body in bodies:
        bio_count = _safe_int(body.get("bio_count"))
        complete = _safe_int(body.get("organic_complete_count"))
        needs_dss = not bool(body.get("dss_complete"))
        if not needs_dss and (not bio_count or complete >= bio_count):
            continue
        lo, hi = _body_value_range(body)
        rows.append({
            "name": body.get("name") or "Unknown body",
            "bio_count": bio_count,
            "complete": complete,
            "needs_dss": needs_dss,
            "min_value": lo,
            "max_value": hi,
            "first_footfall": bool(body.get("first_footfall")),
        })
    rows.sort(key=lambda row: (not bool(row["bio_count"]), row["name"]))
    if not rows and not sampling:
        return None
    return {"mode": "system", "system": system_name or "", "rows": rows, "sampling": sampling}


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
                                   focused_body_name, sampling)
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
        self._text(18, y, f"SAMPLE {progress}/3 · {_truncate(sampling.get('species'), 27)}", COLOR_ORANGE, ("Courier", 8, "bold"))
        self._text(WIDTH - 18, y, status, _GREEN if clear else COLOR_TEXT, ("Courier", 8, "bold"), "e")
        return y + 19

    def _redraw(self, model):
        is_body = model["mode"] == "body"
        rows = model["rows"]
        sample_h = 19 if model.get("sampling") else 0
        h = 48 + sample_h + max(1, len(rows)) * 19 + 25
        self.canvas.config(width=WIDTH, height=h)
        self.win.geometry(f"{WIDTH}x{h}")
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(self.canvas, WIDTH, h, bracket_len=10)
        title = "BIO SURVEY" if is_body else "SURVEY STATUS"
        self._text(18, 18, title, COLOR_ACCENT, ("Courier", 9, "bold"))
        self._text(WIDTH - 18, 18, _truncate(model["system"].upper(), 30), COLOR_TEXT, ("Courier", 9, "bold"), "e")
        self.canvas.create_line(18, 28, WIDTH - 18, 28, fill="#1a2530", width=1)
        y = self._sample_row(model.get("sampling"), 42)

        if is_body:
            body = model["body"]
            count = _safe_int(body.get("bio_count"))
            done = _safe_int(body.get("organic_complete_count"))
            self._text(18, y, _truncate(body.get("name"), 34), COLOR_ORANGE, ("Courier", 8, "bold"))
            self._text(WIDTH - 18, y, f"BIO {done}/{count}", COLOR_TEXT, ("Courier", 8, "bold"), "e")
            y += 20
            for row in rows:
                symbol = {"complete": "✓", "sample": "●", "detected": "○", "predicted": "?"}.get(row["kind"], "·")
                color = _GREEN if row["kind"] == "complete" else (COLOR_ORANGE if row["kind"] == "sample" else COLOR_TEXT if row["kind"] == "detected" else _DIM)
                label = row["name"] + (f" · {row['variant']}" if row.get("variant") else "")
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
            self._text(18, y, "BODY", _DIM, ("Courier", 7, "bold"))
            self._text(WIDTH - 18, y, "STATUS / EST. VALUE", _DIM, ("Courier", 7, "bold"), "e")
            y += 20
            for row in rows:
                bio = row["bio_count"]
                if bio:
                    state = f"BIO {row['complete']}/{bio}"
                    color = COLOR_ORANGE
                else:
                    state, color = "DSS REQUIRED", _DIM
                lo, hi = row["min_value"], row["max_value"]
                estimate = "" if not hi else (f" · {_credits(lo)}" if lo == hi else f" · {_credits(lo)}–{_credits(hi)}")
                self._text(20, y, _truncate(row["name"], 29), color, ("Courier", 8, "bold"))
                self._text(WIDTH - 18, y, state + estimate, color, ("Courier", 8, "bold"), "e")
                y += 19

        if is_body:
            lo, hi = model["min_value"], model["max_value"]
            total = _credits(lo) if lo == hi else f"{_credits(lo)}–{_credits(hi)}"
            self._text(18, h - 15, "ESTIMATED BASE", _DIM, ("Courier", 7, "bold"))
            self._text(WIDTH - 18, h - 15, total, COLOR_ORANGE, ("Courier", 8, "bold"), "e")
