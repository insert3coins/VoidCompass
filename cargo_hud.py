"""Compact, theme-aware cargo manifest overlay."""

import math
import tkinter as tk

from config import save_config
import overlay_chrome
import themes


WIDTH = 360
MIN_HEIGHT = 148
MAX_ROWS = 14


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _cargo_name(item):
    value = str(item.get("Name_Localised") or item.get("Name") or "Unknown").strip()
    if value.startswith("$"):
        value = value[1:]
    if value.endswith(";"):
        value = value[:-1]
    return value.replace("_name", "").replace("_", " ").title() or "Unknown"


def build_cargo_model(inventory, capacity=0):
    """Normalise Cargo.json inventory and expose mission/stolen distinctions."""
    stacks = {}
    for item in inventory or []:
        if not isinstance(item, dict):
            continue
        name = _cargo_name(item)
        count = max(0, _integer(item.get("Count")))
        if not count:
            continue
        key = name.casefold()
        row = stacks.setdefault(key, {
            "name": name, "count": 0, "mission": 0, "stolen": 0,
        })
        row["count"] += count
        if item.get("MissionID") not in (None, "", 0, "0"):
            row["mission"] += count
        row["stolen"] += min(count, max(0, _integer(item.get("Stolen"))))

    rows = sorted(stacks.values(), key=lambda row: row["name"].casefold())
    total = sum(row["count"] for row in rows)
    capacity_value = max(0, _integer(capacity))
    utilisation = None
    if capacity_value:
        utilisation = max(0.0, min(1.0, total / capacity_value))
    return {
        "rows": rows,
        "total": total,
        "capacity": capacity_value,
        "free": max(0, capacity_value - total) if capacity_value else None,
        "utilisation": utilisation,
        "mission": sum(row["mission"] for row in rows),
        "stolen": sum(row["stolen"] for row in rows),
    }


class CargoHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_inventory = []
        self._last_capacity = 0
        self._last_render_key = None
        self._html_render_model = build_cargo_model([], 0)
        self._height = MIN_HEIGHT
        self._save_job = None

        overlay_bg = overlay_chrome.configure_overlay_window(self.win, "#ff00ff")
        self.canvas = tk.Canvas(
            self.win, width=WIDTH, height=self._height,
            bg=overlay_bg, highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        default_x = screen_width - WIDTH - 20
        default_y = (screen_height // 2) - 200
        x = self._safe_int(self.config.get("cargo_hud_x"), default_x)
        y = self._safe_int(self.config.get("cargo_hud_y"), default_y)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        self.win.after(0, self._apply_initial_position)
        self.win.after(250, self._apply_initial_position)
        self.win.after(700, self._apply_initial_position)
        self.force_topmost()
        self.update([], 0)

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        except Exception:
            pass

    def force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self.force_topmost)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        x = self.win.winfo_x() + (event.x - self.x)
        y = self.win.winfo_y() + (event.y - self.y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._desired_pos = (x, y)
        self.config["cargo_hud_x"] = x
        self.config["cargo_hud_y"] = y
        self._schedule_config_save()

    def save_final_pos(self, _event):
        self.config["cargo_hud_x"] = self.win.winfo_x()
        self.config["cargo_hud_y"] = self.win.winfo_y()
        self._desired_pos = (self.config["cargo_hud_x"], self.config["cargo_hud_y"])
        self._write_config()

    def _write_config(self):
        save_config(self.config)

    def _schedule_config_save(self):
        if self._save_job:
            try:
                self.win.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.win.after(250, self._flush_scheduled_save)

    def _flush_scheduled_save(self):
        self._save_job = None
        try:
            self._write_config()
        except Exception:
            pass

    def draw_text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _capacity_bar(self, y, utilisation, tone):
        """Draw the original ten-segment cargo meter in the refreshed layout."""
        left = 16
        right = WIDTH - 16
        segment_count = 10
        gap = 3
        segment_width = (right - left - (gap * (segment_count - 1))) / segment_count
        filled = 0
        if utilisation is not None and utilisation > 0:
            filled = min(segment_count, math.ceil(utilisation * segment_count))

        for index in range(segment_count):
            x1 = left + index * (segment_width + gap)
            x2 = x1 + segment_width
            active = index < filled
            self.canvas.create_rectangle(
                x1, y, x2, y + 7,
                fill=self._palette[tone] if active else self._palette["panel_alt"],
                outline=self._palette[tone] if active else self._palette["border_soft"],
                width=1,
            )

    def update(self, inventory, capacity=0):
        inventory = list(inventory or [])
        self._last_inventory = list(inventory)
        self._last_capacity = capacity
        model = build_cargo_model(inventory, capacity)
        self._html_render_model = model
        render_key = repr(model)
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key
        shown = model["rows"][:MAX_ROWS]
        overflow = model["rows"][MAX_ROWS:]
        row_count = max(1, len(shown)) + (1 if overflow else 0)
        self._height = max(MIN_HEIGHT, 116 + row_count * 21 + 28)
        x, y = self._desired_pos
        self.canvas.config(width=WIDTH, height=self._height)
        self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        self.canvas.delete("all")

        palette = self._palette
        # Dense manifests use clean fields: scanline scaling creates false row rules in OBS.
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, self._height, accent=palette["accent"], scanlines=False,
        )
        self.draw_text(16, 18, "CARGO MANIFEST", palette["accent"], ("Courier", 10, "bold"))
        total_text = f'{model["total"]:,}'
        if model["capacity"]:
            total_text += f' / {model["capacity"]:,} T'
        else:
            total_text += " T"
        self.draw_text(WIDTH - 16, 18, total_text, palette["orange"],
                       ("Courier", 10, "bold"), anchor="e")
        utilisation = model["utilisation"]
        status_text = "CAPACITY UNKNOWN"
        status_tone = "dim"
        if utilisation is not None:
            status_text = f'{utilisation * 100:.0f}% USED  ·  {model["free"]:,} T FREE'
            status_tone = "red" if utilisation >= 0.95 else "yellow" if utilisation >= 0.8 else "green"
        self.draw_text(16, 48, status_text, palette[status_tone], ("Courier", 8, "bold"))
        bar_y = 58
        self._capacity_bar(bar_y, utilisation, status_tone)
        self.draw_text(16, 90, "COMMODITY", palette["dim"], ("Courier", 8, "bold"))
        self.draw_text(WIDTH - 16, 90, "TONNES", palette["dim"],
                       ("Courier", 8, "bold"), anchor="e")
        y_pos = 109
        if not shown:
            self.draw_text(WIDTH // 2, y_pos, "[ HOLD EMPTY ]", palette["dim"],
                           ("Courier", 9), anchor="center")
            y_pos += 21
        else:
            for row in shown:
                flags = []
                if row["mission"]:
                    flags.append("MISSION")
                if row["stolen"]:
                    flags.append("STOLEN")
                color = palette["red"] if row["stolen"] else palette["orange"] if row["mission"] else palette["text"]
                name = row["name"] if len(row["name"]) <= 27 else row["name"][:26] + "…"
                if flags:
                    flag_text = "/".join(flags)
                    allowed = max(7, 25 - len(flag_text))
                    name = (name if len(name) <= allowed else name[:allowed - 1] + "…") + f"  {flag_text}"
                self.draw_text(16, y_pos, name, color, ("Courier", 9))
                self.draw_text(WIDTH - 16, y_pos, f'{row["count"]:,}', color,
                               ("Courier", 9, "bold"), anchor="e")
                y_pos += 21

        if overflow:
            hidden_tonnes = sum(row["count"] for row in overflow)
            self.draw_text(WIDTH // 2, y_pos,
                           f'+ {len(overflow)} MORE STACKS  ·  {hidden_tonnes:,} T',
                           palette["dim"], ("Courier", 8), anchor="center")
            y_pos += 21

        footer = []
        if model["mission"]:
            footer.append(f'MISSION {model["mission"]:,} T')
        if model["stolen"]:
            footer.append(f'STOLEN {model["stolen"]:,} T')
        footer_text = "  ·  ".join(footer) if footer else f'{len(model["rows"])} COMMODITY STACKS'
        footer_color = palette["red"] if model["stolen"] else palette["orange"] if model["mission"] else palette["muted"]
        self.draw_text(16, y_pos + 18, footer_text, footer_color, ("Courier", 8, "bold"))

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._last_render_key = None
        self.update(self._last_inventory, self._last_capacity)
