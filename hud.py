import tkinter as tk
import tkinter.font as tkfont
import time
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config

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

        x = self._safe_int(self.config.get("hud_x"), 100)
        y = self._safe_int(self.config.get("hud_y"), 100)
        self._desired_pos = (x, y)
        self.win.geometry(f"{self.width}x{self.base_height}+{x}+{y}")
        self.win.after(0, self._apply_initial_position)
        self.win.after(250, self._apply_initial_position)
        self.win.after(700, self._apply_initial_position)
        
        self.force_topmost()
        
        self.anim_step = 0
        self.anim_frames = [
            "⢄",
            "⢂",
            "⢁",
            " ",
            "⡈",
            "⡐",
            "⡠",
            "⡰",
            "⣠",
            "⣐",
            "⣈",
            "⣁",
            "⣂",
            "⣄",
            "⣆",
            "⣇",
            "⣧",
            "⣷",
            "⣾",
            "⣶",
            "⣼",
            "⣸",
            "⣙",
            "⣉",
            "⣁",
        ]
        self._mouse_down = None
        self._mouse_dragging = False
        self._save_job = None
        self._anim_interval_ms = int(self.config.get("hud_anim_interval_ms", 100) or 100)
        if self._anim_interval_ms < 80:
            self._anim_interval_ms = 80
        self.animate_ui()

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(f"{self.width}x{self.base_height}+{x}+{y}")
        except Exception:
            pass

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def force_topmost(self):
        """Keeps the window on top of the game."""
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000)
        if refresh_ms < 2000:
            refresh_ms = 2000
        self.win.after(refresh_ms, self.force_topmost)

    def animate_ui(self):
        try:
            self._draw_title_anim()
            self.anim_step = (self.anim_step + 1) % len(self.anim_frames)
        except Exception:
            pass
        finally:
            try:
                self.win.after(self._anim_interval_ms, self.animate_ui)
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
        # Persist while dragging so release outside the canvas still keeps the new position.
        self.config["hud_x"] = x
        self.config["hud_y"] = y
        self._schedule_config_save()

    def save_final_pos(self, event=None):
        self.config["hud_x"] = self.win.winfo_x()
        self.config["hud_y"] = self.win.winfo_y()
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
        self.save_final_pos()
        self._mouse_down = None
        self._mouse_dragging = False

    def draw_text(self, x, y, text, fill, font, anchor="w", tags=None):
        self.canvas.create_text(x+1, y+1, text=text, fill="black", font=font, anchor=anchor, tags=tags)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=tags)

    def _draw_title_anim(self):
        self.canvas.delete("anim_title")
        if not self.anim_frames:
            return
        frame = self.anim_frames[self.anim_step]
        self.draw_text(440, 20, text=frame, fill=COLOR_ACCENT, font=("Courier", 12, "bold"), anchor="e", tags="anim_title")

    def draw_fitted_text(self, x, y, text, fill, family="Courier", size=9, weight="bold", max_width=300, min_size=4):
        font_size = size
        while font_size > min_size:
            font = tkfont.Font(family=family, size=font_size, weight=weight)
            if font.measure(text) <= max_width:
                break
            font_size -= 1
        self.draw_text(x, y, text=text, fill=fill, font=(family, font_size, weight), anchor="w")

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
        route_waypoint=None,
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
        
        self.draw_text(20, 20, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        self._draw_title_anim()
        _ = hud_health
        # Bio logs hidden for now (counting disabled)

        self.draw_text(20, 48, text=f"SYS: {current_sys.upper()}", fill=COLOR_TEXT, font=("Courier", 10, "bold"), anchor="w")
        
        dest_txt = f"NAV: {dest_name.upper() if dest_name else '---'}"
        if game_r_pos:
            dest_txt += f" [{game_r_pos[0]}/{game_r_pos[1]}]"
        self.draw_text(20, 66, text=dest_txt, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(440, 66, text=dist_ly, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="e")
        
        self.canvas.create_line(20, 80, 440, 80, fill="#333", width=1)
        
        pct = (scanned / total) if total > 0 else 0
        pct = max(0.0, min(1.0, pct))
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
        route_count_txt = "ROUTE 0/0"
        if route_counts and route_counts[1] > 0:
            route_pct = max(0.0, min(1.0, route_counts[0] / route_counts[1]))
            route_count_txt = f"ROUTE {route_counts[0]}/{route_counts[1]}"
        route_text = f"{route_count_txt} {int(route_pct * 100)}%"
        if r_pos and len(r_pos) > 2 and r_pos[2]:
            route_text = f"{route_text} {r_pos[2].replace(' ', '')}"

        if route_waypoint:
            waypoint_text = f"WP: {route_waypoint.upper()}"
            route_font = tkfont.Font(family="Courier", size=9, weight="bold")
            route_width = route_font.measure(route_text)
            waypoint_width = max(40, 440 - route_width - 28)
            self.draw_fitted_text(20, route_y, waypoint_text, COLOR_ORANGE, max_width=waypoint_width)
        self.draw_text(440, route_y, text=route_text, fill=COLOR_ACCENT, font=("Courier", 9, "bold"), anchor="e")
