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
import route_strip

class TacticalHUD:
    MIN_READABLE_FONT = 9

    def __init__(self, root, config, on_widget_click=None):
        self.win = tk.Toplevel(root)
        self.config = config
        self.on_widget_click = on_widget_click

        overlay_bg = overlay_chrome.configure_overlay_window(self.win, "#ff00ff")

        self.full_width = 620
        self.full_height = 286
        self.compact_width = 500
        self.compact_height = 238
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
        self._last_update_args = None
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

    def _text_scale_percent(self):
        try:
            return max(75, min(200, int(float(self.config.get("overlay_text_scale_percent", 100)))))
        except (TypeError, ValueError):
            return 100

    def _readable_font(self, font):
        """Scale a HUD font without ever rendering unreadably small text."""
        scaled = overlay_chrome.scaled_font(font, self.config)
        if not isinstance(scaled, (tuple, list)) or len(scaled) < 2:
            return scaled
        try:
            size = int(scaled[1])
        except (TypeError, ValueError):
            return scaled
        sign = -1 if size < 0 else 1
        size = sign * max(self.MIN_READABLE_FONT, abs(size))
        return tuple([scaled[0], size, *scaled[2:]])

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
        font = self._readable_font(font)
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
        x = getattr(self, "_title_anim_x", 170)
        y = getattr(self, "_title_anim_y", 17)
        self.draw_text(x, y, text=frame, fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e", tags="anim_title")

    @staticmethod
    def _ellipsize(text, font, max_width):
        text = str(text or "")
        if font.measure(text) <= max_width:
            return text
        suffix = "…"
        if font.measure(suffix) > max_width:
            return ""
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if font.measure(text[:mid] + suffix) <= max_width:
                low = mid
            else:
                high = mid - 1
        return text[:low].rstrip() + suffix

    def draw_fitted_text(self, x, y, text, fill, family="Courier", size=9, weight="bold", max_width=300, min_size=8, anchor="w"):
        text = str(text or "")
        min_size = max(self.MIN_READABLE_FONT, int(min_size or self.MIN_READABLE_FONT))
        font_size = size
        while font_size > min_size:
            rendered = self._readable_font((family, font_size, weight))
            font = tkfont.Font(family=rendered[0], size=rendered[1], weight=weight)
            if font.measure(text) <= max_width:
                break
            font_size -= 1
        rendered = self._readable_font((family, font_size, weight))
        font = tkfont.Font(family=rendered[0], size=rendered[1], weight=weight)
        display_text = self._ellipsize(text, font, max_width)
        self.draw_text(x, y, text=display_text, fill=fill, font=(family, font_size, weight), anchor=anchor)

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
            size=9, min_size=9, max_width=max(60, max_width), anchor="center",
        )

    def _draw_section_rule(self, x1, x2, y, accent=None):
        """Separate HUD instruments with one lit index and a quiet baseline."""
        accent = accent or COLOR_ACCENT
        dim = self._glow_color(accent, 0.34)
        self.canvas.create_line(x1, y, x1 + 18, y, fill=dim, width=4)
        self.canvas.create_line(x1, y, x1 + 18, y, fill=accent, width=1)
        self.canvas.create_polygon(
            x1 + 18, y - 3, x1 + 24, y, x1 + 18, y + 3,
            fill="#010101", outline=dim, width=1,
        )
        self.canvas.create_line(x1 + 27, y, x2, y, fill="#1a2530", width=1)

    def _draw_locator_rail(self, x, y1, y2, color=None):
        """Small illuminated rail used to anchor the current-system block."""
        color = color or COLOR_ACCENT
        glow = self._glow_color(color, 0.28)
        self.canvas.create_line(x, y1, x, y2, fill=glow, width=5)
        self.canvas.create_line(x, y1, x, y2, fill=color, width=1)
        self.canvas.create_polygon(
            x, y1 - 3, x + 3, y1, x, y1 + 3, x - 3, y1,
            fill="#010101", outline=color, width=1,
        )

    def _draw_metric_cells(self, cells, label_y, value_y):
        """Draw open cockpit instruments without adding boxed visual clutter."""
        for x1, x2, label, value, color in cells:
            rail_color = color if color != "#7d8891" else COLOR_ACCENT
            self.canvas.create_line(
                x1, label_y - 6, x1, value_y + 7,
                fill=self._glow_color(rail_color, 0.42), width=3,
            )
            self.canvas.create_line(
                x1, label_y - 4, x1, value_y + 5,
                fill=rail_color, width=1,
            )
            self.draw_fitted_text(
                x1 + 9, label_y, label, "#85939d",
                size=10, min_size=9, max_width=max(30, x2 - x1 - 13), anchor="w",
            )
            self.draw_fitted_text(
                x1 + 9, value_y, value, color,
                size=13, min_size=10, max_width=max(30, x2 - x1 - 13), anchor="w",
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
        rendered = self._readable_font(("Courier", 9, "bold"))
        font = tkfont.Font(family=rendered[0], size=rendered[1], weight="bold")
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
        self.draw_text(cx, cy, text=label, fill=color, font=("Courier", 9, "bold"), anchor="center")
        return width

    def _state_text(self, nav_context):
        flight_state = str(nav_context.get("flight_state") or "").upper()
        vehicle_name = str(nav_context.get("vehicle_name") or "").upper()
        music_mode = str(nav_context.get("music_mode") or "").upper()
        music_track = str(nav_context.get("music_track") or "")

        # A jump is the only physical state that outranks a focused cockpit
        # screen. Maps and scanners otherwise describe what the commander is
        # actively using, even while the ship remains in supercruise.
        if flight_state in ("HYPERSPACE", "JUMPING"):
            return flight_state

        focus_key = (
            str(nav_context.get("gui_focus", ""))
            .replace(" ", "").replace("_", "").upper()
        )
        track_key = music_track.replace(" ", "").replace("_", "").upper()
        focus_labels = {
            "6": "GALAXY MAP",
            "GALAXYMAP": "GALAXY MAP",
            "7": "SYSTEM MAP",
            "SYSTEMMAP": "SYSTEM MAP",
            "8": "ORRERY",
            "ORRERY": "ORRERY",
            "9": "FSS",
            "FSS": "FSS",
            "10": "DSS",
            "SAA": "DSS",
            "SURFACEANALYSIS": "DSS",
            "11": "CODEX",
            "CODEX": "CODEX",
        }
        # The journal gives the exact map name during a direct map-to-map
        # transition; Status.json remains the fallback if that event is late.
        focused_state = focus_labels.get(track_key) or focus_labels.get(focus_key)
        if focused_state:
            return focused_state
        if track_key == "GALACTICPOWERS":
            return "POWER MAP"
        if music_mode == "MAP":
            return "MAP"
        if nav_context.get("in_fss"):
            return "FSS"
        if flight_state == "ONFOOT" or nav_context.get("on_foot") or music_mode == "ONFOOT":
            return "ONFOOT"
        if nav_context.get("docked"):
            return "DOCKED"
        if flight_state == "NOMAD" or vehicle_name == "NOMAD":
            return "NOMAD"
        if flight_state == "FIGHTER" or nav_context.get("in_fighter"):
            return "FIGHTER"
        if flight_state == "SRV" or nav_context.get("in_srv"):
            return "SRV"
        if flight_state == "LANDED" or nav_context.get("landed"):
            return "LANDED"
        if flight_state == "SUPERCRUISE":
            return "SUPERCRUISE"
        if music_mode in ("MAP", "COMBAT", "EXPLORATION", "STATION"):
            return music_mode
        return "FLIGHT"

    def _state_color(self, state_text):
        if state_text in (
            "DOCKED", "LANDED", "FSS", "DSS", "FIGHTER", "SRV", "NOMAD",
            "ONFOOT", "MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY",
            "CODEX", "EXPLORATION", "STATION",
        ):
            return COLOR_ACCENT
        if state_text in ("HYPERSPACE", "SUPERCRUISE", "JUMPING", "COMBAT"):
            return COLOR_ORANGE
        return "#7d8891"

    def _draw_status_beacon(self, center_x, center_y, text, color):
        """Draw the active flight mode as an integrated cockpit beacon."""
        label = str(text or "FLIGHT").upper()
        rendered = self._readable_font(("Courier", 10, "bold"))
        font = tkfont.Font(family=rendered[0], size=rendered[1], weight="bold")
        half_width = max(48, font.measure(label) / 2 + 16)
        left_edge = center_x - half_width
        right_edge = center_x + half_width
        top = center_y - 10
        bottom = center_y + 10
        chamfer = 7
        line_span = 17
        glow = self._glow_color(color, 0.28)

        plate = (
            left_edge + chamfer, top,
            right_edge - chamfer, top,
            right_edge, center_y,
            right_edge - chamfer, bottom,
            left_edge + chamfer, bottom,
            left_edge, center_y,
        )
        self.canvas.create_polygon(plate, fill="#03070a", outline=glow, width=3)
        self.canvas.create_polygon(plate, fill="#03070a", outline=color, width=1)
        self.canvas.create_line(
            left_edge - line_span, center_y, left_edge - 3, center_y,
            fill=glow, width=3,
        )
        self.canvas.create_line(
            right_edge + 3, center_y, right_edge + line_span, center_y,
            fill=glow, width=3,
        )
        self.canvas.create_line(
            left_edge - line_span, center_y, left_edge - 3, center_y,
            fill=color, width=1,
        )
        self.canvas.create_line(
            right_edge + 3, center_y, right_edge + line_span, center_y,
            fill=color, width=1,
        )
        for marker_x in (left_edge - line_span, right_edge + line_span):
            self.canvas.create_polygon(
                marker_x, center_y - 3, marker_x + 3, center_y,
                marker_x, center_y + 3, marker_x - 3, center_y,
                fill="#010101", outline=color, width=1,
            )
        self.draw_text(center_x, center_y, text=label, fill=color,
                       font=("Courier", 10, "bold"), anchor="center")
        return (right_edge + line_span) - (left_edge - line_span)

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
            return f"TRAFFIC {day}/{week}/{total}"
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
    def _survey_metrics(nav_context):
        context = nav_context or {}

        def _number(key):
            try:
                return max(0, int(context.get(key, 0) or 0))
            except (TypeError, ValueError):
                return 0

        fuel_percent = context.get("fuel_percent")
        try:
            fuel_percent = max(0, min(100, int(round(float(fuel_percent)))))
        except (TypeError, ValueError):
            fuel_percent = None
        fuel_color = COLOR_GREEN if fuel_percent is not None and fuel_percent > 40 else (
            COLOR_YELLOW if fuel_percent is not None and fuel_percent > 15 else (
                COLOR_ORANGE if fuel_percent is not None else "#7d8891"
            )
        )
        bio_done = _number("bio_complete")
        bio_total = _number("bio_signals")
        bio_color = COLOR_GREEN if bio_total > 0 and bio_done >= bio_total else (
            COLOR_ORANGE if bio_total > 0 else "#7d8891"
        )
        return (
            ("FUEL", f"{fuel_percent}%" if fuel_percent is not None else "--", fuel_color),
            ("BIO", f"{bio_done}/{bio_total}", bio_color),
            ("GEO", str(_number("geo_signals")), COLOR_YELLOW),
        )

    def _draw_inline_metrics(self, left_x, right_x, y, metrics, value_size=11):
        """Draw open, unboxed FUEL/BIO/GEO readouts in three stable columns."""
        column_width = (right_x - left_x) / 3
        for index, (label, value, color) in enumerate(metrics):
            x1 = left_x + index * column_width
            x2 = x1 + column_width
            self.canvas.create_line(
                x1, y - 8, x1, y + 8,
                fill=self._glow_color(color, 0.42), width=3,
            )
            self.canvas.create_line(x1, y - 7, x1, y + 7, fill=color, width=1)
            self.draw_text(x1 + 8, y, text=label, fill="#85939d",
                           font=("Courier", 10, "bold"), anchor="w")
            self.draw_text(x2 - 9, y, text=value, fill=color,
                           font=("Courier", value_size, "bold"), anchor="e")

    @staticmethod
    def _context_presentation(nav_context, attention_text="", attention_state="muted"):
        """Choose the single most useful contextual line for the current state."""
        context = nav_context or {}
        if context.get("docked") and context.get("station"):
            return f"STATION · {context['station']}", COLOR_ACCENT
        body = str(context.get("body") or "").strip()
        if body:
            gravity = context.get("gravity_g")
            try:
                gravity_text = f" · {float(gravity):.2f} G" if gravity is not None else ""
            except (TypeError, ValueError):
                gravity_text = ""
            return f"BODY · {body}{gravity_text}", COLOR_ACCENT
        if context.get("on_foot") or context.get("landed") or context.get("in_srv"):
            lat, lon = context.get("latitude"), context.get("longitude")
            try:
                return f"SURFACE · {float(lat):.3f}, {float(lon):.3f}", COLOR_ACCENT
            except (TypeError, ValueError):
                return "SURFACE OPERATIONS", COLOR_ACCENT
        if attention_text:
            return attention_text, COLOR_ORANGE if attention_state == "alert" else COLOR_YELLOW
        return "", "#7d8891"

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
            "jump_text": jump_text,
            "distance": distance,
            "progress_text": progress_text,
            "progress": progress,
            "active": active,
            "hops": hops,
        }

    @staticmethod
    def _classic_route_header_parts(route, nav_context, route_waypoint=False):
        """Split route data across the original left/centre/right header."""
        if not route.get("active"):
            return "NO ACTIVE ROUTE", "", ""
        if route_waypoint:
            left_parts = (route.get("target"), route.get("progress_text"))
        else:
            left_parts = (route.get("source"), route.get("jump_text"))
        left = " · ".join(str(part) for part in left_parts if part)
        center = str((nav_context or {}).get("next_distance") or "")
        if center == "--":
            center = ""
        right = str(route.get("distance") or (nav_context or {}).get("total_distance_text") or "")
        if right == center:
            right = ""
        return left, center, right

    def _draw_progress_track(self, x1, x2, top_y, pct, fill):
        pct = max(0.0, min(1.0, float(pct or 0.0)))
        bottom_y = top_y + 8
        self.canvas.create_rectangle(
            x1, top_y, x2, bottom_y,
            fill="#061016", outline="#26313a", width=1,
        )
        for fraction in (0.25, 0.5, 0.75):
            tick_x = x1 + ((x2 - x1) * fraction)
            self.canvas.create_line(tick_x, top_y + 2, tick_x, bottom_y - 1,
                                    fill="#17242d", width=1)
        if pct > 0:
            end_x = x1 + ((x2 - x1) * pct)
            glow = self._glow_color(fill, 0.34)
            self.canvas.create_rectangle(
                x1 + 1, top_y + 1, end_x, bottom_y - 1,
                fill=glow, outline="",
            )
            self.canvas.create_line(x1 + 1, top_y + 3, end_x, top_y + 3,
                                    fill=fill, width=2)
            self.canvas.create_line(end_x, top_y - 1, end_x, bottom_y + 1,
                                    fill=fill, width=2)

    def _draw_route_track(self, x1, x2, y, route, dot_radius=4):
        """Draw the original distance-proportional upcoming-hop pip strip."""
        active = bool(route.get("active"))
        color = COLOR_ORANGE if active else "#7d8891"
        if self._crt_enabled():
            glow = self._glow_color(color, 0.22 if self._crt_intensity() == "Subtle" else 0.32)
            self.canvas.create_line(x1, y, x2, y, fill=glow, width=5)
        self.canvas.create_line(x1, y, x2, y, fill="#1a2530", width=2)

        hops = list(route.get("hops") or [])
        if hops:
            route_strip.draw_pip_line(
                self.canvas, x1, x2, y, hops,
                {"accent": COLOR_ACCENT, "orange": COLOR_ORANGE},
                dot_radius=dot_radius, bg="#010101",
            )
        elif active:
            self.canvas.create_line(x1, y, x2, y, fill=COLOR_ORANGE, width=2, dash=(4, 3))
            self.canvas.create_polygon(
                x2, y - 5, x2 + 5, y, x2, y + 5, x2 - 5, y,
                fill="#010101", outline=COLOR_ORANGE, width=2,
            )

        # The commander remains the cyan origin, just as in the original HUD.
        self.canvas.create_oval(
            x1 - dot_radius - 1, y - dot_radius - 1,
            x1 + dot_radius + 1, y + dot_radius + 1,
            outline=COLOR_ACCENT if active else "#7d8891", width=2, fill="#010101",
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
        return (labels[0] if labels else ""), state

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
        route_header, next_distance, route_distance = self._classic_route_header_parts(
            route, nav_context, route_waypoint=bool(route_waypoint),
        )
        survey_metrics = self._survey_metrics(nav_context)
        traffic_text = self._traffic_summary(system_traffic, compact=True)
        attention_text, attention_state = self._attention_summary(nav_context)
        context_text, context_color = self._context_presentation(
            nav_context, attention_text, attention_state,
        )

        self._draw_chrome(bracket_len=11)
        self._title_anim_x, self._title_anim_y = w - 16, 17
        self.draw_text(16, 17, text="NAVIGATION HUD", fill=COLOR_ACCENT,
                       font=("Courier", 11, "bold"), anchor="w")
        self._draw_title_anim()
        self._draw_status_beacon(w / 2, 17, state_text, state_color)
        self._draw_section_rule(16, w - 16, 34)

        # The current system is the primary landmark, held by a lit locator rail.
        self._draw_locator_rail(17, 47, 70)
        self.draw_text(27, 47, text="CURRENT SYSTEM", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self._draw_region_label(nav_context, 325, 47, max_width=270)
        self.draw_fitted_text(
            27, 66, str(current_display).upper(), COLOR_TEXT,
            size=14, min_size=11, max_width=w - 43, anchor="w",
        )
        self._draw_section_rule(16, w - 16, 79)

        # Original split route header: target/status, next leg, total distance.
        left_x, right_x = 16, w - 16
        route_color = COLOR_ORANGE if route["active"] else "#7d8891"
        self.draw_fitted_text(left_x, 95, route_header, route_color,
                              size=10, min_size=9, max_width=215, anchor="w")
        self.draw_fitted_text(w / 2, 95, next_distance, route_color,
                              size=10, min_size=9, max_width=90, anchor="center")
        self.draw_fitted_text(right_x, 95, route_distance, COLOR_ORANGE,
                              size=10, min_size=9, max_width=175, anchor="e")
        self._draw_route_track(left_x, right_x, 113, route, dot_radius=4)
        self.draw_text(left_x, 130, text="CURRENT", fill=COLOR_ACCENT,
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(right_x, 130, text="DEST" if route["active"] else "NEXT", fill=route_color,
                       font=("Courier", 10, "bold"), anchor="e")
        self._draw_section_rule(16, w - 16, 141)

        # Original scan block, retaining the newer accurate survey state.
        self.draw_text(16, 157, text="SYSTEM SURVEY", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(w - 16, 157, text=scan_progress_text, fill=scan_color,
                       font=("Courier", 12, "bold"), anchor="e")
        self._draw_progress_track(16, w - 16, 169, pct, scan_color)
        self._draw_section_rule(16, w - 16, 184)

        self._draw_inline_metrics(16, w - 16, 199, survey_metrics, value_size=12)

        context_display = f"◆  {context_text}" if context_text else ""
        self.draw_fitted_text(16, 222, context_display, context_color,
                              size=10, min_size=9, max_width=w - 32 - 142, anchor="w")
        self.draw_fitted_text(w - 16, 222, traffic_text, "#7d8891",
                              size=10, min_size=9, max_width=136, anchor="e")

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
        self._last_update_args = (
            current_sys, dest_name, dist_ly, scanned, total, r_pos,
            system_traffic, game_r_pos, route_waypoint, route_counts,
            hud_status, hud_health, nav_context,
        )
        target_w, target_h = self._target_dimensions()
        presentation = (
            self._text_scale_percent(), self._crt_enabled(), self._crt_intensity(),
            bool(self.config.get("hud_crt_motion_enabled", True)),
        )
        render_fingerprint = repr((
            target_w, target_h, current_sys, dest_name, dist_ly, scanned, total,
            r_pos, system_traffic, game_r_pos, route_waypoint, route_counts,
            hud_status, hud_health, nav_context, presentation,
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
        route_header, next_distance, route_distance = self._classic_route_header_parts(
            route, nav_context, route_waypoint=bool(route_waypoint),
        )
        pct, scan_progress_text = self._scan_progress_state(scanned, total, nav_context)
        scan_color = COLOR_GREEN if pct >= 1.0 and total > 0 else COLOR_ACCENT
        survey_metrics = self._survey_metrics(nav_context)
        traffic_text = self._traffic_summary(system_traffic)
        attention_text, attention_state = self._attention_summary(nav_context)
        context_text, context_color = self._context_presentation(
            nav_context, attention_text, attention_state,
        )

        self._draw_chrome(bracket_len=15)
        self._title_anim_x, self._title_anim_y = w - 20, 19
        self.draw_text(20, 19, text="NAVIGATION HUD", fill=COLOR_ACCENT,
                       font=("Courier", 12, "bold"), anchor="w")
        self._draw_title_anim()
        self._draw_status_beacon(w / 2, 19, state_text, state_color)
        self._draw_section_rule(20, w - 20, 37)

        # Original system block, now anchored as the display's primary landmark.
        self._draw_locator_rail(21, 52, 76)
        self.draw_text(32, 52, text="CURRENT SYSTEM", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self._draw_region_label(nav_context, 445, 52, max_width=270)
        self.draw_fitted_text(32, 71, str(current_display).upper(), COLOR_TEXT,
                              size=16, min_size=12, max_width=w - 54, anchor="w")
        self._draw_section_rule(20, w - 20, 84)

        # Fuel stays immediately visible; traffic keeps the far-right day/week/total slot.
        compact_traffic = " / ".join(str(int((system_traffic or {}).get(key, 0) or 0))
                                     for key in ("day", "week", "total"))
        metric_cells = (
            (20, 165, "FUEL", survey_metrics[0][1], survey_metrics[0][2]),
            (170, 315, "BIO", survey_metrics[1][1], survey_metrics[1][2]),
            (320, 465, "GEO", survey_metrics[2][1], survey_metrics[2][2]),
            (470, w - 20, "TRAFFIC D/W/T", compact_traffic, "#7d8891"),
        )
        self._draw_metric_cells(metric_cells, 99, 116)
        self._draw_section_rule(20, w - 20, 130)

        # Original left/centre/right route header and real upcoming-hop pip strip.
        left_x, right_x = 20, w - 20
        route_color = COLOR_ORANGE if route["active"] else "#7d8891"
        self.draw_fitted_text(left_x, 147, route_header, route_color,
                              size=10, min_size=9, max_width=250, anchor="w")
        self.draw_fitted_text(w / 2, 147, next_distance, route_color,
                              size=10, min_size=9, max_width=110, anchor="center")
        self.draw_fitted_text(right_x, 147, route_distance, COLOR_ORANGE,
                              size=10, min_size=9, max_width=240, anchor="e")
        self._draw_route_track(left_x, right_x, 165, route, dot_radius=5)
        self.draw_text(left_x, 183, text="CURRENT", fill=COLOR_ACCENT,
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(right_x, 183, text="DEST" if route["active"] else "NEXT", fill=route_color,
                       font=("Courier", 10, "bold"), anchor="e")
        self._draw_section_rule(20, w - 20, 195)

        # Original scan-progress block, backed by the newer authoritative state.
        self.draw_text(20, 212, text="SYSTEM SURVEY", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(w - 20, 212, text=scan_progress_text, fill=scan_color,
                       font=("Courier", 12, "bold"), anchor="e")
        self._draw_progress_track(20, w - 20, 224, pct, scan_color)
        self._draw_section_rule(20, w - 20, 241)

        # Context reads as a quiet live status rail rather than another boxed widget.
        # Traffic already has a dedicated D/W/T instrument above, so only a
        # genuine secondary alert competes for footer space.
        if attention_text and context_text != attention_text:
            secondary_text = attention_text
            secondary_color = self._badge_color(attention_state)
        else:
            secondary_text = ""
            secondary_color = "#7d8891"
        context_width = 390 if secondary_text else w - 40
        context_display = f"◆  {context_text}" if context_text else ""
        self.draw_fitted_text(20, 261, context_display, context_color,
                              size=11, min_size=10, max_width=context_width, anchor="w")
        self.draw_fitted_text(w - 20, 261, secondary_text, secondary_color,
                              size=10, min_size=9, max_width=205, anchor="e")
        self._last_render_fingerprint = render_fingerprint

    def apply_theme(self, palette=None):
        """Force an immediate repaint after the shared palette is rebound."""
        del palette
        self._last_render_fingerprint = None
        if self._last_update_args is not None:
            self.update(*self._last_update_args)
