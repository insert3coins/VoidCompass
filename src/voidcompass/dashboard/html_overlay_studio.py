"""Overlay Layout Studio model and command controller."""

from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR, RHINO_MAP_AVAILABLE

from voidcompass.dashboard.html_workspace_support import (
    integer as _integer,
    number as _number,
    text as _text,
)
from voidcompass.overlays.overlay_layout_model import (
    DEFAULT_POSITIONS,
    DEFAULT_SIZES,
    OVERLAY_CARD_LABELS,
    OVERLAY_ENABLE_KEYS,
    OVERLAY_LABELS,
)
from voidcompass.overlays.heartbeat_hud import EYE_COLORS, ORB_SIZES, eye_color, orb_size
from voidcompass.overlays.hud import HUD_FONT_FACES, HUD_LABEL_SIZES, hud_typography

# How lively the Navigation HUD's holographic scenes are.
HUD_ANIMATION_LEVELS = ("Calm", "Standard", "Energetic")
from voidcompass.overlays.galnet_ticker_hud import (
    TICKER_CONTENT, TICKER_CRT, TICKER_GLITCH, TICKER_GLITCH_STRENGTH, TICKER_SPEEDS,
    TICKER_STORIES, TICKER_WIDTH_RANGE, ticker_options,
)
from voidcompass.overlays.survey_options import SPOTLIGHT_ROTATION_MODES, survey_overlay_options


class HtmlOverlayStudioMixin:
    def _html_overlay_desktop(self):
        """Return the complete Windows virtual desktop in screen coordinates."""
        try:
            import ctypes

            user32 = ctypes.windll.user32
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            primary_width = int(user32.GetSystemMetrics(0))
            primary_height = int(user32.GetSystemMetrics(1))
            if width > 0 and height > 0:
                return {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "primary": {
                        "left": 0, "top": 0,
                        "width": max(1, primary_width),
                        "height": max(1, primary_height),
                    },
                }
        except (AttributeError, OSError):
            pass
        try:
            width = max(1, int(self.root.winfo_screenwidth()))
            height = max(1, int(self.root.winfo_screenheight()))
        except Exception:
            width, height = 1920, 1080
        return {
            "left": 0, "top": 0, "width": width, "height": height,
            "primary": {"left": 0, "top": 0, "width": width, "height": height},
        }

    def _html_overlay_monitors(self):
        """Every display, left to right, in the overlays' screen coordinates.

        Overlay positions are stored in virtual-desktop coordinates, so the
        Studio shows one display at a time and still places surfaces on it
        exactly. Without the Windows API the whole desktop is one display.
        """
        monitors = []
        try:
            import ctypes
            import re
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32),
                ]

            user32 = ctypes.windll.user32
            found = []

            def collect(handle, _dc, _rect, _data):
                info = MonitorInfo()
                info.cbSize = ctypes.sizeof(MonitorInfo)
                if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                    bounds, work = info.rcMonitor, info.rcWork
                    match = re.search(r"DISPLAY(\d+)", str(info.szDevice or ""))
                    found.append({
                        "number": int(match.group(1)) if match else 0,
                        "primary": bool(info.dwFlags & 1),
                        "left": int(bounds.left), "top": int(bounds.top),
                        "width": int(bounds.right - bounds.left),
                        "height": int(bounds.bottom - bounds.top),
                        "work": {
                            "left": int(work.left), "top": int(work.top),
                            "width": int(work.right - work.left),
                            "height": int(work.bottom - work.top),
                        },
                    })
                return 1

            callback = ctypes.WINFUNCTYPE(
                ctypes.c_int, wintypes.HANDLE, wintypes.HANDLE,
                ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
            )(collect)
            user32.EnumDisplayMonitors(None, None, callback, 0)
            monitors = [row for row in found if row["width"] > 0 and row["height"] > 0]
        except (AttributeError, OSError, TypeError, ValueError):
            monitors = []
        if not monitors:
            desktop = self._html_overlay_desktop()
            monitors = [{
                "number": 1, "primary": True,
                "left": desktop["left"], "top": desktop["top"],
                "width": desktop["width"], "height": desktop["height"],
                "work": {key: desktop[key] for key in ("left", "top", "width", "height")},
            }]
        monitors.sort(key=lambda row: (row["left"], row["top"]))
        used = set()
        for index, row in enumerate(monitors, 1):
            # Windows' own display number where it is unique, so the Studio's
            # labels match Display settings; otherwise left-to-right order.
            number = row["number"] if row["number"] and row["number"] not in used else index
            while number in used:
                number += 1
            used.add(number)
            row.update({"id": f"display-{number}", "number": number, "label": f"DISPLAY {number}"})
        return monitors

    @staticmethod
    def _html_overlay_monitor_for(row, monitors):
        """The display holding most of a surface, or the nearest one."""
        best, best_area = None, 0
        for monitor in monitors:
            width = (min(row["x"] + row["width"], monitor["left"] + monitor["width"])
                     - max(row["x"], monitor["left"]))
            height = (min(row["y"] + row["height"], monitor["top"] + monitor["height"])
                      - max(row["y"], monitor["top"]))
            area = max(0, width) * max(0, height)
            if area > best_area:
                best, best_area = monitor, area
        if best is None and monitors:
            cx, cy = row["x"] + row["width"] / 2, row["y"] + row["height"] / 2
            best = min(monitors, key=lambda monitor: (
                (monitor["left"] + monitor["width"] / 2 - cx) ** 2
                + (monitor["top"] + monitor["height"] / 2 - cy) ** 2
            ))
        return best

    @staticmethod
    def _html_overlay_window_shown(window):
        try:
            return bool(window.winfo_viewable()) and str(window.state()) not in {
                "withdrawn", "iconic",
            }
        except Exception:
            return False

    def _html_overlay_records(self, *, live=True):
        records = []
        for attr, x_key, y_key in self._OVERLAY_POSITION_SPECS:
            if not OVERLAY_SPEC_BY_ATTR[attr].available:
                continue
            default_x, default_y = DEFAULT_POSITIONS.get(attr, (30, 30))
            default_width, default_height = DEFAULT_SIZES.get(attr, (320, 160))
            x = _integer(self.config.get(x_key), default_x)
            y = _integer(self.config.get(y_key), default_y)
            width, height = default_width, default_height
            overlay = getattr(self, attr, None)
            window = getattr(overlay, "win", overlay)
            shown = self._html_overlay_window_shown(window) if live else False
            html_size = getattr(overlay, "_html_window_size", None)
            if html_ready := bool(getattr(overlay, "_html_ready", False)):
                if isinstance(html_size, (tuple, list)) and len(html_size) == 2:
                    if attr == "toast_hud" and not getattr(overlay, "_toasts", None):
                        # The host shrinks to 24 px when the queue is empty,
                        # but keep a useful placement card in the Studio.
                        width, height = default_width, default_height
                    else:
                        width = max(24, _integer(html_size[0], default_width))
                        height = max(20, _integer(html_size[1], default_height))
            elif live and window is not None:
                try:
                    if window.winfo_exists():
                        if attr == "toast_hud" and not getattr(overlay, "_toasts", None):
                            # Keep a useful draggable footprint in Studio even
                            # while the transient notification queue is empty.
                            width, height = default_width, default_height
                        else:
                            width = max(24, int(window.winfo_width()), int(window.winfo_reqwidth()))
                            height = max(20, int(window.winfo_height()), int(window.winfo_reqheight()))
                except Exception:
                    pass
            enabled = bool(self.config.get(OVERLAY_ENABLE_KEYS.get(attr, ""), False))
            # This flag is ordinary Python state, so it is safe to expose even
            # while avoiding higher-frequency compatibility geometry calls off-page.
            html_ready = bool(getattr(overlay, "_html_ready", False))
            records.append({
                "id": attr,
                "label": OVERLAY_LABELS.get(attr, attr.replace("_", " ").title()),
                "short_label": OVERLAY_CARD_LABELS.get(attr, attr.upper()),
                "x": x, "y": y, "width": width, "height": height,
                "enabled": enabled,
                "shown": shown,
                "html_ready": html_ready,
                "state": (
                    "OFF" if not enabled else
                    "HTML" if html_ready else
                    "SHOWN" if shown else "READY"
                ),
            })
        return records

    def _html_overlay_studio(self):
        presets = self.config.get("overlay_layout_presets") or {}
        preset_names = sorted(
            (_text(name, 50) for name in presets if str(name).strip()),
            key=str.casefold,
        )
        try:
            ground_solution = self._ground_target_solution() or {}
            ground_configured = bool(self._ground_target_configured())
            ground_ready = bool(self._ground_target_should_show(ground_solution))
        except Exception:
            ground_solution = {}
            ground_configured = False
            ground_ready = False
        rhino_tracker = getattr(self, "rhino_minimap", None) if RHINO_MAP_AVAILABLE else None
        rhino_map = getattr(rhino_tracker, "active", None)
        rhino_maps_count, rhino_maps_size = (
            rhino_tracker.usage() if rhino_tracker is not None else (0, 0)
        )
        monitors = self._html_overlay_monitors()
        overlays = self._html_overlay_records(
            live=getattr(self, "_html_dashboard_active_page", "") == "overlay-studio",
        )
        for row in overlays:
            monitor = self._html_overlay_monitor_for(row, monitors)
            row["monitor"] = monitor["id"] if monitor else ""
        return {
            "desktop": self._html_overlay_desktop(),
            "monitors": monitors,
            "overlays": overlays,
            "presets": preset_names,
            "ground_target": {
                "active": ground_configured,
                "lat": _number(getattr(self, "target_lat", None)) if ground_configured else None,
                "lon": _number(getattr(self, "target_lon", None)) if ground_configured else None,
                "on_planet": bool(getattr(self, "on_planet", False)),
                "navigation_ready": ground_ready,
                "state": _text(ground_solution.get("state") or "OFF", 30),
                "current_available": bool(
                    getattr(self, "current_latitude", None) is not None
                    and getattr(self, "current_longitude", None) is not None
                ),
            },
            "rhino_minimap": {
                "active": bool(getattr(rhino_tracker, "in_rhino", False)),
                "map_name": _text(getattr(rhino_map, "name", ""), 80),
                "centered": bool(getattr(rhino_map, "centered", False)),
                "border_m": _number(getattr(rhino_map, "border_m", None)),
                "painted_km2": round(_number(getattr(rhino_map, "painted_km2", 0.0)) or 0.0, 2),
                "center_hotkey": _text(self.config.get("overlay_hotkey_rhino_minimap_center"), 80),
                "border_hotkey": _text(self.config.get("overlay_hotkey_rhino_minimap_border"), 80),
                "drill_hotkey": _text(self.config.get("overlay_hotkey_rhino_minimap_drill"), 80),
                "reset_hotkey": _text(self.config.get("overlay_hotkey_rhino_minimap_reset"), 80),
                "drill_count": sum(
                    str(row.get("site_type") or "").casefold() == "drill"
                    and str(row.get("system") or "").casefold() == str(getattr(rhino_tracker, "system", "")).casefold()
                    and str(row.get("body") or "").casefold() == str(getattr(rhino_map, "body", "")).casefold()
                    and str(row.get("map_name") or "").casefold() in {
                        "", str(getattr(rhino_map, "name", "") or "").casefold(),
                    }
                    for row in self._rhino_minimap_sites()
                ) if rhino_tracker is not None else 0,
                "saved_maps": rhino_maps_count,
                "saved_bytes": rhino_maps_size,
            },
            "options": {
                "overlay_mouse_passthrough": bool(self.config.get("overlay_mouse_passthrough", True)),
                "hud_compact_mode": bool(self.config.get("hud_compact_mode", True)),
                "hud_animation_intensity": (
                    str(self.config.get("hud_animation_intensity") or "Standard").title()
                    if str(self.config.get("hud_animation_intensity") or "Standard").title() in HUD_ANIMATION_LEVELS
                    else "Standard"
                ),
                "hud_text_scale_percent": _integer(self.config.get("hud_text_scale_percent"), 0),
                "hud_font_face": hud_typography(self.config)["face"],
                "hud_label_size": hud_typography(self.config)["labels"],
                "hud_bright_labels": hud_typography(self.config)["bright"],
                "overlay_text_scale_percent": _integer(self.config.get("overlay_text_scale_percent"), 100),
                "overlay_opacity_percent": _integer(self.config.get("overlay_opacity_percent"), 100),
                "rebuy_warnings_enabled": bool(self.config.get("rebuy_warnings_enabled", True)),
                "data_risk_warnings_enabled": bool(self.config.get("data_risk_warnings_enabled", True)),
                "prospector_hud_timeout_s": _integer(self.config.get("prospector_hud_timeout_s"), 45),
                "gravity_warning_hud_timeout_s": _integer(self.config.get("gravity_warning_hud_timeout_s"), 20),
                "station_info_auto_hide_enabled": bool(self.config.get("station_info_auto_hide_enabled", False)),
                "survey_status_show_all_bodies": bool(self.config.get("survey_status_show_all_bodies", False)),
                **{
                    f"survey_{key}": value
                    for key, value in survey_overlay_options(self.config).items()
                },
                "survey_text_scale_percent": _integer(self.config.get("survey_text_scale_percent"), 0),
                "station_info_timeout_s": _integer(self.config.get("station_info_timeout_s"), 30),
                "contact_scope_timeout_s": _integer(self.config.get("contact_scope_timeout_s"), 45),
                "heartbeat_orb_size": orb_size(self.config),
                **{f"galnet_ticker_{key}": value for key, value in ticker_options(self.config).items()},
                "heartbeat_eye_color": eye_color(self.config),
                "gravity_warning_threshold_g": _number(self.config.get("gravity_warning_threshold_g"), 3.0),
                "hud_crt_enabled": bool(self.config.get("hud_crt_enabled", True)),
                "hud_crt_motion_enabled": bool(self.config.get("hud_crt_motion_enabled", True)),
                "hud_crt_intensity": _text(self.config.get("hud_crt_intensity") or "Subtle", 20).title(),
            },
        }

    def _html_overlay_row(self, overlay_id):
        overlay_id = _text(overlay_id, 50)
        spec = next(
            (item for item in self._OVERLAY_POSITION_SPECS if item[0] == overlay_id),
            None,
        )
        if spec is None:
            return None
        return spec

    def _html_overlay_position(self, overlay_id, x, y, *, persist=False, preview=False):
        spec = self._html_overlay_row(overlay_id)
        if spec is None:
            return False
        attr, _x_key, _y_key = spec
        records = {row["id"]: row for row in self._html_overlay_records()}
        record = records.get(attr) or {}
        desktop = self._html_overlay_desktop()
        width = max(20, _integer(record.get("width"), DEFAULT_SIZES.get(attr, (320, 160))[0]))
        height = max(20, _integer(record.get("height"), DEFAULT_SIZES.get(attr, (320, 160))[1]))
        left, top = desktop["left"], desktop["top"]
        right, bottom = left + desktop["width"], top + desktop["height"]
        x = max(left, min(_integer(x, left), right - width))
        y = max(top, min(_integer(y, top), bottom - height))
        # Geometry and the lightweight HTML-host window channel stay live
        # during the drag, but the expensive full Dashboard model and config
        # write are deferred until pointer-up.
        self._set_overlay_position(attr, x, y, authority_s=3.0)
        if persist:
            self._persist_config()
        if not preview or persist:
            self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_snap(self, overlay_id):
        records = {row["id"]: row for row in self._html_overlay_records()}
        selected = records.get(overlay_id)
        if selected is None:
            return False
        # Snap to the edges of the display the surface is on, not the whole
        # desktop: the seam between two monitors is an edge too.
        monitor = self._html_overlay_monitor_for(selected, self._html_overlay_monitors())
        area = monitor or self._html_overlay_desktop()
        left, top = area["left"], area["top"]
        right, bottom = left + area["width"], top + area["height"]
        width, height = selected["width"], selected["height"]
        x, y = selected["x"], selected["y"]
        candidates_x = [left, max(left, right - width)]
        candidates_y = [top, max(top, bottom - height)]
        for attr, row in records.items():
            if attr == overlay_id:
                continue
            ox, oy, ow, oh = row["x"], row["y"], row["width"], row["height"]
            candidates_x.extend((ox, ox + ow, ox - width, ox + ow - width))
            candidates_y.extend((oy, oy + oh, oy - height, oy + oh - height))
        nearest_x = min(candidates_x, key=lambda value: abs(value - x))
        nearest_y = min(candidates_y, key=lambda value: abs(value - y))
        if abs(nearest_x - x) <= 20:
            x = nearest_x
        if abs(nearest_y - y) <= 20:
            y = nearest_y
        return self._html_overlay_position(overlay_id, x, y, persist=True)

    def _html_overlay_toggle(self, overlay_id):
        spec = self._html_overlay_row(overlay_id)
        key = OVERLAY_ENABLE_KEYS.get(overlay_id)
        if spec is None or not key:
            return False
        previous = bool(self.config.get(key, False))
        self.config[key] = not previous
        try:
            if overlay_id == "ground_popup":
                self.ground_popup_enabled = not previous
                self.update_ground_target_ui()
            self._apply_runtime_feature_toggles()
        except Exception:
            self.config[key] = previous
            if overlay_id == "ground_popup":
                self.ground_popup_enabled = previous
            return False
        self._persist_config()
        try:
            self.add_event_feed_entry(
                "SYSTEM",
                f"{OVERLAY_LABELS.get(overlay_id, overlay_id)} "
                f"{'enabled' if not previous else 'disabled'} in Overlay Studio",
                severity="INFO",
            )
        except Exception:
            pass
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_option_toggle(self, key, requested_value=None):
        allowed = {
            "overlay_mouse_passthrough", "hud_compact_mode",
            "rebuy_warnings_enabled",
            "data_risk_warnings_enabled", "station_info_auto_hide_enabled",
            "survey_status_show_all_bodies",
            "hud_crt_enabled", "hud_crt_motion_enabled", "hud_bright_labels",
            "galnet_ticker_show_date", "galnet_ticker_crt_motion", "galnet_ticker_glitch_on_news",
        }
        key = _text(key, 80)
        if key not in allowed:
            return False
        self.config[key] = (
            requested_value if isinstance(requested_value, bool)
            else not bool(self.config.get(key, False))
        )
        self._persist_config()
        if key == "overlay_mouse_passthrough":
            self._apply_overlay_mouse_passthrough()
        elif key in {"hud_compact_mode", "hud_crt_enabled", "hud_crt_motion_enabled", "hud_bright_labels"}:
            self.update_hud()
        elif key == "station_info_auto_hide_enabled":
            station = getattr(self, "station_info_hud", None)
            if station is not None:
                apply_setting = getattr(station, "apply_auto_hide_setting", None)
                if callable(apply_setting):
                    apply_setting(self, self.config[key])
                elif getattr(self, "current_docked", False) and getattr(self, "current_station_name", None):
                    station.on_docked(self)
                else:
                    station.hide()
        elif key in {"galnet_ticker_show_date", "galnet_ticker_crt_motion", "galnet_ticker_glitch_on_news"}:
            ticker = getattr(self, "galnet_ticker_hud", None)
            if ticker is not None:
                ticker.apply_settings()
        elif key == "survey_status_show_all_bodies":
            survey = getattr(self, "survey_status_hud", None)
            if survey is not None:
                survey._last_render_key = None
                if survey._last_update is not None:
                    survey.update(*survey._last_update)
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_settings_save(self, payload):
        numeric = {
            "overlay_text_scale_percent": (75.0, 200.0, 100.0, True),
            "overlay_opacity_percent": (40.0, 100.0, 100.0, True),
            "prospector_hud_timeout_s": (5.0, 3600.0, 45.0, True),
            "gravity_warning_hud_timeout_s": (5.0, 3600.0, 20.0, True),
            "station_info_timeout_s": (5.0, 3600.0, 30.0, True),
            "contact_scope_timeout_s": (0.0, 3600.0, 45.0, True),
            "gravity_warning_threshold_g": (0.5, 20.0, 3.0, False),
        }
        # Studio saves one field as it changes, so a key missing from the
        # payload keeps the commander's current value rather than resetting.
        for key, (low, high, default, integer) in numeric.items():
            if key not in payload:
                continue
            value = _number(payload.get(key), default)
            value = max(low, min(high, value if value is not None else default))
            self.config[key] = int(round(value)) if integer else round(value, 2)
        if "hud_crt_intensity" in payload:
            intensity = _text(payload.get("hud_crt_intensity") or "Subtle", 20).title()
            self.config["hud_crt_intensity"] = (
                intensity if intensity in {"Subtle", "Standard", "Strong"} else "Subtle"
            )
        # Survey Operations presentation.
        if "survey_spotlight_rotation" in payload:
            mode = _text(payload.get("survey_spotlight_rotation"), 20).casefold()
            self.config["survey_spotlight_rotation"] = (
                mode if mode in SPOTLIGHT_ROTATION_MODES else "auto"
            )
        if "survey_spotlight_threshold" in payload:
            threshold = _number(payload.get("survey_spotlight_threshold"), 8)
            self.config["survey_spotlight_threshold"] = int(round(max(2, min(40, threshold if threshold is not None else 8))))
        if "survey_text_scale_percent" in payload:
            # 0 follows the overlay-wide text scale; otherwise 75-200 %.
            scale = _number(payload.get("survey_text_scale_percent"), 0) or 0
            self.config["survey_text_scale_percent"] = 0 if scale <= 0 else int(round(max(75, min(200, scale))))
        # Navigation HUD type: its own text size (0 follows all overlays; the
        # window grows with it), typeface and small-text size.
        if "hud_text_scale_percent" in payload:
            scale = _number(payload.get("hud_text_scale_percent"), 0) or 0
            self.config["hud_text_scale_percent"] = 0 if scale <= 0 else int(round(max(75, min(200, scale))))
        if "hud_animation_intensity" in payload:
            intensity = _text(payload.get("hud_animation_intensity"), 20).title()
            self.config["hud_animation_intensity"] = intensity if intensity in HUD_ANIMATION_LEVELS else "Standard"
        if "hud_font_face" in payload:
            face = _text(payload.get("hud_font_face"), 20).casefold()
            self.config["hud_font_face"] = face if face in HUD_FONT_FACES else "cockpit"
        if "hud_label_size" in payload:
            labels = _text(payload.get("hud_label_size"), 20).casefold()
            self.config["hud_label_size"] = labels if labels in HUD_LABEL_SIZES else "standard"
        # Galnet ticker: its length, scroll speed and how much it reads.
        if "galnet_ticker_width" in payload:
            low, high = TICKER_WIDTH_RANGE
            width = _integer(payload.get("galnet_ticker_width"), ticker_options(self.config)["width"])
            self.config["galnet_ticker_width"] = max(low, min(high, width))
        if "galnet_ticker_speed" in payload:
            speed = _text(payload.get("galnet_ticker_speed"), 20).casefold()
            self.config["galnet_ticker_speed"] = speed if speed in TICKER_SPEEDS else "standard"
        if "galnet_ticker_content" in payload:
            content = _text(payload.get("galnet_ticker_content"), 20).casefold()
            self.config["galnet_ticker_content"] = content if content in TICKER_CONTENT else "summary"
        if "galnet_ticker_stories" in payload:
            stories = _integer(payload.get("galnet_ticker_stories"), 5)
            self.config["galnet_ticker_stories"] = stories if stories in TICKER_STORIES else 5
        if "galnet_ticker_text_scale_percent" in payload:
            # 0 follows the overlay-wide text size; otherwise 75-200 %.
            scale = _number(payload.get("galnet_ticker_text_scale_percent"), 0) or 0
            self.config["galnet_ticker_text_scale_percent"] = 0 if scale <= 0 else int(round(max(75, min(200, scale))))
        # Its CRT screen and signal glitches.
        for key, choices, default in (
            ("galnet_ticker_crt", TICKER_CRT, "follow"),
            ("galnet_ticker_glitch", TICKER_GLITCH, "occasional"),
            ("galnet_ticker_glitch_strength", TICKER_GLITCH_STRENGTH, "standard"),
        ):
            if key in payload:
                choice = _text(payload.get(key), 20).casefold()
                self.config[key] = choice if choice in choices else default
        # Journal heartbeat orb: its window size and resting eye colour.
        if "heartbeat_orb_size" in payload:
            size = _integer(payload.get("heartbeat_orb_size"), orb_size(self.config))
            self.config["heartbeat_orb_size"] = size if size in ORB_SIZES else orb_size(self.config)
        if "heartbeat_eye_color" in payload:
            eye = _text(payload.get("heartbeat_eye_color"), 20).casefold()
            self.config["heartbeat_eye_color"] = eye if eye in EYE_COLORS else "theme"
        self._persist_config()
        heartbeat = getattr(self, "heartbeat_hud", None)
        if heartbeat is not None and hasattr(heartbeat, "apply_settings"):
            heartbeat.apply_settings()
        ticker = getattr(self, "galnet_ticker_hud", None)
        if ticker is not None and hasattr(ticker, "apply_settings"):
            ticker.apply_settings()
        self.update_hud()
        station = getattr(self, "station_info_hud", None)
        if station is not None and getattr(self, "current_docked", False):
            station.on_docked(self)
        contact_scope = getattr(self, "contact_scope_hud", None)
        if contact_scope is not None:
            apply_timer = getattr(contact_scope, "apply_auto_hide_setting", None)
            if callable(apply_timer):
                apply_timer()
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _handle_html_overlay_studio_command(self, payload):
        operation = _text(payload.get("operation"), 40).casefold()
        overlay_id = _text(payload.get("overlay_id"), 50)
        if operation == "set_opacity":
            sequence = max(0, _integer(payload.get("sequence"), 0))
            if sequence and sequence < getattr(self, "_html_overlay_opacity_sequence", 0):
                return True
            if sequence:
                self._html_overlay_opacity_sequence = sequence
            current = _integer(self.config.get("overlay_opacity_percent"), 100)
            requested = _number(payload.get("value"), current)
            opacity = int(round(max(40, min(100, requested))))
            if opacity != current:
                self.config["overlay_opacity_percent"] = opacity
                self._persist_config()
                self.update_hud()
                self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation.startswith("rhino_") and not RHINO_MAP_AVAILABLE:
            return False
        if operation == "rhino_center":
            return self._set_rhino_minimap_center()
        if operation == "rhino_border":
            return self._set_rhino_minimap_border()
        if operation == "rhino_drill":
            return self._mark_rhino_drill()
        if operation == "rhino_reset":
            return bool(payload.get("confirmed") and self._reset_rhino_minimap())
        if operation == "rhino_open_maps":
            return self._open_rhino_minimap_folder()
        if operation == "move":
            sequence = max(0, _integer(payload.get("sequence"), 0))
            seen = getattr(self, "_html_overlay_move_sequences", None)
            if not isinstance(seen, dict):
                seen = self._html_overlay_move_sequences = {}
            if sequence and sequence < _integer(seen.get(overlay_id), 0):
                return True
            if sequence:
                seen[overlay_id] = sequence
            return self._html_overlay_position(
                overlay_id, payload.get("x"), payload.get("y"),
                persist=bool(payload.get("commit")),
                preview=not bool(payload.get("commit")),
            )
        if operation == "toggle":
            return self._html_overlay_toggle(overlay_id)
        if operation == "snap":
            return self._html_overlay_snap(overlay_id)
        if operation == "reset":
            x, y = DEFAULT_POSITIONS.get(overlay_id, (30, 30))
            return self._html_overlay_position(overlay_id, x, y, persist=True)
        if operation == "toggle_option":
            return self._html_overlay_option_toggle(
                payload.get("key"), payload.get("value"),
            )
        if operation == "save_settings":
            return self._html_overlay_settings_save(payload)
        if operation == "save_preset":
            name = _text(payload.get("name"), 50)
            if not name:
                return False
            presets = self.config.setdefault("overlay_layout_presets", {})
            presets[name] = {
                row["id"]: {"x": row["x"], "y": row["y"]}
                for row in self._html_overlay_records()
            }
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "apply_preset":
            name = _text(payload.get("name"), 50)
            preset = (self.config.get("overlay_layout_presets") or {}).get(name)
            if not isinstance(preset, dict):
                return False
            applied = False
            for attr, position in preset.items():
                if not isinstance(position, dict) or self._html_overlay_row(attr) is None:
                    continue
                applied = self._html_overlay_position(
                    attr, position.get("x"), position.get("y"), persist=False,
                ) or applied
            if applied:
                self._persist_config()
            return applied
        if operation == "delete_preset":
            name = _text(payload.get("name"), 50)
            presets = self.config.get("overlay_layout_presets") or {}
            if name not in presets:
                return False
            presets.pop(name, None)
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        return False
