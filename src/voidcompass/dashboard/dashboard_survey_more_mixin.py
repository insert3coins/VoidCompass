"""Explore & Survey's other tabs (5.7.8): SEARCH, PLOT ROUTE, FIRSTS and
CHECKLIST, the ARCHIVE's Journal Log, a body's detail panel and the nearest
place to dock. Built on ED-Outrider's views (github.com/weslocke/ED-Outrider,
GPLv3), rewritten for our journal-backed state.

Search: tick boxes in sections (stars, planets, rings, hotspots, exobiology,
planetary mining). Any tick in a section counts; a system must match every
section you ticked. Spansh searches what other commanders reported; Local only
your own scans, which can say what search can't (unfinished biology, mining
locations, potential green gas giants), but covers only where you've been.

Plot Route: one route at a time, from any plotter, followed as you fly it.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import statistics
import threading
import time

from voidcompass.core.config import get_active_profile
from voidcompass.exploration import bio_values, journal_events, nearby, sample_runs
from voidcompass.exploration.galactic_regions import find_region, region_names
from voidcompass.outrider import fsd, ggg, records as outrider_records
from voidcompass.services import spansh

logger = logging.getLogger(__name__)

ROUTE_FILE = "explore_route.json"
# Canonn's codex pictures: links only, loaded by the page when an entry is opened.
CANONN_PICTURES = "https://storage.googleapis.com/canonn-downloads/"
_GEO_CODEX = None
_PICTURES = None
_CODEX_REFERENCE = None
_BIO_VARIANTS = None


def _codex_reference():
    global _CODEX_REFERENCE
    if _CODEX_REFERENCE is None:
        from voidcompass.core.paths import resource_path
        try:
            with open(resource_path("data", "codexRef.json"), encoding="utf-8") as handle:
                _CODEX_REFERENCE = json.load(handle)
        except (OSError, ValueError):
            _CODEX_REFERENCE = {}
    return _CODEX_REFERENCE


def _bio_variants():
    global _BIO_VARIANTS
    if _BIO_VARIANTS is None:
        variants = {}
        for entry in _codex_reference().values():
            if entry.get("hud_category") != "Biology" or str(entry.get("platform")).lower() != "odyssey":
                continue
            species, _sep, colour = str(entry.get("english_name") or "").partition(" - ")
            info = variants.setdefault(species.strip().casefold(), {"species": species.strip(), "colours": [], "pictures": []})
            info["colours"].append((colour.strip(), str(entry.get("name") or "")))
            if str(entry.get("image_url") or "").startswith(CANONN_PICTURES):
                info["pictures"].append({"colour": colour.strip(), "url": entry["image_url"], "cmdr": entry.get("image_cmdr") or ""})
        _BIO_VARIANTS = variants
    return _BIO_VARIANTS


def _geo_codex():
    """Canonn's geology and phenomena entries with their reported sites by region (data/geo_codex.json)."""
    global _GEO_CODEX
    if _GEO_CODEX is None:
        from voidcompass.core.paths import resource_path
        try:
            with open(resource_path("data", "geo_codex.json"), encoding="utf-8") as handle:
                _GEO_CODEX = json.load(handle).get("entries") or []
        except (OSError, ValueError):
            _GEO_CODEX = []
    return _GEO_CODEX


def _codex_pictures():
    """{English name lower-cased: [{url, cmdr}]} from Canonn's codex reference."""
    global _PICTURES
    if _PICTURES is None:
        _PICTURES = {}
        for entry in _codex_reference().values():
            url = str(entry.get("image_url") or "")
            name = str(entry.get("english_name") or "").strip()
            if name and url.startswith(CANONN_PICTURES):
                _PICTURES.setdefault(name.casefold(), []).append({"colour": "", "url": url, "cmdr": entry.get("image_cmdr") or ""})
    return _PICTURES
ROUTE_NOTE = "Route: "
DSSA_URL = "https://edastro.com/json/DSSA-carriers.json"

STAR_TICKS = {
    "o": ["O (Blue-White) Star"], "b": ["B (Blue-White) Star"], "a": ["A (Blue-White) Star"], "f": ["F (White) Star"],
    "g": ["G (White-Yellow) Star"], "k": ["K (Yellow-Orange) Star"], "m": ["M (Red dwarf) Star"],
    "brown": ["L (Brown dwarf) Star", "T (Brown dwarf) Star", "Y (Brown dwarf) Star"],
    "neutron": ["Neutron Star"], "black_hole": ["Black Hole", "Supermassive Black Hole"],
    "white_dwarf": [f"White Dwarf ({c}) Star" for c in ("D", "DA", "DAB", "DAO", "DAV", "DAZ", "DB", "DBV", "DBZ", "DC", "DCV", "DO", "DOV", "DQ", "DX")],
    "wolf_rayet": ["Wolf-Rayet Star", "Wolf-Rayet N Star", "Wolf-Rayet NC Star", "Wolf-Rayet C Star", "Wolf-Rayet O Star"],
    "carbon": ["C Star", "CN Star", "CJ Star", "CH Star", "CHd Star", "MS-type Star", "S-type Star"],
    "proto": ["T Tauri Star", "Herbig Ae/Be Star"],
    "giant": ["A (Blue-White super giant) Star", "B (Blue-White super giant) Star", "F (White super giant) Star",
              "G (White-Yellow super giant) Star", "K (Yellow-Orange giant) Star", "M (Red giant) Star",
              "M (Red super giant) Star", "O (Blue-White super giant) Star"],
}
PLANET_TICKS = {"elw": ["Earth-like world"], "ww": ["Water world"], "aw": ["Ammonia world"],
                "ggw": ["Gas giant with water-based life"], "gga": ["Gas giant with ammonia-based life"],
                "wg": ["Water giant"], "tf": None, "landable": None}
RING_TICKS = {"icy": "Icy", "rocky": "Rocky", "metal_rich": "Metal Rich", "metallic": "Metallic"}
HOTSPOT_TICKS = ("Painite", "Platinum", "Low Temperature Diamonds", "Alexandrite", "Tritium", "Monazite", "Musgravite",
                 "Grandidierite", "Rhodplumsite", "Serendibite", "Benitoite", "Void Opals", "Bromellite")
BIO_TICKS = ("Aleoida", "Bacterium", "Cactoida", "Clypeus", "Concha", "Electricae", "Fonticulua", "Frutexa", "Fumerola",
             "Fungoida", "Osseus", "Recepta", "Stratum", "Tubus", "Tussock", "Amphora Plant", "Anemone", "Bark Mounds",
             "Brain Tree", "Crystalline Shards", "Sinuous Tubers")
LOCAL_ONLY = {"mining": "planetary mining locations", "ggg": "potential green gas giants",
              "bio_left": "unfinished biology"}
SECTIONS = ("stars", "planets", "rings", "hotspots", "bio", "mining")
DOCK_SERVICES = {"uc": "Universal Cartographics", "vista": "Vista Genomics", "refuel": "Refuel", "repair": "Repair",
                 "rearm": "Restock", "shipyard": "Shipyard", "outfitting": "Outfitting", "trader": "Material Trader",
                 "broker": "Technology Broker", "factors": "Interstellar Factors Contact", "market": "Market",
                 "black_market": "Black Market"}


def _text(value, limit=140):
    return " ".join(str(value or "").split())[:limit]


def _num(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _sale_time(sale):
    """A sale's timestamp: the game's sale events are kept as {timestamp, value, system, station}."""
    if isinstance(sale, dict):
        return str(sale.get("timestamp") or "")
    return str(sale or "")


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class DashboardSurveyMoreMixin:

    # -- the profile's scan cache, parsed once per change ---------------------------------------------
    def _survey_all_items(self):
        conn, lock = getattr(self, "conn", None), getattr(self, "db_lock", None)
        if conn is None or lock is None:
            return []
        parsing = self.__dict__.setdefault("_survey_items_parse_lock", threading.Lock())
        with parsing:
            return self._survey_all_items_now(conn, lock)

    def _survey_items_soon(self):
        """The scan cache for the UI thread, which never parses it: what's parsed
        now (None before the first parse), re-checked off the UI thread at most
        every few seconds. A change brings the Archive and the Atlas up to date."""
        cached = getattr(self, "_survey_items_cache", None)
        now = time.monotonic()
        if now - getattr(self, "_survey_items_checked", -1e9) >= 5.0 and not getattr(self, "_survey_items_busy", False):
            self._survey_items_checked = now
            self._survey_items_busy = True

            def run():
                try:
                    self._survey_all_items()
                except Exception:
                    logger.debug("Scan cache check failed", exc_info=True)
                finally:
                    self._survey_items_busy = False
                if getattr(self, "_survey_items_cache", None) is not cached:
                    post = getattr(self, "_ui_post", None)
                    if callable(post):
                        post(self._survey_items_changed, key="survey-items-changed")

            threading.Thread(target=run, name="SurveyItems", daemon=True).start()
        return cached[1] if cached else None

    def _survey_items_changed(self):
        refresh = getattr(self, "_refresh_exploration_window", None)
        if callable(refresh):
            refresh()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish()

    def _survey_all_items_now(self, conn, lock):
        try:
            with lock:
                count = conn.execute("SELECT COUNT(*), MAX(ts) FROM scan_hud_items").fetchone()
                cached = getattr(self, "_survey_items_cache", None)
                if cached and cached[0] == tuple(count):
                    return cached[1]
                rows = conn.execute("SELECT system_name, data_json FROM scan_hud_items").fetchall()
        except sqlite3.Error:
            return []
        items = []
        for system, data in rows:
            try:
                item = json.loads(data)
            except ValueError:
                continue
            if isinstance(item, dict):
                item["_system"] = system
                items.append(item)
        self._survey_items_cache = (tuple(count), items)
        return items

    def _survey_coords_index(self):
        history = getattr(self, "travel_history", None)
        if history is None:
            return {}
        with history.lock:
            key = len(history.rows)
            cached = getattr(self, "_survey_coords_cache", None)
            if cached and cached[0] == key:
                return cached[1]
            index = {str(row[1]).casefold(): (row[2], row[3], row[4]) for row in history.rows}
        self._survey_coords_cache = (key, index)
        return index

    # -- SEARCH ----------------------------------------------------------------------------------------
    def _search_state(self):
        return self._html_profile_transient("_survey_search", {"status": "ready", "detail": "Tick what you want and search.",
                                                               "results": [], "rev": 0, "generation": 0, "found": None})

    def _search_find(self, name):
        """A system by name: your own record first, then Spansh."""
        state = self._search_state()
        name = _text(name)
        if not name:
            return False
        visits = (getattr(self, "travel_history", None).recall(name) if getattr(self, "travel_history", None) else None)
        coords = self._survey_coords_of(name)
        own = self._survey_own_items([name]).get(name.casefold(), [])
        if visits or own:
            state.update(found={"name": name, "source": "yours", "visits": visits, "bodies": len(own), "coords": coords,
                                "firsts": sum(1 for item in own if item.get("was_discovered") is False)},
                         rev=state["rev"] + 1)
            self._survey_bump()
            return True
        state.update(status="working", detail=f"Looking for {name}…")
        self._survey_bump()

        def done(result, error):
            if error:
                state.update(status="failed", detail=error, found=None)
            else:
                state.update(status="ready", detail=f"Found {result['name']} on Spansh.",
                             found={"name": result["name"], "source": "spansh", "id64": result["id64"], "coords": result["coords"],
                                    "visits": None, "bodies": int((result.get("record") or {}).get("body_count") or 0), "firsts": 0})
            state["rev"] += 1
            self._survey_bump()

        self._survey_task("find", lambda: spansh.system_lookup(name), done)
        return True

    @staticmethod
    def _search_spansh_filters(section, tick, payload):
        if section == "stars":
            filters = {"subtype": {"value": STAR_TICKS[tick]}}
            if payload.get("arrival_only"):
                filters["is_main_star"] = {"value": True}
            return filters
        if section == "planets":
            if tick == "tf":
                return {"terraforming_state": {"value": ["Terraformable"]}}
            if tick == "landable":
                return {"is_landable": {"value": True}}
            return {"subtype": {"value": PLANET_TICKS[tick]}}
        if section == "rings":
            return {"rings": [{"type": RING_TICKS[tick]}]}
        if section == "hotspots":
            return {"ring_signals": [{"name": tick, "value": [1, 999], "comparison": "<=>"}]}
        if section == "bio":
            if tick == "any":
                return {"signals": [{"name": "Biological", "value": [max(1, int(payload.get("min_signals") or 1)), 999],
                                     "comparison": "<=>"}]}
            return {"landmarks": [{"type": tick}]}
        if section == "mining" and tick == "geo":
            return {"signals": [{"name": "Geological", "value": [1, 999], "comparison": "<=>"}]}
        return None

    @staticmethod
    def _search_local_match(section, tick, item, payload):
        star = bool(item.get("is_star") or item.get("star_type"))
        if section == "stars":
            if not star or (payload.get("arrival_only") and item.get("distance_to_arrival")):
                return False
            cls = nearby.star_class(item.get("star_type"))
            giant = "giant" in str(item.get("star_type") or "").casefold() or str(item.get("star_type") or "").endswith(("Giant", "SuperGiant"))
            return {"o": cls == "O", "b": cls == "B", "a": cls == "A", "f": cls == "F", "g": cls == "G", "k": cls == "K",
                    "m": cls == "M", "brown": cls in ("L", "T", "Y"), "neutron": cls == "N", "black_hole": cls == "BH",
                    "white_dwarf": cls.startswith("D"), "wolf_rayet": cls.startswith("W"),
                    "carbon": cls in ("C", "CN", "CJ", "CH", "CHd", "MS", "S"), "proto": cls in ("TTS", "Ae/Be", "AeBe"),
                    "giant": giant}.get(tick, False)
        if star:
            return False
        if section == "planets":
            if tick == "tf":
                return bool(item.get("terraformable"))
            if tick == "landable":
                return bool(item.get("landable"))
            return nearby.planet_kind(item.get("planet_class")) == tick
        if section == "rings":
            want = RING_TICKS[tick].replace(" ", "").casefold()
            return any(want in str(ring.get("RingClass") or "").casefold() for ring in item.get("rings") or ()
                       if isinstance(ring, dict) and "belt" not in str(ring.get("Name") or "").casefold())
        if section == "bio":
            if tick == "any":
                return int(item.get("bio_count") or 0) >= max(1, int(payload.get("min_signals") or 1))
            if tick == "bio_left":
                return int(item.get("bio_count") or 0) > int(item.get("organic_complete_count") or 0)
            genera = [str(g.get("Genus_Localised") or g.get("Genus") or "") if isinstance(g, dict) else str(g)
                      for g in item.get("genuses") or ()]
            genera += [str(scan.get("genus") or "") for scan in (item.get("organic_scans") or {}).values() if isinstance(scan, dict)]
            return any(tick.casefold() in genus.casefold() for genus in genera)
        if section == "mining":
            if tick == "geo":
                return int(item.get("geo_count") or 0) > 0
            if tick == "mining":
                return int(item.get("mining_count") or 0) > 0
            if tick == "ggg":
                return bool(item.get("green_giant")) or bool(ggg.predict({
                    "PlanetClass": item.get("planet_class"), "SurfaceTemperature": item.get("surface_temp"),
                    "MassEM": item.get("mass"), "Radius": item.get("radius")}))
        return False

    def _search_run(self, payload):
        state = self._search_state()
        ticks = {section: [str(t) for t in (payload.get("ticks") or {}).get(section) or () if t]
                 for section in SECTIONS}
        ticks = {section: values for section, values in ticks.items() if values}
        if not ticks:
            state.update(status="failed", detail="Tick at least one box.")
            self._survey_bump()
            return False
        source = "local" if payload.get("source") == "local" else "spansh"
        try:
            radius = max(1.0, min(1000.0 if source == "spansh" else 100000.0, float(payload.get("radius") or 100)))
        except (TypeError, ValueError):
            radius = 100.0
        at_least = max(1, int(_num(payload.get("at_least"), 1) or 1))
        centre = self._survey_centre(_text(payload.get("centre"), 20) or "here", _text(payload.get("name")))
        if centre.get("error"):
            state.update(status="failed", detail=centre["error"])
            self._survey_bump()
            return False
        if source == "spansh" and any(t in LOCAL_ONLY for values in ticks.values() for t in values):
            state.update(status="failed", detail="Unfinished biology, mining locations and potential green gas giants come "
                                                 "from your own scans: search Local for them.")
            self._survey_bump()
            return False
        generation = state["generation"] + 1
        form = {"source": source, "ticks": ticks, "radius": radius, "at_least": at_least,
                "arrival_only": bool(payload.get("arrival_only")), "two_hotspots": bool(payload.get("two_hotspots")),
                "min_signals": int(_num(payload.get("min_signals"), 1) or 1), "centre": centre}
        state.update(generation=generation, status="working", form=form, results=[],
                     detail=f"Searching {'Spansh' if source == 'spansh' else 'your own scans'} within {radius:g} ly of {centre['name']}…")
        self._survey_bump()

        def work():
            coords = centre.get("coords")
            if not coords:
                coords = spansh.system_lookup(centre["name"]).get("coords")
            if not coords:
                raise spansh.SpanshError(f"No position known for {centre['name']}.")
            if source == "local":
                return self._search_local(form, coords)
            return self._search_spansh(form, coords)

        def done(result, error):
            if state.get("generation") != generation:
                return
            if error:
                state.update(status="failed", detail=error)
            else:
                rows, note = result
                visits = self._survey_visits()
                for row in rows:
                    row["visited"] = row["system"].casefold() in visits
                state.update(status="ready", results=rows,
                             detail=f"{len(rows):,} system{'s' if len(rows) != 1 else ''} match every section." + (f" {note}" if note else ""))
            state["rev"] += 1
            self._survey_bump()

        self._survey_task("search", work, done)
        return True

    def _search_spansh(self, form, coords):
        systems, sets, cut_note = {}, [], ""
        for section, values in form["ticks"].items():
            matched = {}
            for tick in values:
                filters = self._search_spansh_filters(section, tick, form)
                if not filters:
                    continue
                bodies, count, cut = spansh.body_search(filters, coords, form["radius"], size=100, max_pages=3)
                if cut is not None:
                    cut_note = f"Some sections had more matches than were fetched: complete to {cut:.0f} ly."
                for body in bodies:
                    if section == "hotspots" and form.get("two_hotspots"):
                        best = max((sum(1 for s in ring.get("signals") or () if isinstance(s, dict) and s.get("name") == tick)
                                    for ring in body.get("rings") or () if isinstance(ring, dict)), default=0)
                        counts = [sum(int(s.get("count") or 1) for s in ring.get("signals") or () if isinstance(s, dict))
                                  for ring in body.get("rings") or () if isinstance(ring, dict)]
                        if max(counts or [0]) < 2 and best < 2:
                            continue
                    key = str(body.get("system_id64") or body.get("system_name"))
                    entry = systems.setdefault(key, {"system": body.get("system_name") or "", "id64": str(body.get("system_id64") or ""),
                                                     "distance": _num(body.get("distance")),
                                                     "coords": [body.get("system_x"), body.get("system_y"), body.get("system_z")]
                                                     if body.get("system_x") is not None else None, "matches": {}})
                    name = str(body.get("name") or "")
                    short = name[len(entry["system"]):].strip() if name.casefold().startswith(entry["system"].casefold()) else name
                    matched.setdefault(key, {})[short or name] = tick
                    entry["matches"].setdefault(section, {})[short or name] = tick
            sets.append({key for key, bodies in matched.items() if len(bodies) >= form["at_least"]})
        keep = set.intersection(*sets) if sets else set()
        rows = [self._search_row(systems[key], coords) for key in keep]
        rows.sort(key=lambda row: (row["distance"] is None, row["distance"] or 0))
        return rows[:500], cut_note

    def _search_local(self, form, coords):
        index = self._survey_coords_index()
        by_system = {}
        for item in self._survey_all_items():
            system = str(item.get("_system") or "")
            where = index.get(system.casefold())
            if not where:
                continue
            distance = math.dist(coords, where)
            if distance > form["radius"]:
                continue
            for section, values in form["ticks"].items():
                for tick in values:
                    if self._search_local_match(section, tick, item, form):
                        entry = by_system.setdefault(system.casefold(), {"system": system, "id64": str(item.get("system_address") or ""),
                                                                          "distance": distance, "coords": list(where), "matches": {}})
                        entry["matches"].setdefault(section, {})[str(item.get("name") or "")] = tick
        rows = [self._search_row(entry, coords) for entry in by_system.values()
                if all(len(entry["matches"].get(section) or {}) >= form["at_least"] for section in form["ticks"])]
        rows.sort(key=lambda row: row["distance"] or 0)
        searched = len({str(item.get("_system") or "").casefold() for item in self._survey_all_items()})
        return rows[:500], f"Local covers only the {searched:,} systems you've scanned yourself."

    def _search_row(self, entry, centre):
        here = getattr(self, "current_coords", None)
        from_you = math.dist(here, entry["coords"]) if here and entry.get("coords") and None not in entry["coords"] else None
        return {"system": entry["system"], "id64": entry["id64"], "coords": entry["coords"],
                "distance": round(entry["distance"], 2) if entry["distance"] is not None else None,
                "from_you": round(from_you, 1) if from_you is not None else None,
                "matches": [{"section": section, "body": body, "what": tick}
                            for section, bodies in entry["matches"].items() for body, tick in bodies.items()]}

    def _search_payload(self):
        state = self._search_state()
        return {"status": state["status"], "detail": state["detail"], "results": state["results"], "rev": state["rev"],
                "form": {k: v for k, v in (state.get("form") or {}).items() if k != "centre"},
                "found": state.get("found"),
                "options": {"stars": list(STAR_TICKS), "planets": list(PLANET_TICKS), "rings": list(RING_TICKS),
                            "hotspots": list(HOTSPOT_TICKS), "bio": ["any", *BIO_TICKS, "bio_left"],
                            "mining": ["geo", "mining", "ggg"], "local_only": list(LOCAL_ONLY)}}

    # -- PLOT ROUTE -------------------------------------------------------------------------------------
    def _route(self):
        path = self._profile_path(ROUTE_FILE)
        cached = getattr(self, "_route_cache", None)
        if cached and cached[0] == path:
            return cached[1]
        try:
            with open(path, encoding="utf-8") as handle:
                route = json.load(handle)
        except (OSError, ValueError):
            route = None
        route = route if isinstance(route, dict) and route.get("rows") else None
        self._route_cache = (path, route)
        # A route plotted before 5.7.8 becomes the waypoint route the first time
        # it's read, so the Nav HUD and the maps follow it too.
        if (route and not route.get("waypoint_note") and route.get("kind") != "waypoints" and not route.get("done_at")
                and getattr(self, "waypoint_manager", None) is not None):
            self._route_adopt(route)
        return route

    def _route_save(self, route):
        path = self._profile_path(ROUTE_FILE)
        try:
            if route is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                temp = f"{path}.tmp"
                with open(temp, "w", encoding="utf-8") as handle:
                    json.dump(route, handle, separators=(",", ":"))
                os.replace(temp, path)
        except OSError as exc:
            logger.warning("Route not saved: %s", exc)
        self._route_cache = (path, route)
        self._survey_bump()
        getattr(self, "_update_galaxy_minimap_safely", lambda: None)()

    def _route_plotting(self):
        return self._html_profile_transient("_route_plotting_state", {"status": "ready", "detail": "", "generation": 0})

    def _route_ships(self):
        """Every ship you've flown with a Loadout on record: its figures for the plotters."""
        state = getattr(self, "companion_state", None) or {}
        current = (state.get("loadout") or {}).get("ShipID")
        ships = []
        for ship_id, loadout in (state.get("fleet_loadouts") or {}).items():
            if not isinstance(loadout, dict):
                continue
            try:
                figures = fsd.fleet_figures(loadout)
            except Exception:
                continue
            ships.append({"id": str(ship_id), "name": str(loadout.get("ShipName") or ""), "type": str(loadout.get("Ship") or ""),
                          "range": fsd.fleet_range(figures) if figures.get("unladen") else _num(loadout.get("MaxJumpRange")),
                          "exact": bool(figures.get("exact")), "current": str(ship_id) == str(current),
                          "scoop": any("fuelscoop" in str(m.get("Item") or "").casefold() for m in loadout.get("Modules") or ())})
        ships.sort(key=lambda ship: (not ship["current"], ship["name"]))
        return ships

    def _route_plot(self, payload, *, adopt=True, note=None, on_done=None, on_error=None):
        """Plot on Spansh. With ``adopt`` the route is the one flown: PLOT ROUTE
        shows it and it becomes the waypoint route (``note`` marks its stops).
        ``on_done(route)`` / ``on_error(text)`` tell whoever asked (Expeditions)."""
        plotting = self._route_plotting()
        kind = _text(payload.get("plotter"), 20) or "neutron"
        source = _text(payload.get("from")) or str(getattr(self, "current_sys", "") or "")
        destination = _text(payload.get("to"))
        state = getattr(self, "companion_state", None) or {}
        ship_id = _text(payload.get("ship"), 30) or str((state.get("loadout") or {}).get("ShipID") or "")
        loadout = (state.get("fleet_loadouts") or {}).get(ship_id) or (state.get("loadout") if not ship_id else None)
        figures = fsd.fleet_figures(loadout) if isinstance(loadout, dict) and loadout.get("Modules") else {}
        cargo = int(_num(payload.get("cargo"), 0) or 0)
        typed = _num(payload.get("range"))
        jump_range = typed or (fsd.fleet_range(figures, cargo=cargo) if figures.get("unladen") else None) or self._survey_jump_range()
        margin = _num(payload.get("conservative_ly")) if payload.get("conservative") else None
        if margin and jump_range:
            jump_range = fsd.conservative_range(jump_range, margin, figures.get("booster_ly") or 0)
        if not source:
            plotting.update(status="failed", detail="No start: the journal hasn't said where you are.")
            self._survey_bump()
            return False
        if kind in ("neutron", "exact") and not destination:
            plotting.update(status="failed", detail="Where to? Type a destination.")
            self._survey_bump()
            return False
        if kind == "exact" and not figures.get("exact"):
            plotting.update(status="failed", detail="The exact plotter needs a ship whose frame shift drive we know: "
                                                    "pick another, or use the neutron plotter with a range.")
            self._survey_bump()
            return False
        if not jump_range and kind != "exact":
            plotting.update(status="failed", detail="Give a jump range, or pick a ship you've flown.")
            self._survey_bump()
            return False
        systems = [_text(name) for name in payload.get("systems") or () if _text(name)][:100]
        if kind == "sweep" and not systems:
            plotting.update(status="failed", detail="Tick systems to sweep in Search, Nearby, Firsts or your bookmarks.")
            self._survey_bump()
            return False
        generation = plotting["generation"] + 1
        label = {"neutron": "Neutron plotter", "exact": "Exact plotter", "sweep": "Sweep",
                 **{key: spec["label"] for key, spec in spansh.SURVEY_KINDS.items()}}.get(kind, kind)
        plotting.update(generation=generation, status="working", detail=f"Asking Spansh for a {label.lower()} route from {source}…")
        self._survey_bump()
        options = {k: payload.get(k) for k in ("radius", "max_results", "max_distance", "min_value", "use_mapping_value",
                                               "avoid_thargoids", "loop", "efficiency", "supercharged", "no_neutrons",
                                               "injections", "exclude_secondary") if payload.get(k) not in (None, "")}

        def plot(start, end):
            if kind == "exact":
                optimal = None
                if margin:
                    short = fsd.conservative_optimal_mass(figures, cargo, margin)
                    optimal = short[0] if short else None
                return spansh.exact_route(start, end, figures, cargo, supercharged=bool(options.get("supercharged")),
                                          use_supercharge=not options.get("no_neutrons"), injections=bool(options.get("injections")),
                                          exclude_secondary=bool(options.get("exclude_secondary")), optimal_mass=optimal)
            if kind == "neutron":
                return spansh.neutron_rows(start, end, jump_range, int(_num(options.get("efficiency"), 60) or 60),
                                           figures.get("supercharge") or 4)
            if kind == "sweep":
                return spansh.tourist_route(start, systems, jump_range, loop=bool(options.get("loop")))
            return spansh.survey_route(kind, start, jump_range, destination=end or None,
                                       radius=int(_num(options.get("radius"), 25) or 25),
                                       max_results=int(_num(options.get("max_results"), 100) or 100),
                                       max_distance=int(_num(options.get("max_distance"), 50) or 50),
                                       min_value=int(_num(options.get("min_value"), 1_000_000) or 1_000_000),
                                       use_mapping_value=options.get("use_mapping_value", True) not in (False, "false", 0),
                                       avoid_thargoids=options.get("avoid_thargoids", True) not in (False, "false", 0),
                                       loop=options.get("loop", True) not in (False, "false", 0))

        def stand_in(name):
            """A system Spansh knows near one it doesn't (yours, freshly found)."""
            coords = self._survey_coords_of(name)
            if not coords:
                return None
            found = spansh.systems_sphere(coords, 25, max_pages=1).get("results") or []
            known = [row for row in found if str(row.get("name") or "").casefold() != name.casefold()]
            return (known[0].get("name"), coords) if known else None

        def work():
            note = ""
            start, end = source, destination
            try:
                rows = plot(start, end)
            except spansh.SpanshError as exc:
                text = str(exc).casefold()
                if not ("know" in text or "not found" in text or "could not find" in text or "unable to find" in text):
                    raise
                swapped = False
                first = stand_in(start)
                if first:
                    start, swapped = first[0], True
                last = stand_in(end) if end else None
                if last:
                    end, swapped = last[0], True
                if not swapped:
                    raise
                rows = plot(start, end)
                if start != source and first:
                    rows.insert(0, {"system": source, "id64": None, "coords": list(first[1]), "jumps": 0, "distance": None,
                                    "remaining": None, "neutron": False, "refuel": False, "bodies": []})
                    note += f" Spansh doesn't know {source} yet: plotted from {start}, nearby."
                if end and end != destination and last:
                    rows.append({"system": destination, "id64": None, "coords": list(last[1]), "jumps": 1, "distance": None,
                                 "remaining": 0, "neutron": False, "refuel": False, "bodies": []})
                    note += f" Spansh doesn't know {destination} yet: plotted to {end}, then the last jump is yours."
            permits, stars = {}, {}
            try:
                names = list({row["system"] for row in rows})[:500]
                body = {"filters": {"name": {"value": names}}, "sort": [], "size": len(names), "page": 0}
                answer = spansh._call("POST", "systems/search", body=body, ttl=86400)
                for found in answer.get("results") or ():
                    key = str(found.get("name") or "").casefold()
                    permits[key] = bool(found.get("needs_permit"))
                    # Each stop's main star, for the Nav HUD's pips (5.7.8).
                    main = next((b for b in found.get("bodies") or () if isinstance(b, dict) and b.get("is_main_star")), None)
                    if main and main.get("subtype"):
                        stars[key] = main["subtype"]
            except Exception:
                permits, stars = {}, {}
            for row in rows:
                row["permit"] = permits.get(row["system"].casefold(), False)
                subtype = stars.get(row["system"].casefold())
                row["star_class"] = nearby.star_class(subtype) if subtype else ("N" if row.get("neutron") else "")
                row["scoopable"] = nearby.scoopable(subtype) if subtype else None
            return rows, note.strip()

        waypoint_note = note

        def done(result, error):
            if plotting.get("generation") != generation:
                return
            if error:
                plotting.update(status="failed", detail=error)
                self._survey_bump()
                if on_error:
                    on_error(error)
                return
            rows, note = result
            route = {"kind": kind, "label": label, "created": _now_iso(), "from": source, "to": destination or rows[-1]["system"],
                     "options": {**options, "range": round(jump_range, 2) if jump_range else None, "cargo": cargo,
                                 "conservative_ly": margin},
                     "ship": {"id": ship_id, "name": str((loadout or {}).get("ShipName") or ""), "type": str((loadout or {}).get("Ship") or "")}
                     if loadout else None,
                     "rows": rows, "at": None, "furthest": None, "off_route": False, "done_at": None, "note": note,
                     "target_check": None}
            current = str(getattr(self, "current_sys", "") or "").casefold()
            if rows and rows[0]["system"].casefold() == current:
                route["at"] = route["furthest"] = 0
            plotting.update(status="ready", detail=f"{label}: {len(rows) - 1:,} stops to {route['to']}." + (f" {note}" if note else ""))
            if adopt:
                self._route_adopt(route, waypoint_note)
                if rows and len(rows) > 1:
                    self._html_copy_text(rows[1]["system"] if route["at"] == 0 else rows[0]["system"])
            if on_done:
                on_done(route)
            self._survey_bump()

        self._survey_task("plot", work, done)
        return True

    def _route_adopt(self, route, note=None, waypoints=True):
        """The route being flown (5.7.8): PLOT ROUTE shows it, and its stops are
        the waypoint route, so the Nav HUD, COPY NEXT, the copy on arrival, the
        Galaxy Minimap and the Atlas all follow it. The waypoints you had wait in
        the route file and come back when it's cleared."""
        manager = getattr(self, "waypoint_manager", None)
        previous = self._route() or {}
        if manager is not None and waypoints:
            mine = [dict(row) for row in manager.waypoints or () if isinstance(row, dict)]
            ours = any(str(row.get("note") or "").startswith(ROUTE_NOTE) for row in mine)
            route["kept_waypoints"] = (previous.get("kept_waypoints") or []) if ours else mine
            note = note or f"{ROUTE_NOTE}{route.get('label') or 'Plotted'}"
            stops = route["rows"][1:] if len(route["rows"]) > 1 else route["rows"]
            manager.waypoints = [{"name": row["system"], "coords": row.get("coords"), "note": note,
                                  "neutron": bool(row.get("neutron")), "jumps": row.get("jumps"),
                                  "star_class": row.get("star_class") or ("N" if row.get("neutron") else ""),
                                  "scoopable": row.get("scoopable"),
                                  **({"refuel": True} if row.get("refuel") else {})}
                                 for row in stops if row.get("system")]
            manager.save()
            route["waypoint_note"] = note
        elif previous.get("kept_waypoints"):
            route["kept_waypoints"] = previous["kept_waypoints"]
        self._route_save(route)
        self._route_follow_everywhere()
        if any("star_class" not in row for row in route["rows"]):
            self._route_fill_stars()

    def _route_fill_stars(self):
        """A route plotted before 5.7.8 has no stars: ask Spansh once for each
        stop's main star, for the Nav HUD's pips."""
        route = self._route()
        if not route or getattr(self, "_route_stars_asked", None) == route.get("created"):
            return
        self._route_stars_asked = route.get("created")
        names = list({row["system"] for row in route["rows"]})[:500]

        def work():
            body = {"filters": {"name": {"value": names}}, "sort": [], "size": len(names), "page": 0}
            answer = spansh._call("POST", "systems/search", body=body, ttl=86400)
            stars = {}
            for found in answer.get("results") or ():
                main = next((b for b in found.get("bodies") or () if isinstance(b, dict) and b.get("is_main_star")), None)
                if main and main.get("subtype"):
                    stars[str(found.get("name") or "").casefold()] = main["subtype"]
            return stars

        def done(stars, error):
            current = self._route()
            if error or not current or current.get("created") != route.get("created"):
                return
            for row in current["rows"]:
                subtype = (stars or {}).get(row["system"].casefold())
                row["star_class"] = nearby.star_class(subtype) if subtype else ("N" if row.get("neutron") else "")
                row["scoopable"] = nearby.scoopable(subtype) if subtype else None
            by_name = {row["system"].casefold(): row for row in current["rows"]}
            manager = getattr(self, "waypoint_manager", None)
            if manager is not None and current.get("waypoint_note"):
                for waypoint in manager.waypoints or ():
                    row = by_name.get(str(waypoint.get("name") or "").casefold())
                    if row and waypoint.get("note") == current["waypoint_note"]:
                        waypoint.update(star_class=row["star_class"], scoopable=row["scoopable"])
                manager.save()
            self._route_save(current)
            self._route_follow_everywhere()

        self._survey_task("route-stars", work, done)

    def _route_forget(self, note=None):
        """The waypoint route was cleared somewhere else (Expeditions, the
        waypoint list): Plot Route is the source, so it goes too, and with it
        the Nav HUD's, the maps' and COPY NEXT's route. ``note``: only when the
        route is that one (an expedition's)."""
        route = self._route()
        if not route or (note is not None and not str(route.get("waypoint_note") or "").startswith(note)):
            return False
        self._route_save(None)
        self._route_follow_everywhere()
        return True

    @staticmethod
    def _route_skipped(route):
        return {int(i) for i in (route or {}).get("skipped") or () if isinstance(i, int)}

    def _route_next_index(self, route, after):
        """The first stop after ``after`` that isn't marked done."""
        skipped = self._route_skipped(route)
        return next((i for i in range(after + 1, len(route["rows"])) if i not in skipped), None)

    def _route_skip(self, index, on=True):
        """Mark a stop ahead done, so the route goes on to the one after it (or
        bring it back). Its waypoint is marked visited too, so the Nav HUD,
        COPY NEXT and the maps skip it as well."""
        route = self._route()
        if not route or route.get("done_at"):
            return False
        rows = route["rows"]
        at = route.get("at") if isinstance(route.get("at"), int) else 0
        if not at < index < len(rows):
            return False
        skipped = self._route_skipped(route)
        if on:
            skipped.add(index)
        else:
            skipped.discard(index)
        route["skipped"] = sorted(skipped)
        route["target_check"] = None
        manager = getattr(self, "waypoint_manager", None)
        note = route.get("waypoint_note")
        if manager is not None and (note or route.get("kind") == "waypoints"):
            name = str(rows[index]["system"] or "").casefold()
            changed = False
            for waypoint in manager.waypoints or ():
                if not isinstance(waypoint, dict) or str(waypoint.get("name") or "").casefold() != name:
                    continue
                if note and waypoint.get("note") != note:
                    continue
                if bool(waypoint.get("visited")) != on:
                    waypoint["visited"] = on
                    changed = True
            if changed:
                manager.save()
        self._route_save(route)
        self._route_follow_everywhere()
        return True

    def _route_follow_everywhere(self):
        """The Nav HUD and the Galactic Atlas see the waypoint route change now."""
        for name in ("update_hud", "_refresh_exploration_window"):
            action = getattr(self, name, None)
            if callable(action):
                try:
                    action()
                except Exception:
                    logger.debug("%s after a route change failed", name, exc_info=True)

    def _route_clear(self):
        """Clear the route, and give back the waypoints it set aside."""
        route = self._route() or {}
        manager = getattr(self, "waypoint_manager", None)
        note = route.get("waypoint_note")
        if manager is not None and note:
            mine = [row for row in manager.waypoints or () if isinstance(row, dict) and row.get("note") != note]
            manager.waypoints = mine + [row for row in route.get("kept_waypoints") or () if isinstance(row, dict)]
            manager.save()
        self._route_save(None)
        self._route_follow_everywhere()
        return True

    def _route_follow_waypoints(self):
        """Your waypoint route (and an expedition's FLY IT) followed as a route."""
        manager = getattr(self, "waypoint_manager", None)
        rows = [{"system": str(row.get("name") or ""), "id64": None, "coords": row.get("coords"), "jumps": row.get("jumps") or 0,
                 "distance": None, "remaining": None, "neutron": bool(row.get("neutron")), "refuel": False, "bodies": [],
                 "permit": False}
                for row in getattr(manager, "waypoints", None) or () if isinstance(row, dict) and row.get("name")]
        if not rows:
            return False
        current = str(getattr(self, "current_sys", "") or "")
        if rows[0]["system"].casefold() != current.casefold() and current:
            rows.insert(0, {"system": current, "id64": None, "coords": getattr(self, "current_coords", None), "jumps": 0,
                            "distance": None, "remaining": None, "neutron": False, "refuel": False, "bodies": [], "permit": False})
        self._route_save({"kind": "waypoints", "label": "Your waypoints", "created": _now_iso(), "from": rows[0]["system"],
                          "to": rows[-1]["system"], "options": {}, "ship": None, "rows": rows, "at": 0, "furthest": 0,
                          "off_route": False, "done_at": None, "note": "", "target_check": None})
        return True

    def _route_on_arrival(self, system, live=True):
        route = self._route()
        if not route:
            return
        rows = route["rows"]
        key = str(system or "").casefold()
        at = route.get("at")
        index = None
        start = max(0, (at or 0) - 1)
        for i in list(range(start, len(rows))) + list(range(0, start)):
            if rows[i]["system"].casefold() == key:
                index = i
                break
        if route.get("done_at"):
            if index is None:
                # Finished routes clear themselves once you've moved on.
                self._route_clear()
            return
        if index is None:
            if at is not None:
                route["off_route"] = True
                self._route_save(route)
            return
        route.update(at=index, off_route=False, furthest=max(index, route.get("furthest") or 0), target_check=None,
                     arrival=_now_iso())
        following = self._route_next_index(route, index)
        if following is None:
            route["done_at"] = _now_iso()
        self._route_save(route)
        if live:
            nxt = rows[following]["system"] if following is not None else ""
            if nxt and self.config.get("auto_copy_waypoint", False) and not route.get("waypoint_note"):
                self._html_copy_text(nxt)
            self._route_say_arrival(route, index)

    def _route_say_arrival(self, route, index):
        rows = route["rows"]
        row = rows[index]
        if route.get("done_at"):
            text = f"{route['label']} complete. That's {row['system']}."
        elif route["kind"] in spansh.SURVEY_KINDS:
            left = self._route_left_at(row)
            if not left:
                return
            text = f"Stop {index} of {len(rows) - 1}: {left}."
        elif row.get("refuel"):
            text = f"Refuel here: scoop before the next jump to {rows[index + 1]['system']}."
        else:
            return
        mind = getattr(self, "_orders_mind", lambda: None)()
        if mind is not None and hasattr(mind, "crew_say"):
            try:
                from voidcompass.core import companions
                mind.crew_say(companions.identity(self.config), text, heading="ROUTE", topic="route_stop", converse=False)
            except Exception:
                logger.debug("Route line not said", exc_info=True)

    def _route_left_at(self, row):
        """What's left at a survey stop, from your own scans: bodies to scan,
        map, or species to sample."""
        bodies = row.get("bodies") or []
        if not bodies:
            return ""
        own = {str(item.get("name") or "").casefold(): item
               for item in self._survey_own_items([row["system"]]).get(row["system"].casefold(), [])}
        todo = []
        for body in bodies:
            name = str(body.get("name") or "")
            short = name[len(row["system"]):].strip() if name.casefold().startswith(row["system"].casefold()) else name
            item = own.get(short.casefold())
            if body.get("species"):
                done = {str(scan.get("species") or "").casefold() for scan in ((item or {}).get("organic_scans") or {}).values()
                        if isinstance(scan, dict) and scan.get("is_complete")}
                left = [s for s in body["species"] if str(s.get("name") or "").casefold() not in done]
                if left:
                    todo.append(f"{len(left)} species on {short}")
            elif item is None:
                todo.append(f"scan and map {short}")
            elif not item.get("dss_complete"):
                todo.append(f"map {short}")
        return ", ".join(todo[:4]) + (f" and {len(todo) - 4} more" if len(todo) > 4 else "")

    def _route_on_target(self, raw):
        """FSDTarget: the right system targeted? Said once."""
        route = self._route()
        if not route or route.get("at") is None or route.get("done_at"):
            return
        rows = route["rows"]
        at = route["at"]
        name = str(raw.get("Name") or "")
        following = self._route_next_index(route, at)
        if following is None or not name:
            return
        nxt = rows[following]["system"]
        if name.casefold() == nxt.casefold():
            check = {"state": "ok", "text": f"✓ {nxt} targeted"}
        else:
            ahead = next((i for i in range(at + 2, min(len(rows), at + 30)) if rows[i]["system"].casefold() == name.casefold()), None)
            check = ({"state": "ahead", "text": f"↷ {name} is {ahead - at} stops ahead"} if ahead is not None
                     else {"state": "wrong", "text": f"⚠ targeted {name}, not the next stop ({nxt})"})
        if (route.get("target_check") or {}).get("text") == check["text"]:
            return
        route["target_check"] = check
        self._route_save(route)
        if check["state"] != "ok":
            toast = getattr(self, "toast_hud", None)
            if toast is not None and hasattr(toast, "push"):
                try:
                    toast.push("ROUTE", check["text"])
                except Exception:
                    pass

    def _route_pace(self):
        """Seconds a jump takes at your real pace this session (gaps of over
        ten minutes left out), or None."""
        history = getattr(self, "travel_history", None)
        if history is None:
            return None
        with history.lock:
            rows = history.rows[-40:]
        stamps = [time.mktime(time.strptime(str(row[0])[:19], "%Y-%m-%dT%H:%M:%S")) for row in rows]
        gaps = [b - a for a, b in zip(stamps, stamps[1:]) if 0 < b - a < 600]
        return statistics.median(gaps) if len(gaps) >= 3 else None

    def _route_fuel(self, route):
        """Fuel against the route ahead (exact plotter): too much for a jump
        planned at the limit, or too little to reach the next refuel stop."""
        if route.get("kind") != "exact" or route.get("at") is None or route.get("off_route"):
            return None
        state = getattr(self, "companion_state", None) or {}
        loadout = state.get("loadout") or {}
        if str((route.get("ship") or {}).get("id") or "") != str(loadout.get("ShipID") or ""):
            return None
        figures = fsd.fleet_figures(loadout) if loadout.get("Modules") else {}
        model = fsd.fleet_model(figures)
        fuel = _num(getattr(self, "current_fuel_main", None))
        if not model or fuel is None or not figures.get("max_fuel"):
            return None
        rows = route["rows"]
        at = route["at"]
        hops = []
        for row in rows[at + 1:at + 1 + fsd.FUEL_RUN_MAX_HOPS]:
            if row.get("distance") is None:
                break
            hops.append((row["distance"], 4 if row.get("neutron") else 1))
            if row.get("refuel"):
                break
        if not hops:
            return None
        cargo = float(route.get("options", {}).get("cargo") or 0)
        window = fsd.fuel_window(model, cargo + (figures.get("fuel_reserve") or 0), hops, figures.get("fuel_main"))
        refuel_at = next((rows[i]["system"] for i in range(at + 1, len(rows)) if rows[i].get("refuel")), None)
        dry = next((i - at for i in range(at + 1, len(rows)) if rows[i].get("refuel")), len(rows) - at - 1)
        if window is None:
            return {"state": "short", "text": f"No fuel load reaches {refuel_at or 'the next stop'} from here: re-plot from here."}
        low, high = window
        if fuel < low - 0.05:
            return {"state": "short", "text": f"Won't reach the refuel stop{f' at {refuel_at}' if refuel_at else ''}: scoop to at least {low:.1f} t."}
        if fuel > high + 0.5:
            return {"state": "heavy", "text": f"Too much fuel for the next jump: {fuel:.1f} t aboard, the plan wants at most {high:.1f} t."}
        if rows[at].get("refuel") and dry >= 3:
            return {"state": "last", "text": f"Last scoop before {dry} dry jumps: fill up here."}
        return None

    def _route_payload(self):
        route = self._route()
        plotting = self._route_plotting()
        ships = self._route_ships()
        if not route:
            return {"route": None, "plotting": {k: plotting.get(k) for k in ("status", "detail")}, "ships": ships,
                    "kinds": {"neutron": "Neutron", "exact": "Exact", **{k: v["label"] for k, v in spansh.SURVEY_KINDS.items()},
                              "sweep": "Sweep"}, "current": str(getattr(self, "current_sys", "") or ""),
                    "auto_copy": bool(self.config.get("auto_copy_waypoint", False))}
        rows = route["rows"]
        at = route.get("at")
        visits = self._survey_visits()
        survey = route["kind"] in spansh.SURVEY_KINDS
        skipped = self._route_skipped(route)
        shown = []
        for index, row in enumerate(rows):
            entry = dict(row)
            entry["index"] = index
            entry["passed"] = at is not None and index < at
            entry["here"] = at == index
            entry["skipped"] = index in skipped and not entry["passed"] and not entry["here"]
            entry["visited"] = row["system"].casefold() in visits
            if survey and not entry["passed"]:
                entry["left"] = self._route_left_at(row)
                entry["finished"] = bool(row.get("bodies")) and not entry["left"] and entry["visited"]
            shown.append(entry)
        nxt = next((row for row in shown if row["index"] > (at if at is not None else -1) and not row["skipped"]), None)
        if nxt is not None:
            nxt["next"] = True
        jumps_left = sum(int(row.get("jumps") or 0) for row in shown if row["index"] > (at if at is not None else 0))
        pace = self._route_pace()
        refuel_in = next((row["index"] - at for row in shown if at is not None and row["index"] > at and row.get("refuel")), None)
        ship = route.get("ship") or {}
        current_ship = str(((getattr(self, "companion_state", None) or {}).get("loadout") or {}).get("ShipID") or "")
        return {
            "route": {**{k: v for k, v in route.items() if k != "rows"}, "rows": shown, "total": len(rows) - 1,
                      "next": nxt["system"] if nxt else None, "jumps_left": jumps_left,
                      "ly_left": (rows[at].get("remaining") if at is not None else rows[0].get("remaining")),
                      "eta_s": round(jumps_left * pace) if pace and jumps_left and not route.get("done_at") else None,
                      "refuel_in": refuel_in, "other_ship": bool(ship.get("id") and current_ship and ship["id"] != current_ship),
                      "fuel": self._route_fuel(route), "permits": sum(1 for row in rows if row.get("permit"))},
            "plotting": {k: plotting.get(k) for k in ("status", "detail")}, "ships": ships,
            "auto_copy": bool(self.config.get("auto_copy_waypoint", False)),
            "kinds": {"neutron": "Neutron", "exact": "Exact", **{k: v["label"] for k, v in spansh.SURVEY_KINDS.items()}, "sweep": "Sweep"},
            "current": str(getattr(self, "current_sys", "") or ""),
        }

    # -- the nearest place to dock -------------------------------------------------------------------------
    def _dock_state(self):
        # Not "_dock_search": the transient is an attribute, and would replace the method.
        return self._html_profile_transient("_dock_search_state", {"status": "ready", "detail": "", "rows": [], "rev": 0, "generation": 0})

    def _dock_search(self, payload):
        state = self._dock_state()
        centre = self._survey_centre(_text(payload.get("centre"), 20) or "here", _text(payload.get("name")))
        if centre.get("error"):
            state.update(status="failed", detail=centre["error"])
            self._survey_bump()
            return False
        services = [DOCK_SERVICES[s] for s in payload.get("services") or () if s in DOCK_SERVICES]
        pad = _text(payload.get("pad"), 2).upper() or "L"
        carriers = bool(payload.get("carriers", True))
        dssa = bool(payload.get("dssa"))
        max_age = _num(payload.get("max_age_days"))
        trader = _text(payload.get("trader"), 20).casefold()
        generation = state["generation"] + 1
        state.update(generation=generation, status="working", detail=f"Looking round {centre['name']}…")
        self._survey_bump()

        def work():
            coords = centre.get("coords") or spansh.system_lookup(centre["name"]).get("coords")
            filters = {"distance": {"min": "0", "max": "10000"}}
            if services:
                filters["services"] = [{"name": s} for s in services]
            if pad == "L":
                filters["has_large_pad"] = {"value": True}
            elif pad == "M":
                filters["medium_pads"] = {"value": [1, 999], "comparison": "<=>"}
            if trader in ("raw", "manufactured", "encoded"):
                filters["material_trader"] = {"value": [trader.title()]}
            body = {"filters": filters, "reference_coords": {"x": coords[0], "y": coords[1], "z": coords[2]},
                    "sort": [{"distance": {"direction": "asc"}}], "size": 50, "page": 0}
            answer = spansh._call("POST", "stations/search", body=body, ttl=120)
            rows = []
            cutoff = time.time() - max_age * 86400 if max_age else None
            for row in answer.get("results") or ():
                kind = str(row.get("type") or "")
                carrier = "carrier" in kind.casefold()
                if carrier and not carriers:
                    continue
                stamp = str(row.get("updated_at") or "")
                if cutoff and stamp:
                    try:
                        if time.mktime(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")) < cutoff:
                            continue
                    except ValueError:
                        pass
                rows.append({"name": row.get("name"), "system": row.get("system_name"), "distance": _num(row.get("distance")),
                             "ls": _num(row.get("distance_to_arrival")), "type": kind, "carrier": carrier,
                             "large": bool(row.get("has_large_pad")), "updated": stamp[:10],
                             "services": sorted(str(s.get("name") or "") for s in row.get("services") or () if isinstance(s, dict))[:20],
                             "dssa": False})
            if dssa:
                try:
                    data = spansh.http().get(DSSA_URL, timeout=20).json()
                except Exception:
                    data = []
                for row in data if isinstance(data, list) else ():
                    if not isinstance(row, dict) or "operational" not in str(row.get("status") or "operational").casefold():
                        continue
                    where = row.get("coords") if isinstance(row.get("coords"), dict) else {}
                    try:
                        xyz = [float(where[k]) for k in "xyz"]
                    except (KeyError, TypeError, ValueError):
                        continue
                    rows.append({"name": f"{row.get('name') or ''} ({row.get('callsign') or ''})".strip(),
                                 "system": row.get("lastSeenSystem") or row.get("designatedSystem") or "",
                                 "distance": round(math.dist(coords, xyz), 2), "ls": None, "type": "DSSA carrier",
                                 "carrier": True, "large": True, "updated": str(row.get("lastSeenDate") or "")[:10],
                                 "services": [str(s) for s in row.get("services") or ()][:20], "dssa": True})
            rows.sort(key=lambda row: (row["distance"] is None, row["distance"] or 0))
            return rows[:80]

        def done(result, error):
            if state.get("generation") != generation:
                return
            if error:
                state.update(status="failed", detail=error)
            else:
                state.update(status="ready", rows=result, detail=f"{len(result)} places near {centre['name']}.")
            state["rev"] += 1
            self._survey_bump()

        self._survey_task("dock", work, done)
        return True

    # -- FIRSTS -----------------------------------------------------------------------------------------
    def _survey_records(self):
        """Your records over every body you've scanned (outrider/records.py)."""
        items = self._survey_all_items()
        history = getattr(self, "travel_history", None)
        key = (len(items), len(history.rows) if history is not None else 0)
        cached = getattr(self, "_survey_records_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        bodies = []
        for item in items:
            raw = {"StarType": item.get("star_type"), "PlanetClass": item.get("planet_class"), "Landable": item.get("landable"),
                   "SurfaceTemperature": item.get("surface_temp"), "Radius": item.get("radius"),
                   "StellarMass": item.get("mass") if item.get("star_type") else None,
                   "MassEM": item.get("mass") if not item.get("star_type") else None,
                   "SurfaceGravity": item.get("surface_gravity"), "SurfacePressure": item.get("surface_pressure"),
                   "RotationPeriod": item.get("rotation_period"), "OrbitalPeriod": item.get("orbital_period"),
                   "DistanceFromArrivalLS": item.get("distance_to_arrival"), "Rings": item.get("rings") or [],
                   "ScanType": item.get("scan_type")}
            raw = {k: v for k, v in raw.items() if v is not None}
            bodies.append((item.get("system_address"), item.get("_system"), item.get("full_name") or item.get("name"),
                           item.get("scan_timestamp"), raw))
        jumps = []
        if history is not None:
            with history.lock:
                jumps = [(None, row[1], row[2], row[3], row[4], row[0]) for row in history.rows]
        rows = outrider_records.records(bodies, jumps)
        for row in rows:
            body = str(row.get("body") or "")
            system = str(row.get("system") or "")
            row["body_short"] = body[len(system):].strip() if system and body.casefold().startswith(system.casefold()) else body
        self._survey_records_cache = (key, rows)
        return rows

    def _firsts_payload(self):
        companion = getattr(self, "companion_state", None) or {}
        last_sale = _sale_time(companion.get("last_exploration_sale"))
        items = self._survey_all_items()
        unsold = {}
        for item in items:
            if item.get("was_discovered") is not False:
                continue
            stamp = str(item.get("scan_timestamp") or "")
            # Sold already: scanned before the last sale, or before scans were timed at all.
            if last_sale and (not stamp or stamp < last_sale):
                continue
            system = str(item.get("_system") or "")
            entry = unsold.setdefault(system.casefold(), {"system": system, "bodies": 0, "mapped": 0, "value": 0,
                                                         "first": stamp, "coords": None})
            entry["bodies"] += 1
            entry["mapped"] += 1 if item.get("dss_complete") else 0
            entry["value"] += int(item.get("dss_reward") or item.get("reward") or 0)
            entry["first"] = min(entry["first"] or stamp, stamp) if stamp else entry["first"]
        index = self._survey_coords_index()
        for entry in unsold.values():
            entry["coords"] = list(index.get(entry["system"].casefold()) or []) or None
        left_items = {}
        current = str(getattr(self, "current_sys", "") or "").casefold()
        for item in items:
            system = str(item.get("_system") or "")
            if system.casefold() == current:
                continue
            bio, done = int(item.get("bio_count") or 0), int(item.get("organic_complete_count") or 0)
            if bio > done:
                entry = left_items.setdefault(system.casefold(), {"system": system, "reasons": [], "coords": None, "source": "biology"})
                entry["reasons"].append(f"{item.get('name')}: {bio - done} of {bio} biology left")
        for entry in left_items.values():
            entry["coords"] = list(index.get(entry["system"].casefold()) or []) or None
        returns = []
        try:
            for row in self._reconcile_return_later().get("entries") or ():
                if isinstance(row, dict):
                    returns.append({"id": row.get("id"), "system": row.get("system"), "body": row.get("body"),
                                    "reasons": list(row.get("reasons") or [])[:5], "last_visited": row.get("last_visited"),
                                    "coords": row.get("coords"), "source": "return later"})
        except Exception:
            returns = []
        watch = self._html_profile_transient("_firsts_watch_state", {"status": "ready", "detail": "", "rows": []})
        return {"unsold": sorted(unsold.values(), key=lambda row: -row["value"]), "left": returns + sorted(left_items.values(), key=lambda r: r["system"]),
                "records": self._survey_records(), "watch": {k: watch.get(k) for k in ("status", "detail", "rows")},
                "uploads": bool(self.config.get("edsm_upload_enabled")), "last_sale": last_sale}

    def _firsts_watch(self):
        """Firsts watch: has anyone else's scan of your unsold first discoveries reached Spansh?"""
        watch = self._html_profile_transient("_firsts_watch_state", {"status": "ready", "detail": "", "rows": []})
        unsold = self._firsts_payload()["unsold"]
        names = [row["system"] for row in unsold][:200]
        if not names:
            watch.update(status="ready", detail="No unsold first discoveries.", rows=[])
            self._survey_bump()
            return True
        watch.update(status="working", detail=f"Asking Spansh about {len(names)} systems…")
        self._survey_bump()
        firsts = {row["system"].casefold(): row for row in unsold}

        def work():
            body = {"filters": {"name": {"value": names}}, "sort": [], "size": len(names), "page": 0}
            return spansh._call("POST", "systems/search", body=body, ttl=3600).get("results") or []

        def done(result, error):
            if error:
                watch.update(status="failed", detail=error)
            else:
                rows = []
                for row in result:
                    mine = firsts.get(str(row.get("name") or "").casefold())
                    if not mine:
                        continue
                    updated = str(row.get("updated_at") or "")
                    if updated and updated >= str(mine.get("first") or ""):
                        rows.append({"system": row.get("name"), "updated": updated[:16].replace("T", " "),
                                     "value": mine["value"], "bodies": mine["bodies"]})
                note = " Your own EDSM uploads reach Spansh too, so some may be yours." if self.config.get("edsm_upload_enabled") else ""
                watch.update(status="ready", rows=rows,
                             detail=(f"{len(rows)} of your unsold first-discovery systems are on Spansh since you found them: "
                                     "time to sell." if rows else "Nobody else has reported them yet.") + note)
            self._survey_bump()

        self._survey_task("watch", work, done)
        return True

    # -- CHECKLIST ----------------------------------------------------------------------------------------
    def _checklist_payload(self, region_name=""):
        from voidcompass.exploration import bio_requirements
        from voidcompass.exploration.codex_index import species_prefix
        names = list(region_names())
        coords = getattr(self, "current_coords", None)
        here = find_region(*coords) if coords else None
        region = here[0] if here else None
        if region_name:
            match = next((i for i, name in enumerate(names, start=1) if name.casefold() == str(region_name).casefold()), None)
            region = match or region
        region_label = names[region - 1] if region and 0 < region <= len(names) else "Unknown region"
        codex = getattr(self, "codex_index", None)
        rows_by_entry = {}
        if codex is not None:
            for row in codex.entries():
                rows_by_entry.setdefault(str(row[1]), []).append(row)
        variants = _bio_variants()
        rows = []
        for genus_key, species_map in bio_requirements.CATALOG.items():
            for species_key, species in species_map.items():
                prefix = species_prefix(species_key)
                info = variants.get(str(species.get("name") or "").casefold()) or {"species": species.get("name"), "colours": []}
                entry_ids = {entry for _colour, entry in info["colours"]}
                possible = None
                for rule in species.get("rulesets") or ():
                    verdict = bio_requirements._regions_allow(rule.get("regions") or (), region) if rule.get("regions") else True
                    if verdict:
                        possible = True
                        break
                    if verdict is False and possible is None:
                        possible = False
                logged_rows = [row for key, entries in rows_by_entry.items()
                               if key in entry_ids or key == species_key or (prefix and key.startswith(prefix + "_"))
                               for row in entries]
                here_rows = [row for row in logged_rows if row[2] == region]
                colours_here = {colour for colour, entry in info["colours"] if any(r[1] == entry and r[2] == region for r in logged_rows)}
                colours_any = {colour for colour, entry in info["colours"] if any(r[1] == entry for r in logged_rows)}
                rows.append({"species": species.get("name") or info["species"],
                    "genus": bio_requirements.family_for_species(species.get("name")) or genus_key,
                    "value": int(species.get("value") or 0), "possible": possible, "logged_here": bool(here_rows),
                    "regions": len({row[2] for row in logged_rows if row[2] is not None}),
                    "colours": [c for c, _e in info["colours"]], "colours_here": sorted(colours_here),
                    "colours_any": sorted(colours_any), "pictures": info.get("pictures") or []})
        rows.sort(key=lambda row: (row["genus"], row["species"]))
        possible_here = [row for row in rows if row["possible"] is not False]
        geology = []
        from voidcompass.outrider import codex_geo
        types = getattr(codex, "types", {}) if codex is not None else {}
        for entry_id, name in sorted(codex_geo.NAMES.items(), key=lambda kv: kv[1]):
            regions = types.get(str(entry_id)) or []
            geology.append({"name": name, "logged_here": region in regions, "regions": len([r for r in regions if r is not None])})
        return {"region": region_label, "regions": names, "rows": rows,
                "done_here": sum(1 for row in possible_here if row["logged_here"]), "possible_here": len(possible_here),
                "geology": geology, "codex": self._html_dashboard_codex_hunt(region_label)
                if hasattr(self, "_html_dashboard_codex_hunt") else {}}

    def _codex_list_payload(self, which, region_name=""):
        """5.7.8, after ED-Outrider: Geology (on the surface) or Phenomena (in
        space, at notable stellar phenomena) for a region: each entry, how many
        sites Canonn has reports of there, and whether your Codex has it there."""
        names = list(region_names())
        coords = getattr(self, "current_coords", None)
        here = find_region(*coords) if coords else None
        region = here[0] if here else None
        if region_name:
            match = next((i for i, name in enumerate(names, start=1) if name.casefold() == str(region_name).casefold()), None)
            region = match or region
        region_label = names[region - 1] if region and 0 < region <= len(names) else "Unknown region"
        codex = getattr(self, "codex_index", None)
        types = getattr(codex, "types", {}) if codex is not None else {}
        pictures = _codex_pictures()
        rows = []
        for entry in _geo_codex():
            if (entry.get("list") or ("geo" if entry.get("kind") == "Geology" else "phen")) != which:
                continue
            logged = [r for r in types.get(str(entry.get("id"))) or () if r is not None]
            sites = int((entry.get("regions") or {}).get(str(region), 0) or 0) if region else 0
            # A one-of-a-kind site is listed, but never counted as possible here.
            unique = bio_values.is_unique(entry.get("name"))
            rows.append({"id": entry.get("id"), "name": entry.get("name"), "group": entry.get("group") or entry.get("kind"),
                         "kind": entry.get("kind"), "sites": sites, "possible": sites > 0 and not unique, "unique": unique,
                         "logged_here": region in logged, "logged_any": bool(logged), "regions": len(set(logged)),
                         "pictures": pictures.get(str(entry.get("name") or "").casefold(), [])})
        rows.sort(key=lambda row: (row["group"] or "", row["name"] or ""))
        possible = [row for row in rows if row["possible"]]
        return {"list": which, "region": region_label, "regions": names, "rows": rows,
                "done_here": sum(1 for row in possible if row["logged_here"]), "possible_here": len(possible),
                "source": "Canonn (canonn.science): codex reports counted by region"}

    def _samples_payload(self):
        path = str(self.config.get("journal_path") or "")
        key = (get_active_profile(self.config), path, getattr(self, "cmdr_name", None), getattr(self, "cmdr_fid", None),
               journal_events.signature(path) if path else ())
        cached = getattr(self, "_survey_samples_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        events = journal_events.read(path, sample_runs.EVENTS, commander=getattr(self, "cmdr_name", None),
                                     fid=getattr(self, "cmdr_fid", None)) if path else []
        rows = sample_runs.runs(events)
        payload = {"rows": rows[:3000], "count": len(rows),
                "aboard": sum(1 for row in rows if row["state"] == "aboard"),
                "sold_value": sum(int(row.get("sold_for") or 0) for row in rows if row["state"] == "sold"),
                "lost": sum(1 for row in rows if row["state"] == "lost")}
        self._survey_samples_cache = (key, payload)
        return payload

    # -- the Journal Log ----------------------------------------------------------------------------------
    def _log_payload(self, query):
        from voidcompass.outrider import log as journal_log
        path = str(self.config.get("journal_path") or "")
        if not path:
            return {"rows": [], "next": None}
        cats = [c for c in str(query.get("cats") or "").split(",") if c in journal_log.CATEGORIES] or None
        try:
            days = max(1, min(3650, int(query.get("days") or 30)))
        except (TypeError, ValueError):
            days = 30
        answer = journal_log.read_log([path], days=days, before=query.get("before") or None, limit=200, cats=cats,
                                      q=str(query.get("q") or "") or None, noise=query.get("noise") == "1", budget_s=2.0)
        rows = []
        for row in answer.get("rows") or ():
            rows.append({k: row.get(k) for k in ("id", "ts", "event", "cat", "summary", "system", "body")}
                        | {"raw": row.get("raw") if query.get("raw") == "1" else None})
        return {"rows": rows, "next": answer.get("next"), "categories": list(journal_log.CATEGORIES)}

    def _log_raw(self, cursor):
        from voidcompass.outrider import log as journal_log
        path = str(self.config.get("journal_path") or "")
        try:
            name, index = journal_log.parse_cursor(cursor)
        except Exception:
            return None
        full = os.path.join(path, os.path.basename(str(name)))
        try:
            with open(full, encoding="utf-8", errors="ignore") as handle:
                for number, line in enumerate(handle):
                    if number == int(index):
                        return {"raw": json.loads(line)}
        except (OSError, ValueError):
            return None
        return None

    # -- a body's detail panel ------------------------------------------------------------------------------
    def _body_detail(self, system, body):
        system = _text(system)
        own = self._survey_own_items([system]).get(system.casefold(), [])
        item = next((row for row in own if str(row.get("name") or "").casefold() == str(body).casefold()), None)
        table = self._survey_system_payload(system)
        row = next((r for r in table.get("rows") or () if str(r.get("name")).casefold() == str(body).casefold()), None)
        if row is None and item is None:
            return None
        detail = {"system": system, "body": body, "row": row, "facts": {}}
        source = item or {}
        if item:
            detail["facts"] = {k: item.get(k) for k in ("planet_class", "star_type", "atmosphere", "volcanism", "surface_temp",
                                                        "gravity_g", "surface_pressure", "radius", "mass", "landable",
                                                        "terraformable", "distance_to_arrival", "reserve_level") if item.get(k) not in (None, "")}
            region = find_region(*self._survey_coords_of(system)) if self._survey_coords_of(system) else None
            try:
                predicted = bio_values.predict_genera(item.get("planet_class"), item.get("atmosphere_type"), item.get("surface_temp"),
                                                      item.get("gravity_g"), item.get("volcanism"),
                                                      (float(item["surface_pressure"]) / 101325.0) if item.get("surface_pressure") else None,
                                                      region[0] if region else None, self._survey_coords_of(system),
                                                      geo=bool(item.get("geo_count")), distance_ls=item.get("distance_to_arrival"))
            except Exception:
                predicted = []
            expected = [row.get("name") for row in predicted or () if row.get("name")]
            detail["expected"] = expected
            detail["not_expected"] = [genus for genus in BIO_TICKS if genus not in expected]
            # What your own runs found on worlds like this one.
            like = []
            for other in self._survey_all_items():
                if other is item or other.get("planet_class") != item.get("planet_class"):
                    continue
                if str(other.get("atmosphere_type") or "") != str(item.get("atmosphere_type") or ""):
                    continue
                for scan in (other.get("organic_scans") or {}).values():
                    if isinstance(scan, dict) and scan.get("is_complete") and scan.get("species"):
                        like.append(str(scan["species"]))
            counts = {}
            for name in like:
                counts[name] = counts.get(name, 0) + 1
            detail["similar"] = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
        return detail

    def _body_reported(self, system):
        """Species other commanders reported on this system's bodies (Spansh landmarks)."""
        state = self._html_profile_transient("_body_reported_state", {"system": "", "rows": [], "status": "ready"})
        if state["system"].casefold() == system.casefold() and state["status"] != "failed":
            return True
        state.update(system=system, rows=[], status="working")

        def done(result, error):
            if error:
                state.update(status="failed", rows=[])
            else:
                state.update(status="ready", rows=[row for row in result or () if str(row.get("system") or "").casefold() == system.casefold()])
            self._survey_bump()

        self._survey_task("reported", lambda: spansh.bio_landmarks(system, max_distance=1, size=40), done)
        return True

    # -- known sites from Canonn (asked when a body panel opens, never stored) -------------------------------
    def _canonn_sites(self, system, id64, body_id, body, radius_km=None):
        from voidcompass.outrider import canonn_sites
        state = self._html_profile_transient("_canonn_state", {"key": None, "status": "ready", "sites": [], "error": ""})
        key = (system.casefold(), str(body_id), str(body).casefold())
        if state["key"] == key:
            return True
        state.update(key=key, status="working", sites=[], error="")

        def work():
            sites = []
            if id64:
                reply = spansh.http().get(canonn_sites.SETTLEMENT_URL.format(int(id64)), timeout=45)
                rows = reply.json() if reply.status_code < 400 else []
                try:
                    sites += canonn_sites.guardian_sites(rows, int(body_id) if body_id not in (None, "") else None, radius_km)
                except (TypeError, ValueError):
                    pass
            reply = spansh.http().get(canonn_sites.POI_URL, params={"system": system, "odyssey": "Y"}, timeout=45)
            poi = reply.json() if reply.status_code < 400 else {}
            sites += canonn_sites.geology_sites(poi, body)
            return sites

        def done(result, error):
            if state.get("key") != key:
                return
            state.update(status="failed" if error else "ready", sites=result or [], error=error or "")
            self._survey_bump()

        self._survey_task("canonn", work, done)
        return True

    def _pin_site(self, payload):
        try:
            self.set_ground_target(float(payload.get("lat")), float(payload.get("lon")), system=_text(payload.get("system")),
                                   body=_text(payload.get("body")), label=_text(payload.get("label"), 80) or "Known site")
        except (TypeError, ValueError):
            return False
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    # -- the Local API (5.7.8) -------------------------------------------------------------------------------
    def api_explore_nearby(self):
        data = self._survey_nearby_payload()
        return {k: data.get(k) for k in ("status", "detail", "centre", "radius", "count", "not_visited", "rows")}

    def api_explore_system(self, name):
        data = self._survey_system_payload(name or str(getattr(self, "current_sys", "") or ""))
        return {k: data.get(k) for k in ("system", "id64", "region", "status", "meta", "rows")}

    def api_explore_route(self):
        return self._route_payload().get("route") or {"route": None}

    def api_journal_log(self, q, days):
        return self._log_payload({"q": q, "days": days})

    def api_earnings(self, period):
        return self._cmdr_earnings_payload(period)

    def api_history(self, period):
        return self._history_payload(period)

    # -- dispatch -------------------------------------------------------------------------------------------
    def _survey_more_command(self, operation, payload):
        if operation == "search_find":
            return self._search_find(payload.get("name"))
        if operation == "search_run":
            return self._search_run(payload)
        if operation == "search_clear":
            state = self._search_state()
            state.update(results=[], status="ready", detail="Cleared.", found=None, rev=state["rev"] + 1)
            self._survey_bump()
            return True
        if operation == "plot_route":
            return self._route_plot(payload)
        if operation == "plot_follow_waypoints":
            return self._route_follow_waypoints()
        if operation == "plot_clear":
            return self._route_clear()
        if operation == "plot_replot":
            route = self._route()
            if not route:
                return False
            return self._route_plot({"plotter": route["kind"] if route["kind"] != "waypoints" else "neutron",
                                     "from": str(getattr(self, "current_sys", "") or ""), "to": route["rows"][-1]["system"],
                                     **(route.get("options") or {}),
                                     "systems": [row["system"] for i, row in enumerate(route["rows"])
                                                 if i > (route.get("at") or 0) and i not in self._route_skipped(route)]
                                     if route["kind"] == "sweep" else None})
        if operation == "plot_skip":
            try:
                index = int(payload.get("index"))
            except (TypeError, ValueError):
                return False
            return self._route_skip(index, bool(payload.get("on", True)))
        if operation == "plot_copy_next":
            data = self._route_payload().get("route") or {}
            return bool(data.get("next")) and self._html_copy_text(data["next"], "next stop")
        if operation == "plot_dock":
            return self._dock_search(payload)
        if operation == "firsts_watch":
            return self._firsts_watch()
        if operation == "firsts_copy_trip":
            return False
        if operation.startswith("history_"):
            return self._history_command(operation, payload)
        if operation == "system_reported":
            self._body_reported(_text(payload.get("name")))
            if payload.get("body"):
                self._canonn_sites(_text(payload.get("name")), _text(payload.get("id64"), 30), payload.get("body_id"),
                                   _text(payload.get("body")), _num(payload.get("radius_km")))
            return True
        if operation == "system_pin_site":
            return self._pin_site(payload)
        return False

    def _survey_more_data(self, name, query):
        if name == "explore-search":
            return self._search_payload()
        if name == "explore-route":
            payload = self._route_payload()
            dock = self._dock_state()
            payload["dock"] = {k: dock.get(k) for k in ("status", "detail", "rows")}
            return payload
        if name == "explore-firsts":
            return self._firsts_payload()
        if name == "explore-checklist":
            if query.get("list") in ("geo", "phen"):
                return self._codex_list_payload(query.get("list"), query.get("region") or "")
            return self._checklist_payload(query.get("region") or "")
        if name == "explore-samples":
            return self._samples_payload()
        if name == "explore-log":
            if query.get("raw_of"):
                return self._log_raw(query.get("raw_of"))
            return self._log_payload(query)
        if name == "explore-body":
            detail = self._body_detail(query.get("system") or "", query.get("body") or "")
            reported = self._html_profile_transient("_body_reported_state", {"system": "", "rows": [], "status": "ready"})
            if detail is not None:
                detail["reported"] = reported["rows"] if reported["system"].casefold() == str(query.get("system") or "").casefold() else []
                detail["reported_status"] = reported["status"]
                canonn = self._html_profile_transient("_canonn_state", {"key": None, "status": "ready", "sites": [], "error": ""})
                detail["sites"] = canonn["sites"]
                detail["sites_status"] = canonn["status"]
            return detail
        more = getattr(self, "_records_data", None)
        return more(name, query) if callable(more) else None
