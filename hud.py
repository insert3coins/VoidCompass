import tkinter as tk
import tkinter.font as tkfont
import logging
import math
import os
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
import ui_theme
from html_navigation_hud import HtmlNavigationHudBridge
from html_overlay_runtime import overlay_opacity_ratio
from navigation_instrument import (
    NavigationEventRenderer,
)
from navigation_state_indicator import NavigationStateIndicator

class TacticalHUD:
    MIN_READABLE_FONT = 9

    def __init__(self, root, config, on_widget_click=None):
        self.win = tk.Toplevel(root)
        self.config = config
        self.on_widget_click = on_widget_click

        overlay_bg = overlay_chrome.configure_overlay_window(self.win, "#ff00ff")

        self.full_width = 620
        self.full_height = 294
        self.compact_width = 500
        self.compact_height = 254
        self.width, self.base_height = self._target_dimensions()
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.base_height, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()
        self._nav_event_renderer = NavigationEventRenderer(
            self.canvas, self._glow_color,
        )
        self._nav_state_indicator = NavigationStateIndicator(
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
        self._nav_visual_time = 0.0
        self._nav_frame_elapsed_s = 0.0
        self._nav_state_phase_origin = 0.0
        self._nav_marker_model = None
        self._nav_state_identity = None
        self._nav_state_color = None
        self._nav_state_transition = None
        self._nav_event_sequence = -1
        self._nav_event_motion = None
        self._nav_dwell_model = None
        self._nav_dwell_last_text = None
        self._survey_rail_model = None
        self._survey_rail_state = None
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
        self._html_bridge = None
        self._html_ready = False
        self._html_last_window_fingerprint = None
        self._html_last_model = None
        self._html_sync_job = None
        self._anim_interval_ms = int(self.config.get("hud_anim_interval_ms", 33) or 33)
        self._anim_interval_ms = max(30, min(500, self._anim_interval_ms))
        self.win.bind("<Destroy>", self._on_window_destroyed, add="+")
        # load_config/apply_profile_config always supplies the platform-aware
        # default. Treat deliberately minimal/test configs as native-only.
        self.set_html_renderer(bool(self.config.get("hud_html_renderer", False)))
        self._schedule_html_sync()
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

    def _html_window_payload(self):
        width, height = self._target_dimensions()
        try:
            state = str(self.win.state())
            shown = state not in {"withdrawn", "iconic"}
        except Exception:
            shown = False
        startup_held = bool(
            getattr(self.win.master, "_voidcompass_startup_presentation_held", False)
        )
        return {
            "x": self._safe_int(self.config.get("hud_x"), 100),
            "y": self._safe_int(self.config.get("hud_y"), 100),
            "width": int(width),
            "height": int(height),
            "visible": bool(
                shown and not startup_held
                and self.config.get("overlay_enabled", True)
            ),
            # The WebView is only a visual surface. Input always falls through
            # to the authoritative Tk proxy: that proxy either passes input to
            # Elite or handles the existing drag bindings according to the
            # commander's overlay passthrough setting.
            "click_through": True,
        }

    def _html_base_model(self):
        theme = ui_theme.THEME
        return {
            "schema": 1,
            "layout": "standard" if self._is_compact() else "expanded",
            "theme": {
                "accent": str(theme.accent), "orange": str(theme.orange),
                "green": str(theme.green), "yellow": str(theme.yellow),
                "red": str(theme.red), "text": str(theme.text),
                "muted": str(theme.muted), "dim": str(theme.dim),
                "bg": str(theme.bg), "panel": str(theme.panel),
                "border": str(theme.border), "inset": str(theme.inset),
                "text_scale": self._text_scale_percent() / 100.0,
            },
            "effects": {
                "crt": self._crt_enabled(),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "opacity": overlay_opacity_ratio(self.config),
                "energy": {
                    "Calm": 0.72, "Standard": 1.0, "Energetic": 1.28,
                }.get(str(self.config.get("hud_animation_intensity") or "Standard").title(), 1.0),
            },
            "state": {
                "label": "FLIGHT", "color": str(theme.dim), "motion": "flight",
            },
            "system": {"name": "---", "region": "REGION UNKNOWN", "arrival_epoch": 0},
            "route": {"header": "NO ACTIVE ROUTE", "hops": []},
            "survey": {"label": "COUNT UNKNOWN", "count": "0/? · --%", "percent": 0},
            "metrics": {
                "fuel": {"value": "--", "color": str(theme.dim)},
                "bio": {"value": "0/0", "color": str(theme.dim)},
                "geo": {"value": "0", "color": str(theme.yellow)},
                "traffic": {"value": "0 / 0 / 0", "color": str(theme.dim)},
            },
            "context": {"primary": "", "secondary": "", "traffic": ""},
            "window": self._html_window_payload(),
        }

    def set_html_renderer(self, enabled):
        """Enable the isolated WebView2 HUD, retaining Tk as live fallback."""
        enabled = bool(enabled and os.name == "nt")
        if not enabled:
            bridge, self._html_bridge = self._html_bridge, None
            self._html_ready = False
            if bridge is not None:
                bridge.dispose()
            try:
                held = bool(getattr(
                    self.win.master, "_voidcompass_startup_presentation_held", False,
                ))
                self.win.attributes("-alpha", 0.0 if held else 1.0)
            except Exception:
                pass
            self._last_render_fingerprint = None
            if self._last_update_args is not None:
                self.update(*self._last_update_args)
            return False
        if self._html_bridge is not None:
            return True
        try:
            self._html_bridge = HtmlNavigationHudBridge(self.win.master, self.config)
            model = self._html_last_model or self._html_base_model()
            model = dict(model)
            model["window"] = self._html_window_payload()
            self._html_bridge.publish(model)
            return True
        except Exception as exc:
            self._html_bridge = None
            self._html_ready = False
            logging.warning("HTML Navigation HUD unavailable; using Tk renderer: %s", exc)
            return False

    def _schedule_html_sync(self):
        try:
            self._html_sync_job = self.win.after(180, self._sync_html_renderer)
        except Exception:
            self._html_sync_job = None

    def sync_html_window(self, x=None, y=None):
        """Move the WebView2 surface immediately during Layout Studio drags."""
        bridge = self._html_bridge
        if bridge is None:
            return False
        window = self._html_window_payload()
        if x is not None:
            window["x"] = int(round(float(x)))
        if y is not None:
            window["y"] = int(round(float(y)))
        bridge.update_window(window)
        self._html_last_window_fingerprint = repr(window)
        return True

    def _sync_html_renderer(self):
        self._html_sync_job = None
        bridge = self._html_bridge
        if bridge is not None:
            if bridge.startup_failed:
                logging.warning(
                    "HTML Navigation HUD unavailable; returning to Tk renderer (%s)",
                    bridge.host_status or "host exited or renderer did not connect",
                )
                self.set_html_renderer(False)
            else:
                was_ready = self._html_ready
                ready = bridge.ready
                self._html_ready = ready
                if ready:
                    try:
                        # Keep the native Tk window as the authoritative
                        # position/visibility proxy used by hotkeys and Layout
                        # Studio, but make its renderer completely invisible.
                        self.win.attributes("-alpha", 0.0)
                    except Exception:
                        pass
                    if not was_ready:
                        logging.info("HTML Navigation HUD renderer is live")
                window = self._html_window_payload()
                fingerprint = repr(window)
                if fingerprint != self._html_last_window_fingerprint:
                    self._html_last_window_fingerprint = fingerprint
                    model = dict(self._html_last_model or self._html_base_model())
                    model["window"] = window
                    self._html_last_model = model
                    bridge.publish(model)
        self._schedule_html_sync()

    def _on_window_destroyed(self, event):
        if event.widget is not self.win:
            return
        if self._html_sync_job is not None:
            try:
                self.win.after_cancel(self._html_sync_job)
            except Exception:
                pass
            self._html_sync_job = None
        bridge, self._html_bridge = self._html_bridge, None
        if bridge is not None:
            bridge.dispose()

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
        elapsed = max(0.0, now - self._nav_phase_last_ts)
        self._nav_phase_last_ts = now
        # Tk can occasionally be held for hundreds of milliseconds by a busy
        # desktop/game frame or another UI redraw. Discard that visual backlog
        # instead of teleporting every animation forward to catch up. Normal
        # 30 FPS callbacks retain their measured delta; a delayed callback gets
        # one bounded motion step and resumes smoothly on the following frame.
        max_visual_step = max(
            0.040, min(0.066, (self._anim_interval_ms / 1000.0) * 1.5),
        )
        visual_elapsed = min(elapsed, max_visual_step)
        self._nav_frame_elapsed_s = visual_elapsed
        self._nav_visual_time += visual_elapsed
        # One phase unit remains the original 100 ms animation step.
        self._nav_marker_phase += visual_elapsed / 0.1
        try:
            if not self._html_ready:
                self._draw_navigation_marker_animation()
                self._draw_route_track_animation()
                self._draw_fuel_scoop_animation()
                self._draw_survey_rail_animation()
                self._draw_navigation_dwell_clock()
                if now >= self._next_crt_frame_ts:
                    self._draw_crt_animation()
                    self._next_crt_frame_ts = now + 0.1
        except Exception:
            pass
        finally:
            try:
                delay = self._anim_interval_ms
                if self._html_ready:
                    delay = max(delay, 120)
                elif self.config.get("reduced_motion_enabled", False):
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
        """Draw the Codex region between CURRENT SYSTEM and the dwell clock.

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

    @staticmethod
    def _format_system_dwell(seconds):
        try:
            seconds = max(0, int(float(seconds)))
        except (TypeError, ValueError):
            return "--:--"
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _set_navigation_dwell_clock(self, x, y, nav_context):
        epoch = (nav_context or {}).get("system_arrival_epoch")
        try:
            epoch = float(epoch)
        except (TypeError, ValueError):
            epoch = None
        self._nav_dwell_model = {
            "x": float(x), "y": float(y), "epoch": epoch,
        } if epoch is not None else None
        # A full HUD redraw removed the previous Canvas item even if its text
        # has not ticked over yet.
        self._nav_dwell_last_text = None
        self._draw_navigation_dwell_clock()

    def _draw_navigation_dwell_clock(self):
        """Update the system-residence clock once per second, without a HUD redraw."""
        model = self._nav_dwell_model
        if not isinstance(model, dict):
            return
        try:
            elapsed = max(0.0, time.time() - float(model["epoch"]))
        except (KeyError, TypeError, ValueError):
            return
        text = f"SYSTEM TIME {self._format_system_dwell(elapsed)}"
        if text == self._nav_dwell_last_text:
            return
        self._nav_dwell_last_text = text
        self.canvas.delete("nav_dwell_text")
        self.draw_text(
            model["x"], model["y"], text=text, fill="#7d8891",
            font=("Courier", 9, "bold"), anchor="e", tags="nav_dwell_text",
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
            "10": "DSS",
            "SAA": "DSS",
            "SURFACEANALYSIS": "DSS",
            "11": "CODEX",
            "CODEX": "CODEX",
        }
        # Status.json is authoritative for scanner focus: Elite uses the
        # shared SystemAndSurfaceScanner music track for both FSS and DSS,
        # while GuiFocus distinguishes FSS (9) from DSS/SAA (10).  Exact
        # journal music names remain a useful fallback for map-to-map handoffs
        # while the next Status snapshot is still arriving.
        focused_state = focus_labels.get(focus_key) or focus_labels.get(track_key)
        if focused_state:
            return focused_state
        if track_key == "GALACTICPOWERS":
            return "POWER MAP"
        if music_mode == "MAP":
            return "MAP"
        if nav_context.get("in_fss"):
            return "FSS"
        if (fsd_state == "asteroid_field" and flight_state in {"", "FLIGHT"}
                and not any(nav_context.get(key) for key in (
                    "docked", "landed", "in_fighter", "in_srv", "on_foot",
                    "in_taxi", "in_multicrew",
                ))):
            return "ASTEROID FIELD"
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
            return vehicle_name if vehicle_name in {"SCARAB", "SCORPION"} else "SRV"
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
            "DOCKED", "LANDED", "FSS", "DSS", "FIGHTER", "SRV", "SCARAB", "SCORPION", "NOMAD",
            "TAXI", "MULTICREW",
            "ONFOOT", "MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY",
            "CODEX", "EXPLORATION", "STATION", "FSD COOLDOWN", "ORBITAL APPROACH",
            "ORBITAL DEPARTURE", "SURFACE HOLD",
        ):
            return COLOR_ACCENT
        if state_text in {
                "MASS LOCK", "ASTEROID FIELD", "GLIDE",
                "SURFACE APPROACH", "SURFACE DEPARTURE"}:
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
        if state == "ASTEROID FIELD":
            return "asteroid_field"
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
        if state in {"SRV", "SCARAB", "SCORPION", "NOMAD"}:
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


    @staticmethod
    def _navigation_event_palette():
        return {
            "accent": COLOR_ACCENT,
            "orange": COLOR_ORANGE,
            "green": COLOR_GREEN,
            "yellow": COLOR_YELLOW,
            "muted": COLOR_MUTED,
        }

    def _draw_navigation_state_marker(
        self,
        center_x,
        center_y,
        text,
        color,
        *,
        track_left=None,
        track_right=None,
        journal_event=None,
        gravity_g=None,
        surface_active=False,
        neutron_boost=None,
    ):
        """Build the code-native Navigation State Instrument."""
        label = str(text or "FLIGHT").upper()
        neutron_boost = neutron_boost if isinstance(neutron_boost, dict) else {}

        rendered = self._readable_font(("Courier", 10, "bold"))
        font = tkfont.Font(family=rendered[0], size=rendered[1], weight="bold")
        label_width = font.measure(label)
        left_edge = float(track_left) if track_left is not None else center_x - 270
        right_edge = float(track_right) if track_right is not None else center_x + 270
        # The code-native state sigil and response lane occupy the complete
        # top-instrument bay while leaving the centre clear for native text.
        scene_y = center_y + 2
        scene_top = center_y - 13
        scene_bottom = center_y + 17
        # Seat the native label on the instrument centreline so the state sigil
        # and live motion response visually lead into it from either side.
        label_y = scene_y
        # Keep one stable centre aperture across normal state labels. Without
        # this floor, changing from a short label such as FSS to a longer one
        # physically snapped both animated wings sideways between frames.
        aperture_width = max(
            label_width,
            font.measure("INTERDICTION EVADED") + 4,
        )
        group_left = center_x - (aperture_width / 2)
        group_right = center_x + (aperture_width / 2)
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
            "accent_color": COLOR_ACCENT,
            "motion_profile": profile,
            "scene_y": scene_y,
            "scene_top": scene_top,
            "scene_bottom": scene_bottom,
            "scene_x1": left_edge,
            "scene_x2": right_edge,
            "group_left": group_left,
            "group_right": group_right,
            "label_x": float(center_x),
            "label_y": float(label_y),
            "label_width": float(label_width),
            "gravity_load": gravity_load,
            "gravity_color": gravity_color,
            "boost_armed": bool(neutron_boost.get("armed")),
            "animation_intensity": self.config.get(
                "hud_animation_intensity", "Standard",
            ),
            "activity_kind": "",
            "activity_progress": 0.0,
            "activity_energy": 0.0,
        }
        self._nav_marker_model = model

        reduced_motion = self.config.get("reduced_motion_enabled", False)
        state_phase = max(
            0.0,
            self._nav_marker_phase - self._nav_state_phase_origin,
        )
        self._nav_state_indicator.draw_state(
            model, 0.0 if reduced_motion else state_phase,
            tags="nav_state_static" if reduced_motion else "nav_state_core",
            motion=not reduced_motion,
        )
        self._nav_state_indicator.draw_static(model)
        self._nav_state_indicator.draw_center_core(
            model, 0.0 if reduced_motion else state_phase,
            motion=not reduced_motion,
            tags="nav_state_static" if reduced_motion else "nav_state_core",
        )
        self.draw_text(
            center_x, label_y, text=label, fill=color,
            font=("Courier", 10, "bold"), anchor="center",
            tags="nav_state_static",
        )
        self._accept_navigation_journal_event(journal_event)
        return right_edge - left_edge




    def _accept_navigation_state_transition(self, label, profile, color):
        """Start one compact morph only when the displayed state changes."""
        identity = (str(label or "FLIGHT"), str(profile or "flight"))
        previous = getattr(self, "_nav_state_identity", None)
        previous_color = getattr(self, "_nav_state_color", None) or color
        self._nav_state_identity = identity
        self._nav_state_color = color
        if previous is None:
            self._nav_state_phase_origin = self._nav_marker_phase
            return
        if previous == identity:
            return
        # Every state begins at its deliberate animation seam rather than at
        # an arbitrary point inherited from the previous global phase.
        self._nav_state_phase_origin = self._nav_marker_phase
        if self.config.get("reduced_motion_enabled", False):
            self._nav_state_transition = None
            return
        self._nav_state_transition = {
            "from_profile": previous[1],
            "from_color": previous_color,
            "to_profile": identity[1],
            "to_color": color,
            "started": time.monotonic(),
            "visual_started": self._nav_visual_time,
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

        # Fuel flow already belongs to the live fuel cell, and neutron charge
        # is retained as a scoped flight-state cue. Neither may paint a second
        # green/accent response across the Navigation State Instrument.
        if str(event.get("kind") or "") in {"fuel", "boost"}:
            return

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
        if same_burst:
            motion["visual_started"] = current.get(
                "visual_started", self._nav_visual_time,
            )
        else:
            # If this journal pulse also changed the sustained state, let the
            # morph establish itself before the event response joins it.
            transition = getattr(self, "_nav_state_transition", None)
            delay = 0.16 if isinstance(transition, dict) else 0.0
            motion["visual_started"] = self._nav_visual_time + delay
        self._nav_event_motion = motion

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




    def _draw_navigation_marker_animation(self):
        """Animate the code-native Navigation State Instrument."""
        self.canvas.delete("nav_state_motion")
        self.canvas.delete("nav_state_core")
        self.canvas.delete("nav_event_motion")
        model = self._nav_marker_model
        if not model or self.config.get("reduced_motion_enabled", False):
            return
        try:
            if (not self.win.winfo_viewable()
                    or str(self.win.state()) in ("withdrawn", "iconic")):
                return
        except Exception:
            return

        visual_now = self._nav_visual_time
        transition_progress = None
        transition = getattr(self, "_nav_state_transition", None)
        if isinstance(transition, dict):
            try:
                duration = max(0.3, float(transition.get("duration", 0.68)))
                visual_started = transition.get("visual_started")
                if visual_started is None:
                    visual_started = visual_now
                    transition["visual_started"] = visual_started
                transition_progress = (
                    visual_now - float(visual_started)
                ) / duration
            except (TypeError, ValueError, ZeroDivisionError):
                self._nav_state_transition = None
                transition = None
            else:
                if transition_progress >= 1.0:
                    self._nav_state_transition = None
                    transition = None
                    transition_progress = None
                elif transition_progress < 0.0:
                    transition_progress = None

        event_progress = None
        event = getattr(self, "_nav_event_motion", None)
        if isinstance(event, dict):
            try:
                duration = max(0.4, float(event.get("duration", 1.3)))
                visual_started = event.get("visual_started")
                if visual_started is None:
                    visual_started = visual_now
                    event["visual_started"] = visual_started
                event_progress = (
                    visual_now - float(visual_started)
                ) / duration
            except (TypeError, ValueError, ZeroDivisionError):
                self._nav_event_motion = None
                event = None
            else:
                if event_progress >= 1.0:
                    self._nav_event_motion = None
                    event = None
                    event_progress = None
                elif event_progress < 0.0:
                    event_progress = None

        # Journal activity raises the energy of the sustained scene and then
        # decays naturally. Priority controls amplitude, never frame rate.
        event_energy = 0.0
        if isinstance(event, dict) and event_progress is not None:
            try:
                priority = float(event.get("priority", 60) or 60)
            except (TypeError, ValueError):
                priority = 60.0
            weight = max(0.45, min(1.0, priority / 100.0))
            event_energy = (math.sin(math.pi * event_progress) ** 0.70) * weight
        transition_energy = 0.0
        if isinstance(transition, dict) and transition_progress is not None:
            transition_energy = math.sin(math.pi * transition_progress) * 0.75

        model["animation_intensity"] = self.config.get(
            "hud_animation_intensity", "Standard",
        )
        model["activity_kind"] = (
            str(event.get("kind") or "") if isinstance(event, dict) else ""
        )
        model["activity_progress"] = event_progress or 0.0
        model["activity_energy"] = max(event_energy, transition_energy)
        model["transition_progress"] = transition_progress

        # Sustained state, transitions, and event responses have separate
        # owners so an old fallback scene cannot leak into the live indicator.
        palette = self._navigation_event_palette()
        state_phase = max(
            0.0,
            self._nav_marker_phase - self._nav_state_phase_origin,
        )
        self._nav_state_indicator.draw_state(
            model, state_phase, tags="nav_state_core",
        )
        self._nav_state_indicator.draw_center_core(
            model, state_phase, tags="nav_state_core",
        )
        try:
            self.canvas.tag_lower("nav_state_core", "nav_state_static")
        except tk.TclError:
            pass
        if isinstance(transition, dict) and transition_progress is not None:
            self._nav_state_indicator.draw_transition(
                model, transition, transition_progress,
            )
        if isinstance(event, dict) and event_progress is not None:
            self._nav_event_renderer.draw_event(
                model, event, event_progress, palette,
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
        local_target = context.get("local_target") or {}
        target_name = str(local_target.get("name") or "").strip()
        if target_name:
            target_detail = ""
            if local_target.get("is_current_body"):
                try:
                    gravity = context.get("gravity_g")
                    target_detail = f" · {float(gravity):.2f} G" if gravity is not None else ""
                except (TypeError, ValueError):
                    target_detail = ""
            return f"LOCAL TARGET · {target_name}{target_detail}", COLOR_ACCENT
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
            vector = context.get("galactic_vector") or {}
            vector_parts = [
                str(vector.get("direction") or "").strip(),
                str(vector.get("plane") or "").strip(),
            ]
            vector_text = " · ".join(part for part in vector_parts if part)
            prefix = f"{vector_text} · " if vector_text else ""
            return f"{prefix}NEXT {star_label} · {scoop_text}{dry_text}", (
                COLOR_YELLOW if scoop is False else COLOR_ACCENT
            )
        vector = context.get("galactic_vector") or {}
        vector_label = str(vector.get("label") or "").strip()
        if vector_label:
            return f"GALACTIC VECTOR · {vector_label}", COLOR_ACCENT
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

    @staticmethod
    def _survey_rail_presentation(scanned, total, pct, nav_context):
        context = nav_context or {}
        source = str(context.get("scan_progress_source") or "bodies").casefold()
        try:
            scanned = max(0, int(scanned or 0))
            total = max(0, int(total or 0))
        except (TypeError, ValueError):
            scanned, total = 0, 0
        pct = max(0.0, min(1.0, float(pct or 0.0)))
        complete = bool(source != "unknown" and pct >= 0.999 and total > 0)
        # ``scan_progress_source == fss`` may remain authoritative after the
        # commander closes the scanner. Only the live UI state should keep the
        # moving scanner and LIVE FSS label active.
        live = bool(context.get("in_fss")) and not complete
        try:
            dss = max(0, int(context.get("dss_complete", 0) or 0))
        except (TypeError, ValueError):
            dss = 0
        remaining = max(0, total - scanned) if total > 0 and not complete else 0

        if source == "unknown":
            label, tone, state = "COUNT UNKNOWN", "#7d8891", "unknown"
        elif complete:
            label, tone, state = "COMPLETE", COLOR_GREEN, "complete"
        elif live:
            label, tone, state = "LIVE FSS", COLOR_ORANGE, "live"
        else:
            label, tone, state = "LOCAL RECORD", COLOR_ACCENT, "local"
        if remaining:
            label += f" · {remaining} REMAINS"
        elif dss:
            label += f" · DSS {dss}"
        return {
            "label": label,
            "tone": tone,
            "state": state,
            "complete": complete,
            "live": live,
            "scanned": scanned,
            "total": total,
            "pct": pct,
        }

    def _draw_discovery_rail(self, x1, x2, y, presentation, system_name):
        """Draw a segmented, evidence-aware FSS discovery instrument."""
        pct = float(presentation.get("pct", 0.0) or 0.0)
        tone = presentation.get("tone") or COLOR_ACCENT
        state = str(presentation.get("state") or "local")
        dim = self._glow_color(tone, 0.28 if state != "unknown" else 0.20)
        span = max(1.0, x2 - x1)
        segment_count = 12
        gap = 3.0
        segment_width = max(2.0, (span - gap * (segment_count - 1)) / segment_count)
        completion = pct * segment_count

        self.canvas.create_line(x1, y, x2, y, fill="#17242d", width=1)
        for index in range(segment_count):
            start = x1 + index * (segment_width + gap)
            end = min(x2, start + segment_width)
            self.canvas.create_line(start, y, end, y, fill=dim, width=3)
            lit = max(0.0, min(1.0, completion - index))
            if lit > 0.0:
                self.canvas.create_line(
                    start, y, start + (end - start) * lit, y,
                    fill=tone, width=3,
                )

        marker_x = x1 + span * pct
        if 0.0 < pct < 1.0 and state != "unknown":
            self.canvas.create_line(
                marker_x, y - 5, marker_x, y + 5,
                fill=tone, width=1,
            )

        previous = self._survey_rail_state or {}
        old_model = self._survey_rail_model or {}
        same_system = bool(
            system_name and previous.get("system") == system_name
        )
        discovery_started = old_model.get("discovery_started") if same_system else None
        completion_started = old_model.get("completion_started") if same_system else None
        if same_system and presentation["scanned"] > int(previous.get("scanned", 0) or 0):
            discovery_started = self._nav_visual_time
        if (same_system and presentation.get("complete")
                and not previous.get("complete")):
            completion_started = self._nav_visual_time
        self._survey_rail_state = {
            "system": system_name,
            "scanned": presentation["scanned"],
            "total": presentation["total"],
            "complete": bool(presentation.get("complete")),
        }
        self._survey_rail_model = {
            "x1": float(x1), "x2": float(x2), "y": float(y),
            "marker_x": marker_x, "tone": tone,
            "live": bool(presentation.get("live")),
            "complete": bool(presentation.get("complete")),
            "discovery_started": discovery_started,
            "completion_started": completion_started,
        }

    def _draw_survey_rail_animation(self):
        self.canvas.delete("nav_survey_motion")
        model = self._survey_rail_model
        if (not isinstance(model, dict)
                or self.config.get("reduced_motion_enabled", False)):
            return
        try:
            if not self.win.winfo_viewable():
                return
        except Exception:
            return
        x1, x2, y = model["x1"], model["x2"], model["y"]
        marker_x = model.get("marker_x", x1)
        tone = model.get("tone") or COLOR_ACCENT

        # The active scanner travels only through the unresolved portion.
        if model.get("live") and x2 - marker_x > 5:
            local = self._cycle_progress(self._nav_marker_phase, 18)
            x = marker_x + 2 + (x2 - marker_x - 2) * local
            self._draw_contrast_motion_tail(
                max(marker_x + 1, x - 8), x, y,
                self._glow_color(tone, 0.78), width=1,
                tags="nav_survey_motion",
            )
            self._draw_contrast_motion_dot(
                x, y, tone, radius=1, tags="nav_survey_motion",
            )

        discovery_started = model.get("discovery_started")
        if discovery_started is not None:
            elapsed = self._nav_visual_time - float(discovery_started)
            if 0.0 <= elapsed < 0.72:
                wave = math.sin((elapsed / 0.72) * math.pi)
                radius = 3 + wave * 5
                self.canvas.create_oval(
                    marker_x - radius, y - radius,
                    marker_x + radius, y + radius,
                    fill="", outline=tone, width=2 if wave > 0.55 else 1,
                    tags="nav_survey_motion",
                )
            elif elapsed >= 0.72:
                model["discovery_started"] = None

        completion_started = model.get("completion_started")
        if completion_started is not None:
            elapsed = self._nav_visual_time - float(completion_started)
            if 0.0 <= elapsed < 0.82:
                local = min(1.0, elapsed / 0.82)
                eased = local * local * (3.0 - 2.0 * local)
                x = x1 + (x2 - x1) * eased
                self._draw_contrast_motion_tail(
                    max(x1, x - 18), x, y, COLOR_GREEN,
                    width=2, tags="nav_survey_motion",
                )
            elif elapsed >= 0.82:
                model["completion_started"] = None

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
            visual_started = event.get("visual_started")
            if visual_started is None:
                visual_started = self._nav_visual_time
                event["visual_started"] = visual_started
            progress = (
                self._nav_visual_time - float(visual_started)
            ) / duration
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
        survey_rail = self._survey_rail_presentation(
            scanned, total, pct, nav_context,
        )
        scan_color = survey_rail["tone"]
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
            track_left=marker_left,
            track_right=marker_right,
            journal_event=nav_context.get("journal_event"),
            gravity_g=nav_context.get("gravity_g"),
            surface_active=bool(
                nav_context.get("landed") or nav_context.get("in_srv")
                or nav_context.get("on_foot")
                or state_text in {"LANDED", "SRV", "NOMAD", "ONFOOT"}
            ),
            neutron_boost=nav_context.get("neutron_boost"),
        )
        self._draw_section_rule(16, w - 16, 42)

        # The current system is the primary landmark, held by a lit locator rail.
        self._draw_locator_rail(17, 55, 78)
        self.draw_text(27, 55, text="CURRENT SYSTEM", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self._draw_region_label(nav_context, 241, 55, max_width=217)
        self._set_navigation_dwell_clock(w - 27, 55, nav_context)
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
        self.draw_fitted_text(
            135, 165, survey_rail["label"], survey_rail["tone"],
            size=9, min_size=9, max_width=max(80, w - 290), anchor="w",
        )
        self.draw_fitted_text(
            w - 16, 165, scan_progress_text, scan_color,
            size=11, min_size=9, max_width=132, anchor="e",
        )
        self._draw_discovery_rail(
            16, w - 16, 179, survey_rail, current_display,
        )
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

    def _build_html_model(
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
        """Build the renderer-neutral model consumed by the WebView HUD."""
        nav_context = nav_context or {}
        model = self._html_base_model()
        current_display = str(nav_context.get("current") or current_sys or "---").upper()
        state_text = self._state_text(nav_context)
        state_color = self._state_color(state_text)
        journal_event = nav_context.get("journal_event") or {}
        approach = nav_context.get("surface_approach") or {}
        ship_config = nav_context.get("ship_config") or {}

        def finite_number(value, default=None):
            try:
                number = float(value)
            except (TypeError, ValueError):
                return default
            return number if math.isfinite(number) else default

        model["state"] = {
            "label": state_text,
            "color": state_color,
            "motion": self._navigation_motion_profile(state_text),
            "vehicle": {
                "ship_symbol": str(nav_context.get("ship_symbol") or "").casefold(),
                "ship_type": str(nav_context.get("ship_type") or ""),
                "ship_name": str(nav_context.get("ship_name") or ""),
                "surface": str(nav_context.get("vehicle_name") or "").upper(),
            },
            "event_sequence": journal_event.get("seq"),
            "event_kind": str(journal_event.get("kind") or ""),
            "dynamics": {
                "gravity_g": finite_number(nav_context.get("gravity_g"), 0.0),
                "altitude_m": finite_number(approach.get("altitude_m")),
                "vertical_mps": finite_number(approach.get("descent_mps"), 0.0),
                "scan_percent": finite_number(nav_context.get("scan_progress"), 0.0),
                "landing_gear": bool(ship_config.get("landing_gear")),
                "analysis_mode": bool(ship_config.get("analysis_mode")),
                "neutron_boost": bool((nav_context.get("neutron_boost") or {}).get("armed")),
                "route_active": str(nav_context.get("route_mode") or "NO ROUTE") != "NO ROUTE",
            },
        }

        region = nav_context.get("region") or {}
        region_text = "REGION UNKNOWN"
        if region.get("name"):
            try:
                region_text = f"REGION {int(region.get('id') or 0):02d} // {str(region['name']).upper()}"
            except (TypeError, ValueError):
                region_text = f"REGION // {str(region['name']).upper()}"
            if region.get("crossed"):
                region_text += " // NEW"
        model["system"] = {
            "name": current_display,
            "region": region_text,
            "arrival_epoch": float(nav_context.get("system_arrival_epoch") or 0.0),
        }

        route = self._route_presentation(
            nav_context, route_waypoint, route_counts, game_r_pos, r_pos,
        )
        route_header, next_distance, route_distance = self._classic_route_header_parts(
            route, nav_context, route_waypoint=bool(route_waypoint),
        )
        source_hops = list(route.get("track_hops") or route.get("hops") or [])
        track_width = max(260, self._target_dimensions()[0] - 32)
        positions, dense = route_strip.pip_layout(0, track_width, source_hops)
        html_hops = []
        for index, hop in enumerate(source_hops):
            html_hops.append({
                "name": str(hop.get("name") or "")[:120],
                "position": round((positions[index] / track_width) * 100.0, 3)
                if index < len(positions) else 0.0,
                "completed": bool(hop.get("completed")),
                "current": bool(hop.get("current")),
                "next": bool(hop.get("next")),
                "scoopable": hop.get("scoopable"),
            })
        progress_percent = 100.0 if route.get("complete") else 0.0
        if html_hops and not route.get("complete"):
            progress_index = next(
                (index for index, hop in enumerate(html_hops) if hop["current"]),
                -1,
            )
            if progress_index < 0:
                progress_index = max(
                    (index for index, hop in enumerate(html_hops) if hop["completed"]),
                    default=-1,
                )
            if progress_index >= 0:
                progress_percent = float(html_hops[progress_index]["position"])
        model["route"] = {
            "header": route_header,
            "next_distance": next_distance,
            "distance": route_distance,
            "active": bool(route.get("active")),
            "complete": bool(route.get("complete")),
            "origin_current": bool(route.get("track_origin_current", True)),
            "progress_percent": round(progress_percent, 2),
            "dense": bool(dense),
            "cells": max(10, min(18, int(round(track_width / 28.0)))),
            "hops": html_hops,
        }
        model["state"]["dynamics"]["route_progress"] = round(
            max(0.0, min(1.0, progress_percent / 100.0)), 4,
        )

        pct, scan_progress_text = self._scan_progress_state(scanned, total, nav_context)
        survey = self._survey_rail_presentation(scanned, total, pct, nav_context)
        model["survey"] = {
            "label": survey["label"],
            "tone": survey["tone"],
            "count": scan_progress_text,
            "percent": round(float(survey["pct"]) * 100.0, 2),
            "live": bool(survey["live"]),
            "complete": bool(survey["complete"]),
        }

        survey_metrics = self._survey_metrics(nav_context)
        metric_values = {
            label.casefold(): {"value": value, "color": color}
            for label, value, color in survey_metrics
        }
        traffic = system_traffic or {}
        traffic_value = " / ".join(
            str(int(traffic.get(key, 0) or 0)) for key in ("day", "week", "total")
        )
        model["metrics"] = {
            "fuel": metric_values.get("fuel"),
            "bio": metric_values.get("bio"),
            "geo": metric_values.get("geo"),
            "traffic": {"value": traffic_value, "color": "#7d8891"},
        }

        attention_text, attention_state = self._attention_summary(nav_context)
        context_text, context_color = self._context_presentation(
            nav_context, attention_text, attention_state,
        )
        secondary_text = (
            attention_text if attention_text and context_text != attention_text else ""
        )
        model["context"] = {
            "primary": context_text,
            "primary_color": context_color,
            "secondary": secondary_text,
            "secondary_color": self._badge_color(attention_state),
            "traffic": self._traffic_summary(system_traffic, compact=True),
        }
        model["window"] = self._html_window_payload()
        return model

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
        if self._html_bridge is not None:
            try:
                html_model = self._build_html_model(
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
                self._html_last_model = html_model
                self._html_bridge.publish(html_model)
            except Exception as exc:
                logging.warning("HTML Navigation HUD state publish failed: %s", exc)
        presentation = (
            self._text_scale_percent(), self._crt_enabled(), self._crt_intensity(),
            bool(self.config.get("hud_crt_motion_enabled", True)),
            self.config.get("overlay_opacity_percent", 100),
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
        if self._html_ready:
            self._last_render_fingerprint = render_fingerprint
            return
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
        survey_rail = self._survey_rail_presentation(
            scanned, total, pct, nav_context,
        )
        scan_color = survey_rail["tone"]
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
            track_left=marker_left,
            track_right=marker_right,
            journal_event=nav_context.get("journal_event"),
            gravity_g=nav_context.get("gravity_g"),
            surface_active=bool(
                nav_context.get("landed") or nav_context.get("in_srv")
                or nav_context.get("on_foot")
                or state_text in {"LANDED", "SRV", "NOMAD", "ONFOOT"}
            ),
            neutron_boost=nav_context.get("neutron_boost"),
        )
        self._draw_section_rule(20, w - 20, 37)

        # Original system block, now anchored as the display's primary landmark.
        self._draw_locator_rail(21, 52, 76)
        self.draw_text(32, 52, text="CURRENT SYSTEM", fill="#85939d",
                       font=("Courier", 10, "bold"), anchor="w")
        self._draw_region_label(nav_context, 350, 52, max_width=230)
        self._set_navigation_dwell_clock(w - 32, 52, nav_context)
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
        self.draw_fitted_text(
            148, 212, survey_rail["label"], survey_rail["tone"],
            size=9, min_size=9, max_width=max(110, w - 322), anchor="w",
        )
        self.draw_fitted_text(
            w - 20, 212, scan_progress_text, scan_color,
            size=11, min_size=9, max_width=145, anchor="e",
        )
        self._draw_discovery_rail(
            20, w - 20, 226, survey_rail, current_display,
        )
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
