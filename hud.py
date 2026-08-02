import tkinter as tk
import tkinter.font as tkfont
import time
from config import (
    COLOR_ACCENT,
    COLOR_GREEN,
    COLOR_TEXT,
    COLOR_ORANGE,
    COLOR_MUTED,
    COLOR_YELLOW,
    save_config,
)
import overlay_chrome

class TacticalHUD:
    def __init__(self, root, config, on_widget_click=None):
        self.win = tk.Toplevel(root)
        self.config = config
        self.on_widget_click = on_widget_click

        overlay_bg = overlay_chrome.configure_overlay_window(self.win, "#ff00ff")

        self.full_width = 560
        self.full_height = 224
        self.compact_width = 450
        self.compact_height = 176
        self.width, self.base_height = self._target_dimensions()
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.base_height, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        x = self._safe_int(self.config.get("hud_x"), 100)
        y = self._safe_int(self.config.get("hud_y"), 100)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y, self.width, self.base_height))
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
        self._last_render_fingerprint = None
        self._anim_interval_ms = int(self.config.get("hud_anim_interval_ms", 100) or 100)
        if self._anim_interval_ms < 80:
            self._anim_interval_ms = 80
        self.animate_ui()

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(overlay_chrome.position_geometry(x, y, self.width, self.base_height))
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
            self.win.geometry(overlay_chrome.position_geometry(x, y, width, height))

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
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._desired_pos = (x, y)
        # Persist while dragging so release outside the canvas still keeps the new position.
        self.config["hud_x"] = x
        self.config["hud_y"] = y
        self._schedule_config_save()

    def save_final_pos(self, event=None):
        self.config["hud_x"] = self.win.winfo_x()
        self.config["hud_y"] = self.win.winfo_y()
        self._desired_pos = (self.config["hud_x"], self.config["hud_y"])
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
        font = overlay_chrome.scaled_font(font, self.config)
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
        if (not self._crt_enabled() or not self.config.get("hud_crt_motion_enabled", True)
                or self.config.get("reduced_motion_enabled", False)):
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

    def _draw_region_label(self, nav_context, x, y, max_width):
        """Draw the Codex region between the CURRENT SYSTEM and STATE labels.

        Shown in the label row's own dim styling so it reads as context, and
        lifted to the accent colour for a short spell after crossing into a new
        region — a rare event that would otherwise cost a badge slot.
        """
        region = (nav_context or {}).get("region") or {}
        name = str(region.get("name") or "").strip()
        if not name:
            return
        try:
            text = f"{int(region.get('id')):02d}  {name.upper()}"
        except (TypeError, ValueError):
            text = name.upper()
        crossed = bool(region.get("crossed"))
        self.draw_fitted_text(
            x, y, text,
            COLOR_ACCENT if crossed else "#7d8891",
            size=7, max_width=max(60, max_width), anchor="center",
        )

    def _badge_color(self, state):
        if state == "alert":
            return COLOR_ORANGE
        if state == "ok":
            return COLOR_GREEN
        if state == "info":
            return COLOR_YELLOW
        return COLOR_MUTED

    _BADGE_GLYPHS = {"alert": "●", "ok": "✓", "info": "◆", "muted": "○"}

    def _draw_badge(self, x, y, text, state="muted", height=18):
        color = self._badge_color(state)
        label = f"{self._BADGE_GLYPHS.get(state, '○')} {text}"
        font = tkfont.Font(family="Courier", size=9, weight="bold")
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
        if nav_context.get("docked"):
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

    def _draw_status_pill(self, right_x, center_y, text, color, height=16):
        """Draw a restrained state indicator that does not resemble a button."""
        label = str(text or "FLIGHT").upper()
        font = tkfont.Font(family="Courier", size=8, weight="bold")
        width = max(54, font.measure(label) + 16)
        left_x = right_x - width
        top_y = center_y - (height / 2)
        bottom_y = top_y + height
        self.canvas.create_rectangle(
            left_x, top_y, right_x, bottom_y,
            fill=self._glow_color(color, 0.18), outline=color, width=1,
        )
        self.draw_text(
            (left_x + right_x) / 2, center_y,
            text=label, fill=color, font=("Courier", 9, "bold"), anchor="center",
        )
        return width

    @staticmethod
    def _traffic_summary(system_traffic, compact=False):
        traffic = system_traffic or {}
        try:
            day = int(traffic.get("day", 0) or 0)
            week = int(traffic.get("week", 0) or 0)
            total = int(traffic.get("total", 0) or 0)
        except (TypeError, ValueError):
            day, week, total = 0, 0, 0
        if compact:
            return f"TRAFFIC {day} TODAY · {total} TOTAL"
        return f"TRAFFIC {day} TODAY · {week} THIS WEEK · {total} TOTAL"

    @staticmethod
    def _survey_summary(nav_context):
        context = nav_context or {}

        def _number(key):
            try:
                return max(0, int(context.get(key, 0) or 0))
            except (TypeError, ValueError):
                return 0

        dss = _number("dss_complete")
        bio_done = _number("bio_complete")
        bio_total = _number("bio_signals")
        geo_total = _number("geo_signals")
        return f"DSS {dss} · BIO {bio_done}/{bio_total} · GEO {geo_total}"

    @staticmethod
    def _route_presentation(nav_context, route_waypoint, route_counts, game_r_pos, r_pos):
        context = nav_context or {}
        source = str(context.get("route_mode") or "NO ROUTE").upper()
        target = str(route_waypoint or context.get("next") or "---").upper()
        remaining = context.get("route_remaining")
        hops = list(context.get("hops") or [])
        active = source != "NO ROUTE" and target not in ("", "---")
        progress = 0.0
        progress_text = ""

        if route_counts and len(route_counts) >= 2 and route_counts[1] > 0:
            done, total = max(0, int(route_counts[0])), max(1, int(route_counts[1]))
            progress = max(0.0, min(1.0, done / total))
            progress_text = f"{done}/{total} STOPS"
        elif game_r_pos and len(game_r_pos) >= 2 and game_r_pos[1] > 0:
            current_pos, total = max(1, int(game_r_pos[0])), max(1, int(game_r_pos[1]))
            denominator = max(1, total - 1)
            progress = max(0.0, min(1.0, (current_pos - 1) / denominator))

        if isinstance(remaining, int):
            jump_text = "ROUTE COMPLETE" if remaining <= 0 else f"{remaining} JUMP{'S' if remaining != 1 else ''}"
        elif hops:
            jump_text = f"{len(hops)}+ JUMPS" if context.get("hops_truncated") else f"{len(hops)} JUMP{'S' if len(hops) != 1 else ''}"
        else:
            jump_text = ""

        distance = ""
        if route_waypoint and r_pos and len(r_pos) >= 3:
            distance = str(r_pos[2] or "")
        if not distance:
            distance = str(context.get("next_distance") or "")
        if distance == "--":
            distance = ""

        meta_parts = [part for part in (jump_text, distance, progress_text) if part]
        if not active:
            source = "NO ACTIVE ROUTE"
            target = "NO DESTINATION PLOTTED"
            meta_parts = []
        return {
            "source": source,
            "target": target,
            "meta": " · ".join(meta_parts),
            "progress": progress,
            "active": active,
            "hops": hops,
        }

    def _draw_progress_track(self, x1, x2, top_y, pct, fill):
        pct = max(0.0, min(1.0, float(pct or 0.0)))
        self.canvas.create_rectangle(x1, top_y, x2, top_y + 7, outline="#26313a", width=1)
        if pct > 0:
            end_x = x1 + ((x2 - x1) * pct)
            self.canvas.create_rectangle(x1, top_y, end_x, top_y + 7, fill=fill, outline=fill)

    def _draw_route_track(self, x1, x2, y, route):
        active = bool(route.get("active"))
        progress = max(0.0, min(1.0, float(route.get("progress") or 0.0)))
        base_color = "#26313a"
        self.canvas.create_line(x1, y, x2, y, fill=base_color, width=2)
        if not active:
            self.canvas.create_oval(x1 - 3, y - 3, x1 + 3, y + 3, outline="#7d8891", width=1)
            return

        current_x = x1 + ((x2 - x1) * progress)
        if current_x > x1:
            self.canvas.create_line(x1, y, current_x, y, fill=COLOR_ACCENT, width=3)
        self.canvas.create_oval(current_x - 4, y - 4, current_x + 4, y + 4,
                                fill="#010101", outline=COLOR_ACCENT, width=2)

        # One quiet beacon indicates the immediate leg without recreating the
        # dense pip chain that previously dominated this small overlay.
        hops = route.get("hops") or []
        if hops and progress < 1.0:
            remaining_span = max(1.0, x2 - current_x)
            next_x = current_x + (remaining_span / max(2, min(8, len(hops) + 1)))
            self.canvas.create_line(next_x, y - 4, next_x, y + 4, fill=COLOR_ACCENT, width=2)

        self.canvas.create_polygon(
            x2, y - 5, x2 + 5, y, x2, y + 5, x2 - 5, y,
            fill="#010101", outline=COLOR_ORANGE, width=2,
        )

    @staticmethod
    def _attention_summary(nav_context):
        labels = []
        state = "muted"
        for label, badge_state in (nav_context or {}).get("badges", []):
            label = str(label or "").strip().upper()
            if (not label or label in {"FSS", "DOCKED", "CLEAR"}
                    or label.startswith("BIO ")):
                continue
            labels.append(label)
            if badge_state == "alert":
                state = "alert"
            elif badge_state == "info" and state != "alert":
                state = "info"
            elif badge_state == "ok" and state == "muted":
                state = "ok"
        return " · ".join(labels[:3]), state

    @staticmethod
    def _scan_progress_state(scanned, total, nav_context):
        if nav_context.get("scan_progress_source") == "unknown":
            return 0.0, f"{scanned}/?  ·  --%"
        body_pct = (scanned / total) if total > 0 else 0.0
        body_pct = max(0.0, min(1.0, body_pct))
        if nav_context.get("scan_progress_source") != "fss":
            return body_pct, f"{scanned}/{total}  ·  {int(body_pct * 100)}%"
        try:
            live_pct = float(nav_context.get("scan_progress"))
        except (TypeError, ValueError):
            return body_pct, f"{scanned}/{total}  ·  {int(body_pct * 100)}%"
        live_pct = max(body_pct, min(1.0, max(0.0, live_pct)))
        return live_pct, f"{scanned}/{total}  ·  FSS {int(live_pct * 100)}%"

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
        pct, scan_progress_text = self._scan_progress_state(scanned, total, nav_context)
        scan_color = COLOR_GREEN if pct >= 1.0 and total > 0 else COLOR_ACCENT
        route = self._route_presentation(nav_context, route_waypoint, route_counts, game_r_pos, r_pos)
        survey_text = self._survey_summary(nav_context)
        traffic_text = self._traffic_summary(system_traffic, compact=True)
        attention_text, attention_state = self._attention_summary(nav_context)

        self._draw_chrome(bracket_len=10)
        self.draw_text(16, 14, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 11, "bold"), anchor="w")
        self._draw_title_anim()
        self.canvas.create_line(16, 26, w - 16, 26, fill="#1a2530", width=1)

        # System / state
        self.draw_text(16, 35, text="CURRENT SYSTEM", fill="#7d8891", font=("Courier", 7, "bold"), anchor="w")
        self.draw_text(w - 16, 35, text="STATE", fill="#7d8891", font=("Courier", 7, "bold"), anchor="e")
        self._draw_region_label(nav_context, (16 + (w - 16)) // 2, 35, max_width=w - 210)
        pill_width = self._draw_status_pill(w - 16, 49, state_text, state_color, height=16)
        self.draw_fitted_text(
            16, 49, str(current_display).upper(), COLOR_TEXT,
            size=11, max_width=w - pill_width - 52, anchor="w",
        )
        self.canvas.create_line(16, 60, w - 16, 60, fill="#1a2530", width=1)

        # Route
        left_x, right_x = 16, w - 16
        self.draw_text(left_x, 69, text=route["source"], fill=COLOR_ORANGE if route["active"] else "#7d8891",
                       font=("Courier", 7, "bold"), anchor="w")
        self.draw_fitted_text(right_x, 69, route["meta"], COLOR_ORANGE, size=7,
                              max_width=190, anchor="e")
        self.draw_fitted_text(left_x, 82, route["target"], COLOR_TEXT if route["active"] else "#7d8891",
                              size=9, max_width=w - 32, anchor="w")
        self._draw_route_track(left_x, right_x - 5, 98, route)
        self.canvas.create_line(16, 106, w - 16, 106, fill="#1a2530", width=1)

        # Survey progress remains permanently visible, including on known systems.
        self.draw_text(16, 116, text="SYSTEM SURVEY", fill="#7d8891", font=("Courier", 8, "bold"), anchor="w")
        self.draw_text(w - 16, 116, text=scan_progress_text, fill=scan_color,
                       font=("Courier", 9, "bold"), anchor="e")
        self._draw_progress_track(16, w - 16, 124, pct, scan_color)
        self.draw_fitted_text(16, 143, survey_text, COLOR_TEXT, size=7, min_size=6, max_width=235, anchor="w")
        self.draw_fitted_text(w - 16, 143, traffic_text, "#7d8891", size=7, min_size=6, max_width=185, anchor="e")

        if attention_text:
            attention_color = self._badge_color(attention_state)
            self.draw_fitted_text(16, 161, attention_text, attention_color, size=8, min_size=7, max_width=w - 32, anchor="w")
        elif nav_context.get("docked") and nav_context.get("station"):
            self.draw_fitted_text(16, 161, f"STATION · {nav_context['station']}", COLOR_ACCENT,
                                  size=8, min_size=7, max_width=w - 32, anchor="w")

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
        render_fingerprint = repr((
            target_w, target_h, current_sys, dest_name, dist_ly, scanned, total,
            r_pos, system_traffic, game_r_pos, route_waypoint, route_counts,
            hud_status, hud_health, nav_context,
        ))
        if render_fingerprint == self._last_render_fingerprint and self.canvas.find_all():
            return
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
            self._last_render_fingerprint = render_fingerprint
            return

        w = self.width
        current_display = nav_context.get("current") or current_sys or "---"
        state_text = self._state_text(nav_context)
        state_color = self._state_color(state_text)
        route = self._route_presentation(nav_context, route_waypoint, route_counts, game_r_pos, r_pos)
        pct, scan_progress_text = self._scan_progress_state(scanned, total, nav_context)
        scan_color = COLOR_GREEN if pct >= 1.0 and total > 0 else COLOR_ACCENT
        survey_text = self._survey_summary(nav_context)
        traffic_text = self._traffic_summary(system_traffic)
        attention_text, attention_state = self._attention_summary(nav_context)

        self._draw_chrome(bracket_len=14)
        self.draw_text(20, 18, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 11, "bold"), anchor="w")
        self._draw_title_anim()
        self.canvas.create_line(20, 32, w - 20, 32, fill="#1a2530", width=1)

        # ── System / State ──────────────────────────────────────────────
        self.draw_text(20, 44, text="CURRENT SYSTEM", fill="#7d8891", font=("Courier", 7, "bold"), anchor="w")
        self.draw_text(w - 20, 44, text="STATE", fill="#7d8891", font=("Courier", 7, "bold"), anchor="e")
        self._draw_region_label(nav_context, (20 + (w - 20)) // 2, 44, max_width=w - 220)
        pill_width = self._draw_status_pill(w - 20, 60, state_text, state_color, height=18)
        self.draw_fitted_text(20, 60, str(current_display).upper(), COLOR_TEXT, size=13,
                              max_width=w - pill_width - 70, anchor="w")
        self.canvas.create_line(20, 72, w - 20, 72, fill="#1a2530", width=1)

        # ── Route ────────────────────────────────────────────────────────
        left_x, right_x = 20, w - 20
        self.draw_text(left_x, 84, text=route["source"], fill=COLOR_ORANGE if route["active"] else "#7d8891",
                       font=("Courier", 8, "bold"), anchor="w")
        self.draw_fitted_text(right_x, 84, route["meta"], COLOR_ORANGE, size=8,
                              max_width=270, anchor="e")
        self.draw_fitted_text(left_x, 101, route["target"], COLOR_TEXT if route["active"] else "#7d8891",
                              size=12, max_width=w - 40, anchor="w")
        self._draw_route_track(left_x, right_x - 5, 118, route)
        self.canvas.create_line(20, 130, w - 20, 130, fill="#1a2530", width=1)

        # ── Survey ───────────────────────────────────────────────────────
        self.draw_text(20, 143, text="SYSTEM SURVEY", fill="#7d8891", font=("Courier", 8, "bold"), anchor="w")
        self.draw_text(w - 20, 143, text=scan_progress_text, fill=scan_color,
                       font=("Courier", 10, "bold"), anchor="e")
        self._draw_progress_track(20, w - 20, 152, pct, scan_color)
        self.draw_fitted_text(20, 174, survey_text, COLOR_TEXT, size=9, min_size=7, max_width=315, anchor="w")
        self.draw_fitted_text(w - 20, 174, traffic_text, "#7d8891", size=8, min_size=7, max_width=215, anchor="e")
        self.canvas.create_line(20, 190, w - 20, 190, fill="#1a2530", width=1)

        # ── Context / attention ──────────────────────────────────────────
        context_detail = ""
        if nav_context.get("docked") and nav_context.get("station"):
            context_detail = f"STATION · {nav_context['station']}"
        elif nav_context.get("body"):
            context_detail = f"BODY · {nav_context['body']}"
        if context_detail:
            self.draw_fitted_text(20, 208, context_detail, COLOR_ACCENT, size=9,
                                  max_width=310, anchor="w")
        elif attention_text:
            self.draw_fitted_text(20, 208, attention_text, self._badge_color(attention_state),
                                  size=9, max_width=310, anchor="w")

        if context_detail and attention_text:
            self.draw_fitted_text(w - 20, 208, attention_text, self._badge_color(attention_state),
                                  size=9, max_width=210, anchor="e")
        elif not context_detail and not attention_text:
            self.draw_text(20, 208, text="NAVIGATION NOMINAL", fill="#7d8891",
                           font=("Courier", 9, "bold"), anchor="w")
        self._last_render_fingerprint = render_fingerprint
