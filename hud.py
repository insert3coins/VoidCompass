import tkinter as tk
import tkinter.font as tkfont
import time
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, COLOR_MUTED, save_config
import route_strip
import overlay_chrome

class TacticalHUD:
    def __init__(self, root, config, on_widget_click=None):
        self.win = tk.Toplevel(root)
        self.config = config
        self.on_widget_click = on_widget_click

        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")

        self.full_width = 560
        self.full_height = 246
        self.compact_width = 450
        self.compact_height = 190
        self.width, self.base_height = self._target_dimensions()
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
        self._crt_phase = 0
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

    def _is_compact(self):
        return bool(self.config.get("hud_compact_mode", False))

    def _target_dimensions(self):
        if self._is_compact():
            return self.compact_width, self.compact_height
        return self.full_width, self.full_height

    def _ensure_dimensions(self, width, height):
        self.width = width
        self.base_height = height
        if self.canvas.winfo_width() != width or self.canvas.winfo_height() != height:
            self.canvas.config(width=width, height=height)
            x = self.win.winfo_x()
            y = self.win.winfo_y()
            self.win.geometry(f"{width}x{height}+{x}+{y}")

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
            self._draw_crt_animation()
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

    def _crt_enabled(self):
        return bool(self.config.get("hud_crt_enabled", True))

    def _crt_intensity(self):
        value = str(self.config.get("hud_crt_intensity", "Subtle") or "Subtle").title()
        return value if value in ("Subtle", "Standard", "Strong") else "Subtle"

    @staticmethod
    def _glow_color(fill, factor):
        try:
            text = str(fill).lstrip("#")
            if len(text) != 6:
                return "#101820"
            red, green, blue = int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
            return f"#{int(red * factor):02x}{int(green * factor):02x}{int(blue * factor):02x}"
        except Exception:
            return "#101820"

    def draw_text(self, x, y, text, fill, font, anchor="w", tags=None):
        if self._crt_enabled():
            intensity = self._crt_intensity()
            factor = {"Subtle": 0.18, "Standard": 0.26, "Strong": 0.34}[intensity]
            glow = self._glow_color(fill, factor)
            offsets = [(-1, 0), (1, 0)]
            if intensity in ("Standard", "Strong"):
                offsets += [(0, -1), (0, 1)]
            if intensity == "Strong":
                offsets += [(-1, -1), (1, 1)]
            for dx, dy in offsets:
                self.canvas.create_text(x + dx, y + dy, text=text, fill=glow, font=font, anchor=anchor, tags=tags)
        self.canvas.create_text(x+1, y+1, text=text, fill="black", font=font, anchor=anchor, tags=tags)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=tags)

    def _draw_crt_animation(self):
        self.canvas.delete("crt_motion")
        if not self._crt_enabled() or not self.config.get("hud_crt_motion_enabled", True):
            return
        intensity = self._crt_intensity()
        step = {"Subtle": 3, "Standard": 5, "Strong": 7}[intensity]
        color = {"Subtle": "#0a2025", "Standard": "#0d2a31", "Strong": "#123841"}[intensity]
        speck_count = {"Subtle": 1, "Standard": 3, "Strong": 5}[intensity]
        # Keep the display gently alive without a conspicuous refresh bar
        # sweeping from the top of the HUD to the bottom.
        inner_w = max(1, self.width - 36)
        inner_h = max(1, self.base_height - 36)
        for index in range(speck_count):
            x = 18 + ((self._crt_phase * (17 + index * 4) + index * 73) % inner_w)
            y = 18 + ((self._crt_phase * (11 + index * 6) + index * 41) % inner_h)
            size = 2 if intensity == "Strong" and index == 0 else 1
            self.canvas.create_rectangle(
                x, y, x + size, y + size,
                fill=color, outline="", tags="crt_motion",
            )
        self._crt_phase = (self._crt_phase + step) % max(1, self.base_height)

    def _draw_title_anim(self):
        self.canvas.delete("anim_title")
        if not self.anim_frames:
            return
        frame = self.anim_frames[self.anim_step]
        # Match the title row's baseline and margin per mode (compact draws
        # its header at y=14/x=16; full at y=18/x=20) so the spinner sits
        # optically centered on the same line as "NAVIGATION HUD".
        if self._is_compact():
            x, y = self.width - 16, 14
        else:
            x, y = self.width - 20, 18
        self.draw_text(x, y, text=frame, fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e", tags="anim_title")

    def draw_fitted_text(self, x, y, text, fill, family="Courier", size=9, weight="bold", max_width=300, min_size=4, anchor="w"):
        font_size = size
        while font_size > min_size:
            font = tkfont.Font(family=family, size=font_size, weight=weight)
            if font.measure(text) <= max_width:
                break
            font_size -= 1
        self.draw_text(x, y, text=text, fill=fill, font=(family, font_size, weight), anchor=anchor)

    # ── Chrome (SrvSurvey-style tri-line stripe border + corner brackets) ──

    def _draw_chrome(self, accent=None, bracket_len=12):
        accent = accent or COLOR_ACCENT
        crt_enabled = self._crt_enabled()
        intensity = self._crt_intensity()
        step = {"Subtle": 4, "Standard": 3, "Strong": 2}[intensity]
        scanline = {"Subtle": "#070c11", "Standard": "#0a1117", "Strong": "#0d171e"}[intensity]
        overlay_chrome.draw_chrome(
            self.canvas, self.width, self.base_height, accent=accent,
            bracket_len=bracket_len, scanlines=crt_enabled,
            scanline_step=step, scanline_color=scanline,
        )
        if crt_enabled:
            overlay_chrome.draw_crt_vignette(self.canvas, self.width, self.base_height, intensity)
            overlay_chrome.draw_crt_noise(self.canvas, self.width, self.base_height, intensity)

    def _draw_stat(self, x, y, label, value, color=COLOR_TEXT, anchor="w", label_size=6, value_size=9, value_gap=13):
        self.draw_text(x, y, text=str(label).upper(), fill="#7d8891", font=("Courier", label_size, "bold"), anchor=anchor)
        self.draw_text(x, y + value_gap, text=str(value), fill=color, font=("Courier", value_size, "bold"), anchor=anchor)

    def _badge_color(self, state):
        if state == "alert":
            return COLOR_ORANGE
        if state == "ok":
            return COLOR_ACCENT
        return COLOR_MUTED

    _BADGE_GLYPHS = {"alert": "●", "ok": "✓", "muted": "○"}

    def _draw_badge(self, x, y, text, state="muted", height=18):
        color = self._badge_color(state)
        label = f"{self._BADGE_GLYPHS.get(state, '○')} {text}"
        font = tkfont.Font(family="Courier", size=8, weight="bold")
        text_w = font.measure(label)
        width = max(52, text_w + 16)
        cx, cy = x + width / 2, y + height / 2

        if self._crt_enabled():
            # Match the soft glow already used on chrome brackets and text so
            # badges read as part of the same lit display, not a flat overlay.
            glow_factor = 0.30 if self._crt_intensity() == "Subtle" else 0.42
            glow = self._glow_color(color, glow_factor)
            self.canvas.create_rectangle(x - 2, y - 2, x + width + 2, y + height + 2, outline=glow, width=3)

        if state == "alert":
            # Hazard-stripe treatment for genuine alerts (undiscovered, valuable, bio signals).
            self.canvas.create_rectangle(x, y, x + width, y + height, fill="#05080c", outline="")
            step = 6
            xx = x - height
            while xx < x + width:
                x0, x1 = max(x, xx), min(x + width, xx + height)
                if x1 > x0:
                    self.canvas.create_line(x0, y + height, x1, y, fill=color, width=1)
                xx += step
            # Clear a flat backdrop directly behind the text — otherwise the
            # stripes cross the letters and wreck legibility. Stripes stay
            # visible in the badge's margins/corners around the text.
            pad_x = 4
            self.canvas.create_rectangle(
                cx - text_w / 2 - pad_x, y + 2, cx + text_w / 2 + pad_x, y + height - 2,
                fill="#05080c", outline="",
            )
        elif state == "ok":
            # Backlit solid fill so a resolved/positive badge reads differently
            # from a plain empty outline at a glance.
            self.canvas.create_rectangle(x, y, x + width, y + height, fill=self._glow_color(color, 0.35), outline="")
        else:
            self.canvas.create_rectangle(x, y, x + width, y + height, fill="#05080c", outline="")
        self.canvas.create_rectangle(x, y, x + width, y + height, outline=color, width=1)
        self.draw_text(cx, cy, text=label, fill=color, font=("Courier", 8, "bold"), anchor="center")
        return width

    def _state_text(self, nav_context):
        flight_state = str(nav_context.get("flight_state") or "").upper()
        vehicle_name = str(nav_context.get("vehicle_name") or "").upper()
        music_mode = str(nav_context.get("music_mode") or "").upper()
        if flight_state in ("HYPERSPACE", "SUPERCRUISE", "JUMPING"):
            return flight_state
        if flight_state == "ONFOOT" or nav_context.get("on_foot") or music_mode == "ONFOOT":
            return "ONFOOT"
        if nav_context.get("docked") and nav_context.get("station"):
            return "DOCKED"
        if nav_context.get("in_fss"):
            return "FSS"
        if flight_state == "NOMAD" or vehicle_name == "NOMAD":
            return "NOMAD"
        if flight_state == "FIGHTER" or nav_context.get("in_fighter"):
            return "FIGHTER"
        if flight_state == "SRV" or nav_context.get("in_srv"):
            return "SRV"
        if flight_state == "LANDED" or nav_context.get("landed"):
            return "LANDED"
        if music_mode in ("MAP", "COMBAT", "EXPLORATION", "STATION"):
            return music_mode
        return "FLIGHT"

    def _state_color(self, state_text):
        if state_text in ("DOCKED", "LANDED", "FSS", "FIGHTER", "SRV", "NOMAD", "ONFOOT", "MAP", "EXPLORATION", "STATION"):
            return COLOR_ACCENT
        if state_text in ("HYPERSPACE", "SUPERCRUISE", "JUMPING", "COMBAT"):
            return COLOR_ORANGE
        return "#7d8891"

    def _route_header(self, nav_context, route_waypoint, route_counts, game_r_pos, remaining):
        """A single consolidated route-status string: what we're following, plus
        how far through it we are — replaces the old duplicated ROUTE/WAYPOINT
        footer and the separate GAME/ROUTE progress readout."""
        route_mode = str(nav_context.get("route_mode", "NO ROUTE"))
        if route_waypoint:
            label = route_waypoint.upper()
            color = COLOR_ORANGE
        else:
            label = route_mode
            color = COLOR_ORANGE if route_mode != "NO ROUTE" else "#7d8891"

        progress = ""
        if isinstance(remaining, int):
            progress = f"{remaining} JUMPS"
        elif route_counts and route_counts[1] > 0:
            pct = int(max(0.0, min(1.0, route_counts[0] / route_counts[1])) * 100)
            progress = f"{route_counts[0]}/{route_counts[1]} {pct}%"
        elif game_r_pos and game_r_pos[1] > 0:
            pct = int(max(0.0, min(1.0, game_r_pos[0] / game_r_pos[1])) * 100)
            progress = f"{game_r_pos[0]}/{game_r_pos[1]} {pct}%"

        if progress:
            label = f"{label}  ·  {progress}" if label else progress
        return label, color

    def _draw_route_strip(self, x1, x2, strip_y, nav_context, header_color, dot_radius):
        hops = nav_context.get("hops") or []
        if self._crt_enabled():
            glow = self._glow_color(header_color, 0.22 if self._crt_intensity() == "Subtle" else 0.32)
            self.canvas.create_line(x1, strip_y, x2, strip_y, fill=glow, width=5)
        self.canvas.create_line(x1, strip_y, x2, strip_y, fill="#1a2530", width=2)
        theme = {"accent": COLOR_ACCENT, "orange": COLOR_ORANGE}
        if hops:
            route_strip.draw_pip_line(self.canvas, x1, x2, strip_y, hops, theme, dot_radius=dot_radius, bg="#010101")
        self.canvas.create_oval(x1 - dot_radius - 1, strip_y - dot_radius - 1, x1 + dot_radius + 1, strip_y + dot_radius + 1,
                                 outline=COLOR_ACCENT, width=2, fill="#010101")
        dest_color = COLOR_ORANGE if hops else "#7d8891"
        return dest_color

    def _draw_compact(
        self,
        current_sys,
        scanned,
        total,
        r_pos,
        system_traffic,
        game_r_pos=None,
        route_waypoint=None,
        route_counts=None,
        nav_context=None,
    ):
        nav_context = nav_context or {}
        w = self.width
        current_display = nav_context.get("current") or current_sys or "---"
        state_text = self._state_text(nav_context)
        state_color = self._state_color(state_text)
        remaining = nav_context.get("route_remaining")

        pct = (scanned / total) if total > 0 else 0
        pct = max(0.0, min(1.0, pct))
        traffic_text = f"{system_traffic.get('day', 0)}/{system_traffic.get('week', 0)}/{system_traffic.get('total', 0)}"

        self._draw_chrome(bracket_len=10)
        self.draw_text(16, 14, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        self._draw_title_anim()
        self.canvas.create_line(16, 26, w - 16, 26, fill="#1a2530", width=1)

        self.draw_text(16, 36, text="CURRENT SYSTEM", fill="#7d8891", font=("Courier", 6, "bold"), anchor="w")
        self.draw_text(w - 16, 36, text="STATE", fill="#7d8891", font=("Courier", 6, "bold"), anchor="e")
        self.draw_fitted_text(16, 50, str(current_display).upper(), COLOR_TEXT, size=10, max_width=w - 160, anchor="w")
        self.draw_fitted_text(w - 16, 50, state_text, state_color, size=9, max_width=130, anchor="e")
        self.canvas.create_line(16, 58, w - 16, 58, fill="#1a2530", width=1)

        header_label, header_color = self._route_header(nav_context, route_waypoint, route_counts, game_r_pos, remaining)
        left_x, right_x = 16, w - 16
        strip_y = 82
        self.draw_fitted_text(left_x, 68, header_label, header_color, size=7, max_width=(right_x - left_x) - 80, anchor="w")
        dest_color = self._draw_route_strip(left_x, right_x, strip_y, nav_context, header_color, dot_radius=4)
        self.draw_text((left_x + right_x) // 2, 68, text=nav_context.get("next_distance", "--"), fill=dest_color, font=("Courier", 7, "bold"), anchor="center")
        total_dist_text = nav_context.get("total_distance_text")
        if total_dist_text:
            self.draw_text(right_x, 68, text=total_dist_text, fill=COLOR_ORANGE, font=("Courier", 7, "bold"), anchor="e")
        self.draw_text(left_x, 94, text="CURRENT", fill=COLOR_ACCENT, font=("Courier", 8, "bold"), anchor="w")
        self.draw_text(right_x, 94, text="DEST" if (nav_context.get("hops") or []) else "NEXT", fill=dest_color, font=("Courier", 8, "bold"), anchor="e")
        self.canvas.create_line(16, 102, w - 16, 102, fill="#1a2530", width=1)

        self.draw_text(16, 112, text="SCAN PROGRESS", fill="#7d8891", font=("Courier", 7, "bold"), anchor="w")
        self.draw_text(w - 16, 112, text=f"{scanned}/{total}  ·  {int(pct*100)}%", fill=COLOR_TEXT, font=("Courier", 8, "bold"), anchor="e")
        self.canvas.create_rectangle(16, 120, w - 16, 126, outline="#26313a", width=1)
        if pct > 0:
            self.canvas.create_rectangle(16, 120, 16 + ((w - 32) * pct), 126, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
        self.canvas.create_line(16, 134, w - 16, 134, fill="#1a2530", width=1)

        self.draw_text(16, 144, text=f"TRAFFIC {traffic_text}", fill="#7d8891", font=("Courier", 8, "bold"), anchor="w")

        badges = nav_context.get("badges", [])
        x = 16
        y = 154
        for badge, state in badges:
            bw = self._draw_badge(x, y, str(badge), state, height=16)
            x += bw + 5
            if x > w - 70:
                break

    def update(
        self,
        current_sys,
        dest_name,
        dist_ly,
        scanned,
        total,
        r_pos,
        system_traffic,
        game_r_pos=None,
        route_waypoint=None,
        route_counts=None,
        hud_status="OK",
        hud_health=None,
        nav_context=None,
    ):
        nav_context = nav_context or {}
        target_w, target_h = self._target_dimensions()
        self._ensure_dimensions(target_w, target_h)
        self.canvas.delete("all")
        if self._is_compact():
            self._draw_compact(
                current_sys,
                scanned,
                total,
                r_pos,
                system_traffic,
                game_r_pos=game_r_pos,
                route_waypoint=route_waypoint,
                route_counts=route_counts,
                nav_context=nav_context,
            )
            return

        w = self.width
        current_display = nav_context.get("current") or current_sys or "---"
        credits = nav_context.get("credits", "---")
        cargo = nav_context.get("cargo", "0T")
        trade_profit = nav_context.get("trade_profit", "---")
        state_text = self._state_text(nav_context)
        state_color = self._state_color(state_text)
        remaining = nav_context.get("route_remaining")
        t_day = system_traffic.get('day', 0)
        t_week = system_traffic.get('week', 0)
        t_total = system_traffic.get('total', 0)

        self._draw_chrome(bracket_len=14)
        self.draw_text(20, 18, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        self._draw_title_anim()
        self.canvas.create_line(20, 32, w - 20, 32, fill="#1a2530", width=1)

        # ── System / State ──────────────────────────────────────────────
        self._draw_stat(20, 44, "CURRENT SYSTEM", "", COLOR_TEXT)
        self.draw_text(w - 20, 44, text="STATE", fill="#7d8891", font=("Courier", 6, "bold"), anchor="e")
        self.draw_fitted_text(20, 60, str(current_display).upper(), COLOR_TEXT, size=13, max_width=w - 260, anchor="w")
        self.draw_fitted_text(w - 20, 60, state_text, state_color, size=11, max_width=200, anchor="e")
        self.canvas.create_line(20, 72, w - 20, 72, fill="#1a2530", width=1)

        # ── Stat grid ────────────────────────────────────────────────────
        col_xs = (20, 160, 300, 430)
        for x, label, value, color in (
            (col_xs[0], "CREDITS", str(credits), COLOR_ACCENT),
            (col_xs[1], "CARGO", str(cargo), COLOR_TEXT),
            (col_xs[2], "PROFIT", str(trade_profit), COLOR_ORANGE),
            (col_xs[3], "TRAFFIC", f"{t_day}/{t_week}/{t_total}", "#7d8891"),
        ):
            self._draw_stat(x, 84, label, value, color)
        self.canvas.create_line(20, 108, w - 20, 108, fill="#1a2530", width=1)

        # ── Route header + pip line ─────────────────────────────────────
        header_label, header_color = self._route_header(nav_context, route_waypoint, route_counts, game_r_pos, remaining)
        left_x, right_x = 20, w - 20
        strip_y = 136
        self.draw_fitted_text(left_x, 120, header_label, header_color, size=8, max_width=(right_x - left_x) * 0.4, anchor="w")
        dest_color = self._draw_route_strip(left_x, right_x, strip_y, nav_context, header_color, dot_radius=5)
        self.draw_text((left_x + right_x) // 2, 120, text=nav_context.get("next_distance", "--"), fill=dest_color, font=("Courier", 8, "bold"), anchor="center")
        total_dist_text = nav_context.get("total_distance_text")
        if total_dist_text:
            self.draw_text(right_x, 120, text=total_dist_text, fill=COLOR_ORANGE, font=("Courier", 8, "bold"), anchor="e")
        self.draw_text(left_x, 152, text="CURRENT", fill=COLOR_ACCENT, font=("Courier", 8, "bold"), anchor="w")
        self.draw_text(right_x, 152, text="DEST" if (nav_context.get("hops") or []) else "NEXT", fill=dest_color, font=("Courier", 8, "bold"), anchor="e")
        self.canvas.create_line(20, 162, w - 20, 162, fill="#1a2530", width=1)

        # ── Scan progress ────────────────────────────────────────────────
        pct = (scanned / total) if total > 0 else 0
        pct = max(0.0, min(1.0, pct))
        self.draw_text(20, 174, text="SCAN PROGRESS", fill="#7d8891", font=("Courier", 7, "bold"), anchor="w")
        self.draw_text(w - 20, 174, text=f"{scanned}/{total}  ·  {int(pct*100)}%", fill=COLOR_TEXT, font=("Courier", 8, "bold"), anchor="e")
        self.canvas.create_rectangle(20, 182, w - 20, 190, outline="#26313a", width=1)
        if pct > 0:
            self.canvas.create_rectangle(20, 182, 20 + ((w - 40) * pct), 190, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
        self.canvas.create_line(20, 200, w - 20, 200, fill="#1a2530", width=1)

        # ── Badges ───────────────────────────────────────────────────────
        x = 20
        for badge, state in nav_context.get("badges", []):
            bw = self._draw_badge(x, 208, str(badge), state)
            x += bw + 6
            if x > w - 60:
                break
