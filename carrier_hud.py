import tkinter as tk
from datetime import datetime, timedelta, timezone

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
import overlay_chrome


WIDTH = 380
_CHROMA = "#ff00ff"
_COOLDOWN_SECS = 290
_MUTED = "#7a8a98"
_OK = "#21d189"
_WARN = "#ff9a3c"
_FAIL = "#ff5c5c"


def _parse_dt(ts_str):
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _fmt_duration(seconds):
    try:
        seconds = max(0, int(seconds))
    except Exception:
        seconds = 0
    mins, secs = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs:d}:{mins:02d}:{secs:02d}"
    return f"{mins:d}:{secs:02d}"


def _truncate(text, max_chars):
    text = str(text or "")
    return text if len(text) <= max_chars else text[:max_chars - 1] + "..."


def _fmt_location(system, body):
    system = str(system or "Unknown").strip() or "Unknown"
    body = str(body or "").strip()
    if body and body.lower().startswith(system.lower()):
        body = body[len(system):].strip()
    return system if not body else f"{system} / {body}"


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

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)

        self.canvas = tk.Canvas(
            self.win, bg=overlay_bg, highlightthickness=0,
            width=WIDTH, height=140,
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        x = self._safe_int(self.config.get("carrier_hud_x"), 30)
        y = self._safe_int(self.config.get("carrier_hud_y"), 180)
        self._desired_pos = (x, y)
        self.win.geometry(f"{WIDTH}x140+{x}+{y}")
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
            self.win.geometry(f"{WIDTH}x{getattr(self, '_height', 140)}+{x}+{y}")
        except Exception:
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
        if not self.is_open():
            return
        self.update()
        self._schedule_tick()

    def update(self, carrier_data=None):
        if not self.is_open():
            return
        cd = carrier_data or getattr(self.tracker, "carrier_data", {}) or {}
        rows, status_text, status_color = self._build_rows(cd)

        line_h = 19
        height = max(116, 43 + len(rows) * line_h + 10)
        self._height = height
        self.canvas.config(width=WIDTH, height=height)
        self.win.geometry(f"{WIDTH}x{height}")
        self.canvas.delete("all")

        overlay_chrome.draw_chrome(self.canvas, WIDTH, height)
        self.canvas.create_line(20, 35, WIDTH - 20, 35, fill="#1a2530", width=1)
        self._draw_text(20, 20, "FLEET CARRIER", COLOR_ACCENT, ("Courier", 10, "bold"))
        self._draw_text(WIDTH - 20, 20, status_text, status_color, ("Courier", 10, "bold"), anchor="e")

        y = 47
        for text, color in rows:
            self._draw_text(20, y, text, color, ("Courier", 9, "bold"))
            y += line_h

    def _build_rows(self, cd):
        status = cd.get("status") or "idle"
        badge = {
            "idle": ("IDLE", _MUTED),
            "jumping": ("JUMPING", COLOR_ACCENT),
            "cooldown": ("COOLDOWN", _WARN),
            "cooldown_cancel": ("CANCELLED", _FAIL),
        }.get(status, (status.upper(), _MUTED))

        name = cd.get("name") or "Fleet Carrier"
        callsign = cd.get("callsign") or "---"
        rows = [(f"{_truncate(name.upper(), 24)}  [{callsign}]", COLOR_TEXT)]

        system = cd.get("system") or "Unknown"
        body = cd.get("body") or ""
        loc = _fmt_location(system, body)
        rows.append((f"LOC: {_truncate(loc, 42)}", COLOR_TEXT))

        now = datetime.now(timezone.utc)
        dep = _parse_dt(cd.get("jump_departure_time"))
        if status == "jumping" and dep:
            dest = cd.get("jump_destination") or "TBD"
            dest_body = cd.get("jump_body") or ""
            target = _fmt_location(dest, dest_body)
            rows.append((f"DST: {_truncate(target, 42)}", COLOR_ORANGE))
            rows.append((f"DEPARTS IN: {_fmt_duration((dep - now).total_seconds())}", COLOR_ACCENT))
        elif status == "cooldown" and dep:
            ready_at = dep + timedelta(seconds=_COOLDOWN_SECS)
            rows.append((f"READY IN: {_fmt_duration((ready_at - now).total_seconds())}", _WARN))
            prev = cd.get("previous_system") or ""
            if prev:
                rows.append((f"FROM: {_truncate(prev, 42)}", _MUTED))
        elif status == "cooldown_cancel":
            rows.append(("JUMP CANCELLED - BRIEF COOLDOWN", _FAIL))
        else:
            dest = cd.get("destination_note") or cd.get("jump_destination") or ""
            if dest:
                rows.append((f"PLAN: {_truncate(dest, 42)}", COLOR_ORANGE))
            else:
                rows.append(("READY TO PLOT JUMP", _MUTED))

        fuel = cd.get("fuel_level")
        cap = cd.get("fuel_capacity") or 1000
        jump_curr = cd.get("jump_range_curr")
        jump_max = cd.get("jump_range_max")
        parts = []
        if fuel is not None:
            parts.append(f"FUEL {int(fuel)}/{int(cap)}T")
        if jump_curr:
            parts.append(f"RANGE {float(jump_curr):.1f}LY")
        elif jump_max:
            parts.append(f"MAX {float(jump_max):.1f}LY")
        if parts:
            fuel_color = _OK
            try:
                pct = float(fuel) / float(cap)
                if pct <= 0.15:
                    fuel_color = _FAIL
                elif pct <= 0.4:
                    fuel_color = _WARN
            except Exception:
                fuel_color = _MUTED
            rows.append(("  |  ".join(parts), fuel_color))

        return rows, badge[0], badge[1]

    def _draw_text(self, x, y, text, fill, font, anchor="w"):
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
        self.win.geometry(f"+{x}+{y}")
        self.config["carrier_hud_x"] = x
        self.config["carrier_hud_y"] = y
        self._schedule_config_save()

    def _on_mouse_up(self, _event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
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
