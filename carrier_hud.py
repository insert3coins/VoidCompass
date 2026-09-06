"""Compact Fleet/Squadron Carrier command overlay."""

import tkinter as tk
from datetime import datetime, timedelta, timezone

from config import save_config
import overlay_chrome
import themes


WIDTH = 430
_CHROMA = "#ff00ff"
_COOLDOWN_SECS = 290


def _parse_dt(ts_str):
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _fmt_duration(seconds):
    try:
        seconds = max(0, int(seconds))
    except Exception:
        seconds = 0
    mins, secs = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:d}:{mins:02d}:{secs:02d}" if hrs else f"{mins:d}:{secs:02d}"


def _truncate(text, max_chars):
    text = str(text or "")
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


def _fmt_location(system, body):
    system = str(system or "Unknown").strip() or "Unknown"
    body = str(body or "").strip()
    if body and body.lower().startswith(system.lower()):
        body = body[len(system):].strip()
    return system if not body else f"{system} / {body}"


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_carrier_hud_model(carrier_data, now=None):
    """Build a renderer-neutral live carrier command summary."""
    cd = carrier_data if isinstance(carrier_data, dict) else {}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    status = str(cd.get("status") or "idle").lower()
    badge, badge_tone = {
        "idle": ("READY", "muted"),
        "jumping": ("JUMPING", "accent"),
        "cooldown": ("COOLDOWN", "yellow"),
        "cooldown_cancel": ("CANCELLED", "red"),
    }.get(status, (status.upper(), "muted"))

    route = [row for row in (cd.get("expedition_route") or []) if isinstance(row, dict)]
    done = sum(1 for row in route if row.get("visited"))
    next_route = next((row for row in route if not row.get("visited")), None)
    remaining_fuel = sum(
        max(0, int(_number(row.get("fuel_used_t"), 0)))
        for row in route if not row.get("visited") and row.get("fuel_used_t") is not None
    )

    dep = _parse_dt(cd.get("jump_departure_time"))
    movement_visible = False
    movement_label = "NEXT JUMP"
    movement_value = "READY TO PLOT JUMP"
    movement_tone = "muted"
    movement_detail = ""
    if status == "jumping":
        movement_visible = True
        movement_value = _fmt_location(cd.get("jump_destination") or "TBD", cd.get("jump_body"))
        movement_tone = "orange"
        movement_detail = f"DEPARTS IN {_fmt_duration((dep - now).total_seconds())}" if dep else "DEPARTURE SCHEDULED"
    elif status == "cooldown":
        movement_visible = True
        movement_label = "JUMP COOLDOWN"
        movement_value = f"READY IN {_fmt_duration(((dep + timedelta(seconds=_COOLDOWN_SECS)) - now).total_seconds())}" if dep else "RECOVERY ACTIVE"
        movement_tone = "yellow"
        previous = cd.get("previous_system")
        movement_detail = f"FROM {previous}" if previous else ""
    elif status == "cooldown_cancel":
        movement_visible = True
        movement_label = "JUMP STATUS"
        movement_value = "JUMP CANCELLED"
        movement_tone = "red"
        movement_detail = "BRIEF COOLDOWN ACTIVE"
    else:
        # A Discord/operator destination note is not a plotted jump. Only
        # journal evidence or a pending expedition stop earns this panel.
        destination = cd.get("jump_destination") or (next_route or {}).get("system")
        if destination:
            movement_visible = True
            movement_value = str(destination)
            movement_tone = "orange"
            if next_route and str(destination) == str(next_route.get("system")):
                detail = []
                distance = _number(next_route.get("distance_ly"))
                tritium = _number(next_route.get("fuel_used_t"))
                if distance is not None:
                    detail.append(f"{distance:.1f} LY")
                if tritium is not None:
                    detail.append(f"{int(tritium)} T TRITIUM")
                movement_detail = "  ·  ".join(detail)

    fuel = _number(cd.get("fuel_level"))
    capacity = _number(cd.get("fuel_capacity"), 1000.0) or 1000.0
    fuel_ratio = None if fuel is None or capacity <= 0 else max(0.0, min(1.0, fuel / capacity))
    fuel_tone = "muted"
    if fuel_ratio is not None:
        fuel_tone = "red" if fuel_ratio <= 0.15 else "yellow" if fuel_ratio <= 0.4 else "green"

    current_range = _number(cd.get("jump_range_curr"))
    maximum_range = _number(cd.get("jump_range_max"))
    cargo = _number(cd.get("space_cargo"))
    free = _number(cd.get("space_free"))
    orders = cd.get("trade_orders") or []
    return {
        "carrier_type": "SQUADRON CARRIER" if cd.get("carrier_type") == "SquadronCarrier" else "FLEET CARRIER",
        "name": cd.get("name") or "Fleet Carrier",
        "callsign": cd.get("callsign") or "---",
        "location": _fmt_location(cd.get("system"), cd.get("body")),
        "status": status,
        "badge": badge,
        "badge_tone": badge_tone,
        "movement_label": movement_label,
        "movement_visible": movement_visible,
        "movement_value": movement_value,
        "movement_tone": movement_tone,
        "movement_detail": movement_detail,
        "route_name": str(cd.get("expedition_name") or "EXPEDITION ROUTE"),
        "route_total": len(route),
        "route_done": done,
        "route_complete": bool(route) and done == len(route),
        "remaining_fuel": remaining_fuel,
        "fuel": fuel,
        "fuel_capacity": capacity,
        "fuel_ratio": fuel_ratio,
        "fuel_tone": fuel_tone,
        "fuel_estimated": bool(cd.get("fuel_level_estimated")),
        "range": current_range if current_range is not None else maximum_range,
        "range_is_max": current_range is None and maximum_range is not None,
        "cargo": cargo,
        "free": free,
        "orders": len(orders) if isinstance(orders, (list, tuple, dict)) else 0,
    }


class CarrierHUD:
    def __init__(self, root, config, tracker):
        self.root = root
        self.config = config
        self.tracker = tracker
        self._save_job = None
        self._tick_job = None
        self._mouse_down = None
        self._mouse_dragging = False
        self._mx = self._my = 0
        self._height = 206
        self._last_render_key = None
        self._html_render_model = build_carrier_hud_model({})
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)
        self.canvas = tk.Canvas(
            self.win, bg=overlay_bg, highlightthickness=0,
            width=WIDTH, height=self._height,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        x = self._safe_int(self.config.get("carrier_hud_x"), 30)
        y = self._safe_int(self.config.get("carrier_hud_y"), 180)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        self.win.after(0, self._apply_initial_position)
        self.win.after(250, self._apply_initial_position)
        self.win.after(700, self._apply_initial_position)
        self._force_topmost()
        self.update()
        self._schedule_tick()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def destroy(self):
        if self._tick_job:
            try:
                self.win.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
        try:
            self.win.destroy()
        except Exception:
            pass

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        except Exception:
            pass

    @staticmethod
    def _fit_position(x, y, _height):
        """Preserve the commander-selected virtual-desktop anchor."""
        return int(x), int(y)

    def show(self):
        if not self.is_open():
            return
        self.update()
        self._apply_initial_position()
        try:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except tk.TclError:
            pass

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self._force_topmost)

    def _schedule_tick(self):
        if self._tick_job:
            try:
                self.win.after_cancel(self._tick_job)
            except Exception:
                pass
        self._tick_job = self.win.after(1000, self._tick)

    def _tick(self):
        self._tick_job = None
        if self.is_open():
            self.update()
            self._schedule_tick()

    def update(self, carrier_data=None):
        if not self.is_open():
            return
        if carrier_data:
            cd = carrier_data
        else:
            display = getattr(self.tracker, "display_carrier", None)
            cd = display() if callable(display) else getattr(self.tracker, "carrier_data", {})
            cd = cd or {}
        model = build_carrier_hud_model(cd)
        self._html_render_model = model
        render_key = repr(model)
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key
        route_extra = 47 if model["route_total"] else 0
        detail_extra = 16 if model["movement_detail"] else 0
        height = 206 + route_extra + detail_extra
        self._height = height
        self.canvas.config(width=WIDTH, height=height)
        x, y = self._desired_pos
        self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, height))
        self.canvas.delete("all")

        palette = self._palette
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, height, accent=palette["accent"],
            scanlines=False,
        )
        self._draw_text(18, 18, model["carrier_type"], palette["accent"], ("Courier", 10, "bold"))
        self._draw_text(WIDTH - 18, 18, model["badge"], palette[model["badge_tone"]],
                        ("Courier", 9, "bold"), anchor="e")
        self._draw_text(18, 50, _truncate(str(model["name"]).upper(), 32), palette["text"],
                        ("Courier", 11, "bold"))
        self._draw_text(WIDTH - 18, 50, f'[{model["callsign"]}]', palette["orange"],
                        ("Courier", 9, "bold"), anchor="e")
        self._draw_text(18, 68, _truncate(model["location"], 52), palette["muted"], ("Courier", 8))
        y = 94
        self._draw_text(18, y, model["movement_label"], palette["dim"], ("Courier", 8, "bold"))
        y += 18
        self._draw_text(18, y, _truncate(model["movement_value"].upper(), 47),
                        palette[model["movement_tone"]], ("Courier", 10, "bold"))
        if model["movement_detail"]:
            y += 16
            self._draw_text(18, y, _truncate(model["movement_detail"], 55), palette["muted"], ("Courier", 8))
        y += 15
        if model["route_total"]:
            y += 15
            route_tone = "green" if model["route_complete"] else "accent"
            self._draw_text(18, y, _truncate(model["route_name"].upper(), 30), palette["dim"],
                            ("Courier", 8, "bold"))
            route_text = f'{model["route_done"]}/{model["route_total"]} COMPLETE'
            self._draw_text(WIDTH - 18, y, route_text, palette[route_tone],
                            ("Courier", 8, "bold"), anchor="e")
            y += 17
            fuel_need = f'{model["remaining_fuel"]:,} T REMAINING' if model["remaining_fuel"] else "ROUTE FUEL CLEAR"
            self._draw_text(18, y, fuel_need, palette["muted"], ("Courier", 8))
            y += 15
        y += 15
        self._draw_text(18, y, "LOGISTICS", palette["dim"], ("Courier", 8, "bold"))
        fuel_text = "TRITIUM UNKNOWN"
        if model["fuel"] is not None:
            estimate = " ~" if model["fuel_estimated"] else " "
            fuel_text = f'TRITIUM{estimate}{int(model["fuel"]):,}/{int(model["fuel_capacity"]):,} T'
        self._draw_text(18, y + 18, fuel_text, palette[model["fuel_tone"]], ("Courier", 9, "bold"))
        if model["range"] is not None:
            prefix = "MAX " if model["range_is_max"] else ""
            self._draw_text(WIDTH - 18, y + 18, f'{prefix}RANGE {model["range"]:.1f} LY', palette["text"],
                            ("Courier", 9, "bold"), anchor="e")

        bar_y = y + 29
        self.canvas.create_rectangle(18, bar_y, WIDTH - 18, bar_y + 5,
                                     fill=palette["panel_alt"], outline="")
        if model["fuel_ratio"] is not None:
            fill_x = 18 + int((WIDTH - 36) * model["fuel_ratio"])
            self.canvas.create_rectangle(18, bar_y, fill_x, bar_y + 5,
                                         fill=palette[model["fuel_tone"]], outline="")
        cargo_parts = []
        if model["cargo"] is not None:
            cargo_parts.append(f'CARGO {int(model["cargo"]):,} T')
        if model["free"] is not None:
            cargo_parts.append(f'FREE {int(model["free"]):,} T')
        if model["orders"]:
            cargo_parts.append(f'{model["orders"]} ORDERS')
        if cargo_parts:
            self._draw_text(18, y + 47, "  ·  ".join(cargo_parts), palette["muted"], ("Courier", 8))

    def _build_rows(self, cd):
        """Compatibility view for callers that previously consumed flat rows."""
        model = build_carrier_hud_model(cd)
        palette = self._palette
        rows = [
            (f'{_truncate(str(model["name"]).upper(), 30)}  [{model["callsign"]}]', palette["text"]),
            (f'LOC: {_truncate(model["location"], 42)}', palette["text"]),
            (f'{model["movement_label"]}: {_truncate(model["movement_value"], 35)}', palette[model["movement_tone"]]),
        ]
        if model["route_total"]:
            rows.append((f'ROUTE: {model["route_done"]}/{model["route_total"]}', palette["accent"]))
        return rows, model["badge"], palette[model["badge_tone"]]

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._last_render_key = None
        self.update()

    def _draw_text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _on_mouse_down(self, event):
        self._mouse_down = (event.x, event.y)
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
        self._desired_pos = (x, y)
        self.config["carrier_hud_x"] = x
        self.config["carrier_hud_y"] = y
        self._schedule_config_save()

    def _on_mouse_up(self, _event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
        x, y = self._fit_position(x, y, self._height)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        if x != 0 or y != 0:
            self.config["carrier_hud_x"] = x
            self.config["carrier_hud_y"] = y
            self._write_config()
        self._mouse_down = None
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
