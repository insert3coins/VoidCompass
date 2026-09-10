"""Navigation state and HTML publication; no native drawing or widgets."""
import logging
import math
import os
import time
import route_strip
import theme_state as ui_theme
from application_runtime import OverlayWindowState
from config import COLOR_ACCENT, COLOR_GREEN, COLOR_TEXT, COLOR_ORANGE, COLOR_MUTED, COLOR_YELLOW
from html_navigation_hud import HtmlNavigationHudBridge
from html_overlay_runtime import overlay_opacity_ratio

class TacticalHUD:
    def __init__(self, root, config, on_widget_click=None):
        self.config = config
        self.on_widget_click = on_widget_click
        self.full_width, self.full_height = 620, 322
        self.compact_width, self.compact_height = 500, 306
        self.width, self.base_height = self._target_dimensions()
        self._desired_pos = (self._safe_int(config.get('hud_x'), 100), self._safe_int(config.get('hud_y'), 100))
        self.win = OverlayWindowState(root, self.width, self.base_height, *self._desired_pos)
        self._html_bridge = None
        self._html_ready = False
        self._html_last_model = None
        self._html_sync_job = None
        self._html_last_window_fingerprint = None
        self._last_update_args = None
        self.win.on_destroy(self._on_window_destroyed)
        self._schedule_html_sync()

    def update(self, current_sys, dest_name, dist_ly, scanned, total, r_pos,
               system_traffic, game_r_pos=None, route_waypoint=None, route_counts=None,
               hud_status='OK', hud_health=None, nav_context=None):
        self._last_update_args = (current_sys, dest_name, dist_ly, scanned, total, r_pos,
            system_traffic, game_r_pos, route_waypoint, route_counts, hud_status, hud_health, nav_context)
        self._html_last_model = self._build_html_model(current_sys, scanned, total, r_pos,
            system_traffic, game_r_pos, route_waypoint, route_counts, nav_context)
        if self._html_bridge is not None:
            self._html_bridge.publish(self._html_last_model)

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
            "click_through": bool(self.config.get("overlay_mouse_passthrough", True)),
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
            "survey": {
                "label": "COUNT UNKNOWN", "state": "unknown",
                "scanned": 0, "total": 0, "total_known": False,
                "count": "0/? · --%", "percent": 0,
                "signals": {"bio": 0, "geo": 0, "mining": 0, "valuable": 0},
            },
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
        """Enable the isolated WebView2 HUD using the Python state model."""
        enabled = bool(enabled and os.name == "nt")
        if not enabled:
            bridge, self._html_bridge = self._html_bridge, None
            self._html_ready = False
            if bridge is not None:
                bridge.dispose()
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
            pass
            logging.warning("HTML Navigation HUD unavailable; overlay suppressed: %s", exc)
            return False

    def _schedule_html_sync(self):
        try:
            self._html_sync_job = self.win.call_later(180, self._sync_html_renderer)
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
        previous_window = (self._html_last_model or {}).get("window") or {}
        if previous_window.get("visible") != window.get("visible"):
            # The browser's state animation also consumes visibility. Keep
            # its model in sync with the host during startup and hotkey shows.
            model = dict(self._html_last_model or self._html_base_model())
            model["window"] = window
            self._html_last_model = model
            bridge.publish(model)
        else:
            bridge.update_window(window)
        self._html_last_window_fingerprint = repr(window)
        return True

    def _sync_html_renderer(self):
        self._html_sync_job = None
        bridge = self._html_bridge
        if bridge is not None:
            if bridge.startup_failed:
                logging.warning(
                    "HTML Navigation HUD unavailable; overlay remains suppressed (%s)",
                    bridge.host_status or "host exited or renderer did not connect",
                )
                self.set_html_renderer(False)
            else:
                was_ready = self._html_ready
                ready = bridge.ready
                self._html_ready = ready
                if ready:
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
                self.win.cancel(self._html_sync_job)
            except Exception:
                pass
            self._html_sync_job = None
        bridge, self._html_bridge = self._html_bridge, None
        if bridge is not None:
            bridge.dispose()

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

    def _badge_color(self, state):
        if state == "alert":
            return COLOR_ORANGE
        if state == "ok":
            return COLOR_GREEN
        if state == "info":
            return COLOR_YELLOW
        return COLOR_MUTED

    def _state_text(self, nav_context):
        flight_state = str(nav_context.get("flight_state") or "").upper()
        vehicle_name = str(nav_context.get("vehicle_name") or "").upper()
        music_mode = str(nav_context.get("music_mode") or "").upper()
        music_track = str(nav_context.get("music_track") or "")
        track_key = music_track.replace(" ", "").replace("_", "").upper()
        fsd = nav_context.get("fsd_readiness") or {}
        fsd_state = str(fsd.get("state") or "ready")
        asteroid_context = bool(
            fsd_state == "asteroid_field" or fsd.get("asteroid_kind")
        )
        normal_ship_flight = bool(
            flight_state in {"", "FLIGHT"}
            and not any(nav_context.get(key) for key in (
                "docked", "landed", "in_fighter", "in_srv", "on_foot",
                "in_taxi", "in_multicrew",
            ))
        )
        ship_config = nav_context.get("ship_config") or {}
        suit_status = nav_context.get("suit_status") or {}
        docking_state = nav_context.get("docking_state") or {}
        journal_event = nav_context.get("journal_event") or {}
        journal_kind = str(journal_event.get("kind") or "")
        transition_label = str(journal_event.get("state_label") or "").strip()

        # StartJump is only the countdown. The exact Status fsdJump flag owns
        # HYPERSPACE, and FSDJump supplies the bounded ARRIVAL phase.
        if fsd_state in {"carrier_preparing", "carrier_lockdown"}:
            return "CARRIER PREPARING" if fsd_state == "carrier_preparing" else "CARRIER LOCKDOWN"
        if fsd_state == "carrier_transit":
            return "CARRIER TRANSIT"
        if fsd_state == "carrier_arrival":
            return "CARRIER ARRIVAL"
        if fsd_state == "arrival":
            return "ARRIVAL"
        if fsd_state == "hyperspace":
            return "HYPERSPACE"
        if journal_kind in {"system_reboot", "jet_cone_damage"} and transition_label:
            return transition_label.upper()
        if ship_config.get("overheating"):
            return "HEAT CRITICAL"
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
        if journal_kind in {
                "vehicle_deploy", "vehicle_board", "vehicle_switch",
                "interdiction", "interdiction_clear", "signal_drop",
                "dock_request", "dock_denied", "maintenance",
                "target_lock", "target_body", "target_signal", "target_system",
                "target_clear", "dss_efficiency", "dss_complete", "fsd_injection"}:
            if transition_label:
                return transition_label.upper()
        if nav_context.get("interdicted") or track_key == "INTERDICTION":
            return "INTERDICTION"

        on_foot = bool(
            flight_state == "ONFOOT" or nav_context.get("on_foot")
            or music_mode == "ONFOOT"
        )
        if on_foot:
            if suit_status.get("low_oxygen"):
                return "SUIT OXYGEN LOW"
            if suit_status.get("low_health"):
                return "SUIT HEALTH LOW"
            if suit_status.get("very_hot"):
                return "EXTREME HEAT"
            if suit_status.get("very_cold"):
                return "EXTREME COLD"
            if suit_status.get("hot"):
                return "SUIT HEAT"
            if suit_status.get("cold"):
                return "SUIT COLD"

        focus_key = (
            str(nav_context.get("gui_focus", ""))
            .replace(" ", "").replace("_", "").upper()
        )
        focus_labels = {
            "1": "RIGHT PANEL",
            "INTERNALPANEL": "RIGHT PANEL",
            "2": "LEFT PANEL",
            "EXTERNALPANEL": "LEFT PANEL",
            "3": "COMMS",
            "COMMSPANEL": "COMMS",
            "4": "ROLE PANEL",
            "ROLEPANEL": "ROLE PANEL",
            "5": "SERVICES",
            "STATIONSERVICES": "SERVICES",
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
        if docking_state.get("phase") in {"requested", "granted"}:
            docking_label = str(docking_state.get("label") or "").strip()
            if docking_label:
                return docking_label.upper()
        music_states = {
            "LIFEFORMFOGCLOUD": "PHENOMENA",
            "COMBATSRV": "SRV THREAT",
            "CAPITALSHIP": "CAPITAL SHIP",
            "UNKNOWNENCOUNTER": "UNIDENTIFIED",
            "COMBATLARGEDOGFIGHT": "HEAVY COMBAT",
            "DOCKINGCOMPUTER": "DOCK ASSIST",
            "UNKNOWNSETTLEMENT": "SETTLEMENT",
            "DESTINATIONFROMSUPERCRUISE": "LOCAL ARRIVAL",
        }
        music_state = None if nav_context.get("docked") else music_states.get(track_key)
        # Threat, docking and the brief post-drop acquisition window need to
        # surface before ordinary environmental states such as mass lock. FSD,
        # map and scanner evidence above still retains absolute precedence.
        if music_state in {
                "SRV THREAT", "CAPITAL SHIP", "UNIDENTIFIED",
                "HEAVY COMBAT", "DOCK ASSIST", "LOCAL ARRIVAL"}:
            return music_state

        # Pilot-selected ship modes are more useful than the persistent local
        # environment.  In a ring/cluster they should temporarily animate in
        # place of ASTEROID FIELD, which returns as soon as the mode is cleared.
        # Short-lived hazards, scanner/map focus and journal transitions above
        # still retain first refusal.
        if normal_ship_flight:
            if ship_config.get("silent_running"):
                return "SILENT RUNNING"
            if ship_config.get("flight_assist_off"):
                return "FLIGHT ASSIST OFF"
        if asteroid_context and normal_ship_flight:
            return "ASTEROID FIELD"
        if fsd_state == "surface_station_vicinity" and normal_ship_flight:
            # A surface port is more specific than the parent planet's generic
            # approach phase, but maps, scanners, clearance and pilot-selected
            # ship modes above still retain priority.
            return "SURFACE STATION"
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
        if (ship_config.get("supercruise_assist")
                and flight_state == "SUPERCRUISE"):
            return "SC ASSIST"
        # Phenomena and settlement music provides context only after exact
        # surface motion has had first refusal, but is still more informative
        # than a generic mass-lock state while the mood remains current.
        if music_state:
            return music_state
        if fsd_state == "carrier_vicinity" and normal_ship_flight:
            return "CARRIER VICINITY"
        if fsd_state == "station_vicinity" and normal_ship_flight:
            return "STATION VICINITY"
        if fsd_state == "mass_lock" and normal_ship_flight:
            return "MASS LOCK"
        if flight_state == "TAXI" or nav_context.get("in_taxi"):
            return "TAXI"
        if on_foot:
            if nav_context.get("on_carrier_deck"):
                return "CARRIER DECK"
            return "ONFOOT"
        if nav_context.get("docked"):
            return "DOCKED"
        if flight_state in {"SRV", "SCARAB", "SCORPION", "RHINO", "NOMAD"} or nav_context.get("in_srv"):
            if ship_config.get("srv_handbrake"):
                return "HANDBRAKE"
            if ship_config.get("srv_turret"):
                return "TURRET VIEW"
            if ship_config.get("srv_drive_assist"):
                return "DRIVE ASSIST"
        if flight_state == "NOMAD" or vehicle_name == "NOMAD":
            return "NOMAD"
        if flight_state == "FIGHTER" or nav_context.get("in_fighter"):
            return "FIGHTER"
        if flight_state in {"SRV", "SCARAB", "SCORPION", "RHINO"} or nav_context.get("in_srv"):
            return vehicle_name if vehicle_name in {"SCARAB", "SCORPION", "RHINO"} else "SRV"
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
        if (state_text.endswith((" DEPLOY", " RECOVERY", " DEPART", " CONTROL"))
                or state_text.startswith("BOARDING ")
                or state_text in {"MULTICREW LINK", "CREW RETURN"}):
            return COLOR_ACCENT
        if state_text in {"ARRIVAL", "CARRIER ARRIVAL"}:
            return COLOR_GREEN
        if state_text.startswith("PAD ") or state_text == "DOCK CLEARED":
            return COLOR_GREEN
        if state_text in {"PHENOMENA", "LOCAL ARRIVAL"}:
            return COLOR_GREEN
        if state_text in (
            "DOCKED", "LANDED", "FSS", "DSS", "FIGHTER", "SRV", "SCARAB", "SCORPION", "RHINO", "NOMAD",
            "TAXI", "MULTICREW", "CARRIER DECK",
            "ONFOOT", "MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY",
            "CODEX", "EXPLORATION", "STATION", "FSD COOLDOWN", "ORBITAL APPROACH",
            "ORBITAL DEPARTURE", "SURFACE HOLD", "DOCK ASSIST", "RIGHT PANEL",
            "LEFT PANEL", "COMMS", "ROLE PANEL", "SERVICES",
            "SC ASSIST", "HANDBRAKE", "TURRET VIEW", "DRIVE ASSIST",
            "AFMU REPAIR", "DOCK REQUEST", "STATION VICINITY", "CARRIER VICINITY",
            "SURFACE STATION",
        ):
            return COLOR_ACCENT
        if state_text in {
                "MASS LOCK", "ASTEROID FIELD", "GLIDE",
                "SURFACE APPROACH", "SURFACE DEPARTURE", "UNIDENTIFIED",
                "SETTLEMENT", "FLIGHT ASSIST OFF", "SILENT RUNNING",
                "SYSTEM REBOOT", "DOCK CANCELLED", "DOCK TIMEOUT"}:
            return COLOR_YELLOW
        if state_text in (
            "HYPERSPACE", "SUPERCRUISE", "JUMPING", "COMBAT",
            "FSD CHARGE", "HYPER CHARGE", "SCO OVERCHARGE",
            "CARRIER PREPARING", "CARRIER LOCKDOWN", "CARRIER TRANSIT",
            "INTERDICTION", "INTERDICTED", "SRV THREAT", "CAPITAL SHIP",
            "HEAVY COMBAT",
            "HEAT CRITICAL", "SUIT OXYGEN LOW", "SUIT HEALTH LOW",
            "EXTREME HEAT", "EXTREME COLD", "SUIT HEAT", "SUIT COLD",
            "JET CONE DAMAGE", "DOCK DENIED",
        ):
            return COLOR_ORANGE
        if state_text == "INTERDICTION EVADED":
            return COLOR_GREEN
        if state_text.startswith("DSS EFFICIENT"):
            return COLOR_GREEN
        if state_text.startswith("DSS ") or state_text.startswith("TARGET ") or state_text.endswith(" TARGET"):
            return COLOR_ACCENT
        if state_text.startswith("SIGNAL THREAT"):
            return COLOR_ORANGE
        if state_text == "SIGNAL DROP":
            return COLOR_YELLOW
        return "#7d8891"

    @staticmethod
    def _navigation_motion_profile(state_text):
        """Map journal/UI states to small, visually distinct motion families."""
        state = str(state_text or "FLIGHT").upper()
        if state.endswith(" DEPLOY") or state.endswith(" DEPART"):
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
        if state == "SC ASSIST":
            return "supercruise_assist"
        if state == "FLIGHT ASSIST OFF":
            return "flight_assist_off"
        if state == "SILENT RUNNING":
            return "silent_running"
        if state == "HEAT CRITICAL":
            return "heat_critical"
        if state in {
                "SUIT OXYGEN LOW", "SUIT HEALTH LOW", "EXTREME HEAT",
                "EXTREME COLD", "SUIT HEAT", "SUIT COLD"}:
            return "suit_hazard"
        if state == "HANDBRAKE":
            return "srv_handbrake"
        if state == "TURRET VIEW":
            return "srv_turret"
        if state == "DRIVE ASSIST":
            return "srv_drive_assist"
        if state.startswith("PAD ") or state in {"DOCK CLEARED", "DOCK REQUEST"}:
            return "docking_clearance"
        if state in {"DOCK DENIED", "DOCK CANCELLED", "DOCK TIMEOUT"}:
            return "docking_denied"
        if state == "AFMU REPAIR":
            return "maintenance"
        if state == "SYSTEM REBOOT":
            return "system_reboot"
        if state == "JET CONE DAMAGE":
            return "jet_cone_damage"
        if state == "MASS LOCK":
            return "fsd_lock"
        if state == "SURFACE STATION":
            return "surface_station"
        if state in {"STATION VICINITY", "CARRIER VICINITY"}:
            return "station"
        if state.startswith("TARGET ") or state.endswith(" TARGET"):
            return "target_lock"
        if state.startswith("DSS "):
            return "scanner"
        if state.startswith("FSD INJECTION"):
            return "fsd_lock"
        if state == "ASTEROID FIELD":
            return "asteroid_field"
        if state in {"FSD CHARGE", "HYPER CHARGE"}:
            return "fsd_charge"
        if state == "SCO OVERCHARGE":
            return "supercruise_overcharge"
        if state in {"CARRIER PREPARING", "CARRIER LOCKDOWN"}:
            return "carrier_preparing" if state == "CARRIER PREPARING" else "carrier_lockdown"
        if state == "CARRIER TRANSIT":
            return "carrier_transit"
        if state == "CARRIER ARRIVAL":
            return "carrier_arrival"
        if state == "CARRIER DECK":
            return "carrier_deck"
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
        if state == "RIGHT PANEL":
            return "right_panel"
        if state == "LEFT PANEL":
            return "left_panel"
        if state == "COMMS":
            return "comms_panel"
        if state == "ROLE PANEL":
            return "role_panel"
        if state == "SERVICES":
            return "station_services"
        if state == "PHENOMENA":
            return "phenomena"
        if state == "SRV THREAT":
            return "srv_threat"
        if state == "CAPITAL SHIP":
            return "capital_contact"
        if state == "UNIDENTIFIED":
            return "unknown_contact"
        if state == "HEAVY COMBAT":
            return "heavy_combat"
        if state == "DOCK ASSIST":
            return "docking_assist"
        if state == "SETTLEMENT":
            return "settlement_area"
        if state == "LOCAL ARRIVAL":
            return "local_arrival"
        if state == "ARRIVAL":
            return "arrival"
        if state in {"DOCKED", "STATION"}:
            return "docked"
        if state == "LANDED":
            return "landed"
        if state == "ONFOOT":
            return "on_foot"
        if state in {"SRV", "SCARAB", "SCORPION", "RHINO", "NOMAD"}:
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

    @staticmethod
    def _context_presentation(nav_context, attention_text="", attention_state="muted"):
        """Choose the single most useful contextual line for the current state."""
        context = nav_context or {}
        travel = context.get("fsd_readiness") or {}
        travel_state = str(travel.get("state") or "").casefold()
        if travel_state in {"carrier_preparing", "carrier_lockdown", "carrier_transit", "carrier_arrival"}:
            target = str(travel.get("target") or "").strip()
            detail = f" · {target}" if target else ""
            if travel_state in {"carrier_preparing", "carrier_lockdown"}:
                schedule = travel.get("carrier_schedule") or {}
                seconds = max(0, int(schedule.get("remaining_seconds") or 0))
                carrier = "SQUADRON" if schedule.get("carrier_type") == "SquadronCarrier" else "PERSONAL"
                return f"{carrier} · JUMP IN {seconds // 60:02d}:{seconds % 60:02d}{detail}", COLOR_ORANGE
            if travel_state == "carrier_transit":
                return f"CARRIER TRANSIT{detail}", COLOR_ORANGE
            return f"CARRIER ARRIVAL{detail}", COLOR_GREEN
        if travel_state in {
                "station_vicinity", "carrier_vicinity",
                "surface_station_vicinity"}:
            station = str(travel.get("local_space_name") or "").strip()
            detail = f" · {station}" if station else ""
            labels = {
                "carrier_vicinity": "CARRIER VICINITY",
                "surface_station_vicinity": "SURFACE STATION",
                "station_vicinity": "STATION VICINITY",
            }
            label = labels[travel_state]
            return f"{label}{detail}", COLOR_ACCENT
        injection = context.get("fsd_injection") or {}
        if injection.get("armed"):
            try:
                amount = int(float(injection.get("percent") or 0))
            except (TypeError, ValueError):
                amount = 0
            suffix = f" · +{amount}%" if amount else ""
            return f"FSD INJECTION ARMED{suffix}", COLOR_ACCENT
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
            left = str(route.get("target") or "")
            center = str(route.get("progress_text") or route.get("jump_text") or "")
            right = str((nav_context or {}).get("next_distance") or "")
            if right == "--":
                right = ""
            return left, center, right
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
            label, tone, state = "COMPLETE", COLOR_ACCENT, "complete"
        elif live:
            label, tone, state = "LIVE FSS", COLOR_ORANGE, "live"
        else:
            label, tone, state = "RECORDED SURVEY", COLOR_ACCENT, "retained"
        if not complete:
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
                "cargo_scoop": bool(ship_config.get("cargo_scoop")),
                "analysis_mode": bool(ship_config.get("analysis_mode")),
                "hardpoints_deployed": bool(ship_config.get("hardpoints_deployed")),
                "shields_known": ship_config.get("shields_up") is not None,
                "shields_up": bool(ship_config.get("shields_up")),
                "night_vision": bool(ship_config.get("night_vision")),
                "in_main_ship": bool(ship_config.get("in_main_ship")),
                "low_fuel": bool(ship_config.get("low_fuel")),
                "fuel_scooping": bool(nav_context.get("fuel_scooping")),
                "neutron_boost": bool((nav_context.get("neutron_boost") or {}).get("armed")),
                "neutron_boost_value": finite_number(
                    (nav_context.get("neutron_boost") or {}).get("value"), 0.0,
                ),
                "fsd_injection": bool((nav_context.get("fsd_injection") or {}).get("armed")),
                "fsd_injection_percent": finite_number(
                    (nav_context.get("fsd_injection") or {}).get("percent"), 0.0,
                ),
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
        positions, _dense = route_strip.pip_layout(0, track_width, source_hops)
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
            "target": str(route.get("target") or ""),
            "progress_text": str(route.get("progress_text") or route.get("jump_text") or ""),
            "leg_distance": str((route.get("distance") if route_waypoint else nav_context.get("next_distance")) or ""),
            "remaining_distance": str(nav_context.get("total_distance_text") or "") if not route_waypoint else "",
            "next_distance": next_distance,
            "distance": route_distance,
            "active": bool(route.get("active")),
            "complete": bool(route.get("complete")),
            "origin_current": bool(route.get("track_origin_current", True)),
            "progress_percent": round(progress_percent, 2),
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
            "state": survey["state"],
            "scanned": int(survey["scanned"]),
            "total": int(survey["total"]),
            "total_known": survey["state"] != "unknown",
            "count": scan_progress_text,
            "percent": round(float(survey["pct"]) * 100.0, 2),
            "live": bool(survey["live"]),
            "complete": bool(survey["complete"]),
            "signals": {
                "bio": max(0, int(nav_context.get("bio_signals", 0) or 0)),
                "geo": max(0, int(nav_context.get("geo_signals", 0) or 0)),
                "mining": max(0, int(nav_context.get("mining_signals", 0) or 0)),
                "valuable": max(0, int(nav_context.get("valuable_count", 0) or 0)),
            },
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
            "attention": attention_state if attention_text else "",
            "primary": context_text,
            "primary_color": context_color,
            "secondary": secondary_text,
            "secondary_color": self._badge_color(attention_state),
            "traffic": self._traffic_summary(system_traffic, compact=True),
        }
        model["window"] = self._html_window_payload()
        return model

    def apply_theme(self, palette=None):
        """Force an immediate repaint after the shared palette is rebound."""
        del palette
        self._last_render_fingerprint = None
        if self._last_update_args is not None:
            self.update(*self._last_update_args)
