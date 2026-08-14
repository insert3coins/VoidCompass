import tkinter as tk
import tkinter.font as tkfont
import math
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
from navigation_instrument import (
    NavigationInstrumentRenderer,
    event_scene,
    state_scene,
)

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
        self.compact_height = 246
        self.width, self.base_height = self._target_dimensions()
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.base_height, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()
        self._nav_instrument = NavigationInstrumentRenderer(
            self.canvas, self._glow_color,
        )

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
        self._nav_target_identity = None
        self._nav_target_transition = None
        self._nav_event_sequence = -1
        self._nav_event_motion = None
        self._route_track_model = None
        self._nav_fuel_model = None
        self._crt_phase = 0
        self._nav_phase_last_ts = time.monotonic()
        self._next_crt_frame_ts = 0.0
        self._mouse_down = None
        self._mouse_dragging = False
        self._save_job = None
        self._last_render_fingerprint = None
        self._last_update_args = None
        self._anim_interval_ms = int(self.config.get("hud_anim_interval_ms", 33) or 33)
        self._anim_interval_ms = max(30, min(500, self._anim_interval_ms))
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
        now = time.monotonic()
        elapsed = max(0.0, min(0.5, now - self._nav_phase_last_ts))
        self._nav_phase_last_ts = now
        # One phase unit remains the old 100 ms animation step. More frequent
        # paints interpolate between those points while delayed Tk callbacks
        # catch up to real time instead of slowing the instrument down.
        self._nav_marker_phase += elapsed / 0.1
        try:
            self._draw_navigation_marker_animation()
            self._draw_route_track_animation()
            self._draw_fuel_scoop_animation()
            if now >= self._next_crt_frame_ts:
                self._draw_crt_animation()
                self._next_crt_frame_ts = now + 0.1
        except Exception:
            pass
        finally:
            try:
                delay = self._anim_interval_ms
                if self.config.get("reduced_motion_enabled", False):
                    delay = max(delay, 250)
                elif not self.win.winfo_viewable():
                    delay = max(delay, 120)
                self.win.after(delay, self.animate_ui)
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
        track_key = music_track.replace(" ", "").replace("_", "").upper()
        fsd = nav_context.get("fsd_readiness") or {}
        fsd_state = str(fsd.get("state") or "ready")

        # StartJump is only the countdown. The exact Status fsdJump flag owns
        # HYPERSPACE, and FSDJump supplies the bounded ARRIVAL phase.
        if fsd_state == "carrier_transit":
            return "CARRIER TRANSIT"
        if fsd_state == "carrier_arrival":
            return "CARRIER ARRIVAL"
        if fsd_state == "arrival":
            return "ARRIVAL"
        if fsd_state == "hyperspace":
            return "HYPERSPACE"
        if fsd_state == "supercruise_entry":
            return "SUPERCRUISE"
        if fsd_state in {"charge", "hyper_charge"}:
            return str(fsd.get("label") or "FSD CHARGE").upper()
        if fsd_state == "cooldown":
            return "FSD COOLDOWN"
        if flight_state in ("HYPERSPACE", "JUMPING"):
            return flight_state
        if (nav_context.get("supercruise_overcharge")
                and flight_state == "SUPERCRUISE"):
            return "SCO OVERCHARGE"
        journal_event = nav_context.get("journal_event") or {}
        if str(journal_event.get("kind") or "") in {
                "vehicle_deploy", "vehicle_board", "vehicle_switch",
                "interdiction", "interdiction_clear", "signal_drop"}:
            transition_label = str(journal_event.get("state_label") or "").strip()
            if transition_label:
                return transition_label.upper()
        if nav_context.get("interdicted") or track_key == "INTERDICTION":
            return "INTERDICTION"

        focus_key = (
            str(nav_context.get("gui_focus", ""))
            .replace(" ", "").replace("_", "").upper()
        )
        focus_labels = {
            "6": "GALAXY MAP",
            "GALAXYMAP": "GALAXY MAP",
            "7": "SYSTEM MAP",
            "SYSTEMMAP": "SYSTEM MAP",
            "8": "ORRERY",
            "ORRERY": "ORRERY",
            "9": "FSS",
            "FSS": "FSS",
            "SYSTEMANDSURFACESCANNER": "FSS",
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
        approach = nav_context.get("surface_approach") or {}
        if approach.get("active"):
            phase = str(approach.get("phase") or "surface").casefold()
            if phase == "orbital_departure":
                return "ORBITAL DEPARTURE"
            if phase == "surface_departure":
                return "SURFACE DEPARTURE"
            if phase == "glide":
                return "GLIDE"
            if phase == "orbital":
                return "ORBITAL APPROACH"
            if phase == "hold":
                return "SURFACE HOLD"
            return "SURFACE APPROACH"
        if (fsd_state == "mass_lock" and flight_state in {"", "FLIGHT"}
                and not any(nav_context.get(key) for key in (
                    "docked", "landed", "in_fighter", "in_srv", "on_foot",
                    "in_taxi", "in_multicrew",
                ))):
            return "MASS LOCK"
        if flight_state == "TAXI" or nav_context.get("in_taxi"):
            return "TAXI"
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
        if flight_state == "MULTICREW" or nav_context.get("in_multicrew"):
            return "MULTICREW"
        if flight_state == "LANDED" or nav_context.get("landed"):
            return "LANDED"
        if flight_state == "SUPERCRUISE":
            return "SUPERCRUISE"
        if music_mode in ("MAP", "COMBAT", "EXPLORATION", "STATION"):
            return music_mode
        return "FLIGHT"

    def _state_color(self, state_text):
        state_text = str(state_text or "").upper()
        if (state_text.endswith((" DEPLOY", " RECOVERY", " EGRESS", " CONTROL"))
                or state_text.startswith("BOARDING ")
                or state_text in {"MULTICREW LINK", "CREW RETURN"}):
            return COLOR_ACCENT
        if state_text in {"ARRIVAL", "CARRIER ARRIVAL"}:
            return COLOR_GREEN
        if state_text in (
            "DOCKED", "LANDED", "FSS", "DSS", "FIGHTER", "SRV", "NOMAD",
            "TAXI", "MULTICREW",
            "ONFOOT", "MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY",
            "CODEX", "EXPLORATION", "STATION", "FSD COOLDOWN", "ORBITAL APPROACH",
            "ORBITAL DEPARTURE", "SURFACE HOLD",
        ):
            return COLOR_ACCENT
        if state_text in {"MASS LOCK", "GLIDE", "SURFACE APPROACH", "SURFACE DEPARTURE"}:
            return COLOR_YELLOW
        if state_text in (
            "HYPERSPACE", "SUPERCRUISE", "JUMPING", "COMBAT",
            "FSD CHARGE", "HYPER CHARGE", "SCO OVERCHARGE", "CARRIER TRANSIT",
            "INTERDICTION", "INTERDICTED",
        ):
            return COLOR_ORANGE
        if state_text == "INTERDICTION EVADED":
            return COLOR_GREEN
        if state_text.startswith("SIGNAL THREAT"):
            return COLOR_ORANGE
        if state_text == "SIGNAL DROP":
            return COLOR_YELLOW
        return "#7d8891"

    @staticmethod
    def _navigation_motion_profile(state_text):
        """Map journal/UI states to small, visually distinct motion families."""
        state = str(state_text or "FLIGHT").upper()
        if state.endswith(" DEPLOY") or state.endswith(" EGRESS"):
            return "vehicle_deploy"
        if state.endswith(" RECOVERY") or state.startswith("BOARDING "):
            return "vehicle_board"
        if state.endswith(" CONTROL"):
            return "vehicle_switch"
        if state in {"MULTICREW LINK", "CREW RETURN"}:
            return "vehicle_switch"
        if state in {"INTERDICTION", "INTERDICTED"}:
            return "combat"
        if state == "INTERDICTION EVADED":
            return "arrival"
        if state.startswith("SIGNAL "):
            return "fsd_lock"
        if state == "MASS LOCK":
            return "fsd_lock"
        if state in {"FSD CHARGE", "HYPER CHARGE"}:
            return "fsd_charge"
        if state == "SCO OVERCHARGE":
            return "supercruise_overcharge"
        if state == "CARRIER TRANSIT":
            return "carrier_transit"
        if state == "CARRIER ARRIVAL":
            return "carrier_arrival"
        if state == "ORBITAL APPROACH":
            return "orbital_approach"
        if state == "GLIDE":
            return "glide"
        if state == "SURFACE APPROACH":
            return "surface_approach"
        if state == "SURFACE HOLD":
            return "surface_hold"
        if state == "SURFACE DEPARTURE":
            return "surface_departure"
        if state == "ORBITAL DEPARTURE":
            return "orbital_departure"
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
        if state == "TAXI":
            return "supercruise"
        if state == "MULTICREW":
            return "flight"
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
        if profile == "supercruise_overcharge":
            # Three compressed forward gates distinguish sustained SCO from
            # ordinary supercruise without adding a second status label.
            for offset, tone in ((-4, dim), (0, color), (4, dim)):
                self.canvas.create_line(
                    *flat((offset - 4, -4), (offset, 0), (offset - 4, 4)),
                    fill=tone, width=1, tags=tags,
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
        if profile in {"carrier_transit", "carrier_arrival"}:
            # Broad parallel decks distinguish a carrier translation from the
            # compact forward vector used by the commander's own ship.
            self.canvas.create_rectangle(
                *flat((-5, -2), (5, 2)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            self.canvas.create_line(
                *flat((-7, -4), (3, -4)), fill=dim, width=1, tags=tags,
            )
            self.canvas.create_line(
                *flat((-3, 4), (7, 4)), fill=dim, width=1, tags=tags,
            )
            if profile == "carrier_arrival":
                for offset in (-7, 7):
                    self.canvas.create_line(
                        *flat((offset, -3), (offset, 3)),
                        fill=color, width=1, tags=tags,
                    )
            return
        if profile in {"orbital_approach", "glide", "surface_approach", "surface_hold"}:
            # A horizon, descending ship reference and approach gates give the
            # three planetary phases one coherent static silhouette.
            self.canvas.create_arc(
                *flat((-5, -1), (5, 7)), start=18, extent=144,
                style="arc", outline=dim, width=1, tags=tags,
            )
            self.canvas.create_polygon(
                *flat((0, -4), (3, 0), (0, -1), (-3, 0)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            if profile == "glide":
                for offset in (-6, 6):
                    self.canvas.create_line(
                        *flat((offset, -4), (offset / 2, -1)),
                        fill=color, width=1, tags=tags,
                    )
            elif profile in {"surface_approach", "surface_hold"}:
                self.canvas.create_line(
                    *flat((-4, 4), (4, 4)), fill=color, width=1, tags=tags,
                )
            return
        if profile in {"surface_departure", "orbital_departure"}:
            # The same planet/ship language used on approach is inverted for
            # ascent: the ship points away from a receding horizon.
            self.canvas.create_arc(
                *flat((-5, 0), (5, 8)), start=18, extent=144,
                style="arc", outline=dim, width=1, tags=tags,
            )
            self.canvas.create_polygon(
                *flat((0, -5), (3, 1), (0, -1), (-3, 1)),
                fill="#010101", outline=color, width=1, tags=tags,
            )
            if profile == "orbital_departure":
                for offset in (-6, 6):
                    self.canvas.create_line(
                        *flat((offset / 2, -1), (offset, -4)),
                        fill=color, width=1, tags=tags,
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
        if profile in {"vehicle_deploy", "vehicle_board", "vehicle_switch"}:
            # Three transfer cells mirror the bounded journal pulse. Their
            # emphasis distinguishes leaving, returning and changing control.
            reverse = profile == "vehicle_board"
            for index in range(3):
                offset = (index - 1) * 4
                tone = color if index == (0 if reverse else 2) else dim
                self.canvas.create_rectangle(
                    *flat((offset - 1.5, -2), (offset + 1.5, 2)),
                    fill=tone, outline="", tags=tags,
                )
            if profile == "vehicle_switch":
                self.canvas.create_line(
                    *flat((-5, -4), (5, -4)), fill=color, width=1, tags=tags,
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

    @staticmethod
    def _navigation_instrument_palette():
        return {
            "accent": COLOR_ACCENT,
            "orange": COLOR_ORANGE,
            "green": COLOR_GREEN,
            "yellow": COLOR_YELLOW,
            "muted": COLOR_MUTED,
        }

    def _draw_navigation_instrument_v3(
        self,
        center_x,
        center_y,
        text,
        color,
        *,
        compact=False,
        track_left=None,
        track_right=None,
        journal_event=None,
        gravity_g=None,
        surface_active=False,
        fsd_readiness=None,
        local_target=None,
        neutron_boost=None,
        fuel_scooping=False,
        surface_approach=None,
        ship_config=None,
    ):
        """Build the open, bootloader-derived Navigation Instrument V3."""
        label = str(text or "FLIGHT").upper()
        fsd_readiness = fsd_readiness if isinstance(fsd_readiness, dict) else {}
        local_target = local_target if isinstance(local_target, dict) else None
        neutron_boost = neutron_boost if isinstance(neutron_boost, dict) else {}
        surface_approach = surface_approach if isinstance(surface_approach, dict) else {}
        ship_config = ship_config if isinstance(ship_config, dict) else {}

        rendered = self._readable_font(("Courier", 10, "bold"))
        font = tkfont.Font(family=rendered[0], size=rendered[1], weight="bold")
        label_width = font.measure(label)
        left_edge = float(track_left) if track_left is not None else center_x - (220 if compact else 270)
        right_edge = float(track_right) if track_right is not None else center_x + (220 if compact else 270)
        label_y = center_y - 7
        scene_y = center_y + 7
        scene_top = scene_y - 5
        scene_bottom = scene_y + 5
        group_left = center_x - (label_width / 2)
        group_right = center_x + (label_width / 2)
        profile = self._navigation_motion_profile(label)

        gravity_value = None
        if surface_active:
            try:
                gravity_value = max(0.0, float(gravity_g))
            except (TypeError, ValueError):
                gravity_value = None
        gravity_load = min(1.0, gravity_value / 3.0) if gravity_value is not None else 0.0
        if gravity_value is not None and gravity_value >= 3.0:
            gravity_color = COLOR_ORANGE
        elif gravity_value is not None and gravity_value >= 1.5:
            gravity_color = COLOR_YELLOW
        else:
            gravity_color = self._glow_color(color, 0.72)

        self._accept_navigation_state_transition(label, profile, color)
        model = {
            "state": label,
            "state_color": color,
            "motion_profile": profile,
            "label_y": label_y,
            "scene_y": scene_y,
            "scene_top": scene_top,
            "scene_bottom": scene_bottom,
            "scene_x1": left_edge,
            "scene_x2": right_edge,
            "group_left": group_left,
            "group_right": group_right,
            "marker_x": center_x,
            "y": scene_y,
            "shell_x1": left_edge,
            "shell_x2": right_edge,
            "shell_top": scene_top,
            "shell_bottom": scene_bottom,
            "gravity_g": gravity_value,
            "gravity_load": gravity_load,
            "gravity_color": gravity_color,
            "fsd_readiness": dict(fsd_readiness),
            # Target presentation belongs to the separate target pulse overlay.
            "local_target": None,
            "boost_armed": bool(neutron_boost.get("armed")),
            "boost_value": neutron_boost.get("value"),
            "fuel_scooping": bool(fuel_scooping),
            "surface_approach": dict(surface_approach),
            "ship_config": dict(ship_config),
            # Compatibility geometry for the independent route/fuel event
            # animations elsewhere in the Navigation HUD.
            "left_x1": left_edge + 8,
            "left_x2": group_left - 10,
            "right_x1": group_right + 10,
            "right_x2": right_edge - 8,
            "route_x1": left_edge + 8,
            "route_x2": group_left - 10,
            "survey_x1": group_right + 10,
            "survey_x2": right_edge - 8,
        }
        self._nav_marker_model = model

        self._nav_instrument.draw_static(model)
        self.draw_text(
            center_x, label_y, text=label, fill=color,
            font=("Courier", 10, "bold"), anchor="center",
            tags="nav_state_static",
        )
        self._accept_navigation_journal_event(journal_event)
        if self.config.get("reduced_motion_enabled", False):
            self._nav_instrument.draw_state(
                model, 0.0, self._navigation_instrument_palette(),
                tags="nav_state_static", motion=False,
            )
        return right_edge - left_edge

    def _draw_navigation_state_marker_legacy(
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
        fuel_scooping=False,
        surface_approach=None,
        ship_config=None,
    ):
        """Retained tapered-rail renderer for visual rollback diagnostics.

        Route and survey progress have dedicated, more legible instruments
        below this row. The retained compatibility arguments deliberately do
        not illuminate either wing; both sides now belong to the centre state.
        """
        label = str(text or "FLIGHT").upper()
        fsd_readiness = fsd_readiness if isinstance(fsd_readiness, dict) else {}
        local_target = local_target if isinstance(local_target, dict) else None
        neutron_boost = neutron_boost if isinstance(neutron_boost, dict) else {}
        surface_approach = surface_approach if isinstance(surface_approach, dict) else {}
        ship_config = ship_config if isinstance(ship_config, dict) else {}
        boost_armed = bool(neutron_boost.get("armed"))

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
        left_end = group_left - 6
        right_start = group_right + 6
        muted = COLOR_MUTED
        dim = self._glow_color(muted, 0.54)
        shell_color = self._glow_color(color, 0.48)
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

        # Both wings are intentionally neutral at rest. Their motion is
        # supplied by the centre state's profile rather than route/scan data.
        for x1, x2 in ((inner_left, left_end), (right_start, inner_right)):
            self.canvas.create_line(
                x1, center_y, x2, center_y,
                fill=dim, width=1, tags="nav_state_static",
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
        self._accept_navigation_target(local_target)
        if local_target and self.config.get("reduced_motion_enabled", False):
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

        # Configuration cues are real state, not decoration, so their quiet
        # baseline remains visible even when reduced motion is enabled.
        if ship_config.get("landing_gear"):
            for x in (group_left - 3, group_right + 3):
                self.canvas.create_line(
                    x, shell_bottom, x, shell_bottom + 3,
                    fill=color, width=1, tags="nav_state_static",
                )
                self.canvas.create_line(
                    x - 2, shell_bottom + 3, x + 2, shell_bottom + 3,
                    fill=color, width=1, tags="nav_state_static",
                )
        if ship_config.get("cargo_scoop"):
            x = group_left - 10
            self.canvas.create_line(
                x - 3, center_y + 2, x, center_y + 5, x + 3, center_y + 2,
                fill=COLOR_ORANGE, width=1, tags="nav_state_static",
            )
        if ship_config.get("analysis_mode"):
            x = group_right + 8
            self.canvas.create_line(
                x, center_y - 3, x, center_y + 3,
                fill=self._glow_color(COLOR_ACCENT, 0.72),
                width=1, tags="nav_state_static",
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
            "fuel_scooping": bool(fuel_scooping),
            "surface_approach": dict(surface_approach),
            "ship_config": dict(ship_config),
            "left_x1": inner_left,
            "left_x2": left_end,
            "right_x1": right_start,
            "right_x2": inner_right,
            # Compatibility aliases for the bounded journal-response drawing
            # code; these are geometry only and carry no progress semantics.
            "route_x1": inner_left,
            "route_x2": left_end,
            "survey_x1": right_start,
            "survey_x2": inner_right,
        }
        self._accept_navigation_journal_event(journal_event)
        return right_edge - left_edge

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
        fuel_scooping=False,
        surface_approach=None,
        ship_config=None,
    ):
        """Draw the open, bootloader-derived Navigation Instrument V3."""
        return self._draw_navigation_instrument_v3(
            center_x, center_y, text, color,
            compact=compact,
            track_left=track_left,
            track_right=track_right,
            journal_event=journal_event,
            gravity_g=gravity_g,
            surface_active=surface_active,
            fsd_readiness=fsd_readiness,
            local_target=local_target,
            neutron_boost=neutron_boost,
            fuel_scooping=fuel_scooping,
            surface_approach=surface_approach,
            ship_config=ship_config,
        )

    def _accept_navigation_target(self, local_target):
        """Start a short acquisition sweep when the selected local target changes."""
        identity = str((local_target or {}).get("name") or "").strip().casefold()
        previous = self._nav_target_identity
        self._nav_target_identity = identity
        if not identity or identity == previous:
            if not identity:
                self._nav_target_transition = None
            return
        if self.config.get("reduced_motion_enabled", False):
            self._nav_target_transition = None
            return
        self._nav_target_transition = {
            "started": time.monotonic(), "duration": 0.78,
        }

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

    @staticmethod
    def _cycle_progress(phase, period):
        """Return continuous animation progress without endpoint overshoot."""
        period = max(1.0, float(period))
        return (float(phase) % period) / period

    def _draw_contrast_motion_dot(self, x, y, color, radius=1,
                                  tags="nav_state_motion"):
        """Cut moving lights free from same-colour rails and scanlines."""
        radius = max(1.0, float(radius or 1))
        halo = radius + 1.25
        self.canvas.create_oval(
            x - halo, y - halo, x + halo, y + halo,
            fill="#010101", outline="#010101", width=1, tags=tags,
        )
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=color, outline="", tags=tags,
        )

    def _draw_contrast_motion_tail(self, x1, x2, y, color, width=2,
                                   tags="nav_state_motion"):
        """Give a tracer tail a narrow dark underlay over illuminated rails."""
        width = max(1, int(width or 1))
        self.canvas.create_line(
            x1, y, x2, y, fill="#010101", width=width + 2, tags=tags,
        )
        self.canvas.create_line(
            x1, y, x2, y, fill=color, width=width, tags=tags,
        )

    def _draw_navigation_boot_aperture(
        self, model, scene, phase, color, dim, tags,
    ):
        """Adapt the bootloader's scope/readiness language to the HUD core."""
        family = scene.family
        if family == "dedicated":
            return
        marker_x = model["marker_x"]
        y = model["y"]
        shell_top = model.get("shell_top", y - 6)
        shell_bottom = model.get("shell_bottom", y + 6)
        travel = self._cycle_progress(phase, scene.period)
        glow = self._glow_color(color, min(0.82, scene.intensity))

        if family == "scope":
            # A compressed FSS scope: two range arcs, a rotating sweep and
            # deterministic contacts.  It surrounds only the glyph aperture,
            # keeping the state label completely readable.
            self.canvas.create_arc(
                marker_x - 7, y - 5, marker_x + 7, y + 5,
                start=24, extent=132, style="arc", outline=dim,
                width=1, tags=tags,
            )
            self.canvas.create_arc(
                marker_x - 7, y - 5, marker_x + 7, y + 5,
                start=204, extent=132, style="arc", outline=dim,
                width=1, tags=tags,
            )
            angle = (-0.72 * math.pi) + (travel * 1.44 * math.pi)
            sweep_x = marker_x + (math.cos(angle) * 6)
            sweep_y = y + (math.sin(angle) * 4)
            self.canvas.create_line(
                marker_x, y, sweep_x, sweep_y,
                fill=glow, width=1, tags=tags,
            )
            contact = 1 if int(phase // 8) % 2 else -1
            self._draw_contrast_motion_dot(
                marker_x + (contact * 4), y - 2,
                color, radius=1, tags=tags,
            )
            return

        if family == "plot":
            # The map state resolves a tiny route solution through the core,
            # echoing the startup route plot without duplicating real hops.
            points = (
                (marker_x - 7, y + 2),
                (marker_x - 2, y - 3),
                (marker_x + 5, y + 1),
            )
            self.canvas.create_line(
                *[value for point in points for value in point],
                fill=dim, width=1, smooth=True, tags=tags,
            )
            active = min(2, int(travel * 3))
            for index, (x, py) in enumerate(points):
                radius = 1.5 if index == active else 1
                self.canvas.create_oval(
                    x - radius, py - radius, x + radius, py + radius,
                    fill=color if index == active else dim,
                    outline="", tags=tags,
                )
            return

        if family == "horizon":
            wave = abs((travel * 2.0) - 1.0)
            radius = 6 + (wave * 2)
            self.canvas.create_arc(
                marker_x - radius, y - 1,
                marker_x + radius, y + 6,
                start=18, extent=144, style="arc",
                outline=glow, width=1, tags=tags,
            )
            self.canvas.create_line(
                marker_x - 5, shell_bottom - 1,
                marker_x + 5, shell_bottom - 1,
                fill=dim, width=1, tags=tags,
            )
            return

        if family == "terrain":
            step = int(travel * 4) % 4
            for index, dx in enumerate((-6, -2, 2, 6)):
                height = 2 + ((index + step) % 3)
                self.canvas.create_line(
                    marker_x + dx, shell_bottom - height,
                    marker_x + dx, shell_bottom,
                    fill=color if index == step else dim,
                    width=1, tags=tags,
                )
            return

        if family == "alert":
            bright_left = int(phase // 4) % 2 == 0
            for side, bright in ((-1, bright_left), (1, not bright_left)):
                x = marker_x + (side * 7)
                self.canvas.create_line(
                    x, shell_top + 1, x, shell_bottom - 1,
                    fill=color if bright else dim,
                    width=2 if bright else 1, tags=tags,
                )
            return

        # Vector, route, readiness and hand-off scenes share the bootloader's
        # restrained central readiness pulse.  The distinct wing motion below
        # still makes each family immediately recognisable.
        pulse = abs((travel * 2.0) - 1.0)
        radius_x = 4 + (pulse * (2 if family == "route" else 1))
        self.canvas.create_oval(
            marker_x - radius_x, y - 4,
            marker_x + radius_x, y + 4,
            fill="", outline=glow if pulse < 0.55 else dim,
            width=1, tags=tags,
        )

    def _draw_navigation_readiness_cells(
        self, model, scene, phase, color, dim, tags,
    ):
        """Flow a few boot-style readiness cells along the chassis rails."""
        if scene.family == "dedicated" or scene.segments <= 0:
            return
        left_x1 = model.get("left_x1", model["route_x1"])
        left_x2 = model.get("left_x2", model["route_x2"])
        right_x1 = model.get("right_x1", model["survey_x1"])
        right_x2 = model.get("right_x2", model["survey_x2"])
        shell_top = model.get("shell_top", model["y"] - 6)
        shell_bottom = model.get("shell_bottom", model["y"] + 6)
        count = max(2, min(6, int(scene.segments)))
        travel = self._cycle_progress(phase, scene.period)
        active = min((count * 2) - 1, int(travel * count * 2))
        if scene.family in {"readiness", "handoff"}:
            active = int(abs((travel * 2.0) - 1.0) * ((count * 2) - 1))

        cells = []
        for index in range(count):
            amount = (index + 0.5) / count
            cells.append((
                left_x1 + ((left_x2 - left_x1) * amount), shell_top,
            ))
        for index in range(count):
            amount = (index + 0.5) / count
            cells.append((
                right_x1 + ((right_x2 - right_x1) * amount), shell_bottom,
            ))
        for index, (x, py) in enumerate(cells):
            distance = min(
                (index - active) % len(cells),
                (active - index) % len(cells),
            )
            cell_color = color if distance == 0 else (
                self._glow_color(color, 0.66) if distance == 1 else dim
            )
            width = 6 if distance == 0 else 4
            self.canvas.create_line(
                x - (width / 2), py, x + (width / 2), py,
                fill=cell_color, width=1, tags=tags,
            )

    def _draw_navigation_boot_event_scene(
        self, model, kind, progress, color, glow, tags,
    ):
        """Layer a boot-style scope or readiness response under an event."""
        scene = event_scene(kind)
        family = scene.family
        y = model["y"]
        marker_x = model["marker_x"]
        shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
        shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
        shell_top = model.get("shell_top", y - 6)
        shell_bottom = model.get("shell_bottom", y + 6)
        group_left = model["group_left"]
        group_right = model["group_right"]
        eased = progress * progress * (3.0 - (2.0 * progress))

        if family == "scope":
            # Survey events briefly turn the right wing into a compressed FSS
            # array, matching the startup scope while leaving survey totals in
            # their existing dedicated instrument below.
            cx = group_right + ((shell_x2 - group_right) * 0.55)
            radius_x = max(7.0, min(15.0, (shell_x2 - group_right) * 0.19))
            radius_y = 5.0
            self.canvas.create_oval(
                cx - radius_x, y - radius_y,
                cx + radius_x, y + radius_y,
                fill="", outline=glow, width=1, tags=tags,
            )
            self.canvas.create_oval(
                cx - (radius_x * 0.48), y - (radius_y * 0.48),
                cx + (radius_x * 0.48), y + (radius_y * 0.48),
                fill="", outline=self._glow_color(color, 0.42),
                width=1, tags=tags,
            )
            angle = (-0.8 * math.pi) + (eased * 1.6 * math.pi)
            self.canvas.create_line(
                cx, y,
                cx + (math.cos(angle) * radius_x),
                y + (math.sin(angle) * radius_y),
                fill=color, width=1, tags=tags,
            )
            for index in range(min(3, scene.pulses)):
                local = (eased + (index / max(1, scene.pulses))) % 1.0
                contact_x = cx - radius_x + (radius_x * 2 * local)
                contact_y = y + (-2 if index % 2 == 0 else 2)
                self._draw_contrast_motion_dot(
                    contact_x, contact_y, color,
                    radius=1, tags=tags,
                )
            return

        if family == "route":
            # A short route solution grows across the left wing, then hands
            # back to the persistent state animation.
            start = shell_x1
            end = max(start + 1, group_left - 3)
            points = []
            offsets = (1, -2, 2)
            for index in range(3):
                x = start + ((end - start) * index / 2)
                points.append((x, y + offsets[index]))
            self.canvas.create_line(
                *[value for point in points for value in point],
                fill=glow, width=1, smooth=True, tags=tags,
            )
            limit_x = start + ((end - start) * eased)
            reached = [point for point in points if point[0] <= limit_x]
            if reached:
                reached.append((limit_x, y))
                self.canvas.create_line(
                    *[value for point in reached for value in point],
                    fill=color, width=2, smooth=True, tags=tags,
                )
            for x, py in points:
                self.canvas.create_oval(
                    x - 1, py - 1, x + 1, py + 1,
                    fill=color if x <= limit_x else glow,
                    outline="", tags=tags,
                )
            return

        if family in {"boot", "charge", "fuel", "hazard", "recovery"}:
            # Readiness cells converge for charge/fuel, expand for recovery,
            # and alternate for hazards.  This is the clearest visual bridge
            # to the bootloader's final readiness panel.
            count = min(6, max(3, scene.pulses + 1))
            for index in range(count):
                amount = (index + 0.5) / count
                left_x = shell_x1 + ((group_left - shell_x1) * amount)
                right_x = group_right + ((shell_x2 - group_right) * amount)
                threshold = eased if scene.direction != "inward" else 1.0 - eased
                active = amount <= threshold if scene.direction != "inward" else amount >= threshold
                if family == "hazard":
                    active = (index + int(progress * 10)) % 2 == 0
                cell_color = color if active else glow
                self.canvas.create_line(
                    left_x - 3, shell_top, left_x + 3, shell_top,
                    fill=cell_color, width=2 if active else 1, tags=tags,
                )
                self.canvas.create_line(
                    right_x - 3, shell_bottom, right_x + 3, shell_bottom,
                    fill=cell_color, width=2 if active else 1, tags=tags,
                )
            return

        if family == "resource":
            cx = group_right + ((shell_x2 - group_right) * 0.55)
            pulse = math.sin(progress * math.pi)
            radius = 3 + (pulse * 4)
            self.canvas.create_polygon(
                cx, y - radius, cx + radius, y,
                cx, y + radius, cx - radius, y,
                fill="", outline=color, width=1, tags=tags,
            )

    def _draw_navigation_marker_animation(self):
        """Animate the bootloader-derived Navigation Instrument V3."""
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

        palette = self._navigation_instrument_palette()
        self._nav_instrument.draw_state(
            model, self._nav_marker_phase, palette,
        )

        transition = getattr(self, "_nav_state_transition", None)
        if isinstance(transition, dict):
            try:
                duration = max(0.3, float(transition.get("duration", 0.68)))
                progress = (
                    time.monotonic() - float(transition.get("started"))
                ) / duration
            except (TypeError, ValueError, ZeroDivisionError):
                self._nav_state_transition = None
            else:
                if progress >= 1.0:
                    self._nav_state_transition = None
                elif progress >= 0.0:
                    self._nav_instrument.draw_transition(
                        model, transition, progress,
                    )

        event = getattr(self, "_nav_event_motion", None)
        if isinstance(event, dict):
            try:
                duration = max(0.4, float(event.get("duration", 1.3)))
                progress = (
                    time.monotonic() - float(event.get("started"))
                ) / duration
            except (TypeError, ValueError, ZeroDivisionError):
                self._nav_event_motion = None
            else:
                if progress >= 1.0:
                    self._nav_event_motion = None
                elif progress >= 0.0:
                    self._nav_instrument.draw_event(
                        model, event, progress, palette,
                    )

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
        if kind in {"survey_complete", "mapping_complete", "bio_sample"}:
            # Older/cached callers may still offer these retired survey cues.
            # Clear them before the generic chassis response draws a green
            # remnant on the right wing.
            self._nav_event_motion = None
            return
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

        self._draw_navigation_boot_event_scene(
            model, kind, progress, visible, glow, tags,
        )

        def tracer(x1, x2, amount, reverse=False, radius=2):
            amount = max(0.0, min(1.0, amount))
            start, end = (x2, x1) if reverse else (x1, x2)
            x = start + ((end - start) * amount)
            tail = x + (6 if reverse else -6)
            if reverse:
                tail = min(start, tail)
            else:
                tail = max(start, tail)
            self._draw_contrast_motion_tail(tail, x, y, glow, width=3, tags=tags)
            self._draw_contrast_motion_dot(x, y, visible, radius=radius, tags=tags)
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

        if kind in {"arrival", "arrival_neutron", "arrival_white_dwarf", "arrival_valuable", "carrier_arrival"}:
            tracer(lx1, lx2, eased, reverse=True, radius=2)
            tracer(rx1, rx2, eased, radius=2)
            if progress < 0.55:
                diamond(marker_x, 5 + (progress * 10), glow)
            if kind == "arrival_neutron":
                for radius in (7 + (progress * 8), 11 + (progress * 12)):
                    self.canvas.create_oval(
                        marker_x - radius, y - min(5, radius / 3),
                        marker_x + radius, y + min(5, radius / 3),
                        fill="", outline=glow, width=1, tags=tags,
                    )
            elif kind == "arrival_white_dwarf":
                for x in (gx1 - 5, gx2 + 5):
                    self.canvas.create_line(
                        x, y - 5, x, y + 5,
                        fill=visible, width=2, tags=tags,
                    )
            elif kind == "arrival_valuable":
                wave = math.sin(progress * math.pi)
                for radius in (5 + (wave * 3), 10 + (wave * 5)):
                    self.canvas.create_polygon(
                        marker_x, y - radius / 2,
                        marker_x + radius, y,
                        marker_x, y + radius / 2,
                        marker_x - radius, y,
                        fill="", outline=visible, width=1, tags=tags,
                    )
            elif kind == "carrier_arrival":
                spread = 4 + (progress * 15)
                for x, side in ((gx1 - spread, -1), (gx2 + spread, 1)):
                    self.canvas.create_line(
                        x, y - 4, x, y + 4,
                        fill=visible, width=2, tags=tags,
                    )
            return

        if kind == "planet_clear":
            # LeaveBody is the authoritative orbital boundary. Release two
            # packets away from the centre and collapse the last horizon ring
            # so the departure has a visible conclusion before supercruise
            # resumes its ordinary flow.
            left_x = gx1 - ((gx1 - shell_x1) * eased)
            right_x = gx2 + ((shell_x2 - gx2) * eased)
            self._draw_contrast_motion_tail(
                left_x, min(gx1, left_x + 12), shell_top,
                glow, width=2, tags=tags,
            )
            self._draw_contrast_motion_tail(
                max(gx2, right_x - 12), right_x, shell_bottom,
                glow, width=2, tags=tags,
            )
            radius = max(2.0, 11.0 * (1.0 - eased))
            self.canvas.create_arc(
                marker_x - radius, y - 1,
                marker_x + radius, y + 7,
                start=18, extent=144, style="arc",
                outline=visible, width=1, tags=tags,
            )
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
            if kind == "route_divert":
                split = lx1 + ((lx2 - lx1) * 0.55)
                tracer(lx1, split - 4, min(1.0, progress * 1.35), radius=1)
                branch_y = y - (5 * math.sin(progress * math.pi))
                self.canvas.create_line(
                    split, y, lx2, branch_y,
                    fill=visible, width=2, dash=(3, 2), tags=tags,
                )
                return
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
            if kind in {"valuable_discovery", "first_discovery", "footfall_candidate"}:
                x = tracer(rx1, rx2, eased, radius=2)
                if kind == "valuable_discovery":
                    diamond(x, 4 + (2 * math.sin(progress * math.pi)), visible)
                elif kind == "first_discovery":
                    self.canvas.create_oval(
                        x - 5, y - 3, x + 5, y + 3,
                        fill="", outline=visible, width=1, tags=tags,
                    )
                else:
                    self.canvas.create_line(
                        x - 4, y + 3, x, y - 3, x + 4, y + 3,
                        fill=visible, width=1, tags=tags,
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

        if kind in {"touchdown", "liftoff", "body_approach"}:
            reverse = kind == "liftoff"
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

        if kind in {"supercruise_enter", "supercruise_drop", "supercruise_exit"}:
            # DestinationDrop is the committed targeted drop, not the actual
            # transition to normal space. Contract once here; SupercruiseExit
            # supplies the later authoritative expansion.
            expanding = kind == "supercruise_exit"
            size = 5 + ((eased if expanding else 1.0 - eased) * 8)
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
        self._draw_navigation_activity_depth(
            model, profile, phase, color, dim, tags,
        )
        gravity_load = float(model.get("gravity_load", 0.0) or 0.0)
        if gravity_load > 0:
            # Surface gravity loads the lower chassis rather than adding a
            # duplicate numeric readout. Higher gravity widens and brightens
            # the restrained load-bearing pulse.
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            center_x = (shell_x1 + shell_x2) / 2
            max_span = (shell_x2 - shell_x1) * (0.18 + (gravity_load * 0.34))
            wave = abs((self._cycle_progress(phase, 54) * 2.0) - 1.0)
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
            travel = self._cycle_progress(phase, 64)
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

        if model.get("fuel_scooping"):
            # The main FUEL cell owns the prominent flow; this quieter intake
            # keeps the centre instrument physically connected to it.
            travel = self._cycle_progress(phase, 22)
            x1, x2 = model["route_x1"], model["route_x2"]
            for index in range(2):
                local = (travel + (index * 0.5)) % 1.0
                x = x1 + ((x2 - x1) * local)
                self._draw_contrast_motion_tail(
                    max(x1, x - 7), x, y + (2 if index else -2),
                    self._glow_color(COLOR_GREEN, 0.66),
                    width=1, tags=tags,
                )

        ship_config = model.get("ship_config") or {}
        if ship_config.get("analysis_mode"):
            scan = self._cycle_progress(phase, 34)
            x = model["group_right"] + 8 + (scan * 4)
            self.canvas.create_line(
                x, y - 3, x, y + 3,
                fill=self._glow_color(COLOR_ACCENT, 0.76), width=1, tags=tags,
            )

        if model.get("local_target"):
            target_x = model["survey_x2"]
            transition = getattr(self, "_nav_target_transition", None)
            acquisition = 1.0
            if isinstance(transition, dict):
                try:
                    acquisition = (time.monotonic() - transition["started"]) / transition["duration"]
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    acquisition = 1.0
                if acquisition >= 1.0:
                    acquisition = 1.0
                    self._nav_target_transition = None
            acquisition = max(0.0, min(1.0, acquisition))
            eased = acquisition * acquisition * (3.0 - (2.0 * acquisition))
            acquire_x = model["group_right"] + (
                (target_x - model["group_right"]) * eased
            )
            wave = abs((self._cycle_progress(phase, 40) * 2.0) - 1.0)
            radius = 2 + (wave * 2) + ((1.0 - eased) * 3)
            target_color = COLOR_YELLOW if wave < 0.66 else self._glow_color(COLOR_YELLOW, 0.7)
            self.canvas.create_oval(
                acquire_x - radius, y - radius,
                acquire_x + radius, y + radius,
                fill="", outline=target_color, width=1, tags=tags,
            )
            bracket = 5 - (eased * 2)
            for side in (-1, 1):
                bx = acquire_x + (side * (radius + 2))
                self.canvas.create_line(
                    bx, y - bracket, bx, y + bracket,
                    fill=self._glow_color(target_color, 0.68),
                    width=1, tags=tags,
                )

        if profile in {"carrier_transit", "carrier_arrival"}:
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            shell_top = model.get("shell_top", y - 6)
            shell_bottom = model.get("shell_bottom", y + 6)
            span = max(1.0, shell_x2 - shell_x1)
            if profile == "carrier_transit":
                # A carrier translates as a much larger mass: four opposing
                # packets load both hull rails while the centre aperture
                # compresses and releases like the visible jump tunnel.
                travel = self._cycle_progress(phase, 16)
                transit_dim = self._glow_color(COLOR_ORANGE, 0.68)
                for index in range(4):
                    local = (travel + (index / 4.0)) % 1.0
                    x = shell_x1 + (span * local)
                    reverse_x = shell_x2 - (span * local)
                    rail_y = shell_top if index % 2 == 0 else shell_bottom
                    self._draw_contrast_motion_tail(
                        max(shell_x1, x - 10), x, rail_y,
                        transit_dim, width=2, tags=tags,
                    )
                    self._draw_contrast_motion_tail(
                        reverse_x, min(shell_x2, reverse_x + 10), rail_y,
                        transit_dim, width=2, tags=tags,
                    )
                compression = abs((self._cycle_progress(phase, 28) * 2.0) - 1.0)
                gate = 5 + (compression * 8)
                for side in (-1, 1):
                    gate_x = marker_x + (side * gate)
                    self.canvas.create_line(
                        gate_x, y - 5, gate_x, y + 5,
                        fill=color, width=2 if compression < 0.35 else 1,
                        tags=tags,
                    )
                return

            # Arrival releases the compressed carrier aperture as a restrained
            # paired shock front. It is bounded by the CarrierJump phase, so
            # the ordinary docked indicator resumes automatically afterwards.
            wave = abs((self._cycle_progress(phase, 34) * 2.0) - 1.0)
            arrival_dim = self._glow_color(COLOR_GREEN, 0.66)
            spread = 7 + (wave * min(30.0, span * 0.12))
            for side in (-1, 1):
                x = marker_x + (side * spread)
                self.canvas.create_line(
                    x, shell_top, x, shell_bottom,
                    fill=COLOR_GREEN if wave < 0.45 else arrival_dim,
                    width=2 if wave < 0.3 else 1, tags=tags,
                )
            radius = 5 + (wave * 7)
            self.canvas.create_oval(
                marker_x - radius, y - min(5, radius / 2),
                marker_x + radius, y + min(5, radius / 2),
                fill="", outline=arrival_dim, width=1, tags=tags,
            )
            return

        if profile in {"surface_departure", "orbital_departure"}:
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            shell_top = model.get("shell_top", y - 6)
            shell_bottom = model.get("shell_bottom", y + 6)
            departure = model.get("surface_approach") or {}
            try:
                climb = max(0.0, -float(departure.get("descent_mps") or 0.0))
            except (TypeError, ValueError):
                climb = 0.0
            departure_dim = self._glow_color(color, 0.68)

            if profile == "surface_departure":
                # Rising ladder ticks pull away from a contracting horizon.
                # Their pace responds modestly to actual Status altitude gain.
                period = max(10.0, 27.0 - min(14.0, climb / 6.0))
                travel = 1.0 - self._cycle_progress(phase, period)
                for side in (-1, 1):
                    x = marker_x + (side * 11)
                    for index in range(3):
                        local = (travel + (index / 3.0)) % 1.0
                        tick_y = (y - 7) + (local * 14)
                        self.canvas.create_line(
                            x - 3, tick_y, x + 3, tick_y,
                            fill=color if index == 0 else departure_dim,
                            width=1, tags=tags,
                        )
                recede = abs((self._cycle_progress(phase, 34) * 2.0) - 1.0)
                horizon_span = 12 - (recede * 5)
                self.canvas.create_line(
                    marker_x - horizon_span, y + 5,
                    marker_x + horizon_span, y + 5,
                    fill=departure_dim, width=2, tags=tags,
                )
                return

            # Once supercruise engages, paired packets radiate away from the
            # planet aperture toward both ends of the navigation chassis.
            travel = self._cycle_progress(phase, 20)
            for index in range(2):
                local = (travel + (index * 0.5)) % 1.0
                left_x = model["group_left"] - (
                    (model["group_left"] - shell_x1) * local
                )
                right_x = model["group_right"] + (
                    (shell_x2 - model["group_right"]) * local
                )
                rail_y = shell_top if index == 0 else shell_bottom
                self._draw_contrast_motion_tail(
                    left_x, min(model["group_left"], left_x + 9), rail_y,
                    departure_dim, width=2, tags=tags,
                )
                self._draw_contrast_motion_tail(
                    max(model["group_right"], right_x - 9), right_x, rail_y,
                    departure_dim, width=2, tags=tags,
                )
            recede = self._cycle_progress(phase, 40)
            radius = 9 - (recede * 4)
            self.canvas.create_arc(
                marker_x - radius, y,
                marker_x + radius, y + 7,
                start=18, extent=144, style="arc",
                outline=departure_dim, width=1, tags=tags,
            )
            return

        if profile in {"orbital_approach", "glide", "surface_approach", "surface_hold"}:
            # ApproachBody owns the orbital phase; Status' glide bit and live
            # altitude then deepen the same visual language. Motion stays on
            # the chassis rails so the state and altitude text remain stable.
            approach = model.get("surface_approach") or {}
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            shell_top = model.get("shell_top", y - 6)
            shell_bottom = model.get("shell_bottom", y + 6)
            try:
                descent = float(approach.get("descent_mps") or 0.0)
            except (TypeError, ValueError):
                descent = 0.0
            alert_color = COLOR_YELLOW if descent > 40 else color
            approach_dim = self._glow_color(alert_color, 0.68)

            if profile == "surface_hold":
                # No directional ladder while hovering: a slow, symmetric
                # altitude bracket keeps the instrument alive without implying
                # descent or departure.
                breathe = abs((self._cycle_progress(phase, 76) * 2.0) - 1.0)
                bracket = 10 + (breathe * 2)
                for side in (-1, 1):
                    x = marker_x + (side * bracket)
                    self.canvas.create_line(
                        x, y - 4, x, y + 4,
                        fill=approach_dim, width=1, tags=tags,
                    )
                    self.canvas.create_line(
                        x, y - 4, x - (side * 3), y - 4,
                        fill=color, width=1, tags=tags,
                    )
                    self.canvas.create_line(
                        x, y + 4, x - (side * 3), y + 4,
                        fill=color, width=1, tags=tags,
                    )
                self.canvas.create_line(
                    marker_x - 9, y + 5, marker_x + 9, y + 5,
                    fill=approach_dim, width=2, tags=tags,
                )
                return

            if profile == "orbital_approach":
                # Paired packets repeatedly converge from orbital space toward
                # the planet aperture, with a slow horizon sweep beneath it.
                travel = self._cycle_progress(phase, 24)
                for index in range(2):
                    local = (travel + (index * 0.5)) % 1.0
                    left_x = shell_x1 + ((model["group_left"] - shell_x1) * local)
                    right_x = shell_x2 - ((shell_x2 - model["group_right"]) * local)
                    rail_y = shell_top if index == 0 else shell_bottom
                    self._draw_contrast_motion_tail(
                        max(shell_x1, left_x - 8), left_x, rail_y,
                        approach_dim, width=1, tags=tags,
                    )
                    self._draw_contrast_motion_tail(
                        right_x, min(shell_x2, right_x + 8), rail_y,
                        approach_dim, width=1, tags=tags,
                    )
                horizon = abs((self._cycle_progress(phase, 42) * 2.0) - 1.0)
                radius = 5 + (horizon * 4)
                self.canvas.create_arc(
                    marker_x - radius, y - 1,
                    marker_x + radius, y + 7,
                    start=18, extent=144, style="arc",
                    outline=approach_dim, width=1, tags=tags,
                )
                return

            if profile == "glide":
                # Glide is deliberately faster and sharper: staggered streaks
                # collapse from both rails while vertical gates fall through
                # the centre, making this phase unmistakable at a glance.
                travel = self._cycle_progress(phase, 9)
                span = max(1.0, shell_x2 - shell_x1)
                for index in range(4):
                    local = (travel + (index / 4.0)) % 1.0
                    x = shell_x1 + (span * local)
                    rail_y = shell_top if index % 2 == 0 else shell_bottom
                    slope = 3 if index % 2 == 0 else -3
                    self.canvas.create_line(
                        x - 8, rail_y - slope, x, rail_y,
                        fill=alert_color if index in {0, 2} else approach_dim,
                        width=2 if index in {0, 2} else 1, tags=tags,
                    )
                fall = self._cycle_progress(phase, 12)
                gate_y = (y - 8) + (fall * 16)
                for x in (model["group_left"] - 6, model["group_right"] + 6):
                    self.canvas.create_line(
                        x - 3, gate_y - 2, x, gate_y + 2, x + 3, gate_y - 2,
                        fill=alert_color, width=1, tags=tags,
                    )
                return

            # Below glide, a descending altitude ladder moves toward the lower
            # horizon. It reverses when climbing and accelerates modestly with
            # descent rate without turning the indicator into a warning flash.
            period = max(10.0, 26.0 - min(14.0, abs(descent) / 6.0))
            travel = self._cycle_progress(phase, period)
            if descent < -1.0:
                travel = 1.0 - travel
            for side in (-1, 1):
                x = marker_x + (side * 11)
                for index in range(3):
                    local = (travel + (index / 3.0)) % 1.0
                    tick_y = (y - 7) + (local * 14)
                    self.canvas.create_line(
                        x - 3, tick_y, x + 3, tick_y,
                        fill=alert_color if index == 0 else approach_dim,
                        width=1, tags=tags,
                    )
            horizon_wave = abs((self._cycle_progress(phase, 30) * 2.0) - 1.0)
            horizon_span = 7 + (horizon_wave * 5)
            self.canvas.create_line(
                marker_x - horizon_span, y + 5,
                marker_x + horizon_span, y + 5,
                fill=approach_dim, width=2, tags=tags,
            )
            return

        if profile == "supercruise_overcharge":
            # SCO is a sustained live Status state, so its motion continues
            # for exactly as long as Flags2 bit 20 remains set. Four staggered
            # packets tear forward across alternating chassis rails while the
            # centre aperture compresses under the overcharge load.
            shell_x1 = model.get("shell_x1", model["route_x1"]) + 7
            shell_x2 = model.get("shell_x2", model["survey_x2"]) - 7
            shell_top = model.get("shell_top", y - 6)
            shell_bottom = model.get("shell_bottom", y + 6)
            travel = self._cycle_progress(phase, 7)
            overcharge_dim = self._glow_color(color, 0.68)
            for index in range(4):
                local = (travel + (index / 4.0)) % 1.0
                x = shell_x1 + ((shell_x2 - shell_x1) * local)
                rail_y = shell_top if index % 2 == 0 else shell_bottom
                packet_color = color if index in {0, 2} else overcharge_dim
                self._draw_contrast_motion_tail(
                    max(shell_x1, x - 13), x, rail_y,
                    packet_color, width=2, tags=tags,
                )
                self._draw_contrast_motion_dot(
                    x, rail_y, packet_color, radius=1, tags=tags,
                )
            compression = abs((self._cycle_progress(phase, 10) * 2.0) - 1.0)
            aperture = 3 + ((1.0 - compression) * 4)
            for side in (-1, 1):
                x = marker_x + (side * aperture)
                self.canvas.create_line(
                    x - (side * 4), y - 4,
                    x, y,
                    x - (side * 4), y + 4,
                    fill=color if compression < 0.55 else overcharge_dim,
                    width=2, tags=tags,
                )
            # A small alternating turbulence shear makes SCO unmistakable
            # without shaking or moving the readable state label itself.
            shear = 2 if int(phase // 2) % 2 == 0 else -2
            for x in (model["group_left"] - 7, model["group_right"] + 7):
                self.canvas.create_line(
                    x - 3, y + shear, x + 3, y - shear,
                    fill=overcharge_dim, width=1, tags=tags,
                )
            return

        if profile == "fsd_lock":
            wave = abs((self._cycle_progress(phase, 26) * 2.0) - 1.0)
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
            # Pull energy into the FSD aperture on the centre rail while two
            # quieter packets chase it along the upper/lower chassis. The
            # stagger keeps a five-second high-wake countdown visibly alive
            # instead of showing one chevron crawl followed by dead space.
            travel = self._cycle_progress(phase, 12)
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
            charge_dim = self._glow_color(color, 0.68)
            for index, rail_y in enumerate((y - 3, y + 3)):
                local = (travel + (index * 0.5)) % 1.0
                packet_left = model["route_x1"] + (
                    (model["route_x2"] - model["route_x1"]) * local
                )
                packet_right = model["survey_x2"] - (
                    (model["survey_x2"] - model["survey_x1"]) * local
                )
                self._draw_contrast_motion_tail(
                    max(model["route_x1"], packet_left - 7),
                    packet_left, rail_y, charge_dim, width=1, tags=tags,
                )
                self._draw_contrast_motion_tail(
                    packet_right,
                    min(model["survey_x2"], packet_right + 7),
                    rail_y, charge_dim, width=1, tags=tags,
                )
            compression = abs((self._cycle_progress(phase, 12) * 2.0) - 1.0)
            ring = 4 + ((1.0 - compression) * 3)
            self.canvas.create_polygon(
                marker_x, y - ring,
                marker_x + ring, y,
                marker_x, y + ring,
                marker_x - ring, y,
                fill="", outline=charge_dim, width=1, tags=tags,
            )
            return

        if profile == "fsd_cooldown":
            travel = self._cycle_progress(phase, 24)
            for index in range(2):
                local = (travel + (index * 0.5)) % 1.0
                offset = 3 + (local * 19)
                fade = color if local < 0.5 else dim
                y_offset = -2 if index == 0 else 2
                for x in (model["group_left"] - offset, model["group_right"] + offset):
                    self.canvas.create_line(
                        x, y + y_offset - 2, x, y + y_offset + 2,
                        fill=fade, width=1, tags=tags,
                    )
            return

        if profile == "arrival":
            travel = self._cycle_progress(phase, 20)
            for index in range(2):
                local = (travel + (index * 0.5)) % 1.0
                radius = 3 + (local * 15)
                fade = color if local < 0.42 else dim
                self.canvas.create_line(
                    marker_x - radius, y,
                    marker_x + radius, y,
                    fill=self._glow_color(fade, 0.52), width=1, tags=tags,
                )
                self.canvas.create_oval(
                    marker_x - radius, y - min(5, radius / 2),
                    marker_x + radius, y + min(5, radius / 2),
                    fill="", outline=fade, width=1, tags=tags,
                )
            return

        if profile == "docked":
            # Two clamps hold the whole annunciator: visibly powered, but locked.
            wave = abs((self._cycle_progress(phase, 32) * 2.0) - 1.0)
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
            wave = abs((self._cycle_progress(phase, 30) * 2.0) - 1.0)
            spread = 3 + (wave * 4)
            for x in (model["group_left"] - spread, model["group_right"] + spread):
                self.canvas.create_oval(x - 1, y + 2, x + 1, y + 4,
                                        fill=color, outline="", tags=tags)
            return

        if profile == "on_foot":
            # Alternating points evoke steps without adding a literal foot icon.
            active = int(phase // 6) % 2
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
            active = int(phase // 4) % 3
            start_x = model["group_left"] - 18
            for index in range(3):
                x = start_x + (index * 5)
                fill = color if index == active else dim
                self.canvas.create_rectangle(x, y - 1, x + 2, y + 1,
                                             fill=fill, outline="", tags=tags)
            return

        if profile == "scanner":
            # The connected activity path owns the complete acquisition flow.
            return

        if profile == "map":
            # The connected activity path owns the complete chart flow.
            return

        if profile == "jump":
            # Witch-space reverses the charge language: three high-speed
            # packets burst out from the aperture on opposing rails, forming
            # a compact tunnel effect without covering the state label.
            travel = self._cycle_progress(phase, 9)
            jump_dim = self._glow_color(color, 0.68)
            left_origin = model["route_x2"]
            right_origin = model["survey_x1"]
            for index in range(3):
                local = (travel + (index / 3.0)) % 1.0
                left_x = left_origin - ((left_origin - model["route_x1"]) * local)
                right_x = right_origin + ((model["survey_x2"] - right_origin) * local)
                rail_y = y - 3 if index % 2 == 0 else y + 3
                packet_color = color if index == 0 else jump_dim
                self._draw_contrast_motion_tail(
                    left_x,
                    min(left_origin, left_x + 9),
                    rail_y, packet_color, width=2, tags=tags,
                )
                self._draw_contrast_motion_tail(
                    max(right_origin, right_x - 9),
                    right_x,
                    (y + 3) if rail_y == y - 3 else (y - 3),
                    packet_color, width=2, tags=tags,
                )
            tunnel_wave = abs((self._cycle_progress(phase, 18) * 2.0) - 1.0)
            tunnel_radius = 4 + (tunnel_wave * 3)
            self.canvas.create_oval(
                marker_x - tunnel_radius, y - min(5, tunnel_radius),
                marker_x + tunnel_radius, y + min(5, tunnel_radius),
                fill="", outline=jump_dim, width=1, tags=tags,
            )
            return

        if profile == "combat":
            # Alternating alert brackets remain deliberately quieter than a flash.
            bright_left = (int(phase // 5) % 2) == 0
            for x, bright in ((model["group_left"] - 5, bright_left),
                              (model["group_right"] + 5, not bright_left)):
                self.canvas.create_line(x, y - 4, x, y + 4,
                                        fill=color if bright else dim, width=1, tags=tags)
            return

    def _draw_navigation_activity_depth(self, model, profile, phase, color, dim, tags):
        """Render a boot-inspired persistent scene through the full chassis."""
        marker_x = model["marker_x"]
        y = model["y"]
        left_x1 = model.get("left_x1", model["route_x1"])
        left_x2 = model.get("left_x2", model["route_x2"])
        right_x1 = model.get("right_x1", model["survey_x1"])
        right_x2 = model.get("right_x2", model["survey_x2"])
        group_left = model["group_left"]
        group_right = model["group_right"]
        full_span = right_x2 - left_x1
        if left_x2 - left_x1 < 4 or right_x2 - right_x1 < 4 or full_span < 20:
            return

        scene = state_scene(profile)
        # High-energy transitions such as FSD charge, hyperspace, glide and
        # carrier transit keep their stronger dedicated renderer below.
        if scene.family == "dedicated":
            return
        period = scene.period
        if model.get("fuel_scooping"):
            period *= 0.78
        elif (model.get("surface_approach") or {}).get("active"):
            period *= 1.12

        shell_top = model.get("shell_top", y - 6)
        shell_bottom = model.get("shell_bottom", y + 6)
        self._draw_navigation_boot_aperture(
            model, scene, phase, color, dim, tags,
        )
        self._draw_navigation_readiness_cells(
            model, scene, phase, color, dim, tags,
        )
        packet_count = max(0, int(scene.packets))
        packet_width = 2 if scene.intensity >= 0.76 else 1
        head_color = color
        trail_color = color if scene.family == "route" else self._glow_color(
            color, min(0.78, scene.intensity),
        )

        def path_point(progress, rail_y):
            """Follow the centre rail, rising around rather than over its label."""
            progress = max(0.0, min(1.0, float(progress)))
            x = left_x1 + (full_span * progress)
            if x <= left_x2:
                return x, y
            if x < group_left:
                blend = (x - left_x2) / max(1.0, group_left - left_x2)
                return x, y + ((rail_y - y) * blend)
            if x <= group_right:
                return x, rail_y
            if x < right_x1:
                blend = (x - group_right) / max(1.0, right_x1 - group_right)
                return x, rail_y + ((y - rail_y) * blend)
            return x, y

        def draw_packet(progress, rail_y, packet_color, index):
            # Sample the short tail so it bends through both centre couplers;
            # a plain straight line would visually jump across the label.
            tail_fraction = min(0.11, 13.0 / full_span)
            tail_start = max(0.0, progress - tail_fraction)
            samples = 6
            points = []
            for sample in range(samples):
                local = tail_start + ((progress - tail_start) * sample / (samples - 1))
                points.extend(path_point(local, rail_y))
            if len(points) >= 4:
                self.canvas.create_line(
                    *points, fill="#010101", width=packet_width + 2,
                    tags=tags,
                )
                self.canvas.create_line(
                    *points, fill=packet_color, width=packet_width,
                    tags=tags,
                )

            x, py = path_point(progress, rail_y)
            if x < group_left:
                # Input geometry identifies the activity before it reaches
                # the state core; mobile, chart and stationary states do not
                # all masquerade as the same travelling light.
                if scene.family == "readiness":
                    self.canvas.create_rectangle(
                        x - 5, py - 2, x, py + 2,
                        fill="", outline=head_color, width=1, tags=tags,
                    )
                elif scene.family == "horizon":
                    self.canvas.create_line(
                        x - 5, py + 2, x, py + 2, x, py - 2,
                        fill=head_color, width=1, tags=tags,
                    )
                elif scene.family == "plot":
                    self.canvas.create_line(
                        x - 4, py - 3, x - 4, py + 3,
                        x, py + 3, x, py - 3,
                        fill=head_color, width=1, tags=tags,
                    )
                elif profile == "surface_vehicle":
                    self.canvas.create_rectangle(
                        x - 5, py - 2, x, py + 2,
                        fill=head_color, outline="", tags=tags,
                    )
                elif profile == "on_foot":
                    self.canvas.create_line(
                        x - 4, py + 3, x - 2, py - 2, x, py + 3,
                        fill=head_color, width=1, tags=tags,
                    )
                else:
                    self.canvas.create_line(
                        x - 4, py - 3, x, py, x - 4, py + 3,
                        fill=head_color, width=packet_width, tags=tags,
                    )
                if profile == "fighter":
                    self.canvas.create_line(
                        x - 7, py - 2, x - 4, py, x - 7, py + 2,
                        fill=packet_color, width=1, tags=tags,
                    )
                elif scene.family == "scope":
                    self.canvas.create_line(
                        x - 6, py - 4, x - 3, py - 1,
                        x - 6, py + 4, x - 3, py + 1,
                        fill=packet_color, width=1, tags=tags,
                    )
            elif x <= group_right:
                # Processing through the state core: energy becomes a rail
                # slash, leaving the readable centre label completely clear.
                tilt = -1 if (index % 2) else 1
                if scene.family == "scope":
                    self.canvas.create_line(
                        x - 3, py - 3, x + 3, py + 3,
                        x - 3, py + 3, x + 3, py - 3,
                        fill=head_color, width=1, tags=tags,
                    )
                elif scene.family == "plot":
                    self.canvas.create_rectangle(
                        x - 3, py - 3, x + 3, py + 3,
                        fill="", outline=head_color, width=1, tags=tags,
                    )
                else:
                    self.canvas.create_line(
                        x - 3, py - (3 * tilt), x + 3, py + (3 * tilt),
                        fill=head_color, width=packet_width, tags=tags,
                    )
                if abs(x - marker_x) < 4:
                    self.canvas.create_line(
                        marker_x - 5, rail_y, marker_x + 5, rail_y,
                        fill=head_color, width=2, tags=tags,
                    )
            else:
                # Output energy resolves as a gate rather than repeating the
                # input chevron, so the flow visibly transforms left-to-right.
                gate_half = 4 if scene.family in {"scope", "plot", "readiness"} else 3
                self.canvas.create_line(
                    x, py - gate_half, x, py + gate_half,
                    fill=head_color, width=packet_width, tags=tags,
                )
                self.canvas.create_line(
                    x, py - gate_half, x + 4, py - gate_half,
                    x, py + gate_half, x + 4, py + gate_half,
                    fill=packet_color, width=1, tags=tags,
                )
                if profile in {"surface_vehicle", "on_foot", "landed"}:
                    self.canvas.create_line(
                        x - 2, py + gate_half + 1,
                        x + 4, py + gate_half + 1,
                        fill=dim, width=1, tags=tags,
                    )

        for index in range(packet_count):
            packet_phase = phase + (index * (period / packet_count))
            progress = self._cycle_progress(packet_phase, period)
            rail_y = shell_top if index % 2 == 0 else shell_bottom
            packet_color = trail_color if index else head_color
            draw_packet(progress, rail_y, packet_color, index)

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
        travel = context.get("fsd_readiness") or {}
        travel_state = str(travel.get("state") or "").casefold()
        if travel_state in {"carrier_transit", "carrier_arrival"}:
            target = str(travel.get("target") or "").strip()
            detail = f" · {target}" if target else ""
            if travel_state == "carrier_transit":
                return f"CARRIER TRANSIT{detail}", COLOR_ORANGE
            return f"CARRIER ARRIVAL{detail}", COLOR_GREEN
        neutron_boost = context.get("neutron_boost") or {}
        if neutron_boost.get("armed"):
            try:
                boost_value = float(neutron_boost.get("value"))
                boost_text = f" · {boost_value:.1f}X"
            except (TypeError, ValueError):
                boost_text = ""
            return f"NEUTRON BOOST ARMED{boost_text}", COLOR_ACCENT
        if context.get("fuel_scooping"):
            try:
                fuel_text = f" · {float(context.get('fuel_percent')):.0f}%"
            except (TypeError, ValueError):
                fuel_text = ""
            return f"FUEL SCOOP ACTIVE{fuel_text}", COLOR_GREEN
        next_star = context.get("next_star") or {}
        star_class = str(next_star.get("star_class") or "").upper()
        star_label = str(next_star.get("star_label") or star_class or "STAR").upper()
        if next_star.get("fuel_risk") in {"warn", "alert"}:
            return (
                f"RANGE WARNING · NEXT {star_label}",
                COLOR_ORANGE if next_star.get("fuel_risk") == "alert" else COLOR_YELLOW,
            )
        if context.get("docked") and context.get("station"):
            return f"STATION · {context['station']}", COLOR_ACCENT
        approach = context.get("surface_approach") or {}
        if approach.get("active"):
            phase = str(approach.get("phase") or "surface").casefold()
            body_name = str(approach.get("body") or "").strip()
            if phase == "orbital":
                detail = f" · {body_name}" if body_name else ""
                return f"ORBITAL APPROACH{detail}", COLOR_ACCENT
            if phase == "orbital_departure":
                detail = f" · {body_name}" if body_name else ""
                return f"ORBITAL DEPARTURE{detail}", COLOR_ACCENT
            try:
                altitude = float(approach.get("altitude_m"))
                altitude_text = (
                    f"{altitude / 1000:.1f} KM" if altitude >= 1000 else f"{altitude:.0f} M"
                )
            except (TypeError, ValueError):
                altitude_text = "ALT --"
            try:
                descent = float(approach.get("descent_mps") or 0.0)
            except (TypeError, ValueError):
                descent = 0.0
            motion = "DESCENT" if descent > 1 else "CLIMB" if descent < -1 else "HOLD"
            if phase == "surface_departure":
                label = "SURFACE DEPARTURE"
            elif phase == "hold":
                return f"SURFACE HOLD · {altitude_text}", COLOR_ACCENT
            else:
                label = "GLIDE" if phase == "glide" else "SURFACE APPROACH"
            return f"{label} · {altitude_text} · {motion}", COLOR_YELLOW
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
        if next_star.get("name") and star_class:
            scoop = next_star.get("scoopable")
            scoop_text = "SCOOPABLE" if scoop is True else "UNSCOOPABLE" if scoop is False else "CLASS UNKNOWN"
            dry = int(next_star.get("consecutive_unscoopable") or 0)
            dry_text = f" · DRY {dry}" if dry >= 2 else ""
            return f"NEXT STAR · {star_label} · {scoop_text}{dry_text}", (
                COLOR_YELLOW if scoop is False else COLOR_ACCENT
            )
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
        track = context.get("route_track") or {}
        track_hops = list(track.get("hops") or []) if isinstance(track, dict) else []
        next_star = context.get("next_star") or {}
        active = source != "NO ROUTE" and target not in ("", "---")
        complete = bool(
            track_hops
            and not any(hop.get("next") for hop in track_hops)
            and any(hop.get("completed") or hop.get("current") for hop in track_hops)
        )
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
            progress_text = f"{current_pos}/{total} STOPS"

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
        if complete:
            target = str(track_hops[-1].get("name") or target or "ROUTE END").upper()
            meta_parts = ["ROUTE COMPLETE"]
        elif not active:
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
            "complete": complete,
            "hops": hops,
            "track_hops": track_hops,
            "next_star": dict(next_star) if isinstance(next_star, dict) else {},
            "track_origin_current": bool(track.get("origin_current", True))
            if isinstance(track, dict) else True,
        }

    @staticmethod
    def _classic_route_header_parts(route, nav_context, route_waypoint=False):
        """Split route data across the original left/centre/right header."""
        if not route.get("active"):
            return "NO ACTIVE ROUTE", "", ""
        if route_waypoint:
            left_parts = (route.get("target"), route.get("progress_text"))
        else:
            left_parts = (
                route.get("progress_text") or route.get("source"),
                route.get("jump_text"),
            )
        left = " · ".join(str(part) for part in left_parts if part)
        center = str((nav_context or {}).get("next_distance") or "")
        if center == "--":
            center = ""
        next_star = route.get("next_star") or {}
        star_class = str(next_star.get("star_class") or "").upper()
        if star_class and len(star_class) <= 4 and "_" not in star_class:
            center = f"{center} · {star_class}" if center else star_class
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
        self._route_track_model = None
        active = bool(route.get("active"))
        color = COLOR_ORANGE if active else "#7d8891"
        if self._crt_enabled():
            glow = self._glow_color(color, 0.22 if self._crt_intensity() == "Subtle" else 0.32)
            self.canvas.create_line(x1, y, x2, y, fill=glow, width=5)
        self.canvas.create_line(x1, y, x2, y, fill="#1a2530", width=2)

        hops = list(route.get("track_hops") or route.get("hops") or [])
        if hops:
            pip_positions, dense = route_strip.pip_layout(x1, x2, hops)
            route_strip.draw_pip_line(
                self.canvas, x1, x2, y, hops,
                {
                    "accent": COLOR_ACCENT,
                    "orange": COLOR_ORANGE,
                    "completed": self._glow_color(COLOR_ACCENT, 0.52),
                    "pending": self._glow_color(COLOR_ORANGE, 0.68),
                    "next": (
                        COLOR_ORANGE if (route.get("next_star") or {}).get("fuel_risk") == "alert"
                        else COLOR_YELLOW if (route.get("next_star") or {}).get("scoopable") is False
                        else COLOR_ORANGE
                    ),
                },
                dot_radius=dot_radius, bg="#010101",
            )
        elif active:
            pip_positions, dense = [x2], False
            self.canvas.create_line(x1, y, x2, y, fill=COLOR_ORANGE, width=2, dash=(4, 3))
            self.canvas.create_polygon(
                x2, y - 5, x2 + 5, y, x2, y + 5, x2 - 5, y,
                fill="#010101", outline=COLOR_ORANGE, width=2,
            )

        current_index = next(
            (index for index, hop in enumerate(hops) if hop.get("current")),
            -1,
        )
        next_index = next(
            (index for index, hop in enumerate(hops) if hop.get("next")),
            -1,
        )
        origin_current = bool(route.get("track_origin_current", True))
        current_x = (
            pip_positions[current_index]
            if current_index >= 0 and current_index < len(pip_positions)
            else x1
        )
        next_x = (
            pip_positions[next_index]
            if next_index >= 0 and next_index < len(pip_positions)
            else None
        )

        # The origin remains visible after departure, while the cyan current
        # marker advances through the fixed route geometry.
        origin_color = COLOR_ACCENT if origin_current else self._glow_color(COLOR_ACCENT, 0.52)
        self.canvas.create_oval(
            x1 - dot_radius - 1, y - dot_radius - 1,
            x1 + dot_radius + 1, y + dot_radius + 1,
            outline=origin_color if hops or active else "#7d8891",
            width=2, fill="#010101",
        )
        if origin_current and (hops or active):
            self.canvas.create_oval(
                x1 - 1.5, y - 1.5, x1 + 1.5, y + 1.5,
                fill=COLOR_ACCENT, outline="",
            )
        if hops or active:
            self._route_track_model = {
                "x1": float(x1),
                "x2": float(x2),
                "y": float(y),
                "pip_positions": tuple(float(x) for x in pip_positions),
                "dense": bool(dense),
                "dot_radius": max(2, int(dot_radius)),
                "hop_count": max(1, len(hops)),
                "origin_current": origin_current,
                "current_x": float(current_x),
                "next_x": float(next_x) if next_x is not None else None,
            }

    @staticmethod
    def _mix_color(first, second, amount):
        """Blend two #RRGGBB colours for theme-aware motion gradients."""
        try:
            amount = max(0.0, min(1.0, float(amount)))
            left = str(first).lstrip("#")
            right = str(second).lstrip("#")
            if len(left) != 6 or len(right) != 6:
                raise ValueError
            mixed = []
            for index in (0, 2, 4):
                start = int(left[index:index + 2], 16)
                end = int(right[index:index + 2], 16)
                mixed.append(round(start + ((end - start) * amount)))
            return "#" + "".join(f"{value:02x}" for value in mixed)
        except (TypeError, ValueError):
            return second

    def _draw_route_track_animation(self):
        """Confirm arrival, then hand navigation to only the next route pip."""
        self.canvas.delete("nav_route_motion")
        model = self._route_track_model
        if not model or self.config.get("reduced_motion_enabled", False):
            return
        try:
            if (not self.win.winfo_viewable()
                    or str(self.win.state()) in ("withdrawn", "iconic")):
                return
        except Exception:
            return

        event = self._nav_event_motion
        arrival_kinds = {
            "arrival", "arrival_neutron", "arrival_white_dwarf",
            "arrival_valuable", "carrier_arrival",
        }
        if not isinstance(event, dict) or event.get("kind") not in arrival_kinds:
            return
        try:
            duration = max(0.4, float(event.get("duration", 1.8)))
            progress = (time.monotonic() - float(event.get("started"))) / duration
        except (TypeError, ValueError, ZeroDivisionError):
            return
        if progress < 0.0 or progress >= 1.0:
            return

        x1, x2, y = model["x1"], model["x2"], model["y"]
        current_x = model.get("current_x", x1)
        next_x = model.get("next_x")
        if x2 <= x1 or next_x is None or next_x <= current_x:
            return
        dense = model["dense"]
        base_radius = model["dot_radius"]

        # Stage one: acknowledge that the former target is now CURRENT.
        if progress < 0.38:
            local = min(1.0, progress / 0.38)
            wave = math.sin(local * math.pi)
            radius = base_radius + 2 + (wave * 4)
            self.canvas.create_oval(
                current_x - radius, y - radius,
                current_x + radius, y + radius,
                fill="", outline=self._glow_color(
                    COLOR_ACCENT, 0.62 + (wave * 0.38),
                ), width=2 if wave > 0.55 else 1,
                tags="nav_route_motion",
            )

        # Stage two: arm only the first upcoming leg. Remaining route pips do
        # not animate, so the strip still communicates a sequence of jumps.
        flow_start, flow_end = 0.16, 0.72
        if flow_start <= progress <= flow_end:
            local = (progress - flow_start) / (flow_end - flow_start)
            eased = local * local * (3.0 - (2.0 * local))
            x = current_x + ((next_x - current_x) * eased)
            packet_color = self._mix_color(COLOR_ACCENT, COLOR_ORANGE, eased)
            self._draw_contrast_motion_tail(
                max(current_x, x - 12), x, y,
                packet_color, width=2, tags="nav_route_motion",
            )
            self._draw_contrast_motion_dot(
                x, y, packet_color, radius=1.5, tags="nav_route_motion",
            )

        # Stage three: confirm the newly selected next waypoint with one
        # bounded pulse instead of a permanent or repeating destination glow.
        if progress >= 0.56:
            local = min(1.0, (progress - 0.56) / 0.44)
            wave = math.sin(local * math.pi)
            next_color = self._mix_color(COLOR_ACCENT, COLOR_ORANGE, local)
            if dense:
                radius = 3 + (wave * 4)
                self.canvas.create_oval(
                    next_x - radius, y - radius,
                    next_x + radius, y + radius,
                    fill="", outline=next_color,
                    width=2 if wave > 0.55 else 1,
                    tags="nav_route_motion",
                )
            else:
                radius = base_radius + 2 + (wave * 4)
                self.canvas.create_oval(
                    next_x - radius, y - radius,
                    next_x + radius, y + radius,
                    fill="", outline=next_color,
                    width=2 if wave > 0.55 else 1,
                    tags="nav_route_motion",
                )

    def _draw_fuel_scoop_animation(self):
        """Flow energy into the live fuel readout only while Status says scooping."""
        self.canvas.delete("nav_fuel_motion")
        model = self._nav_fuel_model
        if (not model or not model.get("active")
                or self.config.get("reduced_motion_enabled", False)):
            return
        try:
            if not self.win.winfo_viewable():
                return
        except Exception:
            return
        x1, x2, y = model["x1"], model["x2"], model["y"]
        span = max(1.0, x2 - x1)
        base = self._cycle_progress(self._nav_marker_phase, 24)
        dim = self._glow_color(COLOR_GREEN, 0.58)
        self.canvas.create_line(
            x1, y, x2, y, fill=self._glow_color(COLOR_GREEN, 0.34),
            width=1, tags="nav_fuel_motion",
        )
        for index in range(3):
            local = (base + (index / 3.0)) % 1.0
            # Scoop flow converges on the displayed tank value at the right.
            x = x1 + (span * local)
            self._draw_contrast_motion_tail(
                max(x1, x - 8), x, y,
                dim, width=1, tags="nav_fuel_motion",
            )
            self._draw_contrast_motion_dot(
                x, y, COLOR_GREEN, radius=1, tags="nav_fuel_motion",
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
            marker_center, 21, state_text, state_color,
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
            fuel_scooping=nav_context.get("fuel_scooping"),
            surface_approach=nav_context.get("surface_approach"),
            ship_config=nav_context.get("ship_config"),
        )
        self._draw_section_rule(16, w - 16, 42)

        # The current system is the primary landmark, held by a lit locator rail.
        self._draw_locator_rail(17, 55, 78)
        self.draw_text(27, 55, text="CURRENT SYSTEM", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self._draw_region_label(nav_context, 325, 55, max_width=270)
        self.draw_fitted_text(
            27, 74, str(current_display).upper(), COLOR_TEXT,
            size=14, min_size=11, max_width=w - 43, anchor="w",
        )
        self._draw_section_rule(16, w - 16, 87)

        # Original split route header: target/status, next leg, total distance.
        left_x, right_x = 16, w - 16
        route_color = COLOR_ACCENT if route.get("complete") else (
            COLOR_ORANGE if route["active"] else "#7d8891"
        )
        self.draw_fitted_text(left_x, 103, route_header, route_color,
                              size=10, min_size=9, max_width=215, anchor="w")
        self.draw_fitted_text(w / 2, 103, next_distance, route_color,
                              size=10, min_size=9, max_width=90, anchor="center")
        self.draw_fitted_text(right_x, 103, route_distance, COLOR_ORANGE,
                              size=10, min_size=9, max_width=175, anchor="e")
        self._draw_route_track(left_x, right_x, 121, route, dot_radius=4)
        route_model = self._route_track_model or {}
        origin_current = bool(route_model.get("origin_current", True))
        self.draw_text(left_x, 138, text="CURRENT" if origin_current else "START",
                       fill=COLOR_ACCENT if origin_current else self._glow_color(COLOR_ACCENT, 0.52),
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(right_x, 138,
                       text="DEST" if route["active"] or route.get("track_hops") else "NEXT",
                       fill=route_color,
                       font=("Courier", 10, "bold"), anchor="e")
        self._draw_section_rule(16, w - 16, 149)

        # Original scan block, retaining the newer accurate survey state.
        self.draw_text(16, 165, text="SYSTEM SURVEY", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(w - 16, 165, text=scan_progress_text, fill=scan_color,
                       font=("Courier", 12, "bold"), anchor="e")
        self._draw_progress_track(16, w - 16, 177, pct, scan_color)
        self._draw_section_rule(16, w - 16, 192)

        self._draw_inline_metrics(16, w - 16, 207, survey_metrics, value_size=12)
        self._nav_fuel_model = {
            "active": bool(nav_context.get("fuel_scooping")),
            "x1": 24.0, "x2": 156.0, "y": 220.0,
        }

        self.draw_fitted_text(16, 230, context_text, context_color,
                              size=10, min_size=9, max_width=w - 32 - 142, anchor="w")
        self.draw_fitted_text(w - 16, 230, traffic_text, "#7d8891",
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
            fuel_scooping=nav_context.get("fuel_scooping"),
            surface_approach=nav_context.get("surface_approach"),
            ship_config=nav_context.get("ship_config"),
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
        self._nav_fuel_model = {
            "active": bool(nav_context.get("fuel_scooping")),
            "x1": 28.0, "x2": 157.0, "y": 126.0,
        }
        self._draw_section_rule(20, w - 20, 130)

        # Original left/centre/right route header and real upcoming-hop pip strip.
        left_x, right_x = 20, w - 20
        route_color = COLOR_ACCENT if route.get("complete") else (
            COLOR_ORANGE if route["active"] else "#7d8891"
        )
        self.draw_fitted_text(left_x, 147, route_header, route_color,
                              size=10, min_size=9, max_width=250, anchor="w")
        self.draw_fitted_text(w / 2, 147, next_distance, route_color,
                              size=10, min_size=9, max_width=110, anchor="center")
        self.draw_fitted_text(right_x, 147, route_distance, COLOR_ORANGE,
                              size=10, min_size=9, max_width=240, anchor="e")
        self._draw_route_track(left_x, right_x, 165, route, dot_radius=5)
        route_model = self._route_track_model or {}
        origin_current = bool(route_model.get("origin_current", True))
        self.draw_text(left_x, 183, text="CURRENT" if origin_current else "START",
                       fill=COLOR_ACCENT if origin_current else self._glow_color(COLOR_ACCENT, 0.52),
                       font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(right_x, 183,
                       text="DEST" if route["active"] or route.get("track_hops") else "NEXT",
                       fill=route_color,
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
        self.draw_fitted_text(20, 261, context_text, context_color,
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
