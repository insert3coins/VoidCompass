"""The local API's side of the dashboard (5.5.7).

services/local_api.py serves /api/v1 and hands every call here, on the app's
own thread. These ``api_*`` methods answer it from the same state and code the
command deck uses, and the ``_api_*`` hooks feed its event stream. Settings ›
Integrations › Local API switches it on; api.md is the reference.
"""

from __future__ import annotations

import json
import logging
import os
import time

from voidcompass.bgs import ticks as bgs_ticks
from voidcompass.bgs import views as bgs_views
from voidcompass.core import debug_tap, themes
from voidcompass.core.config import get_active_profile
from voidcompass.core.overlay_registry import OVERLAY_SPECS, OVERLAY_SPEC_BY_ATTR
from voidcompass.core.version import APP_VERSION
from voidcompass.exploration import bio_values
from voidcompass.exploration.stellar_types import star_type_label
from voidcompass.dashboard.dashboard_api_records_mixin import ApiRecordsMixin
from voidcompass.services.local_api import _SECRET_NAME, ApiError, LocalApi, DEFAULT_PORT

# Deck pages whose data the API never hands out: Settings holds the
# commander's keys and webhooks, Tools only runs actions.
API_HIDDEN_PAGES = frozenset({"settings", "tools"})
COMPANION_FILES = {"status": "Status.json", "cargo": "Cargo.json", "navroute": "NavRoute.json",
                   "market": "Market.json", "shiplocker": "ShipLocker.json"}
_SNAPSHOT_CHANNELS = {"status": "status", "cargo": "cargo", "nav_route": "navroute",
                      "market": "market", "ship_locker": "shiplocker"}
_FEED_SEVERITIES = {"info": "INFO", "warn": "WARN", "fail": "FAIL", "success": "OK", "ok": "OK"}


def _plain(value):
    """Plain JSON-ready data: sets and tuples as lists, anything odd as text."""
    try:
        return json.loads(json.dumps(value, default=lambda item: sorted(item) if isinstance(item, (set, frozenset))
                                     else str(item)))
    except (TypeError, ValueError):
        return None


def _secret_values(config):
    """Every setting that's a key, token, webhook, secret or password."""
    found = []

    def walk(value, secret=False):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, secret or bool(_SECRET_NAME.search(str(key))))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item, secret)
        elif secret and isinstance(value, str) and value.strip():
            found.append(value.strip())

    walk(config or {})
    return found


class DashboardApiMixin(ApiRecordsMixin):
    # -- lifecycle -------------------------------------------------------------
    def _api_server(self):
        api = getattr(self, "_local_api", None)
        if api is None:
            def on_main(task):
                if getattr(self, "_closing", False):
                    return False
                return self.root.call_later(0, task) is not None

            api = self._local_api = LocalApi(self, run_on_main=on_main, version=APP_VERSION)
            # The debugger's log never shows the commander's keys or webhooks.
            debug_tap.secret_values = lambda: _secret_values(self.config)
        return api

    def _api_attach(self):
        """Listen to the journal and its companion files, then apply the settings."""
        journal = getattr(self, "journal", None)
        if journal is not None and not getattr(self, "_api_journal_attached", False):
            self._api_journal_attached = True
            self._api_companion_data = {}
            journal.subscribe_journal(self._api_journal_event, batch_callback=self._api_journal_batch)
            for channel, name in _SNAPSHOT_CHANNELS.items():
                journal.subscribe_snapshot(
                    channel, lambda data, *_rest, name=name: self._api_companion_seen(name, data),
                    dispatch_key=f"api:{name}")
        self._api_sync()

    def _api_sync(self):
        """Start, stop or restart the server to match the settings."""
        config = self.config
        try:
            self._api_server().configure(
                enabled=bool(config.get("api_enabled")), port=config.get("api_port", DEFAULT_PORT),
                allow_lan=bool(config.get("api_allow_lan")), allow_control=bool(config.get("api_allow_control", True)))
        except Exception:
            logging.exception("Local API settings could not be applied")

    def _api_close(self):
        api = getattr(self, "_local_api", None)
        if api is not None:
            api.stop()

    def _api_state(self):
        api = getattr(self, "_local_api", None)
        return api.state() if api is not None else {"running": False, "url": "", "error": ""}

    # -- what happens, for the event stream ----------------------------------
    def _api_publish(self, kind, data):
        api = getattr(self, "_local_api", None)
        if api is not None and api.running:
            api.publish(kind, data)

    def _api_journal_event(self, data):
        if not isinstance(data, dict) or data.get("startup_catchup"):
            return
        raw = data.get("raw") if isinstance(data.get("raw"), dict) else data
        self._api_last_journal_at = time.time()
        self._api_publish("journal", raw)
        try:
            found = self._api_exploration(raw)
        except Exception:
            logging.exception("Local API: exploration event not worked out")
            found = None
        if found:
            self._api_publish("exploration", found)

    def _api_exploration(self, raw):
        """Moments the journal only hints at (5.5.7): a first discovery with
        what it's worth, an organic analysed with what Vista Genomics pays,
        and a first footfall. Each once per body (or species) per run."""
        event = raw.get("event")
        announced = self.__dict__.setdefault("_api_announced", set())
        base = {"commander": getattr(self, "cmdr_name", "") or "",
                "system": raw.get("StarSystem") or getattr(self, "current_sys", "") or ""}
        if event == "Scan" and raw.get("WasDiscovered") is False and (raw.get("PlanetClass") or raw.get("StarType")):
            key = ("discovery", raw.get("SystemAddress"), raw.get("BodyID"))
            if key in announced:
                return None
            announced.add(key)
            planet, star = raw.get("PlanetClass") or "", raw.get("StarType") or ""
            terraformable = raw.get("TerraformState") == "Terraformable"
            mass = raw.get("MassEM") or raw.get("StellarMass") or 0
            first_mapped = raw.get("WasMapped") is False
            value = self._get_body_value(planet, star, terraformable, mass, True, False, first_mapped, True)
            mapped = None if star else self._get_body_value(planet, star, terraformable, mass, True, True, first_mapped, True)
            return {**base, "kind": "first_discovery", "body": raw.get("BodyName") or "", "body_id": raw.get("BodyID"),
                    "class": star_type_label(star, include_star=True) if star else planet, "star": bool(star),
                    "terraformable": terraformable, "landable": bool(raw.get("Landable")),
                    "first_footfall_available": bool(raw.get("Landable") and raw.get("WasFootfalled") is False),
                    "value": value, "mapped_value": mapped}
        items = getattr(self, "scan_items_by_id", None) or {}
        if event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
            species = raw.get("Species_Localised") or raw.get("Species") or ""
            key = ("bio", raw.get("SystemAddress"), raw.get("Body"), species)
            if not species or key in announced:
                return None
            announced.add(key)
            body = items.get(raw.get("Body")) or {}
            value = bio_values.species_value(species)
            # A first-footfall body always pays the first-logged bonus.
            bonus = bool(body.get("first_footfall"))
            return {**base, "kind": "bio_analysed", "body": body.get("name") or "", "body_id": raw.get("Body"),
                    "species": species, "genus": raw.get("Genus_Localised") or "",
                    "variant": raw.get("Variant_Localised") or "", "value": value, "first_logged_bonus": bonus,
                    "estimated_value": None if value is None else value * (bio_values.FIRST_LOGGED_MULTIPLIER if bonus else 1)}
        if event == "Disembark" and raw.get("OnPlanet") and not raw.get("OnStation"):
            body = items.get(raw.get("BodyID")) or {}
            key = ("footfall", raw.get("SystemAddress"), raw.get("BodyID"))
            if not body.get("first_footfall") or key in announced:
                return None
            announced.add(key)
            return {**base, "kind": "first_footfall", "body": raw.get("Body") or body.get("name") or "",
                    "body_id": raw.get("BodyID")}
        return None

    def _api_journal_batch(self, events):
        for data in events or ():
            self._api_journal_event(data)

    def _api_companion_seen(self, name, data):
        if isinstance(data, dict):
            self._api_companion_data[name] = data
            self._api_publish(name, data)

    def _api_thought(self, thought):
        self._api_publish("thought", {key: thought.get(key) for key in ("id", "text", "heading", "mood", "kind")})

    # -- the app -----------------------------------------------------------------
    def api_status(self):
        last = getattr(self, "_api_last_journal_at", 0) or 0
        hud = getattr(self, "heartbeat_hud", None)
        return {
            "version": APP_VERSION,
            "commander": getattr(self, "cmdr_name", "") or "",
            "profile": get_active_profile(self.config),
            "journal": {"folder": str(self.config.get("journal_path") or ""),
                        "last_event_seconds_ago": round(time.time() - last, 1) if last else None,
                        "live": bool(hud is not None and not getattr(hud, "_stalled", True))},
            "game": {"version": getattr(self, "game_version", "") or "", "build": getattr(self, "game_build", "") or "",
                     "odyssey": bool(getattr(self, "game_odyssey", False)),
                     "mode": getattr(self, "current_game_mode", "") or ""},
            "deck_page": getattr(self, "_html_dashboard_active_page", "") or "",
            "overlays_hidden": bool(getattr(self, "_overlay_hotkey_global_hidden", False)),
            "voice": self._watcher_voice_on() if hasattr(self, "_watcher_voice_on") else False,
        }

    def api_debug(self):
        """The app's own view for the live debugger (tools/debug): the deck,
        the game as Void Compass sees it, the overlays, the Watcher, the
        voice and the music. Never a setting's value."""
        hud = getattr(self, "heartbeat_hud", None)
        mind = getattr(hud, "mind", None)
        llm = getattr(self, "_watcher_mind_llm", None)
        dispatcher = getattr(self, "ui_dispatcher", None)
        last = getattr(self, "_api_last_journal_at", 0) or 0
        music = getattr(self, "_music_status", None) or {}
        in_menu = getattr(self, "_in_game_menu", None)
        return _plain({
            "deck": {"page": getattr(self, "_html_dashboard_active_page", "") or "",
                     "ui_queue": dispatcher.pending if dispatcher is not None else None,
                     "closing": bool(getattr(self, "_closing", False))},
            "game": {"commander": getattr(self, "cmdr_name", "") or "", "system": getattr(self, "current_sys", "") or "",
                     "body": getattr(self, "current_body_name", "") or "",
                     "station": getattr(self, "current_station_name", "") or "",
                     "flight_state": getattr(self, "hud_flight_state", "") or "",
                     "gui_focus": getattr(self, "current_gui_focus", -1),
                     "music_track": getattr(self, "current_music_track", "") or "",
                     "last_journal_s": round(time.time() - last, 1) if last else None,
                     "live": bool(hud is not None and not getattr(hud, "_stalled", True))},
            "overlays": {"hidden_all": bool(getattr(self, "_overlay_hotkey_global_hidden", False)),
                         "in_map": getattr(self, "current_gui_focus", -1) in getattr(self, "_MAP_GUI_FOCUS", ()),
                         "in_menu": bool(in_menu()) if callable(in_menu) else False,
                         "hide_on_maps": bool(self.config.get("overlay_hide_on_maps", True)),
                         "hide_in_menus": bool(self.config.get("overlay_hide_in_menus", False))},
            "watcher": {"orb": hud is not None, "mind": mind.debug_state() if mind is not None else None,
                        "llm": llm.debug_state() if llm is not None else None},
            "voice": {"on": self._watcher_voice_on() if hasattr(self, "_watcher_voice_on") else False,
                      "speaking": bool(getattr(self, "_voice_speaking", False)),
                      "hush_s": self._watcher_voice_hush_left() if hasattr(self, "_watcher_voice_hush_left") else 0},
            "music": {"playing": bool(music.get("playing")), "track_id": music.get("track_id") or "",
                      "position": music.get("position"), "duration": music.get("duration"),
                      "scene": music.get("scene") or ""},
        })

    def api_commander(self):
        return _plain({
            "name": getattr(self, "cmdr_name", "") or "",
            "fid": getattr(self, "cmdr_fid", "") or "",
            "profile": get_active_profile(self.config),
            "credits": getattr(self, "cmdr_balance", None),
            "loan": getattr(self, "cmdr_loan", None),
            "ranks": getattr(self, "cmdr_ranks", None) or {},
            "rank_progress": getattr(self, "cmdr_rank_progress", None) or {},
            "reputation": getattr(self, "cmdr_reputation", None) or {},
            "home_system": str(self.config.get("home_system") or ""),
            "ship": getattr(self, "cmdr_ship", None) or {},
            "location": self.api_location(),
        })

    def api_location(self):
        system = getattr(self, "current_sys", "") or ""
        station = getattr(self, "current_station_name", "") or ""
        return _plain({
            "system": "" if system == "---" else system,
            "system_address": getattr(self, "current_system_address", None),
            "coordinates": getattr(self, "current_coords", None),
            "body": getattr(self, "current_body_name", "") or "",
            "body_id": getattr(self, "current_body_id", None),
            "station": {
                "name": station, "type": getattr(self, "current_station_type", "") or "",
                "market_id": getattr(self, "current_station_market_id", None),
                "faction": getattr(self, "current_station_faction", "") or "",
                "government": getattr(self, "current_station_government", "") or "",
                "economy": getattr(self, "current_station_economy", "") or "",
                "allegiance": getattr(self, "current_station_allegiance", "") or "",
                "distance_ls": getattr(self, "current_station_dist_ls", None),
                "services": getattr(self, "current_station_services", None) or [],
            } if station else None,
            "docked": bool(getattr(self, "current_docked", False)),
            "landed": bool(getattr(self, "current_landed", False)),
            "on_foot": bool(getattr(self, "current_on_foot", False)),
            "in_srv": bool(getattr(self, "current_in_srv", False)),
            "in_fighter": bool(getattr(self, "current_in_fighter", False)),
            "in_taxi": bool(getattr(self, "current_in_taxi", False)),
            "multicrew": bool(getattr(self, "current_in_multicrew", False)),
            "surface": {
                "latitude": getattr(self, "current_latitude", None),
                "longitude": getattr(self, "current_longitude", None),
                "altitude_m": getattr(self, "current_altitude_m", None),
                "heading": getattr(self, "current_heading", None),
                "planet_radius_m": getattr(self, "current_planet_radius", None),
            },
            "destination": getattr(self, "current_destination", None),
            "flight_state": getattr(self, "hud_flight_state", "") or "",
            "legal_state": getattr(self, "current_legal_state", "") or "",
        })

    def api_ship(self):
        return _plain({
            "ship": getattr(self, "cmdr_ship", None) or {},
            "vehicle": getattr(self, "current_vehicle_name", "") or "",
            "fuel": {"main": getattr(self, "current_fuel_main", None),
                     "reservoir": getattr(self, "current_fuel_reservoir", None),
                     "low": bool(getattr(self, "current_low_fuel", False)),
                     "scooping": bool(getattr(self, "current_scooping_fuel", False))},
            "hull_percent": getattr(self, "current_hull_percent", None),
            "shields_up": getattr(self, "current_shields_up", None),
            "cargo": {"tons": getattr(self, "current_cargo_tons", None),
                      "capacity": getattr(self, "cargo_capacity", None),
                      "inventory": getattr(self, "current_cargo_inventory", None) or []},
            "fsd": {"charging": bool(getattr(self, "current_fsd_charging", False)),
                    "jumping": bool(getattr(self, "current_fsd_jumping", False)),
                    "cooldown": bool(getattr(self, "current_fsd_cooldown", False)),
                    "mass_locked": bool(getattr(self, "current_fsd_mass_locked", False))},
            "overheating": bool(getattr(self, "current_overheating", False)),
            "silent_running": bool(getattr(self, "current_silent_running", False)),
            "landing_gear_down": bool(getattr(self, "current_landing_gear_down", False)),
            "hardpoints_deployed": bool(getattr(self, "current_hardpoints_deployed", False)),
        })

    # -- the journal ------------------------------------------------------------------
    def api_journal_folder(self):
        return str(self.config.get("journal_path") or "")

    def api_companion(self, name):
        data = (getattr(self, "_api_companion_data", None) or {}).get(name)
        if data is not None:
            return data
        folder = self.api_journal_folder()
        path = os.path.join(folder, COMPANION_FILES[name]) if folder else ""
        try:
            with open(path, "r", encoding="utf-8") as source:
                return json.load(source)
        except (OSError, ValueError):
            return None

    # -- the command deck ------------------------------------------------------------
    def api_dashboard(self):
        runtime = getattr(self.root, "_voidcompass_html_dashboard_runtime", None)
        server = getattr(runtime, "server", None)
        if server is None:
            raise ApiError(503, "The command deck isn't running")
        snapshot = json.loads(getattr(server, "_snapshot_json", "{}") or "{}")
        # The snapshot carries whatever page the deck has open; Settings and Tools stay home.
        workspace = snapshot.get("workspace") if isinstance(snapshot, dict) else None
        if isinstance(workspace, dict) and workspace.get("page") in API_HIDDEN_PAGES:
            snapshot["workspace"] = {"page": workspace["page"], "ready": False, "shared": False}
        return snapshot

    def api_pages(self):
        from voidcompass.dashboard.html_dashboard import _HTML_WORKSPACE_PAGES

        return {"data": sorted(_HTML_WORKSPACE_PAGES - API_HIDDEN_PAGES),
                "open": sorted({"overview", "explore", "map", "records", "operations", "overlay-studio",
                                "settings", "about", "music", *_HTML_WORKSPACE_PAGES})}

    def api_page(self, page):
        from voidcompass.dashboard.html_dashboard import _HTML_WORKSPACE_PAGES

        if page in API_HIDDEN_PAGES:
            raise ApiError(403, f"The {page} page isn't shared through the API")
        if page not in _HTML_WORKSPACE_PAGES:
            raise ApiError(404, f"No page called {page} (see /api/v1/dashboard/pages)")
        workspace = self._html_workspace(page)
        if not workspace.get("ready"):
            raise ApiError(503, workspace.get("error") or f"The {page} page isn't ready")
        return {"page": page, "data": _plain(workspace.get("data"))}

    def api_open_page(self, page):
        return bool(self._request_html_dashboard_page(page))

    def api_feed(self, limit=50):
        return {"entries": [
            {"at": row.get("ts"), "tag": row.get("tag"), "severity": row.get("severity"),
             "message": row.get("message"), "url": row.get("url")}
            for row in list(getattr(self, "event_feed_entries", None) or [])[:limit]]}

    def api_add_feed(self, tag, message, severity="INFO"):
        level = _FEED_SEVERITIES.get(str(severity or "").casefold(), "INFO")
        self.add_event_feed_entry(str(tag or "API").upper(), message, severity=level)
        return {"ok": True}

    def api_themes(self):
        custom = self.config.get("ui_custom_themes") or {}
        name, colors = themes.resolve_theme(self.config.get("ui_theme_name"), custom)
        return {"active": name, "colors": colors,
                "builtin": sorted(themes.BUILTIN_THEMES), "custom": sorted(custom)}

    def api_set_theme(self, name):
        return bool(self.handle_html_dashboard_command({"action": "set_theme", "name": name}))

    # -- overlays ----------------------------------------------------------------------
    def _api_overlay_spec(self, overlay_id):
        key = str(overlay_id or "").strip().casefold()
        for spec in OVERLAY_SPECS:
            if key in {spec.overlay_id, spec.attr}:
                return spec
        raise ApiError(404, f"No overlay called {overlay_id} (see /api/v1/overlays)")

    def _api_overlay_row(self, spec, record):
        own = int(record.get("own_opacity") or 0)
        return {
            "id": spec.overlay_id, "studio_id": spec.attr, "name": spec.label,
            "enabled": bool(record.get("enabled")), "shown": bool(record.get("shown")),
            "x": record.get("x"), "y": record.get("y"), "width": record.get("width"), "height": record.get("height"),
            "opacity": own or int(self.config.get("overlay_opacity_percent") or 100),
            "own_opacity": bool(own), "hide_on_maps": bool(record.get("hide_on_maps")),
            "hide_in_menus": bool(record.get("hide_in_menus")),
        }

    def api_overlays(self):
        records = {row["id"]: row for row in self._html_overlay_records()}
        rows = [self._api_overlay_row(spec, records[spec.attr]) for spec in OVERLAY_SPECS if spec.attr in records]
        return {"hidden": bool(getattr(self, "_overlay_hotkey_global_hidden", False)), "overlays": rows}

    def api_overlay(self, overlay_id):
        spec = self._api_overlay_spec(overlay_id)
        records = {row["id"]: row for row in self._html_overlay_records()}
        if spec.attr not in records:
            raise ApiError(404, f"{spec.label} isn't available")
        runtime = getattr(self.root, "_voidcompass_html_overlay_runtime", None)
        server = getattr(runtime, "server", None)
        data = server.snapshot(spec.overlay_id) if server is not None and hasattr(server, "snapshot") else None
        return {**self._api_overlay_row(spec, records[spec.attr]), "data": data}

    def api_set_overlay(self, overlay_id, changes):
        spec = self._api_overlay_spec(overlay_id)
        if "enabled" in changes:
            wanted = bool(changes["enabled"])
            current = bool(self.config.get(spec.enabled_key, False))
            if wanted != current and not self._html_overlay_toggle(spec.attr):
                raise ApiError(409, f"{spec.label} couldn't be switched {'on' if wanted else 'off'}")
        if "x" in changes or "y" in changes:
            try:
                x = int(changes.get("x", self.config.get(spec.x_key, 0)))
                y = int(changes.get("y", self.config.get(spec.y_key, 0)))
            except (TypeError, ValueError):
                raise ApiError(400, "x and y are whole screen pixels")
            self._html_overlay_position(spec.attr, x, y, persist=True)
        if "opacity" in changes:
            try:
                percent = int(changes["opacity"])
            except (TypeError, ValueError):
                raise ApiError(400, "opacity is 0 (same as all overlays) or 40-100")
            choice = 0 if percent == 0 else min(self._OWN_OPACITY_CHOICES[1:], key=lambda value: abs(value - percent))
            if not self._set_overlay_own_opacity(spec.attr, choice):
                raise ApiError(400, "opacity is 0 (same as all overlays) or 40-100")
        row = self.api_overlay(spec.overlay_id)
        row.pop("data", None)
        self._api_publish("overlay", row)
        return row

    def api_toggle_overlay(self, overlay_id):
        spec = self._api_overlay_spec(overlay_id)
        return self.api_set_overlay(spec.overlay_id, {"enabled": not bool(self.config.get(spec.enabled_key, False))})

    def api_hide_overlays(self, hidden):
        if bool(hidden) != bool(getattr(self, "_overlay_hotkey_global_hidden", False)):
            self._handle_overlay_hotkey("toggle_all")
        state = bool(getattr(self, "_overlay_hotkey_global_hidden", False))
        self._api_publish("overlay", {"hidden": state})
        return {"hidden": state}

    def api_notify(self, title, message="", severity="info", seconds=8.0):
        toast = getattr(self, "toast_hud", None)
        if toast is None:
            raise ApiError(409, "The Cockpit Notifications overlay is off (Overlay Studio)")
        toast.push(title, message, severity=severity, duration_s=seconds)
        return {"ok": True}

    # -- the Watcher and its voice -----------------------------------------------------
    def _api_hud(self):
        hud = getattr(self, "heartbeat_hud", None)
        if hud is None:
            raise ApiError(409, "The Watcher is off (Journal Heartbeat in Overlay Studio)")
        return hud

    def api_watcher(self):
        data = self._html_watcher_workspace()
        hud = getattr(self, "heartbeat_hud", None)
        current = hud.mind.current() if hud is not None else None
        data = dict(data or {})
        data["log"] = list(data.get("log") or [])[:50]
        data["current"] = ({key: current.get(key) for key in ("id", "text", "heading", "mood", "kind")}
                           if current else None)
        return _plain(data)

    def api_watcher_thought(self, text, heading="", speak=False):
        hud = self._api_hud()
        thought = hud.mind.relay(text, heading, speak)
        hud._redraw()
        return {"id": thought["id"], "text": thought["text"], "heading": thought["heading"],
                "spoken": bool(speak and self._watcher_voice_on() and not self._watcher_voice_hushed())}

    def api_watcher_poke(self):
        return {"answered": bool(self._api_hud().poke())}

    # 5.6.1: answer its question, share it, meet another, keep its book.
    def api_watcher_answer(self, answer):
        mind = self._watcher_mind()
        asked = mind.pending_question() if mind is not None else None
        if not asked:
            raise ApiError(409, "It hasn't asked anything just now")
        if not self._watcher_answer(answer):
            keys = ", ".join(row["key"] for row in asked.get("answers") or ())
            raise ApiError(400, f"That isn't one of its answers: give 1 to {len(asked.get('answers') or ())}, or one of {keys}")
        return {"answered": True, "question": asked["id"]}

    def api_watcher_code(self):
        return {"code": self._watcher_share_code()}

    def api_watcher_meet(self, code):
        if not self._watcher_meet(code):
            raise ApiError(400, "That isn't a Watcher's code (they start VCWATCH1)")
        return {"met": True}

    def api_watcher_book(self):
        if not self._watcher_save_book():
            raise ApiError(500, "The book couldn't be saved")
        return {"saved": True, "folder": str(self.wrapped_folder()) if hasattr(self, "wrapped_folder") else ""}

    def api_voice(self):
        from voidcompass.voice import voice_assets

        speaker = getattr(self, "_watcher_voice", None)
        live = speaker.live() if speaker is not None else None
        return {"enabled": bool(self.config.get("watcher_voice_enabled")),
                "installed": bool(voice_assets.installed()),
                "ready": bool(self._watcher_voice_on()),
                "speaking": live is not None,
                # 5.6.1: kept quiet by another app (hushed_for: seconds left, null until lifted).
                "hushed": self._watcher_voice_hushed(),
                "hushed_for": self._watcher_voice_hush_left() if self._watcher_voice_hushed() else 0}

    def api_voice_say(self, text):
        if not self._watcher_voice_on():
            raise ApiError(409, "The voice is off or not downloaded yet (The Watcher › VOICE)")
        if self._watcher_voice_hushed():
            raise ApiError(409, "The voice is hushed: POST /voice/hush with {\"seconds\": 0} lifts it")
        if not self._watcher_voice_say(text, key=f"api-{time.time():.3f}"):
            raise ApiError(409, "The voice couldn't say that")
        return {"spoken": True}

    def api_voice_stop(self):
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            self._voice_stop_reason = "stopped"
            speaker.stop()
        return {"ok": True}

    def api_voice_hush(self, seconds):
        self._watcher_voice_hush(seconds)
        hushed = self._watcher_voice_hushed()
        return {"hushed": hushed, "hushed_for": self._watcher_voice_hush_left() if hushed else 0}

    # -- music ---------------------------------------------------------------------------
    def api_music(self):
        status = dict(getattr(self, "_music_status", None) or {})
        track = None
        if status.get("track_id"):
            found = self.music_library().track(status["track_id"]) or {}
            track = {"id": status["track_id"], "title": found.get("title") or "", "artist": found.get("artist") or "",
                     "album": found.get("album") or "", "duration": found.get("duration")}
        runtime = getattr(self.root, "_voidcompass_html_dashboard_runtime", None)
        seen = getattr(getattr(runtime, "server", None), "last_client_seen", 0) or 0
        return {"playing": bool(status.get("playing")), "track": track,
                "position": status.get("position"), "duration": status.get("duration"),
                "volume": status.get("volume"), "shuffle": status.get("shuffle"), "repeat": status.get("repeat"),
                # The music plays inside the command deck's page.
                "deck_open": bool(seen and time.monotonic() - seen < 30)}

    def api_music_library(self):
        return self.music_library().payload()

    def api_music_control(self, operation):
        op = {"play-pause": "toggle", "next": "next", "previous": "previous"}[operation]
        return {"ok": bool(self.music_remote(op)), "note": "Carried out by the command deck, which must be open"}

    def api_galnet(self):
        return _plain(self._html_dashboard_galnet())

    # -- the BGS (5.5.7): straight from bgs.db, whichever tab the deck has open ----
    def _api_bgs_store(self):
        store = getattr(self, "bgs_store", None)
        if store is None:
            raise ApiError(409, "The BGS record isn't open yet (the BGS page)")
        return store

    @staticmethod
    def _api_bgs_tick(store):
        known = store.ticks()
        start, estimated = bgs_ticks.tick_for(time.time(), known)
        last = known[-1] if known else None
        return known, start, {"last": last, "last_label": bgs_ticks.label(last) if last else "",
                              "current": start, "current_label": bgs_ticks.label(start) if start else "",
                              "estimated": estimated}

    def api_bgs(self):
        from voidcompass.dashboard.html_bgs import HtmlBgsMixin

        store = self._api_bgs_store()
        known, start, tick = self._api_bgs_tick(store)
        tracked = store.tracked("faction")
        alerts = bgs_views.alerts(store)
        address = getattr(self, "current_system_address", None)
        return _plain({
            "tick": tick,
            "tracked_factions": [HtmlBgsMixin._bgs_faction_brief(store, name, alerts) for name in tracked],
            "tracked_systems": [str(item) for item in store.tracked("system")],
            "alerts": alerts,
            "current_system": bgs_views.system_picture(store, address, tracked) if address is not None else None,
            "this_tick": bgs_views.activity(store, start, known)["detail"],
        })

    def api_bgs_factions(self, query=""):
        rows, total = bgs_views.factions_list(self._api_bgs_store(), query)
        return _plain({"factions": rows, "total": total, "query": query})

    def api_bgs_faction(self, name):
        store = self._api_bgs_store()
        _known, start, _tick = self._api_bgs_tick(store)
        detail = bgs_views.faction_detail(store, name, start)
        if not detail:
            raise ApiError(404, f"No faction called {name} in your BGS record (see /api/v1/bgs/factions)")
        detail["alerts"] = [row for row in bgs_views.alerts(store) if row.get("faction") == name]
        return _plain(detail)

    def api_bgs_systems(self, query="", only=""):
        rows, total = bgs_views.systems_list(self._api_bgs_store(), query, only)
        return _plain({"systems": rows, "total": total, "query": query, "only": only})

    def api_bgs_system(self, address, days=90):
        store = self._api_bgs_store()
        picture = bgs_views.system_picture(store, address, store.tracked("faction"))
        if not picture:
            raise ApiError(404, f"No system {address} in your BGS record (see /api/v1/bgs/systems)")
        picture["history"] = bgs_views.history(store, address, days=days)
        picture["days"] = days
        picture["activity"] = bgs_views._kind_rows(store.query(
            "SELECT kind, SUM(amount) amount, SUM(count) count FROM activity WHERE system_address = ? GROUP BY kind",
            (address,)))
        picture["visits"] = (store.query("SELECT visits FROM systems WHERE system_address = ?", (address,)) or [{}])[0].get("visits")
        return _plain(picture)

    def api_bgs_conflicts(self):
        return _plain({"conflicts": bgs_views.conflicts(self._api_bgs_store())})

    def api_bgs_activity(self, tick=None):
        store = self._api_bgs_store()
        return _plain(bgs_views.activity(store, tick, store.ticks()))
