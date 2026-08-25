"""Theme-aware prospector analysis overlay for mining journal events."""

import tkinter as tk

from config import save_config
import overlay_chrome
import themes


_CHROMA = "#ff00ff"
_CONTENT = {
    "high": ("HIGH", "green"),
    "medium": ("MED", "yellow"),
    "med": ("MED", "yellow"),
    "low": ("LOW", "dim"),
}


def _content_info(raw):
    """Return (display label, theme tone) for the asteroid content field."""
    value = (raw.get("Content_Localised") or raw.get("Content") or "").lower()
    value = value.replace("$asteroidmaterialcontent_", "").replace(";", "").strip()
    if "high" in value:
        return _CONTENT["high"]
    if "med" in value:
        return _CONTENT["medium"]
    if "low" in value:
        return _CONTENT["low"]
    return (value.upper() or "UNKNOWN", "text")


def _mining_type(raw):
    value = (raw.get("MiningType_Localised") or raw.get("MiningType") or "").lower()
    value = value.replace("$asteroidtype_", "").replace(";", "").strip()
    return value.title() or "Asteroid"


def _clean_token(value):
    value = str(value or "").strip()
    if value.startswith("$"):
        value = value[1:]
    if value.endswith(";"):
        value = value[:-1]
    return value.title()


def _mat_name(item):
    return _clean_token(item.get("Name_Localised") or item.get("Name"))


def _core_name(raw):
    value = raw.get("MotherlodeMaterial_Localised") or raw.get("MotherlodeMaterial")
    return _clean_token(value) or None


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_prospector_model(raw, refined=None):
    """Normalise one ProspectedAsteroid event for any future renderer."""
    raw = raw if isinstance(raw, dict) else {}
    materials = []
    for item in raw.get("Materials") or []:
        if not isinstance(item, dict):
            continue
        name = _mat_name(item)
        if not name:
            continue
        proportion = max(0.0, _as_float(item.get("Proportion")))
        # Frontier already reports Proportion as a percentage (for example
        # 12.96 means 12.96%), including legitimate values below one percent.
        materials.append({"name": name, "proportion": round(proportion, 1)})
    materials.sort(key=lambda item: item["proportion"], reverse=True)

    refined_rows = []
    for name, count in (refined or {}).items():
        tonnes = max(0, int(_as_float(count)))
        if name and tonnes:
            refined_rows.append({"name": str(name), "tonnes": tonnes})
    refined_rows.sort(key=lambda item: (-item["tonnes"], item["name"].lower()))

    remaining = raw.get("Remaining")
    remaining_value = None if remaining is None else max(0.0, _as_float(remaining))
    content_label, content_tone = _content_info(raw)
    return {
        "mining_type": _mining_type(raw),
        "content_label": content_label,
        "content_tone": content_tone,
        "remaining": remaining_value,
        "core_material": _core_name(raw),
        "materials": materials,
        "refined": refined_rows,
        "refined_total": sum(item["tonnes"] for item in refined_rows),
    }


class ProspectorHUD:
    WIDTH = 380
    MAX_MATERIALS = 10
    _MAT_H = 21
    _MIN_H = 146

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_raw = None
        self._refined = {}
        self._hide_job = None
        self._html_render_model = build_prospector_model({}, {})

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)
        self.canvas = tk.Canvas(
            self.win, width=self.WIDTH, height=self._MIN_H,
            bg=overlay_bg, highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        screen_h = root.winfo_screenheight()
        x = int(config.get("prospector_hud_x", 30))
        y = int(config.get("prospector_hud_y", max(30, screen_h - 320)))
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._force_topmost()
        self.win.withdraw()

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self._force_topmost)

    def show(self):
        try:
            x = int(self.config.get("prospector_hud_x", 30))
            y = int(self.config.get("prospector_hud_y", 600))
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
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
        timeout_s = max(5, int(self.config.get("prospector_hud_timeout_s") or 45))
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def update(self, raw):
        self._last_raw = raw
        self._refined = {}
        self._redraw()
        self.show()
        self._schedule_hide()

    def add_refined(self, material):
        if not material or not self._last_raw:
            return
        material = _clean_token(material)
        self._refined[material] = self._refined.get(material, 0) + 1
        self._redraw()

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._desired_pos = (x, y)
        self.config["prospector_hud_x"] = x
        self.config["prospector_hud_y"] = y

    def _drag_end(self, _event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
        self._desired_pos = (x, y)
        self.config["prospector_hud_x"] = x
        self.config["prospector_hud_y"] = y
        try:
            save_config(self.config)
        except Exception:
            pass

    def _text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _redraw(self):
        if not self._last_raw:
            return

        model = build_prospector_model(self._last_raw, self._refined)
        self._html_render_model = model
        palette = self._palette
        shown = model["materials"][:self.MAX_MATERIALS]
        core_mat = model["core_material"]
        core_extra = 27 if core_mat else 0
        material_extra = max(24, len(shown) * self._MAT_H)
        height = max(self._MIN_H, 104 + core_extra + material_extra + 38)

        self.canvas.config(width=self.WIDTH, height=height)
        x, y = self._desired_pos
        self.win.geometry(overlay_chrome.position_geometry(x, y, self.WIDTH, height))
        self.canvas.delete("all")
        accent = palette["orange"] if core_mat else palette["accent"]
        overlay_chrome.draw_chrome(
            self.canvas, self.WIDTH, height, accent=accent, bracket_len=10,
            scanlines=False,
        )

        self._text(16, 17, "PROSPECTOR ANALYSIS", accent, ("Courier", 10, "bold"))
        badge = "CORE DETECTED" if core_mat else f'{model["content_label"]} CONTENT'
        badge_color = palette["orange"] if core_mat else palette.get(model["content_tone"], palette["text"])
        self._text(self.WIDTH - 16, 17, badge, badge_color, ("Courier", 8, "bold"), "e")
        remaining = model["remaining"]
        remaining_text = f"{remaining:.1f}% REMAINING" if remaining is not None else "REMAINING UNKNOWN"
        self._text(16, 48, model["mining_type"].upper(), palette["text"], ("Courier", 11, "bold"))
        self._text(self.WIDTH - 16, 48, remaining_text, palette["muted"], ("Courier", 8), "e")
        y = 73

        if core_mat:
            self._text(16, y + 7, f"◆ MOTHERLODE  {core_mat.upper()}", palette["orange"],
                       ("Courier", 9, "bold"))
            y += 27
        self._text(16, y + 5, "MATERIAL COMPOSITION", palette["dim"], ("Courier", 8, "bold"))
        y += 20
        bar_x = 154
        bar_end = self.WIDTH - 58
        bar_width = bar_end - bar_x
        max_prop = max((item["proportion"] for item in shown), default=1.0) or 1.0

        if not shown:
            self._text(16, y + 5, "NO EXTRACTABLE MATERIALS REPORTED", palette["dim"], ("Courier", 8))
            y += self._MAT_H
        else:
            for material in shown:
                name = material["name"]
                proportion = material["proportion"]
                row_y = y + 4
                is_core = bool(core_mat and name.lower() == core_mat.lower())
                color = palette["orange"] if is_core else palette["text"]
                bar_color = palette["orange"] if is_core else palette["accent"]
                display = name if len(name) <= 19 else name[:18] + "…"
                self._text(16, row_y + 4, display, color, ("Courier", 9))
                self.canvas.create_rectangle(
                    bar_x, row_y + 1, bar_end, row_y + 9,
                    fill=palette["panel_alt"], outline=palette["border_soft"],
                )
                fill_px = max(2, int(bar_width * (proportion / max_prop)))
                self.canvas.create_rectangle(
                    bar_x, row_y + 1, bar_x + fill_px, row_y + 9,
                    fill=bar_color, outline="",
                )
                self._text(bar_end + 7, row_y + 4, f"{proportion:.1f}%", color, ("Courier", 8))
                y += self._MAT_H

        if model["refined_total"]:
            parts = "  ·  ".join(f'{item["tonnes"]}t {item["name"]}' for item in model["refined"])
            summary = f'{model["refined_total"]}t REFINED  ·  {parts}'
            if len(summary) > 52:
                summary = summary[:51] + "…"
            self._text(16, y + 22, summary, palette["green"], ("Courier", 8, "bold"))
        else:
            self._text(16, y + 22, "REFINEMENT LOG  ·  awaiting refinery events",
                       palette["dim"], ("Courier", 8))

    def apply_theme(self, palette=None):
        """Apply the active commander palette without moving the overlay."""
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._redraw()
