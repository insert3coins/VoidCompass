"""Application actions and profile state, independent of dashboard widgets."""
import time
import logging
import math
import threading
from collections import deque
from application_runtime import OverlayWindowState
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE
import themes
from html_ground_overlay import attach_html_ground_overlay

class DashboardCoreMixin:
    JOURNAL_HISTORY_LIMIT = 100
    UI_BG = themes.ACTIVE_PALETTE['bg']
    UI_MUTED = themes.ACTIVE_PALETTE['muted']
    UI_DIM = themes.ACTIVE_PALETTE['dim']
    UI_OK = themes.ACTIVE_PALETTE['green']
    UI_WARN = themes.ACTIVE_PALETTE['yellow']
    UI_FAIL = themes.ACTIVE_PALETTE['red']

    def setup_layout(self):
        """Initialise dashboard records; all layout lives in web/dashboard."""
        self.log_entries = []
        self.journal_history_entries = []
        self.event_feed_filter = 'ALL'
        self._active_page = 'OVERVIEW'
        self.dashboard_host = None
        self.ground_popup = None
        self._journal_history_pending = deque()
        self._event_feed_pending = deque()
        self._event_feed_pending_lock = threading.Lock()

    def _refresh_command_dashboard(self, route_progress=None):
        self._schedule_html_dashboard_publish()

    def update_dashboard_panels(self):
        self._schedule_html_dashboard_publish()

    def update_dashboard_ui(self):
        if getattr(self, '_startup_restore_active', False):
            self._startup_restore_ui_pending = True
            return
        self.update_waypoint_display()
        self._schedule_html_dashboard_publish()

    def update_carrier_panel(self, force=False):
        self._schedule_html_dashboard_publish()

    def update_nav_label(self):
        self._schedule_html_dashboard_publish()

    def schedule_dashboard_refresh(self, full=False):
        if full:
            self.dashboard_refresh_full_pending = True
        if getattr(self, '_startup_restore_active', False):
            self._startup_restore_ui_pending = True
            return
        if self.dashboard_refresh_job is None:
            self.dashboard_refresh_job = self.root.call_later(120, self._run_scheduled_dashboard_refresh)

    def _run_scheduled_dashboard_refresh(self):
        self.dashboard_refresh_job = None
        if self.dashboard_refresh_full_pending:
            self.dashboard_refresh_full_pending = False
            self.update_dashboard_ui()
        else:
            self.update_dashboard_panels()

    def _tick_session_clock(self):
        if self.is_running:
            self._schedule_html_dashboard_publish()
            self.root.call_later(1000, self._tick_session_clock)

    def update_waypoint_display(self):
        manager = getattr(self, 'waypoint_manager', None)
        if manager is None:
            return
        index = manager.get_waypoint_index(self.current_sys)
        changed = False
        for waypoint in manager.waypoints[:index + 1]:
            if not waypoint.get('visited'):
                waypoint['visited'] = True
                changed = True
                self.add_event_feed_entry('ROUTE', f"Waypoint visited: {waypoint.get('name', '')}")
        if changed:
            manager.save()
        self.target_waypoint = next((row for row in manager.waypoints if not row.get('visited')), None)
        self.update_hud()
        self._schedule_html_dashboard_publish()

    def _dashboard_copy_next(self):
        return self._html_copy_text(self._dashboard_next_destination())

    def _run_nav_command(self, label, command):
        return command()

    def show_dashboard_page(self):
        return self._request_html_dashboard_page('overview')

    def open_ground_target_window(self):
        return self._request_html_dashboard_page('ground')

    def _capture_dashboard_window_geometry(self):
        runtime = getattr(self.root, '_voidcompass_html_dashboard_runtime', None)
        if runtime:
            geometry = runtime.geometry_string()
            if geometry:
                self.config['dashboard_window_geometry'] = geometry

    def _apply_dashboard_window_geometry(self):
        runtime = getattr(self.root, '_voidcompass_html_dashboard_runtime', None)
        if runtime:
            from html_dashboard_runtime import _geometry_payload
            runtime.server.update_host_state(_geometry_payload(self.config.get('dashboard_window_geometry')))

    def _update_main_window_title(self):
        runtime = getattr(self.root, '_voidcompass_html_dashboard_runtime', None)
        if runtime:
            from version import APP_VERSION
            runtime.server.update_host_state({'title': f'VOID COMPASS // v{APP_VERSION}'})

    def _sync_flight_log_shell_visibility(self):
        self._schedule_html_dashboard_publish()

    def _apply_navigation_group_state(self):
        self._schedule_html_dashboard_publish()

    def _sync_cache_rebuild_edsm_option(self):
        self._schedule_html_dashboard_publish()

    @staticmethod
    def _widget_alive(widget):
        return widget is not None and not getattr(widget, 'closed', True)

    def set_event_feed_filter(self, value):
        self.event_feed_filter = str(value or 'ALL').upper()
        self._schedule_html_dashboard_publish()

    def add_event_feed_entry(self, tag, message, severity='INFO', copy_text=None, url=None):
        if not self.root.is_owner_thread:
            self._ui_post(self.add_event_feed_entry, tag, message, severity, copy_text, url)
            return
        if not message or (getattr(self, 'batch_mode', False) and getattr(self, 'is_first_load', False)):
            return
        entry = {'ts': time.time(), 'tag': str(tag or 'INFO').upper(),
                 'severity': str(severity or 'INFO').upper().replace('ERROR', 'FAIL'),
                 'message': ' '.join(str(message).splitlines()), 'copy_text': copy_text or str(message),
                 'url': url, 'new_until': time.time() + 6}
        previous = self.event_feed_entries[0] if self.event_feed_entries else {}
        if previous.get('tag') == entry['tag'] and previous.get('message') == entry['message'] and entry['ts']-previous.get('ts',0)<1.5:
            return
        self.event_feed_entries.insert(0, entry)
        del self.event_feed_entries[self.event_feed_max_entries:]
        self._schedule_html_dashboard_publish()

    def add_journal_history_entry(self, event_name, payload=None):
        if not self.root.is_owner_thread:
            self._ui_post(self.add_journal_history_entry, event_name, payload)
            return
        if not event_name:
            return
        title, detail = self._journal_history_text(event_name, payload)
        self.journal_history_entries.insert(0, {'ts':time.time(),'event':event_name,'title':title,'detail':detail})
        del self.journal_history_entries[self.JOURNAL_HISTORY_LIMIT:]

    def _tick_event_feed_queue(self):
        # Events now use the application dispatcher directly; no UI polling queue.
        self._schedule_html_dashboard_publish()

    def log(self, message):
        logging.info('%s', message)
        if not self.root.is_owner_thread:
            self._ui_post(self._append_log_record, str(message))
        else:
            self._append_log_record(str(message))

    def _append_log_record(self, message):
        self.log_entries.append(f"{time.strftime('%H:%M:%S')} {message}")
        del self.log_entries[:-2000]

    def _ensure_ground_popup(self):
        if self.ground_popup is None or self.ground_popup.closed:
            self.ground_popup = OverlayWindowState(self.root, 370, 154,
                int(self.config.get('ground_popup_x',1320)), int(self.config.get('ground_popup_y',160)))
            attach_html_ground_overlay(self, self.ground_popup, 'ground', 'Planet Waypoint Navigation',
                                       'ground_popup_enabled', 'ground_popup_x', 'ground_popup_y')
        return self.ground_popup

    def _destroy_ground_popup(self):
        if self.ground_popup is not None:
            self.ground_popup.destroy()
            self.ground_popup = None

    def update_ground_target_ui(self):
        solution = self._ground_target_solution()
        if self.ground_popup_enabled and self._ground_target_should_show(solution):
            self._ensure_ground_popup().deiconify()
        elif self.ground_popup is not None:
            self.ground_popup.withdraw()
        self._schedule_html_dashboard_publish()

    def toggle_ground_popup(self):
        self.ground_popup_enabled = not self.ground_popup_enabled
        self.config['ground_popup_enabled'] = self.ground_popup_enabled
        self._save_config_file()
        self.update_ground_target_ui()

    def clear_ground_target(self):
        self.target_latlon_active = False
        self.target_lat = self.target_lon = None
        self.config.update(ground_target_active=False, ground_target_lat=None, ground_target_lon=None)
        self._save_config_file()
        self.update_ground_target_ui()

    def check_updates(self, manual=False):
        def check():
            import requests
            try:
                result = requests.get('https://api.github.com/repos/insert3coins/VoidCompass/releases/latest', timeout=15)
                result.raise_for_status()
                data = result.json()
                self._ui_post(self.add_event_feed_entry, 'UPDATE', f"Latest release: {data.get('tag_name','Unknown')}", url=data.get('html_url'))
            except Exception as exc:
                if manual:
                    self._ui_post(self.add_event_feed_entry, 'UPDATE', f'Update check failed: {exc}', severity='WARN')
        threading.Thread(target=check, name='release-check', daemon=True).start()

    def _current_route_progress(self):
        """Return compact, truthful progress for the live route or saved waypoints."""
        route = list(getattr(self, "route_list", None) or [])
        current = getattr(self, "current_sys", None)
        if route:
            try:
                current_index = route.index(current)
            except (ValueError, TypeError):
                current_index = -1
            remaining = max(0, len(route) - current_index - 1) if current_index >= 0 else len(route)
            if remaining <= 0:
                return {
                    "mode": "game", "remaining": 0,
                    "text": "NAV ROUTE · COMPLETE", "summary": "COMPLETE",
                }
            noun = "JUMP" if remaining == 1 else "JUMPS"
            return {
                "mode": "game", "remaining": remaining,
                "text": f"NAV ROUTE · {remaining} {noun} LEFT",
                "summary": f"{remaining} LEFT",
            }

        waypoint_manager = getattr(self, "waypoint_manager", None)
        waypoints = list(getattr(waypoint_manager, "waypoints", None) or [])
        if waypoints:
            total = len(waypoints)
            visited = sum(1 for waypoint in waypoints if waypoint.get("visited", False))
            remaining = max(0, total - visited)
            if remaining <= 0:
                return {
                    "mode": "waypoints", "visited": visited, "total": total, "remaining": 0,
                    "text": f"WAYPOINTS · {visited}/{total} · COMPLETE", "summary": "COMPLETE",
                }
            return {
                "mode": "waypoints", "visited": visited, "total": total, "remaining": remaining,
                "text": f"WAYPOINTS · {visited}/{total} · {remaining} LEFT",
                "summary": f"{visited}/{total}",
            }

        return {
            "mode": "none", "remaining": 0,
            "text": "NO ACTIVE ROUTE", "summary": "INACTIVE",
        }

    def _dashboard_next_destination(self):
        route = list(getattr(self, "route_list", None) or [])
        current = getattr(self, "current_sys", None)
        if route:
            try:
                index = route.index(current)
            except (ValueError, TypeError):
                index = -1
            if 0 <= index < len(route) - 1:
                return route[index + 1]
            if index < 0:
                return route[0]
        manager = getattr(self, "waypoint_manager", None)
        waypoints = list(getattr(manager, "waypoints", None) or [])
        if manager and current:
            next_name = manager.get_next_waypoint(current)
            if next_name:
                return next_name
        for waypoint in waypoints:
            if not waypoint.get("visited") and waypoint.get("name"):
                return waypoint["name"]
        return getattr(self, "dest_name", None) or None

    def _get_session_elapsed_text(self):
        elapsed = max(int(time.time() - self.session_start_ts), 0)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def _ground_target_configured(self):
        """Return whether this profile has one complete, valid coordinate fix."""
        if not getattr(self, "target_latlon_active", False):
            return False
        try:
            lat = float(self.target_lat)
            lon = float(self.target_lon)
        except (AttributeError, TypeError, ValueError):
            return False
        return bool(
            math.isfinite(lat) and math.isfinite(lon)
            and -90.0 <= lat <= 90.0
            and -180.0 <= lon <= 180.0
        )

    def _ground_target_should_show(self, solution=None):
        """Apply the one authoritative Planet Waypoint visibility policy."""
        if (
            bool(getattr(self, "_startup_presentation_held", False))
            or bool(getattr(
                getattr(self, "root", None),
                "_voidcompass_startup_presentation_held", False,
            ))
            or not bool(getattr(self, "ground_popup_enabled", True))
            or not self._ground_target_configured()
            or not bool(getattr(self, "on_planet", False))
        ):
            return False
        if solution is None:
            solution = self._ground_target_solution()
        return bool(solution and solution.get("state") == "OK")

    def _ground_target_solution(self):
        if not self._ground_target_configured():
            return None
        if self.current_latitude is None or self.current_longitude is None:
            return {"state": "WAIT_POS"}

        bearing = self._bearing_deg(self.current_latitude, self.current_longitude, self.target_lat, self.target_lon)
        distance = self._surface_distance_m(
            self.current_latitude,
            self.current_longitude,
            self.target_lat,
            self.target_lon,
            self.current_planet_radius,
        )
        if self.current_heading is None:
            heading_delta = None
            direction = "HEADING N/A"
        else:
            heading_delta = ((bearing - self.current_heading + 540.0) % 360.0) - 180.0
            direction = self._format_direction(heading_delta)
        return {
            "state": "OK",
            "bearing": bearing,
            "distance_m": distance,
            "direction": direction,
            "heading_delta": heading_delta,
        }

    def _journal_history_text(self, event_name, payload):
        payload = payload if isinstance(payload, dict) else {}
        title = str(event_name or "Journal")
        detail = ""
        if event_name in ("FSDJump", "CarrierJump", "Location"):
            title = payload.get("StarSystem") or payload.get("star_system") or title
            detail = event_name
        elif event_name == "StartJump":
            title = payload.get("StarSystem") or payload.get("star_system") or "Hyperspace"
            detail = "Jump charging"
        elif event_name == "Scan":
            title = payload.get("BodyName") or payload.get("body_name") or "Body scan"
            planet_class = payload.get("PlanetClass") or payload.get("planet_class")
            star_type = payload.get("StarType") or payload.get("star_type")
            detail = planet_class or star_type_label(star_type, "Scan")
        elif event_name in ("FSSDiscoveryScan", "DiscoveryScan"):
            count = payload.get("BodyCount") or payload.get("body_count") or payload.get("Bodies") or payload.get("bodies")
            title = "Discovery scan"
            detail = f"{count} bodies detected" if count else "System honk"
        elif event_name in ("SAAScanComplete", "SAASignalsFound", "FSSBodySignals"):
            title = payload.get("BodyName") or payload.get("body_name") or event_name
            bio = payload.get("Signals", {}).get("$SAA_SignalType_Biological;") if isinstance(payload.get("Signals"), dict) else None
            bio = bio if bio is not None else payload.get("bio_count")
            detail = f"Bio signals: {bio}" if bio else event_name
        elif event_name == "ScanOrganic":
            title = payload.get("Species_Localised") or payload.get("Species") or payload.get("species") or "Organic scan"
            sample = payload.get("ScanType") or payload.get("scan_type") or ""
            detail = f"{sample} sample".strip()
        elif event_name in ("Docked", "Undocked"):
            title = payload.get("StationName") or payload.get("station_name") or event_name
            detail = event_name
        elif event_name == "LoadGame":
            title = payload.get("Commander") or payload.get("commander") or "Commander loaded"
            detail = payload.get("Ship_Localised") or payload.get("Ship") or payload.get("ship") or ""
        elif event_name == "Commander":
            title = payload.get("Name") or payload.get("name") or "Commander"
            detail = payload.get("FID") or payload.get("fid") or ""
        elif event_name == "Music":
            track = payload.get("MusicTrack") or payload.get("music_track") or "No Track"
            title = str(track).replace("_", " ")
            detail = "Music mood"
        elif event_name in ("MaterialCollected", "MaterialDiscarded", "MiningRefined", "CollectCargo", "EjectCargo"):
            title = payload.get("Name_Localised") or payload.get("Name") or payload.get("name") or event_name
            count = payload.get("Count") or payload.get("count")
            detail = f"{event_name} x{count}" if count else event_name
        else:
            system = payload.get("StarSystem") or payload.get("star_system")
            body = payload.get("BodyName") or payload.get("body_name")
            station = payload.get("StationName") or payload.get("station_name")
            detail = system or body or station or ""
        return title, detail

    @staticmethod
    def _dashboard_credits(value):
        value = int(value or 0)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f}B cr"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M cr"
        if value >= 1_000:
            return f"{value / 1_000:.0f}K cr"
        return f"{value:,} cr"

    @staticmethod
    def _dashboard_number(value, default=0):
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return default
