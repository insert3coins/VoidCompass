"""Overlay Layout Studio model and command controller."""

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
        rhino_tracker = getattr(self, "rhino_minimap", None)
        rhino_map = getattr(rhino_tracker, "active", None)
        rhino_maps_count, rhino_maps_size = (
            rhino_tracker.usage() if rhino_tracker is not None else (0, 0)
        )
        return {
            "desktop": self._html_overlay_desktop(),
            "overlays": self._html_overlay_records(
                live=getattr(self, "_html_dashboard_active_page", "") == "overlay-studio",
            ),
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
                "overlay_text_scale_percent": _integer(self.config.get("overlay_text_scale_percent"), 100),
                "overlay_opacity_percent": _integer(self.config.get("overlay_opacity_percent"), 100),
                "sample_clear_notifications_enabled": bool(self.config.get("sample_clear_notifications_enabled", True)),
                "rebuy_warnings_enabled": bool(self.config.get("rebuy_warnings_enabled", True)),
                "data_risk_warnings_enabled": bool(self.config.get("data_risk_warnings_enabled", True)),
                "prospector_hud_timeout_s": _integer(self.config.get("prospector_hud_timeout_s"), 45),
                "gravity_warning_hud_timeout_s": _integer(self.config.get("gravity_warning_hud_timeout_s"), 20),
                "station_info_auto_hide_enabled": bool(self.config.get("station_info_auto_hide_enabled", False)),
                "survey_status_show_all_bodies": bool(self.config.get("survey_status_show_all_bodies", False)),
                "station_info_timeout_s": _integer(self.config.get("station_info_timeout_s"), 30),
                "contact_scope_timeout_s": _integer(self.config.get("contact_scope_timeout_s"), 45),
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
        desktop = self._html_overlay_desktop()
        left, top = desktop["left"], desktop["top"]
        right, bottom = left + desktop["width"], top + desktop["height"]
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
            "sample_clear_notifications_enabled", "rebuy_warnings_enabled",
            "data_risk_warnings_enabled", "station_info_auto_hide_enabled",
            "survey_status_show_all_bodies",
            "hud_crt_enabled", "hud_crt_motion_enabled",
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
        elif key in {"hud_compact_mode", "hud_crt_enabled", "hud_crt_motion_enabled"}:
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
        for key, (low, high, default, integer) in numeric.items():
            value = _number(payload.get(key), default)
            value = max(low, min(high, value if value is not None else default))
            self.config[key] = int(round(value)) if integer else round(value, 2)
        intensity = _text(payload.get("hud_crt_intensity") or "Subtle", 20).title()
        self.config["hud_crt_intensity"] = (
            intensity if intensity in {"Subtle", "Standard", "Strong"} else "Subtle"
        )
        self._persist_config()
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
