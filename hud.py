import tkinter as tk
import json
import time
import math
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, COLOR_GREEN

class TacticalHUD:
    def __init__(self, root, config, on_widget_click=None):
        self.win = tk.Toplevel(root)
        self.config = config
        self.on_widget_click = on_widget_click
        
        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")
        
        self.width = 460
        self.base_height = 180
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.base_height, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        x = self.config.get("hud_x", 100)
        y = self.config.get("hud_y", 100)
        self.win.geometry(f"+{x}+{y}")
        
        self.force_topmost()
        
        # Optional title glyph animation (kept for later use):
        # self.anim_step = 0
        # self.anim_char = "⢄"
        self.status_widget_rect = (252, 8, 452, 32)
        self._mouse_down = None
        self._mouse_dragging = False
        self._last_hud_health = {}
        self._source_anim_targets = {}
        self._source_positions = {"J": 273, "S": 293, "N": 313, "C": 333, "E": 353}
        self._prev_source_states = {}
        self._dot_blink_until = {}
        self._age_cycle_idx = 0
        self._age_cycle_ts = time.time()
        self.animate_ui()

    def force_topmost(self):
        """Keeps the window on top of the game."""
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.win.after(2000, self.force_topmost)

    def animate_ui(self):
        try:
            # Optional title glyph animation (re-enable if desired):
            # frames = ["⢄", "⢂", "⢁", " ", "⡈", "⡐", "⡠", "⡰", "⣠", "⣐", "⣈", "⣁", "⣂", "⣄", "⣆", "⣇", "⣧", "⣷", "⣾", "⣶", "⣼", "⣸", "⣙", "⣉", "⣁"]
            # self.anim_char = frames[self.anim_step]
            # self.anim_step = (self.anim_step + 1) % len(frames)
            # self.canvas.itemconfigure("anim_title", text=self.anim_char)

            # Subtle source-row animation: breathing dots + drifting sparkle.
            if self._source_anim_targets:
                t = time.time()

                for idx, label in enumerate(("J", "S", "N", "C", "E")):
                    base = self._source_anim_targets.get(label)
                    if not base:
                        continue
                    # Phase-shifted per source for a soft shimmer wave.
                    phase = (math.sin((t * 3.4) + (idx * 0.85)) + 1.0) * 0.5
                    mix = 0.18 + (phase * 0.22)
                    blink_until = self._dot_blink_until.get(label, 0.0)
                    if t < blink_until:
                        # One-shot micro-blink whenever a source changes state.
                        blink_phase = (math.sin(t * 18.0) + 1.0) * 0.5
                        mix += 0.35 * blink_phase
                    shimmer = self._mix_with_white(base, mix)
                    self.canvas.itemconfigure(f"source_dot_{label}", fill=shimmer)
        except Exception:
            pass
        finally:
            try:
                self.win.after(33, self.animate_ui)
            except Exception:
                pass

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.win.winfo_x() + deltax
        y = self.win.winfo_y() + deltay
        self.win.geometry(f"+{x}+{y}")

    def save_final_pos(self, event=None):
        self.config["hud_x"] = self.win.winfo_x()
        self.config["hud_y"] = self.win.winfo_y()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def _in_rect(self, x, y, rect):
        x0, y0, x1, y1 = rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def _source_from_x(self, x):
        labels = ["J", "S", "N", "C", "E"]
        dot_x = [275, 293, 311, 329, 347]
        nearest_idx = min(range(len(dot_x)), key=lambda i: abs(x - dot_x[i]))
        idx = nearest_idx
        if 0 <= idx < len(labels):
            return labels[idx]
        return None

    def _on_mouse_down(self, event):
        self._mouse_down = (event.x, event.y)
        self._mouse_dragging = False
        self.start_move(event)

    def _on_mouse_drag(self, event):
        if not self._mouse_down:
            return
        sx, sy = self._mouse_down
        if abs(event.x - sx) > 3 or abs(event.y - sy) > 3:
            self._mouse_dragging = True
        self.do_move(event)

    def _on_mouse_up(self, event):
        clicked_widget = self._in_rect(event.x, event.y, self.status_widget_rect)
        source = self._source_from_x(event.x) if clicked_widget else None
        if not self._mouse_dragging and clicked_widget and callable(self.on_widget_click):
            payload = {"source": source}
            try:
                payload["reason"] = (self._last_hud_health or {}).get("reason")
            except Exception:
                pass
            try:
                self.on_widget_click(payload)
            except Exception:
                pass
        self.save_final_pos()
        self._mouse_down = None
        self._mouse_dragging = False

    @staticmethod
    def _hex_to_rgb(color):
        color = (color or "").lstrip("#")
        if len(color) != 6:
            return (224, 224, 224)
        try:
            return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return (224, 224, 224)

    @staticmethod
    def _rgb_to_hex(rgb):
        r, g, b = rgb
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _pulse_color(self, base, mode):
        # Low-cost pulse: fast in alert, slower in normal, static in failure.
        if mode == "FAIL":
            return "#ff4d4d"
        t = time.time()
        period = 0.5 if mode == "ALERT" else 1.3
        phase = (t % period) / period
        strength = 0.55 + 0.45 * (1.0 - abs(phase * 2.0 - 1.0))
        r, g, b = self._hex_to_rgb(base)
        return self._rgb_to_hex((r * strength, g * strength, b * strength))

    def _mix_with_white(self, color, amount):
        amount = max(0.0, min(1.0, float(amount)))
        r, g, b = self._hex_to_rgb(color)
        nr = r + ((255 - r) * amount)
        ng = g + ((255 - g) * amount)
        nb = b + ((255 - b) * amount)
        return self._rgb_to_hex((nr, ng, nb))

    def draw_text(self, x, y, text, fill, font, anchor="w", tags=None):
        self.canvas.create_text(x+1, y+1, text=text, fill="black", font=font, anchor=anchor, tags=tags)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=tags)

    def update(
        self,
        current_sys,
        dest_name,
        dist_ly,
        scanned,
        total,
        r_pos,
        organic_count,
        system_traffic,
        game_r_pos=None,
        route_destination=None,
        route_counts=None,
        hud_status="OK",
        hud_health=None,
    ):
        target_h = self.base_height
        if self.canvas.winfo_height() != target_h:
            self.canvas.config(height=target_h)
            x = self.win.winfo_x()
            y = self.win.winfo_y()
            self.win.geometry(f"{self.width}x{target_h}+{x}+{y}")
        self.canvas.delete("all")
        
        h = target_h
        self.canvas.create_rectangle(5, 5, self.width - 5, h - 5, fill="#010101", outline=COLOR_ACCENT, width=2)
        self.canvas.create_line(5, 35, self.width - 5, 35, fill=COLOR_ACCENT, width=1)
        
        # Optional title glyph animation (re-enable if desired):
        # txt = getattr(self, "anim_char", "⢄")
        # self.draw_text(32, 20, text=txt, fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e", tags="anim_title")
        # self.draw_text(38, 20, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(20, 20, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        self._last_hud_health = hud_health or {}
        widget_x1 = 452
        self.canvas.create_rectangle(252, 8, 452, 32, outline="#2a2a2a", width=1, fill="#060606")

        age_map = self._last_hud_health.get("age_by_source") or {"J": self._last_hud_health.get("age_journal")}
        age_labels = ["J", "S", "N", "C", "E"]
        valid_labels = [k for k in age_labels if k in age_map]
        if not valid_labels:
            valid_labels = ["J"]
        now = time.time()
        if now - self._age_cycle_ts >= 2.0:
            self._age_cycle_idx = (self._age_cycle_idx + 1) % len(valid_labels)
            self._age_cycle_ts = now
        age_key = valid_labels[self._age_cycle_idx % len(valid_labels)]
        age_val = age_map.get(age_key)
        age_txt = "--.-s"
        if isinstance(age_val, (int, float)):
            age_txt = f"{age_val:4.1f}s"

        source_states = self._last_hud_health.get("source_states") or {}
        source_color = {"OK": COLOR_GREEN, "WARN": "#ffb347", "FAIL": "#ff5a5a"}
        dot_positions = [264, 284, 304, 324, 344]
        labels = ("J", "S", "N", "C", "E")
        self._source_anim_targets = {}
        now = time.time()
        for i, label in enumerate(labels):
            state = source_states.get(label, "FAIL")
            c = source_color.get(state, "#777")
            self._source_anim_targets[label] = c
            prev_state = self._prev_source_states.get(label)
            if prev_state is not None and prev_state != state:
                self._dot_blink_until[label] = now + 0.70
            self._prev_source_states[label] = state
            x = dot_positions[i]
            self.draw_text(x, 20, text=f"{label}", fill="#8a8a8a", font=("Courier", 8, "bold"), anchor="w")
            self.canvas.create_text(x + 9, 20, text="●", fill=c, font=("Courier", 10, "bold"), anchor="w", tags=(f"source_dot_{label}", "source_row"))
        self.draw_text(447, 20, text=f"{age_key} {age_txt}", fill="#9aa7ad", font=("Courier", 8, "bold"), anchor="e")
        # Bio logs hidden for now (counting disabled)

        self.draw_text(20, 48, text=f"SYS: {current_sys.upper()}", fill=COLOR_TEXT, font=("Courier", 10, "bold"), anchor="w")
        
        dest_txt = f"NAV: {dest_name.upper() if dest_name else '---'}"
        if game_r_pos:
            dest_txt += f" [{game_r_pos[0]}/{game_r_pos[1]}]"
        self.draw_text(20, 66, text=dest_txt, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(440, 66, text=dist_ly, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="e")
        
        self.canvas.create_line(20, 80, 440, 80, fill="#333", width=1)
        
        pct = (scanned / total) if total > 0 else 0
        self.canvas.create_rectangle(20, 88, 440, 102, outline="#333", width=1)
        if pct > 0:
            self.canvas.create_rectangle(20, 88, 20 + (420 * pct), 102, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
        
        self.draw_text(20, 116, text=f"SCAN: {scanned}/{total} BODIES", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        self.draw_text(440, 116, text=f"{int(pct*100)}%", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e")

        t_day = system_traffic.get('day', 0)
        t_week = system_traffic.get('week', 0)
        t_total = system_traffic.get('total', 0)
        self.draw_text(20, 140, text=f"TRAFFIC: Today : {t_day}  This Week : {t_week}  Total : {t_total}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        route_y = h - 18

        route_pct = 0.0
        route_count_txt = "ROUTE: 0/0"
        if route_counts and route_counts[1] > 0:
            route_pct = max(0.0, min(1.0, route_counts[0] / route_counts[1]))
            route_count_txt = f"ROUTE: {route_counts[0]}/{route_counts[1]}"
        route_text = f"{route_count_txt} ({int(route_pct * 100)}%)"
        if r_pos and len(r_pos) > 2 and r_pos[2]:
            route_text = f"{route_text} [{r_pos[2]}]"

        if route_destination:
            dest_text = f"DEST: {route_destination.upper()}"
            if len(dest_text) > 34:
                dest_text = dest_text[:31] + "..."
            self.draw_text(20, route_y, text=dest_text, fill=COLOR_ORANGE, font=("Courier", 9, "bold"), anchor="w")
        self.draw_text(440, route_y, text=route_text, fill=COLOR_ACCENT, font=("Courier", 9, "bold"), anchor="e")
