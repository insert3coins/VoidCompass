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

        self._nav_marker_phase = 0
        self._nav_marker_model = None
        self._nav_state_identity = None
        self._nav_state_color = None
        self._nav_state_transition = None
        self._nav_event_sequence = -1
        self._nav_event_motion = None
        self._crt_phase = 0
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
        # The compact geometry is the everyday Standard layout. Expanded is
        # retained for commanders who want the additional planning detail.
        return bool(self.config.get("hud_compact_mode", True))

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
            self._draw_navigation_marker_animation()
            self._draw_crt_animation()
            # Each motion profile owns its own cadence. Keeping one monotonic
            # phase avoids a second artificial reset when unlike periods (for
            # example the 42-frame survey tracer) meet an outer 48-frame wrap.
            self._nav_marker_phase += 1
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
        fsd = nav_context.get("fsd_readiness") or {}
        fsd_state = str(fsd.get("state") or "ready")

        # StartJump is only the countdown. The exact Status fsdJump flag owns
        # HYPERSPACE, and FSDJump supplies the bounded ARRIVAL phase.
        if fsd_state == "arrival":
            return "ARRIVAL"
        if fsd_state == "hyperspace":
            return "HYPERSPACE"
        if fsd_state in {"charge", "hyper_charge"}:
            return str(fsd.get("label") or "FSD CHARGE").upper()
        if fsd_state == "cooldown":
            return "FSD COOLDOWN"
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
        if (fsd_state == "mass_lock" and flight_state in {"", "FLIGHT"}
                and not any(nav_context.get(key) for key in (
                    "docked", "landed", "in_fighter", "in_srv", "on_foot",
                ))):
            return "MASS LOCK"
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
        if state_text == "ARRIVAL":
            return COLOR_GREEN
        if state_text in (
            "DOCKED", "LANDED", "FSS", "DSS", "FIGHTER", "SRV", "NOMAD",
            "ONFOOT", "MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY",
            "CODEX", "EXPLORATION", "STATION", "FSD COOLDOWN",
        ):
            return COLOR_ACCENT
        if state_text == "MASS LOCK":
            return COLOR_YELLOW
        if state_text in (
            "HYPERSPACE", "SUPERCRUISE", "JUMPING", "COMBAT",
            "FSD CHARGE", "HYPER CHARGE",
        ):
            return COLOR_ORANGE
        return "#7d8891"

    @staticmethod
    def _navigation_motion_profile(state_text):
        """Map journal/UI states to small, visually distinct motion families."""
        state = str(state_text or "FLIGHT").upper()
        if state == "MASS LOCK":
            return "fsd_lock"
        if state in {"FSD CHARGE", "HYPER CHARGE"}:
            return "fsd_charge"
        if state == "FSD COOLDOWN":
            return "fsd_cooldown"
        if state == "ARRIVAL":
            return "arrival"
        if state in {"DOCKED", "STATION"}:
            return "docked"
        if state == "LANDED":
            return "landed"
        if state == "ONFOOT":
            return "on_foot"
        if state in {"SRV", "NOMAD"}:
            return "surface_vehicle"
        if state in {"FSS", "DSS"}:
            return "scanner"
        if state in {"MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY", "CODEX"}:
            return "map"
        if state in {"HYPERSPACE", "JUMPING"}:
            return "jump"
        if state == "SUPERCRUISE":
            return "supercruise"
        if state == "FIGHTER":
            return "fighter"
        if state == "COMBAT":
            return "combat"
        if state == "EXPLORATION":
            return "exploration"
        return "flight"

    def _draw_navigation_state_glyph(self, x, y, profile, color, tags, scale=1.0):
        """Draw a scalable state glyph inside the shared navigation chassis."""
        scale = max(0.06, min(1.0, float(scale or 0.0)))
        dim = self._glow_color(color, 0.58)

        def point(dx, dy):
            return x + (dx * scale), y + (dy * scale)

        def flat(*points):
            return tuple(value for dx, dy in points for value in point(dx, dy))

        if profile == "fsd_lock":
            self.canvas.create_polygon(
                *flat((0, -4), (4, 0), (0, 4), (-4, 0)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            for offset in (-6, 6):
                self.canvas.create_line(
                    *flat((offset, -3), (offset, 3)),
                    fill=dim, width=1, tags=tags,
                )
            return
        if profile == "fsd_charge":
            self.canvas.create_line(
                *flat((-5, -4), (-1, 0), (-5, 4)),
                fill=dim, width=1, tags=tags,
            )
            self.canvas.create_line(
                *flat((-1, -4), (4, 0), (-1, 4)),
                fill=color, width=1, tags=tags,
            )
            return
        if profile == "fsd_cooldown":
            self.canvas.create_oval(
                *flat((-4, -4), (4, 4)),
                fill="#010101", outline=dim, width=1, tags=tags,
            )
            self.canvas.create_line(
                *flat((0, 0), (3, -2)), fill=color, width=1, tags=tags,
            )
            return
        if profile == "arrival":
            self.canvas.create_oval(
                *flat((-4, -4), (4, 4)),
                fill="#010101", outline=dim, width=1, tags=tags,
            )
            self.canvas.create_oval(
                *flat((-1.5, -1.5), (1.5, 1.5)),
                fill=color, outline="", tags=tags,
            )
            return
        if profile == "docked":
            self.canvas.create_rectangle(
                *flat((-3, -3), (3, 3)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            for offset in (-5, 5):
                self.canvas.create_line(
                    *flat((offset, -2), (offset, 2)),
                    fill=dim, width=1, tags=tags,
                )
            return
        if profile == "landed":
            self.canvas.create_polygon(
                *flat((0, -4), (4, 2), (-4, 2)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            self.canvas.create_line(
                *flat((-5, 4), (5, 4)), fill=dim, width=1, tags=tags,
            )
            return
        if profile == "on_foot":
            self.canvas.create_oval(
                *flat((-4, -3), (-1, 0)), fill=color, outline="", tags=tags,
            )
            self.canvas.create_oval(
                *flat((1, 0), (4, 3)), fill=dim, outline="", tags=tags,
            )
            return
        if profile == "surface_vehicle":
            self.canvas.create_rectangle(
                *flat((-4, -2), (4, 1)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            for offset in (-3, 3):
                self.canvas.create_oval(
                    *flat((offset - 1, 1), (offset + 1, 3)),
                    fill=dim, outline="", tags=tags,
                )
            return
        if profile == "scanner":
            self.canvas.create_oval(
                *flat((-4, -4), (4, 4)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            self.canvas.create_line(*flat((-5, 0), (5, 0)), fill=dim, tags=tags)
            self.canvas.create_line(*flat((0, -5), (0, 5)), fill=dim, tags=tags)
            return
        if profile == "map":
            self.canvas.create_rectangle(
                *flat((-4, -4), (4, 4)),
                fill="#010101", outline=dim, width=1, tags=tags,
            )
            self.canvas.create_polygon(
                *flat((0, -3), (3, 0), (0, 3), (-3, 0)),
                fill="", outline=color, width=1, tags=tags,
            )
            return
        if profile in {"jump", "supercruise"}:
            self.canvas.create_line(
                *flat((-4, -4), (0, 0), (-4, 4)),
                fill=dim, width=1, tags=tags,
            )
            self.canvas.create_line(
                *flat((0, -4), (4, 0), (0, 4)),
                fill=color, width=1, tags=tags,
            )
            return
        if profile in {"fighter", "combat"}:
            self.canvas.create_polygon(
                *flat((5, 0), (-4, -4), (-2, 0), (-4, 4)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            return
        if profile == "exploration":
            self.canvas.create_polygon(
                *flat((0, -4), (4, 0), (0, 4), (-4, 0)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            self.canvas.create_oval(
                *flat((-1, -1), (1, 1)), fill=color, outline="", tags=tags,
            )
            return

        # A restrained forward vector for ordinary flight.
        self.canvas.create_polygon(
            *flat((5, 0), (-3, -4), (-1, 0), (-3, 4)),
            fill="#010101", outline=color, width=1, tags=tags,
        )

    def _draw_navigation_state_marker(
        self,
        center_x,
        center_y,
        text,
        color,
        *,
        route=None,
        survey_progress=0.0,
        survey_known=False,
        survey_color=None,
        compact=False,
        track_left=None,
        track_right=None,
        journal_event=None,
        gravity_g=None,
        surface_active=False,
        fsd_readiness=None,
        local_target=None,
        neutron_boost=None,
    ):
        """Draw one connected route, state and survey navigation instrument."""
        label = str(text or "FLIGHT").upper()
        route = route or {}
        fsd_readiness = fsd_readiness if isinstance(fsd_readiness, dict) else {}
        local_target = local_target if isinstance(local_target, dict) else None
        neutron_boost = neutron_boost if isinstance(neutron_boost, dict) else {}
        boost_armed = bool(neutron_boost.get("armed"))
        survey_color = survey_color or COLOR_ACCENT
        try:
            survey_progress = max(0.0, min(1.0, float(survey_progress or 0.0)))
        except (TypeError, ValueError):
            survey_progress = 0.0

        rendered = self._readable_font(("Courier", 10, "bold"))
        font = tkfont.Font(family=rendered[0], size=rendered[1], weight="bold")
        label_width = font.measure(label)
        group_width = label_width + 24
        group_left = center_x - (group_width / 2)
        group_right = center_x + (group_width / 2)
        marker_x = group_left + 8
        label_x = group_left + 19
        half_span = 98 if compact else 110
        left_edge = float(track_left) if track_left is not None else center_x - half_span
        right_edge = float(track_right) if track_right is not None else center_x + half_span
        shell_half = 6
        inner_left = left_edge + 7
        inner_right = right_edge - 7
        route_end = group_left - 6
        survey_start = group_right + 6
        muted = COLOR_MUTED
        dim = self._glow_color(muted, 0.54)
        shell_color = self._glow_color(color, 0.48)
        route_active = bool(route.get("active"))
        route_color = COLOR_ORANGE if route_active else color
        route_base = self._glow_color(route_color, 0.68 if route_active else 0.62)
        profile = self._navigation_motion_profile(label)
        gravity_value = None
        if surface_active:
            try:
                gravity_value = max(0.0, float(gravity_g))
            except (TypeError, ValueError):
                gravity_value = None
        gravity_load = min(1.0, gravity_value / 3.0) if gravity_value is not None else 0.0
        gravity_deflection = (
            min(3.0, 0.35 + (gravity_value * 0.8))
            if gravity_value is not None and gravity_value > 0 else 0.0
        )
        if gravity_value is not None and gravity_value >= 3.0:
            gravity_color = COLOR_ORANGE
        elif gravity_value is not None and gravity_value >= 1.5:
            gravity_color = COLOR_YELLOW
        else:
            gravity_color = self._glow_color(color, 0.72)
        shell_top = center_y - shell_half
        shell_bottom = center_y + shell_half + gravity_deflection

        # A single tapered chassis contains every data cue. The central state
        # is embedded in the same spine rather than floating between two bars.
        self.canvas.create_polygon(
            left_edge, center_y,
            left_edge + 6, shell_top,
            right_edge - 6, shell_top,
            right_edge, center_y,
            right_edge - 6, shell_bottom,
            left_edge + 6, shell_bottom,
            fill="", outline=shell_color, width=1, tags="nav_state_static",
        )
        if gravity_load > 0:
            gravity_span = (right_edge - left_edge - 16) * (0.18 + (gravity_load * 0.42))
            self.canvas.create_line(
                center_x - (gravity_span / 2), shell_bottom,
                center_x + (gravity_span / 2), shell_bottom,
                fill=gravity_color, width=2 if gravity_value >= 1.5 else 1,
                tags="nav_state_static",
            )
        if boost_armed:
            boost_dim = self._glow_color(COLOR_ACCENT, 0.62)
            for rail_y in (center_y - 3, center_y + 3):
                self.canvas.create_line(
                    inner_left, rail_y, inner_right, rail_y,
                    fill=boost_dim, width=1, tags="nav_state_static",
                )
        self.canvas.create_line(
            inner_left, center_y, inner_right, center_y,
            fill=dim, width=1, tags="nav_state_static",
        )

        # Route progress and survey knowledge illuminate the shared spine from
        # opposite ends, keeping their meaning without visually splitting it.
        self.canvas.create_line(inner_left, center_y, route_end, center_y,
                                fill=route_base, width=2,
                                tags="nav_state_static")
        try:
            route_progress = max(0.0, min(1.0, float(route.get("progress", 0.0) or 0.0)))
        except (TypeError, ValueError):
            route_progress = 0.0
        if route_progress > 0 and route_end > inner_left:
            route_fill_end = inner_left + ((route_end - inner_left) * route_progress)
            self.canvas.create_line(inner_left, center_y, route_fill_end, center_y,
                                    fill=route_color, width=2, tags="nav_state_static")
        if route_active:
            self.canvas.create_oval(
                route_end - 2, center_y - 2,
                route_end + 2, center_y + 2,
                fill="#010101", outline=route_color, width=1,
                tags="nav_state_static",
            )

        self.canvas.create_line(survey_start, center_y, inner_right, center_y,
                                fill=dim, width=1, tags="nav_state_static")
        survey_front = survey_start
        if survey_known and inner_right > survey_start:
            survey_front = survey_start + ((inner_right - survey_start) * survey_progress)
            if survey_progress > 0:
                self.canvas.create_line(
                    survey_start, center_y, survey_front, center_y,
                    fill=survey_color, width=2, tags="nav_state_static",
                )
            for fraction in (0.5, 1.0):
                tick_x = survey_start + ((inner_right - survey_start) * fraction)
                self.canvas.create_line(
                    tick_x, center_y - 2, tick_x, center_y + 2,
                    fill=survey_color if survey_progress >= fraction else dim,
                    width=1, tags="nav_state_static",
                )

        # The spine passes behind a quiet centre aperture while the chassis
        # remains continuous above and below it.
        self.canvas.create_rectangle(
            group_left - 2, center_y - 5, group_right + 2, center_y + 5,
            fill="#010101", outline="", tags="nav_state_static",
        )
        self._accept_navigation_state_transition(label, profile, color)
        self._draw_navigation_state_glyph(
            marker_x, center_y, profile, color, "nav_state_static",
        )
        self.draw_text(label_x, center_y, text=label, fill=color,
                       font=("Courier", 10, "bold"), anchor="w",
                       tags="nav_state_static")
        if local_target:
            target_x = inner_right
            target_color = COLOR_YELLOW
            self.canvas.create_oval(
                target_x - 2, center_y - 2, target_x + 2, center_y + 2,
                fill="#010101", outline=target_color, width=1,
                tags="nav_state_static",
            )
            for y1, y2 in ((shell_top + 1, shell_top + 4),
                           (shell_bottom - 4, shell_bottom - 1)):
                self.canvas.create_line(
                    target_x - 5, y1, target_x - 5, y2,
                    target_x - 5, y1, target_x - 2, y1,
                    fill=self._glow_color(target_color, 0.72), width=1,
                    tags="nav_state_static",
                )

        self._nav_marker_model = {
            "y": center_y,
            "state": label,
            "state_color": color,
            "motion_profile": profile,
            "marker_x": marker_x,
            "group_left": group_left,
            "group_right": group_right,
            "shell_x1": left_edge,
            "shell_x2": right_edge,
            "shell_top": shell_top,
            "shell_bottom": shell_bottom,
            "gravity_g": gravity_value,
            "gravity_load": gravity_load,
            "gravity_color": gravity_color,
            "fsd_readiness": dict(fsd_readiness),
            "local_target": dict(local_target) if local_target else None,
            "boost_armed": boost_armed,
            "boost_value": neutron_boost.get("value"),
            "route_active": route_active,
            "route_x1": inner_left,
            "route_x2": route_end,
            "route_color": route_color,
            "survey_known": bool(survey_known),
            "survey_progress": survey_progress,
            "survey_x1": survey_start,
            "survey_x2": inner_right,
            "survey_front": survey_front,
            "survey_color": survey_color,
        }
        self._accept_navigation_journal_event(journal_event)
        return right_edge - left_edge

    def _accept_navigation_state_transition(self, label, profile, color):
        """Start one compact morph only when the displayed state changes."""
        identity = (str(label or "FLIGHT"), str(profile or "flight"))
        previous = getattr(self, "_nav_state_identity", None)
        previous_color = getattr(self, "_nav_state_color", None) or color
        self._nav_state_identity = identity
        self._nav_state_color = color
        if previous is None or previous == identity:
            return
        if self.config.get("reduced_motion_enabled", False):
            self._nav_state_transition = None
            return
        self._nav_state_transition = {
            "from_profile": previous[1],
            "from_color": previous_color,
            "to_profile": identity[1],
            "to_color": color,
            "started": time.monotonic(),
            "duration": 0.68,
        }

    def _accept_navigation_journal_event(self, event):
        """Accept each live journal pulse once without replaying stale context."""
        if not isinstance(event, dict):
            return
        try:
            sequence = int(event.get("seq"))
        except (TypeError, ValueError):
            return
        if sequence <= self._nav_event_sequence:
            return
        self._nav_event_sequence = sequence

        now = time.monotonic()
        try:
            observed = float(event.get("observed", now))
            duration = max(0.4, min(3.0, float(event.get("duration", 1.3))))
        except (TypeError, ValueError):
            return
        if now - observed > duration + 0.5:
            return

        current = self._nav_event_motion
        same_burst = bool(
            current
            and current.get("kind") == event.get("kind")
            and now - float(current.get("received", 0.0) or 0.0) < 0.55
            and now - float(current.get("started", 0.0) or 0.0) < duration
        )
        motion = dict(event)
        motion["duration"] = duration
        motion["received"] = now
        motion["started"] = current["started"] if same_burst else observed
        self._nav_event_motion = motion

    @staticmethod
    def _navigation_event_color(tone):
        return {
            "accent": COLOR_ACCENT,
            "orange": COLOR_ORANGE,
            "green": COLOR_GREEN,
            "yellow": COLOR_YELLOW,
            "muted": COLOR_MUTED,
        }.get(str(tone or "accent").lower(), COLOR_ACCENT)

    def _draw_navigation_marker_animation(self):
        """Animate only the data-bearing lights in the centre-state row."""
        self.canvas.delete("nav_state_motion")
        model = self._nav_marker_model
        if not model or self.config.get("reduced_motion_enabled", False):
            return
        try:
            if (not self.win.winfo_viewable()
                    or str(self.win.state()) in ("withdrawn", "iconic")):
                return
        except Exception:
            return

        y = model["y"]
        profile = model["motion_profile"]
        travel_profiles = {"flight", "fighter", "supercruise", "surface_vehicle"}
        if (model["route_active"] and profile in travel_profiles
                and model["route_x2"] > model["route_x1"]):
            travel = (self._nav_marker_phase % 36) / 35.0
            x = model["route_x1"] + ((model["route_x2"] - model["route_x1"]) * travel)
            tail_x = max(model["route_x1"], x - 6)
            self.canvas.create_line(
                tail_x, y, x, y,
                fill=self._glow_color(model["route_color"], 0.72),
                width=2, tags="nav_state_motion",
            )
            self.canvas.create_oval(
                x - 1, y - 1, x + 1, y + 1,
                fill=model["route_color"], outline="",
                tags="nav_state_motion",
            )

        # A restrained data light travels over only the known portion of the
        # survey channel. It remains visible at 100%, unlike the old endpoint
        # blink, but never crosses into progress the journal has not reported.
        if model["survey_known"] and profile not in {"map", "jump"}:
            x1, x2 = model["survey_x1"], model["survey_front"]
            if x2 - x1 >= 3:
                travel = (self._nav_marker_phase % 42) / 41.0
                x = x1 + ((x2 - x1) * travel)
                tail_x = max(x1, x - 6)
                self.canvas.create_line(
                    tail_x, y, x, y,
                    fill=self._glow_color(model["survey_color"], 0.62),
                    width=2, tags="nav_state_motion",
                )
                self.canvas.create_oval(
                    x - 1, y - 1, x + 1, y + 1,
                    fill=model["survey_color"], outline="",
                    tags="nav_state_motion",
                )
            elif model["survey_progress"] <= 0 and (self._nav_marker_phase % 20) < 4:
                self.canvas.create_oval(
                    x1 - 1, y - 1, x1 + 1, y + 1,
                    fill=model["survey_color"], outline="",
                    tags="nav_state_motion",
                )

        self._draw_navigation_state_motion(model)
        self._draw_navigation_state_transition_motion(model)
        self._draw_navigation_journal_event_motion(model)

    def _draw_navigation_state_transition_motion(self, model):
        """Contract the old glyph and expand the new state through one chassis."""
        transition = getattr(self, "_nav_state_transition", None)
        if not isinstance(transition, dict):
            return
        try:
            duration = max(0.3, float(transition.get("duration", 0.68)))
            progress = (time.monotonic() - float(transition.get("started"))) / duration
        except (TypeError, ValueError, ZeroDivisionError):
            self._nav_state_transition = None
            return
        if progress < 0:
            return
        if progress >= 1.0:
            self._nav_state_transition = None
            return

        split = 0.46
        contracting = progress < split
        local = progress / split if contracting else (progress - split) / (1.0 - split)
        local = max(0.0, min(1.0, local))
        eased = local * local * (3.0 - (2.0 * local))
        scale = 1.0 - eased if contracting else eased
        profile = transition["from_profile"] if contracting else transition["to_profile"]
        color = transition["from_color"] if contracting else transition["to_color"]
        if contracting and progress > split * 0.72:
            color = self._glow_color(color, 0.68)

        y = model["y"]
        marker_x = model["marker_x"]
        tags = "nav_state_motion"
        # Hide only the static glyph; the state label and common data spine
        # remain stable and readable throughout the morph.
        self.canvas.create_rectangle(
            marker_x - 6, y - 5, marker_x + 6, y + 5,
            fill="#010101", outline="", tags=tags,
        )
        self._draw_navigation_state_glyph(
            marker_x, y, profile, color, tags, scale=max(0.06, scale),
        )

        shell_x1 = model.get("shell_x1", model["route_x1"])
        shell_x2 = model.get("shell_x2", model["survey_x2"])
        shell_top = model.get("shell_top", y - 6)
        shell_bottom = model.get("shell_bottom", y + 6)
        group_left = model["group_left"]
        group_right = model["group_right"]
        if contracting:
            left_x = shell_x1 + ((group_left - shell_x1) * eased)
            right_x = shell_x2 - ((shell_x2 - group_right) * eased)
        else:
            left_x = group_left - ((group_left - shell_x1) * eased)
            right_x = group_right + ((shell_x2 - group_right) * eased)
        glow = self._glow_color(color, 0.72)
        self.canvas.create_line(
            max(shell_x1, left_x - 12), shell_top,
            min(group_left, left_x), shell_top,
            fill=glow, width=2, tags=tags,
        )
        self.canvas.create_line(
            max(group_right, right_x), shell_bottom,
            min(shell_x2, right_x + 12), shell_bottom,
            fill=glow, width=2, tags=tags,
        )

    def _draw_navigation_journal_event_motion(self, model):
        """Draw a short one-shot response to the latest live journal event."""
        event = self._nav_event_motion
        if not isinstance(event, dict):
            return
        try:
            duration = float(event.get("duration", 1.3))
            progress = (time.monotonic() - float(event.get("started"))) / duration
        except (TypeError, ValueError, ZeroDivisionError):
            self._nav_event_motion = None
            return
        if progress < 0:
            return
        if progress >= 1.0:
            self._nav_event_motion = None
            return

        kind = str(event.get("kind") or "")
        lane = str(event.get("lane") or "center")
        color = self._navigation_event_color(event.get("tone"))
        if progress < 0.72:
            visible = color
        elif progress < 0.9:
            visible = self._glow_color(color, 0.72)
        else:
            visible = self._glow_color(color, 0.46)
        glow = self._glow_color(color, 0.56)
        y = model["y"]
        lx1, lx2 = model["route_x1"], model["route_x2"]
        rx1, rx2 = model["survey_x1"], model["survey_x2"]
        gx1, gx2 = model["group_left"], model["group_right"]
        marker_x = model["marker_x"]
        count = max(1, min(3, int(event.get("count", 1) or 1)))
        tags = "nav_state_motion"
        eased = 1.0 - ((1.0 - progress) ** 3)
        shell_x1 = model.get("shell_x1", lx1)
        shell_x2 = model.get("shell_x2", rx2)
        shell_top = model.get("shell_top", y - 6)
        shell_bottom = model.get("shell_bottom", y + 6)

        def tracer(x1, x2, amount, reverse=False, radius=2):
            amount = max(0.0, min(1.0, amount))
            start, end = (x2, x1) if reverse else (x1, x2)
            x = start + ((end - start) * amount)
            tail = x + (6 if reverse else -6)
            if reverse:
                tail = min(start, tail)
            else:
                tail = max(start, tail)
            self.canvas.create_line(tail, y, x, y, fill=glow, width=3, tags=tags)
            self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=visible, outline="", tags=tags,
            )
            return x

        def diamond(x, size, outline=visible):
            self.canvas.create_polygon(
                x, y - size, x + size, y, x, y + size, x - size, y,
                fill="", outline=outline, width=1, tags=tags,
            )

        # Every journal response also energises the shared chassis. This keeps
        # route-, state- and survey-specific reactions visually part of one
        # instrument rather than three adjacent animations.
        if lane == "all":
            top_x = shell_x1 + ((shell_x2 - shell_x1) * eased)
            bottom_x = shell_x2 - ((shell_x2 - shell_x1) * eased)
            self.canvas.create_line(
                max(shell_x1, top_x - 18), shell_top, top_x, shell_top,
                fill=glow, width=2, tags=tags,
            )
            self.canvas.create_line(
                bottom_x, shell_bottom, min(shell_x2, bottom_x + 18), shell_bottom,
                fill=glow, width=2, tags=tags,
            )
        elif lane == "left":
            edge = gx1 - 2
            x = shell_x1 + ((edge - shell_x1) * eased)
            self.canvas.create_line(
                max(shell_x1, x - 16), shell_top, x, shell_top,
                fill=glow, width=2, tags=tags,
            )
        elif lane == "right":
            edge = gx2 + 2
            x = edge + ((shell_x2 - edge) * eased)
            self.canvas.create_line(
                max(edge, x - 16), shell_bottom, x, shell_bottom,
                fill=glow, width=2, tags=tags,
            )
        else:
            spread = 5 + (eased * 18)
            self.canvas.create_line(
                max(shell_x1, gx1 - spread), shell_top,
                min(shell_x2, gx1 - 2), shell_top,
                fill=glow, width=2, tags=tags,
            )
            self.canvas.create_line(
                max(shell_x1, gx2 + 2), shell_bottom,
                min(shell_x2, gx2 + spread), shell_bottom,
                fill=glow, width=2, tags=tags,
            )

        if kind == "jump_charge":
            tracer(lx1, lx2, eased, radius=2)
            tracer(rx1, rx2, eased, reverse=True, radius=2)
            diamond(marker_x, max(5, 11 - (eased * 6)))
            return

        if kind == "arrival":
            tracer(lx1, lx2, eased, reverse=True, radius=2)
            tracer(rx1, rx2, eased, radius=2)
            if progress < 0.55:
                diamond(marker_x, 5 + (progress * 10), glow)
            return

        if kind == "wake":
            tracer(lx1, lx2, eased, reverse=True, radius=1)
            tracer(rx1, rx2, eased, radius=1)
            diamond(marker_x, 5 + (progress * 5), glow)
            return

        if kind == "warning":
            bright = visible if int(progress * 7) % 2 == 0 else glow
            for x in (lx1, gx1 - 5, gx2 + 5, rx2):
                self.canvas.create_line(x, y - 4, x, y + 4,
                                        fill=bright, width=2, tags=tags)
            return

        if lane == "left":
            reverse = kind == "route_clear"
            pulses = 2 if kind == "boost" else 1
            for index in range(pulses):
                local = (progress * 1.18) - (index * 0.18)
                if 0.0 <= local <= 1.0:
                    tracer(lx1, lx2, local, reverse=reverse, radius=2)
            if kind in {"route_set", "route_target"} and progress < 0.7:
                x = lx1 + ((lx2 - lx1) * eased)
                self.canvas.create_line(lx1, y, x, y,
                                        fill=glow, width=3, tags=tags)
            return

        if lane == "right":
            if kind in {"survey_complete", "mapping_complete"}:
                x = rx1 + ((rx2 - rx1) * eased)
                self.canvas.create_line(rx1, y, x, y,
                                        fill=visible, width=3, tags=tags)
                self.canvas.create_line(x, y - 4, x, y + 4,
                                        fill=visible, width=1, tags=tags)
                return

            if kind == "bio_sample":
                step = max(1, min(3, int(event.get("sample_step", count) or count)))
                for index, fraction in enumerate((0.22, 0.50, 0.78), start=1):
                    x = rx1 + ((rx2 - rx1) * fraction)
                    active = index <= step
                    radius = 3 if index == step and progress < 0.7 else 2
                    self.canvas.create_oval(
                        x - radius, y - radius, x + radius, y + radius,
                        fill=visible if active else "#010101",
                        outline=visible if active else glow, width=1, tags=tags,
                    )
                return

            if kind == "data_sale":
                for index in range(2):
                    local = (progress * 1.2) - (index * 0.2)
                    if 0.0 <= local <= 1.0:
                        tracer(rx1, rx2, local, radius=2)
                return

            if kind == "codex":
                x = tracer(rx1, rx2, eased, radius=1)
                diamond(x, 4, visible)
                return

            for index in range(count):
                local = (progress * 1.22) - (index * 0.16)
                if 0.0 <= local <= 1.0:
                    tracer(rx1, rx2, local, radius=2 if kind == "signals" else 1)
            return

        # Centre-lane transitions animate around the full state label so the
        # hollow ship reference and readable text remain undisturbed.
        if kind in {"dock", "dock_request", "dock_denied", "undock"}:
            closing = kind in {"dock", "dock_request"}
            travel = eased if closing else 1.0 - eased
            offset = 3 + ((1.0 - travel) * 18)
            for x, side in ((gx1 - offset, -1), (gx2 + offset, 1)):
                inward = x - (side * 4)
                self.canvas.create_line(x, y - 4, x, y + 4,
                                        fill=visible, width=1, tags=tags)
                self.canvas.create_line(x, y - 4, inward, y - 4,
                                        fill=glow, width=1, tags=tags)
                self.canvas.create_line(x, y + 4, inward, y + 4,
                                        fill=glow, width=1, tags=tags)
            return

        if kind in {"touchdown", "liftoff", "body_approach", "body_leave"}:
            reverse = kind in {"liftoff", "body_leave"}
            travel = 1.0 - eased if reverse else eased
            spread = 4 + (travel * 12)
            dy = (travel * 3) * (-1 if reverse else 1)
            for x in (gx1 - spread, gx2 + spread):
                self.canvas.create_oval(x - 2, y + dy - 1, x + 2, y + dy + 1,
                                        fill=visible, outline="", tags=tags)
            return

        if kind in {"vehicle_deploy", "vehicle_board", "vehicle_switch"}:
            active = min(2, int(progress * 5) % 3)
            for index in range(3):
                x = marker_x - 7 + (index * 7)
                self.canvas.create_rectangle(
                    x, y - 2, x + 3, y + 2,
                    fill=visible if index == active else glow,
                    outline="", tags=tags,
                )
            return

        if kind in {"supercruise_enter", "supercruise_exit"}:
            size = 5 + ((eased if kind == "supercruise_exit" else 1.0 - eased) * 8)
            diamond(marker_x, size, visible)
            return

        diamond(marker_x, 5 + (eased * 5), visible)

    def _draw_navigation_state_motion(self, model):
        """Add the current activity's restrained motion signature."""
        profile = model["motion_profile"]
        phase = self._nav_marker_phase
        y = model["y"]
        marker_x = model["marker_x"]
        color = model["state_color"]
        dim = self._glow_color(color, 0.46)
        tags = "nav_state_motion"
        gravity_load = float(model.get("gravity_load", 0.0) or 0.0)
        if gravity_load > 0:
            # Surface gravity loads the lower chassis rather than adding a
            # duplicate numeric readout. Higher gravity widens and brightens
            # the restrained load-bearing pulse.
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            center_x = (shell_x1 + shell_x2) / 2
            max_span = (shell_x2 - shell_x1) * (0.18 + (gravity_load * 0.34))
            wave = abs(((phase % 54) / 53.0) * 2.0 - 1.0)
            span = max_span * (0.82 + (wave * 0.18))
            gravity_color = model.get("gravity_color", color)
            pulse_color = gravity_color if wave < 0.55 else self._glow_color(gravity_color, 0.72)
            self.canvas.create_line(
                center_x - (span / 2), model.get("shell_bottom", y + 6),
                center_x + (span / 2), model.get("shell_bottom", y + 6),
                fill=pulse_color, width=1, tags=tags,
            )

        if model.get("boost_armed"):
            # A retained paired flow is the persistent, text-free signature
            # that the next hyperspace jump has neutron boost available.
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            travel = (phase % 64) / 63.0
            top_x = shell_x1 + ((shell_x2 - shell_x1) * travel)
            bottom_x = shell_x2 - ((shell_x2 - shell_x1) * travel)
            boost_dim = self._glow_color(COLOR_ACCENT, 0.68)
            self.canvas.create_line(
                max(shell_x1, top_x - 10), y - 3, top_x, y - 3,
                fill=boost_dim, width=2, tags=tags,
            )
            self.canvas.create_line(
                bottom_x, y + 3, min(shell_x2, bottom_x + 10), y + 3,
                fill=boost_dim, width=2, tags=tags,
            )

        if model.get("local_target"):
            target_x = model["survey_x2"]
            wave = abs(((phase % 40) / 39.0) * 2.0 - 1.0)
            radius = 2 + (wave * 2)
            target_color = COLOR_YELLOW if wave < 0.66 else self._glow_color(COLOR_YELLOW, 0.7)
            self.canvas.create_oval(
                target_x - radius, y - radius,
                target_x + radius, y + radius,
                fill="", outline=target_color, width=1, tags=tags,
            )

        if profile == "fsd_lock":
            wave = abs(((phase % 26) / 25.0) * 2.0 - 1.0)
            offset = 4 + (wave * 4)
            for x, side in ((model["group_left"] - offset, -1),
                            (model["group_right"] + offset, 1)):
                inward = x - (side * 5)
                self.canvas.create_line(
                    x, y - 4, x, y + 4,
                    fill=color, width=2, tags=tags,
                )
                self.canvas.create_line(
                    x, y - 4, inward, y - 4,
                    fill=dim, width=1, tags=tags,
                )
                self.canvas.create_line(
                    x, y + 4, inward, y + 4,
                    fill=dim, width=1, tags=tags,
                )
            return

        if profile == "fsd_charge":
            travel = (phase % 16) / 15.0
            left_x = model["route_x1"] + ((model["route_x2"] - model["route_x1"]) * travel)
            right_x = model["survey_x2"] - ((model["survey_x2"] - model["survey_x1"]) * travel)
            self.canvas.create_line(
                left_x - 4, y - 3, left_x, y, left_x - 4, y + 3,
                fill=color, width=2, tags=tags,
            )
            self.canvas.create_line(
                right_x + 4, y - 3, right_x, y, right_x + 4, y + 3,
                fill=color, width=2, tags=tags,
            )
            return

        if profile == "fsd_cooldown":
            travel = (phase % 30) / 29.0
            offset = 3 + (travel * 17)
            fade = color if travel < 0.55 else dim
            for x in (model["group_left"] - offset, model["group_right"] + offset):
                self.canvas.create_line(
                    x, y - 3, x, y + 3,
                    fill=fade, width=1, tags=tags,
                )
            return

        if profile == "arrival":
            travel = (phase % 18) / 17.0
            radius = 3 + (travel * 14)
            fade = color if travel < 0.5 else dim
            self.canvas.create_oval(
                marker_x - radius, y - min(5, radius / 2),
                marker_x + radius, y + min(5, radius / 2),
                fill="", outline=fade, width=1, tags=tags,
            )
            return

        if profile == "docked":
            # Two clamps hold the whole annunciator: visibly powered, but locked.
            wave = abs(((phase % 32) / 31.0) * 2.0 - 1.0)
            offset = 3 + (wave * 2)
            for x, side in ((model["group_left"] - offset, -1),
                            (model["group_right"] + offset, 1)):
                inward = x - (side * 3)
                self.canvas.create_line(x, y - 3, x, y + 3, fill=color, width=1, tags=tags)
                self.canvas.create_line(x, y - 3, inward, y - 3, fill=dim, width=1, tags=tags)
                self.canvas.create_line(x, y + 3, inward, y + 3, fill=dim, width=1, tags=tags)
            return

        if profile == "landed":
            # Ground-contact points spread and settle outside the annunciator.
            wave = abs(((phase % 30) / 29.0) * 2.0 - 1.0)
            spread = 3 + (wave * 4)
            for x in (model["group_left"] - spread, model["group_right"] + spread):
                self.canvas.create_oval(x - 1, y + 2, x + 1, y + 4,
                                        fill=color, outline="", tags=tags)
            return

        if profile == "on_foot":
            # Alternating points evoke steps without adding a literal foot icon.
            active = (phase // 6) % 2
            for index, (dx, dy) in enumerate(((-4, -1), (4, 1))):
                radius = 2 if index == active else 1
                fill = color if index == active else dim
                self.canvas.create_oval(
                    marker_x + dx - radius, y + dy - radius,
                    marker_x + dx + radius, y + dy + radius,
                    fill=fill, outline="", tags=tags,
                )
            return

        if profile == "surface_vehicle":
            # A three-cell tread crawls along the short approach to the marker.
            active = (phase // 4) % 3
            start_x = model["group_left"] - 18
            for index in range(3):
                x = start_x + (index * 5)
                fill = color if index == active else dim
                self.canvas.create_rectangle(x, y - 1, x + 2, y + 1,
                                             fill=fill, outline="", tags=tags)
            return

        if profile == "scanner":
            # Paired scan gates expand away from the state group.
            travel = (phase % 24) / 23.0
            offset = 2 + (travel * 12)
            left_x = model["group_left"] - offset
            right_x = model["group_right"] + offset
            self.canvas.create_line(left_x, y - 3, left_x, y + 3,
                                    fill=color, width=1, tags=tags)
            self.canvas.create_line(right_x, y - 3, right_x, y + 3,
                                    fill=color, width=1, tags=tags)
            return

        if profile == "map":
            # A single cursor sweeps the right-hand data channel and reverses.
            x1, x2 = model["survey_x1"], model["survey_x2"]
            if x2 > x1:
                travel = abs(((phase % 48) / 47.0) * 2.0 - 1.0)
                x = x1 + ((x2 - x1) * travel)
                self.canvas.create_line(x, y - 3, x, y + 3,
                                        fill=color, width=1, tags=tags)
            return

        if profile == "jump":
            # Fast paired chevrons converge on the central state during a jump.
            travel = (phase % 14) / 13.0
            left_x = model["route_x1"] + ((model["route_x2"] - model["route_x1"]) * travel)
            right_x = model["survey_x2"] - ((model["survey_x2"] - model["survey_x1"]) * travel)
            self.canvas.create_line(left_x - 3, y - 2, left_x, y, left_x - 3, y + 2,
                                    fill=color, width=1, tags=tags)
            self.canvas.create_line(right_x + 3, y - 2, right_x, y, right_x + 3, y + 2,
                                    fill=color, width=1, tags=tags)
            return

        if profile == "combat":
            # Alternating alert brackets remain deliberately quieter than a flash.
            bright_left = ((phase // 5) % 2) == 0
            for x, bright in ((model["group_left"] - 5, bright_left),
                              (model["group_right"] + 5, not bright_left)):
                self.canvas.create_line(x, y - 4, x, y + 4,
                                        fill=color if bright else dim, width=1, tags=tags)
            return

        # Flight, fighter, supercruise and exploration breathe through the
        # chassis itself. The state glyph stays readable and the whole device
        # feels powered without adding another independent pip.
        period = {"supercruise": 18, "fighter": 22, "exploration": 36}.get(profile, 28)
        pulse = phase % period
        if pulse < 7:
            travel = pulse / 6.0
            left_start = model.get("shell_x1", model["route_x1"]) + 6
            right_end = model.get("shell_x2", model["survey_x2"]) - 6
            left_x = left_start + ((model["group_left"] - left_start) * travel)
            right_x = right_end - ((right_end - model["group_right"]) * travel)
            active = color if pulse < 4 else dim
            self.canvas.create_line(
                max(left_start, left_x - 10), model.get("shell_top", y - 6),
                left_x, model.get("shell_top", y - 6),
                fill=active, width=1, tags=tags,
            )
            self.canvas.create_line(
                right_x, model.get("shell_bottom", y + 6),
                min(right_end, right_x + 10), model.get("shell_bottom", y + 6),
                fill=active, width=1, tags=tags,
            )

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
        local_target = context.get("local_target") or {}
        target_name = str(local_target.get("name") or "").strip()
        if target_name:
            gravity_text = ""
            if local_target.get("is_current_body"):
                try:
                    gravity = context.get("gravity_g")
                    gravity_text = f" · {float(gravity):.2f} G" if gravity is not None else ""
                except (TypeError, ValueError):
                    gravity_text = ""
            return f"TARGET LOCK · {target_name}{gravity_text}", COLOR_YELLOW
        neutron_boost = context.get("neutron_boost") or {}
        if neutron_boost.get("armed"):
            try:
                boost_value = float(neutron_boost.get("value"))
                boost_text = f" · {boost_value:.1f}X"
            except (TypeError, ValueError):
                boost_text = ""
            return f"NEUTRON BOOST ARMED{boost_text}", COLOR_ACCENT
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
        marker_left, marker_right = 16, w - 16
        marker_center = (marker_left + marker_right) / 2
        self._draw_navigation_state_marker(
            marker_center, 17, state_text, state_color,
            route=route,
            survey_progress=pct,
            survey_known=total > 0 and nav_context.get("scan_progress_source") != "unknown",
            survey_color=scan_color,
            compact=True,
            track_left=marker_left,
            track_right=marker_right,
            journal_event=nav_context.get("journal_event"),
            gravity_g=nav_context.get("gravity_g"),
            surface_active=bool(
                nav_context.get("landed") or nav_context.get("in_srv")
                or nav_context.get("on_foot")
                or state_text in {"LANDED", "SRV", "NOMAD", "ONFOOT"}
            ),
            fsd_readiness=nav_context.get("fsd_readiness"),
            local_target=nav_context.get("local_target"),
            neutron_boost=nav_context.get("neutron_boost"),
        )
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
        marker_left, marker_right = 20, w - 20
        marker_center = (marker_left + marker_right) / 2
        self._draw_navigation_state_marker(
            marker_center, 19, state_text, state_color,
            route=route,
            survey_progress=pct,
            survey_known=total > 0 and nav_context.get("scan_progress_source") != "unknown",
            survey_color=scan_color,
            track_left=marker_left,
            track_right=marker_right,
            journal_event=nav_context.get("journal_event"),
            gravity_g=nav_context.get("gravity_g"),
            surface_active=bool(
                nav_context.get("landed") or nav_context.get("in_srv")
                or nav_context.get("on_foot")
                or state_text in {"LANDED", "SRV", "NOMAD", "ONFOOT"}
            ),
            fsd_readiness=nav_context.get("fsd_readiness"),
            local_target=nav_context.get("local_target"),
            neutron_boost=nav_context.get("neutron_boost"),
        )
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
