"""Expeditions (5.6.1): Mission Control, rebuilt as the Expeditions page.

An expedition is a named trip with a route of legs (stops, the destination
and the way home), objectives the journal ticks off, and everything the trip
asks of you along the way: the data you're carrying, the ship's health and
supplies, a streak since the last close call. Spansh plots each leg; the
waypoint route is still the one route the HUD and the minimap follow, so a
leg is sent there to fly it. At the end its own Void Wrapped and a replay.

The expedition manager (exploration/expedition_manager.py) keeps the record;
this builds the page from it and answers the page's commands.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import threading
import time

from voidcompass.core.platform_support import application_dir, open_path
from voidcompass.exploration import expedition_plan
from voidcompass.exploration.flight_recorder import epoch
from voidcompass.overlays import hud_pages

# The data at risk nudges at multiples of this, unless Settings says otherwise.
RISK_DEFAULT_CR = 100_000_000
EVENTS_SHOWN = 60
PHOTOS_SHOWN = 48
SELL_SERVICES = (("Universal Cartographics", "CARTOGRAPHICS"), ("Vista Genomics", "VISTA GENOMICS"))
# Part 5: places along the way.
PLACES_SHOWN = 300
FINDS_SHOWN = 12
NEARBY_SHOWN = 40
EXPEDITIONS_FOLDER = "Expeditions"
# A picture within this of a place's screenshot is that screenshot.
PICTURE_MATCH_S = 120


def _text(value, limit=200):
    return str(value or "").strip()[:limit]


def _same(left, right):
    return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def _short_body(name, system):
    """"Col 285 Sector AB-C d1-2 3 a" in its own system is just "3 A"."""
    name, system = str(name or ""), str(system or "")
    short = name[len(system):].strip() if system and name.casefold().startswith(system.casefold()) else name
    return (short or name).upper()


def _body_facts(item):
    """What a body is, from its scan: type, how far in, gravity, heat, air."""
    def number(key):
        try:
            return float(item.get(key))
        except (TypeError, ValueError):
            return None
    atmosphere = str(item.get("atmosphere_type") or item.get("atmosphere") or "").strip()
    return {"class": str(item.get("planet_class") or item.get("star_type") or ""), "ls": number("distance_to_arrival"),
            "gravity": number("gravity_g"), "temp": number("surface_temp"), "landable": bool(item.get("landable")),
            "atmosphere": "" if atmosphere.casefold() in {"", "none", "no atmosphere"} else atmosphere,
            "radius_km": round(number("radius") / 1000) if number("radius") else None,
            "rings": bool(item.get("rings")), "terraformable": bool(item.get("terraformable"))}


def _day(stamp):
    when = epoch(stamp)
    return datetime.fromtimestamp(when).strftime("%Y-%m-%d") if when else ""


class DashboardExpeditionMixin:
    # -- what the page shows -------------------------------------------------------------------------
    def _expedition_coords_of(self, name):
        """Where a system is, from what Void Compass already knows: your own
        arrivals, then the waypoint route."""
        key = str(name or "").strip().casefold()
        if not key:
            return None
        history = getattr(self, "travel_history", None)
        if history is not None:
            with history.lock:
                for row in reversed(history.rows):
                    if str(row[1]).casefold() == key:
                        return [row[2], row[3], row[4]]
        for row in getattr(getattr(self, "waypoint_manager", None), "waypoints", None) or ():
            if str(row.get("name") or "").casefold() == key and expedition_plan.position(row.get("coords")):
                return expedition_plan.position(row.get("coords"))
        return None

    def _expedition_intel(self):
        from voidcompass.exploration.exploration_intelligence import build_field_intelligence
        try:
            return build_field_intelligence(self)
        except Exception as exc:
            logging.debug("Expedition field facts skipped: %s", exc)
            return {}

    def _expedition_sessions(self, start, end):
        lengths = []
        for session in self._journey_sessions() if hasattr(self, "_journey_sessions") else ():
            began, ended = epoch(session.get("started")), epoch(session.get("ended"))
            if began and ended and start <= began <= end:
                lengths.append(ended - began)
        return lengths

    def _expedition_live(self, expedition):
        """The active trip, now: how far along, at what pace, what's at risk,
        the ship's supplies and the streak."""
        stats = expedition.get("stats") or {}
        legs = expedition.get("legs") or []
        start = stats.get("start_pos") or self._expedition_coords_of(expedition.get("start_system"))
        for leg in legs:
            if not leg.get("coords"):
                leg["coords"] = self._expedition_coords_of(leg.get("system"))
        here = self._galaxy_minimap_position() if hasattr(self, "_galaxy_minimap_position") else None
        progress = expedition_plan.path_progress(start, legs, here)
        began = epoch(expedition.get("started")) or time.time()
        measured = expedition_plan.pace(stats.get("jump_times"), stats.get("jump_ly"),
                                        self._expedition_sessions(began, time.time()))
        intel = self._expedition_intel()
        plan = intel.get("return_plan") or {}
        endurance = intel.get("endurance") or {}
        state = getattr(self, "companion_state", None) or {}
        loadout = state.get("loadout") or {}
        modules = " ".join(str(row.get("Item") or "").casefold() for row in loadout.get("Modules") or () if isinstance(row, dict))
        limpets = sum(int(row.get("Count") or 0) for row in getattr(self, "current_cargo_inventory", None) or ()
                      if str(row.get("Name") or "").casefold() == "drones")
        raw = (getattr(self, "engineer_materials", None) or {}).get("raw") or {}
        carrier = getattr(getattr(self, "carrier_tracker", None), "carrier_data", None) or {}
        previous = start
        for leg in legs:
            leg["fuel_runs"] = expedition_plan.fuel_runs((leg.get("plot") or {}).get("waypoints"))
            if leg.get("kind") == "carrier":
                plotted = leg.get("plot") or {}
                guess = expedition_plan.carrier_leg(expedition_plan.distance(previous, leg.get("coords")), carrier.get("fuel"))
                leg["carrier"] = {**(guess or {}), **({"tritium": plotted["tritium"], "jumps": plotted["total_jumps"]}
                                                     if plotted.get("tritium") is not None else {})}
            previous = leg.get("coords") or previous
        threshold = self._expedition_risk_threshold()
        value = int(plan.get("unsold_min_cr") or 0)
        return {
            "progress": progress,
            "pace": measured,
            "eta": expedition_plan.eta(progress.get("to_go_ly"), measured),
            "risk": {"value": value, "hull": plan.get("hull_percent"), "home_ly": plan.get("distance_ly"),
                     "home": plan.get("target_system"), "threshold": threshold,
                     "over": bool(threshold and value >= threshold)},
            "supplies": expedition_plan.supplies(endurance, limpets, "dronecontrol_repair" in modules, raw),
            "streak": expedition_plan.streak(stats),
            "here": getattr(self, "current_sys", "") or "",
            "surface": self._expedition_surface(legs),
            "guide": self._expedition_guide(legs),
        }

    def _expedition_surface(self, legs):
        """When the next stop is a planet, or a spot on one: where it is from
        here. In its system you're told the body; on it, which way to go."""
        upcoming = next((leg for leg in legs or () if not leg.get("reached")), None)
        if not upcoming or not upcoming.get("body"):
            return None
        info = {"system": upcoming.get("system"), "body": upcoming.get("body"), "title": upcoming.get("note") or upcoming.get("body"),
                "lat": upcoming.get("lat"), "lon": upcoming.get("lon"), "here": _same(getattr(self, "current_sys", ""), upcoming.get("system"))}
        on_body = bool(getattr(self, "on_planet", False)) and _same(getattr(self, "current_body_name", ""), upcoming.get("body"))
        info["on_body"] = info["here"] and on_body
        if info["on_body"] and upcoming.get("lat") is not None:
            info["target"] = expedition_plan.surface_target(
                getattr(self, "current_latitude", None), getattr(self, "current_longitude", None), getattr(self, "current_heading", None),
                upcoming["lat"], upcoming["lon"], getattr(self, "current_planet_radius", None) or upcoming.get("radius"))
            info["altitude_m"] = getattr(self, "current_altitude_m", None)
        return info

    def _expedition_guide(self, legs):
        """The next stop, step by step (5.6.5): jump to its system, fly to its
        body, land at the spot, arrive. With the body's facts from your scans
        and the system's bodies around it, so the one to land on is plain."""
        upcoming = next((leg for leg in legs or () if not leg.get("reached")), None)
        if not upcoming or not upcoming.get("system"):
            return None
        system, body = str(upcoming.get("system") or ""), str(upcoming.get("body") or "")
        here = _same(getattr(self, "current_sys", ""), system)
        near = here and bool(body) and _same(getattr(self, "current_body_name", ""), body)
        grounded = bool(getattr(self, "current_landed", False) or getattr(self, "current_in_srv", False)
                        or getattr(self, "current_on_foot", False))
        surface = self._expedition_surface(legs) or {}
        target = surface.get("target") or {}
        if not here:
            stage = "jump"
        elif not body:
            stage = "arrived"
        elif not near:
            stage = "fly"
        elif target.get("arrived") or (grounded and upcoming.get("lat") is None):
            stage = "arrived"
        else:
            stage = "ground" if grounded else "land"
        guide = {"stage": stage, "system": system, "body": body, "short": _short_body(body, system),
                 "title": str(upcoming.get("note") or body or system), "kind": str(upcoming.get("kind") or "stop"),
                 "lat": upcoming.get("lat"), "lon": upcoming.get("lon"), "jumps": None, "info": None, "bodies": []}
        if stage == "jump":
            route = [str((row or {}).get("StarSystem") or "") for row in getattr(self, "nav_route_entries", None) or ()]
            if route and _same(route[-1], system):
                at = next((index for index, name in enumerate(route) if _same(name, getattr(self, "current_sys", ""))), 0)
                guide["jumps"] = max(0, len(route) - 1 - at)
        if here:
            items = list((getattr(self, "scan_items_by_id", None) or {}).values())
            found = next((item for item in items if body and (_same(item.get("full_name"), body) or _same(item.get("name"), body))), None)
            if found:
                guide["info"] = _body_facts(found)
            # The system's bodies by distance, the one you want marked.
            rows = sorted((item for item in items if item.get("distance_to_arrival") is not None),
                          key=lambda item: float(item.get("distance_to_arrival") or 0))
            guide["bodies"] = [{"short": _short_body(item.get("full_name") or item.get("name"), system),
                                "ls": round(float(item.get("distance_to_arrival") or 0)), "star": bool(item.get("star_type")),
                                "class": str(item.get("planet_class") or item.get("star_type") or ""),
                                "landable": bool(item.get("landable")), "target": item is found} for item in rows][:16]
        return guide

    def _expedition_risk_threshold(self):
        try:
            return max(0, int((getattr(self, "config", None) or {}).get("expedition_risk_cr", RISK_DEFAULT_CR)))
        except (TypeError, ValueError):
            return RISK_DEFAULT_CR

    def _expedition_album(self, expedition):
        """Screenshots and postcards taken during the trip."""
        start = epoch(expedition.get("started")) or 0
        end = epoch(expedition.get("ended")) or time.time() + 60
        rows = []
        try:
            for row in self.screenshot_album().rows() if hasattr(self, "screenshot_album") else ():
                if start <= float(row.get("at") or 0) <= end:
                    rows.append({"id": row["id"], "kind": "screenshot", "title": row.get("title") or "", "at": row["at"]})
        except Exception as exc:
            logging.debug("Expedition screenshots skipped: %s", exc)
        for row in self._journey_postcards() if hasattr(self, "_journey_postcards") else ():
            if start <= float(row.get("at") or 0) <= end:
                rows.append({"id": row["id"], "kind": "postcard", "title": row.get("title") or "", "at": row["at"]})
        rows.sort(key=lambda row: row["at"])
        return rows[-PHOTOS_SHOWN:]

    # -- places (Part 5) -----------------------------------------------------------------------------
    def _expedition_pictures(self):
        """Every screenshot and postcard, briefly cached: places find theirs here."""
        cached = getattr(self, "_expedition_pictures_cache", None)
        if cached and time.monotonic() - cached[0] < 15:
            return cached[1]
        rows = []
        try:
            for row in self.screenshot_album().rows() if hasattr(self, "screenshot_album") else ():
                rows.append({"id": row["id"], "kind": "screenshot", "title": row.get("title") or "", "at": float(row.get("at") or 0),
                             "file": str(row.get("file") or ""), "system": row.get("system") or ""})
        except Exception as exc:
            logging.debug("Place pictures skipped: %s", exc)
        for row in self._journey_postcards() if hasattr(self, "_journey_postcards") else ():
            rows.append({"id": row["id"], "kind": "postcard", "title": row.get("title") or "", "at": float(row.get("at") or 0),
                         "file": str(row.get("file") or ""), "system": ""})
        self._expedition_pictures_cache = (time.monotonic(), rows)
        return rows

    @staticmethod
    def _place_pictures(place, pictures):
        """The album pictures of a place's screenshots: the same file, or
        taken within a minute or two in the same system."""
        out, seen = [], set()
        for shot in place.get("shots") or ():
            name = str(shot.get("file") or "").casefold()
            for photo in pictures:
                same_file = name and photo["file"].casefold() == name
                same_time = abs(photo["at"] - float(shot.get("at") or 0)) <= PICTURE_MATCH_S \
                    and (not photo["system"] or _same(photo["system"], place.get("system")))
                if (same_file or same_time) and photo["id"] not in seen:
                    seen.add(photo["id"])
                    out.append({"id": photo["id"], "kind": photo["kind"], "title": photo["title"]})
        return out[:6]

    def _expedition_places(self, row):
        from voidcompass.exploration.expedition_manager import PLACE_KINDS
        manager = getattr(self, "expedition_manager", None)
        if manager is None:
            return []
        on_route = {leg.get("place_id"): leg for leg in row.get("legs") or () if leg.get("place_id")}
        places = manager.bookmarks(row.get("id"))[:PLACES_SHOWN]
        pictures = self._expedition_pictures() if any(place.get("shots") for place in places) else []
        out = []
        for place in places:
            leg = on_route.get(place.get("id"))
            kind = place.get("kind") or "poi"
            out.append({
                "id": _text(place.get("id"), 16), "kind": kind, "kind_label": PLACE_KINDS.get(kind, "Place"),
                "title": _text(place.get("title"), 200), "system": _text(place.get("system"), 120), "body": _text(place.get("body"), 160),
                "lat": place.get("lat"), "lon": place.get("lon"), "notes": _text(place.get("notes"), 1000),
                "visited": place.get("status") == "visited", "visited_at": _text(place.get("visited"), 40),
                "found": bool(place.get("found")), "source": _text(place.get("source"), 80), "url": _text(place.get("url"), 300),
                "tags": [_text(tag, 40) for tag in place.get("tags") or ()][:6],
                "on_route": bool(leg), "reached": bool(leg and leg.get("reached")), "created": _text(place.get("created"), 40),
                "pictures": self._place_pictures(place, pictures),
            })
        return out

    def _gec_catalog(self):
        catalog = getattr(self, "_gec", None)
        if catalog is None:
            from voidcompass.services.gec_catalog import GecCatalog

            def changed():
                self._gec_near_cache = {}
                post = getattr(self, "_ui_post", None)
                publish = getattr(self, "_schedule_html_dashboard_publish", None)
                if callable(post) and callable(publish):
                    post(lambda: publish(immediate=True), key="gec-catalog")

            catalog = self._gec = GecCatalog(application_dir() / "cache" / "gec_catalog.json", on_change=changed)
        return catalog

    def _expedition_poi_range(self):
        try:
            return max(25, min(2000, int((getattr(self, "config", None) or {}).get("expedition_poi_range_ly", 150))))
        except (TypeError, ValueError):
            return 150

    def _expedition_nearby(self, row):
        """Points of interest from EDAstro's catalogue near the route's line,
        in the order you'd pass them; None when it's switched off."""
        from voidcompass.services.gec_catalog import CREDIT, CREDIT_URL
        if not (getattr(self, "config", None) or {}).get("expedition_gec_enabled", True):
            return None
        stats = row.get("stats") or {}
        start = stats.get("start_pos") or self._expedition_coords_of(row.get("start_system"))
        path = [start] + [leg.get("coords") for leg in row.get("legs") or ()]
        placed = [point for point in path if expedition_plan.position(point)]
        out = {"credit": CREDIT, "credit_url": CREDIT_URL, "range_ly": self._expedition_poi_range(), "rows": [], "waiting": False, "error": ""}
        if not placed:
            return out
        catalog = self._gec_catalog()
        points = catalog.rows()
        out["waiting"], out["error"] = not points and not catalog.error, catalog.error if not points else ""
        key = (row.get("id"), json.dumps(placed), out["range_ly"], len(points))
        cache = getattr(self, "_gec_near_cache", None)
        if cache is None:
            cache = self._gec_near_cache = {}
        if key not in cache:
            if len(cache) > 80:
                cache.clear()
            cache[key] = expedition_plan.near_route(points, placed, out["range_ly"], NEARBY_SHOWN)
        kept = {place.get("url") for place in self.expedition_manager.bookmarks(row.get("id")) if place.get("url")}
        out["rows"] = [{key_: poi.get(key_) for key_ in ("id", "name", "type", "region", "system", "summary", "rating", "url", "off_ly", "along_ly")}
                       | {"kept": poi.get("url") in kept} for poi in cache[key]]
        return out

    def _expedition_places_changed(self, expedition_id):
        manager = getattr(self, "expedition_manager", None)
        if manager is not None and hasattr(manager, "refresh_place_objectives"):
            manager.refresh_place_objectives(expedition_id)

    def _expedition_mark_here(self):
        """MARK THIS PLACE (the field bookmark hotkey, 5.6.1): where you are,
        kept as one of the expedition's places. On a planet, the very spot."""
        manager = getattr(self, "expedition_manager", None)
        system = str(getattr(self, "current_sys", "") or "").strip()
        feed = getattr(self, "add_event_feed_entry", None)
        if manager is None or not system or system in {"---", "Unknown"}:
            if callable(feed):
                feed("EXPEDITION", "A place can't be marked until the current system is known", severity="WARN")
            return None
        on_planet = bool(getattr(self, "on_planet", False))
        body = str(getattr(self, "current_body_name", "") or "").strip() if on_planet else ""
        lat = getattr(self, "current_latitude", None) if on_planet else None
        lon = getattr(self, "current_longitude", None) if on_planet else None
        active = manager.active()
        active_id = (active or {}).get("id") if (active or {}).get("status") == "active" else None
        place = manager.add_bookmark("surface" if lat is not None else "system", system=system, body=body, title=body or system,
                                     tags=["marked"], source="mark", position=self._galaxy_minimap_position()
                                     if hasattr(self, "_galaxy_minimap_position") else None, expedition_id=active_id,
                                     lat=lat, lon=lon, radius=getattr(self, "current_planet_radius", None) if on_planet else None, found=True)
        where = f"{body} · {float(lat):.4f}, {float(lon):.4f}" if lat is not None and lon is not None else system
        trip = f"on {active['name']}" if active_id else "with your bookmarks (no expedition is active)"
        if callable(feed):
            feed("EXPEDITION", f"Place marked: {where}", severity="INFO", copy_text=system)
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push("PLACE MARKED", f"{where}, kept {trip}", severity="success", duration_s=8)
        heartbeat = getattr(self, "heartbeat_hud", None)
        if active_id and heartbeat is not None and hasattr(heartbeat, "note"):
            try:
                heartbeat.note("expedition_marked", {"name": active.get("name") or "the expedition", "place": body or system})
            except Exception as exc:
                logging.debug("Watcher place note skipped: %s", exc)
        if active_id:
            self._expedition_places_changed(active_id)
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        return place

    # -- the Expedition overlay ----------------------------------------------------------------------
    def _expedition_overlay_refresh(self, force=False):
        """The overlay's model: at once when the expedition changes, else at
        most every few seconds (the data at risk, the hull)."""
        hud = getattr(self, "expedition_hud", None)
        manager = getattr(self, "expedition_manager", None)
        if hud is None or manager is None:
            return
        active = manager.active()
        active = active if (active or {}).get("status") == "active" else None
        key = ((active or {}).get("id"), (active or {}).get("updated"))
        now = time.monotonic()
        if not force and key == getattr(self, "_expedition_overlay_key", None) \
                and now - float(getattr(self, "_expedition_overlay_at", 0.0) or 0.0) < 3.0:
            return
        from voidcompass.overlays.expedition_hud import build_expedition_model
        self._expedition_overlay_key, self._expedition_overlay_at = key, now
        model = build_expedition_model(active, self._expedition_live(active)) if active else None
        self._expedition_overlay_model = model
        hud.update_expedition(model)

    def _expedition_overlay_surface(self):
        """Between journal events the overlay's compass follows Status.json."""
        hud = getattr(self, "expedition_hud", None)
        model = getattr(self, "_expedition_overlay_model", None)
        if hud is None or not model or not (model.get("surface") or model.get("guide")):
            return
        now = time.monotonic()
        if now - float(getattr(self, "_expedition_surface_at", 0.0) or 0.0) < 0.5:
            return
        self._expedition_surface_at = now
        active = self.expedition_manager.active() or {}
        legs = active.get("legs") or []
        surface = self._expedition_surface(legs)
        # The guide's step too (5.6.5): arriving, approaching, landing show at once.
        model = {**model, "guide": self._expedition_guide(legs),
                 "surface": {key: (surface or {}).get(key) for key in (model.get("surface") or surface or {})} if surface else None}
        self._expedition_overlay_model = model
        hud.update_expedition(model)

    def _expedition_on_position(self):
        """On a planet (Status.json): the places here you've reached, and a
        surface stop on the route ticked off. Checked every couple of seconds."""
        self._expedition_overlay_surface()
        if not getattr(self, "on_planet", False):
            return
        now = time.monotonic()
        if now - float(getattr(self, "_expedition_position_at", 0.0) or 0.0) < 2.0:
            return
        self._expedition_position_at = now
        manager = getattr(self, "expedition_manager", None)
        if manager is None or not hasattr(manager, "visit_near"):
            return
        result = manager.visit_near(getattr(self, "current_sys", ""), getattr(self, "current_body_name", ""),
                                    getattr(self, "current_latitude", None), getattr(self, "current_longitude", None),
                                    getattr(self, "current_planet_radius", None))
        reached = (result.get("legs") or []) + (result.get("places") or [])
        if not reached:
            return
        name = reached[0]
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push("YOU'RE THERE", name, severity="success", duration_s=8)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("EXPEDITION", f"Reached {name}", severity="INFO")
        active = manager.active()
        heartbeat = getattr(self, "heartbeat_hud", None)
        if active and heartbeat is not None and hasattr(heartbeat, "note"):
            try:
                heartbeat.note("expedition_place_reached", {"name": active.get("name") or "the expedition", "place": name})
            except Exception as exc:
                logging.debug("Watcher place note skipped: %s", exc)
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)

    def _expedition_save_file(self, expedition_id):
        """The route and the places as a CSV in the Expeditions folder."""
        manager = self.expedition_manager
        expedition = manager.get(expedition_id)
        if not expedition:
            return False
        rows = [{"system": expedition.get("start_system"), "kind": "start", "title": "Start",
                 "coords": (expedition.get("stats") or {}).get("start_pos")}]
        rows += [{"system": leg.get("system"), "body": leg.get("body"), "lat": leg.get("lat"), "lon": leg.get("lon"),
                  "kind": leg.get("kind"), "title": leg.get("note"), "coords": leg.get("coords")} for leg in expedition.get("legs") or ()]
        on_route = {leg.get("place_id") for leg in expedition.get("legs") or () if leg.get("place_id")}
        rows += [{"system": place.get("system"), "body": place.get("body"), "lat": place.get("lat"), "lon": place.get("lon"),
                  "kind": place.get("kind"), "title": place.get("title"), "note": place.get("notes"), "coords": place.get("position")}
                 for place in reversed(manager.bookmarks(expedition_id)) if place.get("id") not in on_route]
        folder = application_dir() / EXPEDITIONS_FOLDER
        name = re.sub(r'[<>:"/\\|?*]+', " ", str(expedition.get("name") or "Expedition")).strip()[:80] or "Expedition"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{name}.csv"
            # With a byte-order mark, so Excel reads the names as UTF-8.
            target.write_text(expedition_plan.places_csv(rows), encoding="utf-8-sig")
        except OSError as exc:
            self._expedition_job_state(f"Couldn't save it: {exc}", "warn")
            return False
        self._expedition_job_state(f"Saved {target.name} in the Expeditions folder ({len(rows):,} rows).")
        open_path(str(folder))
        return True

    def _expedition_days(self, expedition):
        """A line for each day of the trip, from its log, with your notes."""
        days = {}
        for event in expedition.get("events") or ():
            day = _day(event.get("timestamp"))
            if not day:
                continue
            entry = days.setdefault(day, {"day": day, "jumps": 0, "ly": 0.0, "systems": [], "highlights": []})
            if event.get("kind") == "JUMP":
                entry["jumps"] += 1
                try:
                    entry["ly"] += float(str(event.get("detail") or "0").split()[0])
                except ValueError:
                    pass
                system = str(event.get("title") or "").replace("Arrived in ", "")
                if system:
                    entry["systems"].append(system)
            elif event.get("kind") not in {"SESSION"}:
                entry["highlights"].append(str(event.get("title") or ""))
        notes = expedition.get("day_notes") or {}
        for day in notes:
            days.setdefault(day, {"day": day, "jumps": 0, "ly": 0.0, "systems": [], "highlights": []})
        out = []
        for day in sorted(days):
            entry = days[day]
            out.append({"day": day, "jumps": entry["jumps"], "ly": round(entry["ly"], 1),
                        "from": entry["systems"][0] if entry["systems"] else "", "to": entry["systems"][-1] if entry["systems"] else "",
                        "highlights": entry["highlights"][-6:], "note": notes.get(day, "")})
        return out

    def _expedition_view(self, row, live=False):
        stats = row.get("stats") or {}
        objectives = [{
            "id": _text(objective.get("id"), 20), "title": _text(objective.get("title"), 180), "kind": _text(objective.get("kind"), 40),
            "progress": int(objective.get("progress") or 0), "count": max(1, int(objective.get("count") or 1)),
            "complete": objective.get("status") == "complete", "automatic": bool(objective.get("automatic")),
        } for objective in row.get("objectives") or () if isinstance(objective, dict)]
        view = {
            "id": _text(row.get("id"), 20), "name": _text(row.get("name") or "Expedition", 140),
            "description": _text(row.get("description"), 400), "status": _text(row.get("status") or "paused", 20),
            # 5.6.4: your Hatchling, along for the trip.
            "pet": self._hatchling_trip_view(row.get("id")) if hasattr(self, "_hatchling_trip_view") else None,
            "started": _text(row.get("started"), 40), "ended": _text(row.get("ended"), 40),
            "start_system": _text(row.get("start_system"), 120), "destination": _text(row.get("destination"), 120),
            "return_system": _text(row.get("return_system"), 120), "ironman": bool(row.get("ironman")),
            # An example expedition (5.6.1): where its route came from.
            "example": _text(row.get("example"), 40), "source_url": _text(row.get("source_url"), 300),
            "credit": _text(row.get("credit"), 200),
            "legs": [{key: leg.get(key) for key in ("id", "system", "kind", "coords", "note", "reached", "body", "lat", "lon", "place_id")}
                     | {"plot": {key: (leg.get("plot") or {}).get(key) for key in ("kind", "total_jumps", "range", "tritium", "at")}
                        if leg.get("plot") else None,
                        "stops": len((leg.get("plot") or {}).get("waypoints") or ())}
                     for leg in row.get("legs") or ()],
            "objectives": objectives,
            "stats": {"jumps": int(stats.get("jumps") or 0), "ly": round(float(stats.get("distance_ly") or 0), 1),
                      "systems": len(stats.get("systems") or ()), "regions": int(stats.get("regions") or 0),
                      "fss": int(stats.get("fss_scans") or 0), "dss": int(stats.get("dss_maps") or 0),
                      "bio": int(stats.get("bio_analyses") or 0), "codex": int(stats.get("codex") or 0),
                      "codex_new": int(stats.get("codex_new") or 0), "firsts": int(stats.get("first_discoveries") or 0),
                      "footfalls": int(stats.get("first_footfalls") or 0), "valuable": int(stats.get("valuable_worlds") or 0),
                      "screenshots": int(stats.get("screenshots") or 0), "sessions": int(stats.get("sessions") or 0),
                      "furthest": round(float(stats.get("furthest_ly") or 0), 1)},
            "streak": expedition_plan.streak(stats),
            "events": [{"at": _text(event.get("timestamp"), 30), "kind": _text(event.get("kind"), 20),
                        "title": _text(event.get("title"), 200), "detail": _text(event.get("detail"), 200)}
                       for event in (row.get("events") or [])[-EVENTS_SHOWN:]][::-1],
            "days": self._expedition_days(row),
            "album": self._expedition_album(row),
            "places": self._expedition_places(row),
            "finds": [{key: find.get(key) for key in ("id", "kind", "system", "body", "title", "detail", "at")}
                      for find in reversed(row.get("finds") or []) if find.get("state") == "new"][:FINDS_SHOWN],
            "nearby": self._expedition_nearby(row),
        }
        if live:
            # Fuel runs and carrier needs come with the plot; the live block works them out.
            facts = self._expedition_live(row)
            view["live"] = facts
            for leg_view, leg in zip(view["legs"], row.get("legs") or ()):
                leg_view["coords"] = leg.get("coords")
                leg_view["fuel_runs"] = leg.get("fuel_runs") or []
                leg_view["carrier"] = leg.get("carrier")
        return view

    def _html_expedition_workspace(self):
        manager = getattr(self, "expedition_manager", None)
        rows = manager.expeditions() if manager is not None else []
        active = manager.active() if manager is not None else None
        active_id = (active or {}).get("id") if (active or {}).get("status") == "active" else ""
        templates = []
        try:
            from voidcompass.exploration.expedition_manager import OBJECTIVE_KINDS, OBJECTIVE_TEMPLATES
            templates = [{"key": key, "name": value["name"], "tier": value.get("tier") or "", "description": value.get("description") or ""}
                         for key, value in OBJECTIVE_TEMPLATES.items()]
            kinds = [[key, label] for key, label in OBJECTIVE_KINDS.items()]
        except Exception:
            kinds = []
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        self._expedition_overlay_refresh()
        return {
            "active_id": active_id or "",
            "expeditions": [self._expedition_view(row, live=row.get("id") == active_id) for row in rows[:60]],
            "templates": templates, "kinds": kinds,
            "jump_range": round(float(loadout.get("MaxJumpRange") or 0), 1) or None,
            "here": getattr(self, "current_sys", "") or "",
            "job": dict(getattr(self, "_expedition_job", None) or {}),
            "sell": list(getattr(self, "_expedition_sell", None) or []),
            "risk_threshold": self._expedition_risk_threshold(),
            "examples": self._expedition_examples(),
            # The waypoint route and the neutron plotter (Explore's ROUTE tab
            # until 5.6.1): the one route the HUD and the minimap follow.
            "route_tools": self._html_route_tools() if hasattr(self, "_html_route_tools") else {},
            # A place the Watcher has asked to be taken (5.6.1).
            "pilgrimage": self._expedition_pilgrimage(),
        }

    @staticmethod
    def _expedition_examples():
        from voidcompass.exploration.expedition_examples import EXAMPLES
        rows = [{"key": key, "name": value["name"], "stops": len(value["stops"]), "description": value["description"]}
                for key, value in EXAMPLES.items()]
        return sorted(rows, key=lambda row: row["name"].removeprefix("A ").casefold())

    def _expedition_pilgrimage(self):
        from voidcompass.overlays import watcher_places
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        wanted = ((getattr(mind, "memory", None) or {}).get("pilgrimage") or {}) if mind is not None else {}
        kind = wanted.get("kind")
        if not kind or wanted.get("reached"):
            return None
        return {"kind": kind, "words": watcher_places.words(kind), "how": watcher_places.how(kind),
                "system": (mind.memory.get("first_system") if kind == "first_place" else "") or ""}

    # -- the page's commands -------------------------------------------------------------------------
    def _expedition_job_state(self, text, tone="info", busy=False):
        previous = getattr(self, "_expedition_job", None) or {}
        self._expedition_job = {"text": _text(text, 300), "tone": tone, "busy": bool(busy), "seq": int(previous.get("seq") or 0) + 1}
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)

    def _expedition_worker(self, name, work, done):
        """Spansh and EDSM are slow: off the UI thread, then back on it."""
        def run():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, exc
            post = getattr(self, "_ui_post", None)
            if callable(post):
                post(lambda: done(result, error), key=f"expedition-{name}")
            else:
                done(result, error)
        threading.Thread(target=run, name=f"Expedition-{name}", daemon=True).start()

    def _handle_expedition_command(self, operation, payload):
        """The Expeditions page's own commands; None for the older ones the
        workspace dispatcher still answers (create, status, objectives)."""
        manager = getattr(self, "expedition_manager", None)
        if manager is None:
            return False
        expedition_id = _text(payload.get("expedition_id"), 20)
        ending = (operation == "status" and payload.get("status") in {"completed", "failed"}) or (
            operation == "delete" and payload.get("confirmed"))
        if ending:
            # 5.6.4: a finished or cleared trip takes its route with it (the
            # minimap and the HUD kept flying it).
            expedition = manager.get(expedition_id) or {}
            was_active = expedition.get("status") == "active"
            changed = manager.set_status(expedition_id, payload["status"]) if operation == "status" else manager.delete(expedition_id)
            if changed:
                self._expedition_clear_route(expedition.get("name") or "", was_active)
                # The Hatchling was along for it (5.6.4): finished together, a badge.
                if hasattr(self, "_hatchling_trip_ended"):
                    self._hatchling_trip_ended(expedition_id, operation == "status" and payload["status"] == "completed")
            return bool(changed)
        if operation == "create":
            here = getattr(self, "current_sys", "") or ""
            created = manager.create(_text(payload.get("name"), 100), description=_text(payload.get("description"), 1000),
                                     start_system=_text(payload.get("start_system") or here, 120),
                                     destination=_text(payload.get("destination"), 120),
                                     return_system=_text(payload.get("return_system"), 120),
                                     start_pos=self._galaxy_minimap_position() if hasattr(self, "_galaxy_minimap_position") else None)
            if created:
                self._expedition_locate(created["id"])
            return bool(created)
        if operation == "rename":
            description = payload.get("description")
            return manager.rename(expedition_id, _text(payload.get("name"), 100),
                                  description=None if description is None else _text(description, 1000))
        if operation == "add_leg":
            system = _text(payload.get("system"), 120)
            kind = payload.get("kind") if payload.get("kind") in expedition_plan.LEG_KINDS else "stop"
            leg = manager.add_leg(expedition_id, system, kind, coords=self._expedition_coords_of(system),
                                  note=_text(payload.get("note"), 400))
            if leg and not self._expedition_coords_of(system):
                self._expedition_locate(expedition_id)
            return bool(leg)
        if operation == "remove_leg":
            return manager.remove_leg(expedition_id, _text(payload.get("leg_id"), 16))
        if operation == "move_leg":
            return manager.move_leg(expedition_id, _text(payload.get("leg_id"), 16), int(payload.get("step") or 1))
        if operation == "locate":
            return self._expedition_locate(expedition_id)
        if operation == "plot_leg":
            return self._expedition_plot(expedition_id, _text(payload.get("leg_id"), 16), payload)
        if operation == "use_route":
            return self._expedition_use_route(expedition_id, _text(payload.get("leg_id"), 16))
        if operation == "import":
            return self._expedition_import(expedition_id, str(payload.get("text") or "")[:200_000])
        if operation == "add_pilgrimage":
            wanted = self._expedition_pilgrimage()
            if not wanted:
                return False
            return bool(manager.add_objective(expedition_id, "pilgrimage", target=wanted["kind"], system=wanted["system"],
                                              notes=f"The Watcher asked: {wanted['words']}"))
        if operation == "ironman":
            return manager.set_ironman(expedition_id, bool(payload.get("on")))
        if operation == "day_note":
            return manager.set_day_note(expedition_id, _text(payload.get("day"), 10), str(payload.get("text") or "")[:2000])
        if operation == "template":
            return bool(manager.apply_objective_template(expedition_id, _text(payload.get("template"), 60)))
        if operation == "go_home":
            return self._expedition_go_home(expedition_id)
        if operation == "sell_now":
            return self._expedition_find_sellers()
        if operation == "route_to":
            return self._expedition_route_to(_text(payload.get("system"), 120), "Expedition: to sell")
        if operation == "replay":
            opener = getattr(self, "_recorder_open", None)
            return bool(opener(f"expedition:{expedition_id}")) if callable(opener) else False
        if operation == "wrapped":
            return self._expedition_open_wrapped(expedition_id)
        if operation == "export":
            payload_out = manager.export_payload(expedition_id)
            copy = getattr(self, "_html_copy_text", None)
            return bool(payload_out and callable(copy) and copy(json.dumps(payload_out, ensure_ascii=False)))
        if operation == "import_file":
            try:
                created = manager.import_payload(json.loads(str(payload.get("text") or "")))
            except (ValueError, TypeError) as exc:
                self._expedition_job_state(f"That isn't a Void Compass expedition: {exc}", "warn")
                return False
            return bool(created)
        # Part 5: places along the way.
        place_id = _text(payload.get("place_id"), 16)
        if operation == "add_place":
            system = _text(payload.get("system") or getattr(self, "current_sys", ""), 120)
            if not system:
                return False
            place = manager.add_bookmark(payload.get("kind") or "", system, _text(payload.get("body"), 160), _text(payload.get("title"), 200),
                                         notes=_text(payload.get("notes"), 1000), position=self._expedition_coords_of(system),
                                         source="page", expedition_id=expedition_id or None, lat=payload.get("lat"), lon=payload.get("lon"))
            if place and payload.get("route"):
                manager.place_to_route(expedition_id, place["id"])
            self._expedition_places_changed(expedition_id)
            return bool(place)
        if operation == "mark_here":
            return bool(self._expedition_mark_here())
        if operation == "guide_place":
            # The planet compass (Planetary › ON THE GROUND, the cockpit popup) points there.
            place = next((row for row in manager.bookmarks() if row.get("id") == place_id), None)
            if not place or place.get("lat") is None or not hasattr(self, "set_ground_target"):
                return False
            try:
                self.set_ground_target(place["lat"], place["lon"], system=place.get("system") or "", body=place.get("body") or "",
                                       label=place.get("title") or "")
            except ValueError:
                return False
            self._expedition_job_state(f"The planet compass points to {place.get('title') or place.get('body')}.")
            return True
        if operation == "place_to_route":
            return bool(manager.place_to_route(expedition_id, place_id, next_stop=bool(payload.get("next"))))
        if operation == "remove_place":
            done = manager.remove_bookmark(place_id)
            self._expedition_places_changed(expedition_id)
            return done
        if operation == "place_visited":
            done = manager.update_bookmark(place_id, status="visited" if payload.get("on") else "pending")
            self._expedition_places_changed(expedition_id)
            return done
        if operation == "place_note":
            fields = {key: str(payload.get(key) or "")[:1000] for key in ("notes", "title") if key in payload}
            return manager.update_bookmark(place_id, **fields) if fields else False
        if operation in {"keep_find", "dismiss_find"}:
            done = manager.keep_find(expedition_id, _text(payload.get("find_id"), 16), dismiss=operation == "dismiss_find")
            self._expedition_places_changed(expedition_id)
            return bool(done)
        if operation == "add_poi":
            try:
                wanted = int(payload.get("poi_id") or 0)
            except (TypeError, ValueError):
                return False
            poi = next((row for row in self._gec_catalog().rows(refresh=False) if row.get("id") == wanted), None)
            if not poi:
                return False
            place = manager.add_bookmark("poi", poi["system"], "", poi["name"], notes=poi.get("summary") or "", tags=[poi.get("type") or ""],
                                         position=poi.get("coords"), source=f"edastro:{poi['id']}", expedition_id=expedition_id or None,
                                         url=poi.get("url") or "")
            if place and payload.get("route"):
                manager.place_to_route(expedition_id, place["id"])
            self._expedition_places_changed(expedition_id)
            return bool(place)
        if operation == "open_link":
            url = _text(payload.get("url"), 300)
            known = url.startswith("https://edastro.com/") or any(place.get("url") == url for place in manager.bookmarks())                 or any(row.get("source_url") == url for row in manager.expeditions())
            if not url.startswith("https://") or not known:
                return False
            import webbrowser
            webbrowser.open_new_tab(url)
            return True
        if operation == "add_example":
            added = manager.add_example(_text(payload.get("example"), 40))
            if added:
                self._expedition_job_state(f"{added['name']} added, paused. RESUME it to fly it; FIND WHERE THEY ARE isn't needed, every stop is placed.")
            return bool(added)
        if operation == "save_file":
            return self._expedition_save_file(expedition_id)
        if operation == "open_folder":
            folder = application_dir() / EXPEDITIONS_FOLDER
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError:
                return False
            return bool(open_path(str(folder)))
        return None

    def _expedition_locate(self, expedition_id):
        """Find where each leg is: your own arrivals first, then EDSM."""
        manager = self.expedition_manager
        expedition = manager.get(expedition_id) or {}
        missing = []
        for leg in expedition.get("legs") or ():
            if leg.get("coords"):
                continue
            known = self._expedition_coords_of(leg.get("system"))
            if known:
                manager.update_leg(expedition_id, leg["id"], coords=known)
            else:
                missing.append(leg)
        edsm = getattr(self, "edsm", None)
        if not missing or edsm is None or not hasattr(edsm, "fetch_system_coords"):
            return True
        self._expedition_job_state(f"Looking up {len(missing)} system{'s' if len(missing) != 1 else ''} on EDSM…", busy=True)
        remaining = {"count": len(missing), "unknown": []}

        def found(leg, coords):
            def apply():
                if coords:
                    manager.update_leg(expedition_id, leg["id"], coords=[coords.get("x"), coords.get("y"), coords.get("z")])
                else:
                    remaining["unknown"].append(leg.get("system"))
                remaining["count"] -= 1
                if remaining["count"] <= 0:
                    unknown = remaining["unknown"]
                    self._expedition_job_state(f"Couldn't find {', '.join(unknown[:4])} on EDSM: check the spelling" if unknown
                                               else "Every leg is on the map.", "warn" if unknown else "info")
            post = getattr(self, "_ui_post", None)
            post(apply, key=f"expedition-locate-{leg['id']}") if callable(post) else apply()

        for leg in missing:
            edsm.fetch_system_coords(leg.get("system"), lambda _name, coords, leg=leg: found(leg, coords))
        return True

    def _expedition_plot(self, expedition_id, leg_id, payload):
        """Plot one leg on Spansh: a neutron route, or a carrier route."""
        from voidcompass.services.spansh import fleet_carrier_route, neutron_route
        manager = self.expedition_manager
        expedition = manager.get(expedition_id) or {}
        legs = expedition.get("legs") or []
        index = next((position for position, leg in enumerate(legs) if leg.get("id") == leg_id), None)
        if index is None:
            return False
        leg = legs[index]
        source = legs[index - 1]["system"] if index else (getattr(self, "current_sys", "") or expedition.get("start_system"))
        if not leg.get("reached") and index == next((position for position, row in enumerate(legs) if not row.get("reached")), None):
            source = getattr(self, "current_sys", "") or source  # the next leg starts where you are
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        try:
            jump_range = float(payload.get("range") or loadout.get("MaxJumpRange") or 0)
        except (TypeError, ValueError):
            jump_range = 0.0
        carrier = leg.get("kind") == "carrier"
        if not source or (not carrier and jump_range <= 0):
            self._expedition_job_state("Plotting needs your jump range: it comes with your ship's loadout.", "warn")
            return False
        self._expedition_job_state(f"Spansh is plotting {source} to {leg['system']}…", busy=True)

        def work():
            if carrier:
                result = fleet_carrier_route(source, [leg["system"]])
                return {"kind": "carrier", "total_jumps": max(0, len(result["jumps"]) - 1), "tritium": result.get("fuel_required_t"),
                        "waypoints": [{"system": row["system"], "neutron": False, "jumps": 1} for row in result["jumps"][1:]]}
            result = neutron_route(source, leg["system"], jump_range, int(payload.get("efficiency") or 60))
            return {"kind": "neutron", "range": jump_range, "total_jumps": result.get("total_jumps"),
                    "waypoints": result.get("waypoints") or []}

        def done(result, error):
            if error is not None:
                self._expedition_job_state(f"Spansh couldn't plot it: {error}", "warn")
                return
            result["at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            manager.update_leg(expedition_id, leg_id, plot=result)
            runs = expedition_plan.fuel_runs(result.get("waypoints"))
            extra = f" · {len(runs)} stretch{'es' if len(runs) != 1 else ''} with no star to scoop" if runs else ""
            self._expedition_job_state(f"{leg['system']}: {int(result.get('total_jumps') or 0):,} jumps plotted{extra}.",
                                       "warn" if runs else "info")

        self._expedition_worker(f"plot-{leg_id}", work, done)
        return True

    def _expedition_set_waypoints(self, rows, note):
        manager = getattr(self, "waypoint_manager", None)
        if manager is None or not rows:
            return False
        manager.waypoints = [{"name": row["system"], "coords": row.get("coords"), "note": note,
                              "neutron": bool(row.get("neutron")), "jumps": row.get("jumps")} for row in rows if row.get("system")]
        manager.save()
        for name in ("update_hud", "_update_galaxy_minimap_safely"):
            action = getattr(self, name, None)
            if callable(action):
                action()
        return True

    def _expedition_clear_route(self, name, was_active):
        """Take an expedition's waypoints off the route: all of them (its
        legs, the way home, a trip to sell) when it was the one being flown,
        else only its own legs."""
        manager = getattr(self, "waypoint_manager", None)
        if manager is None:
            return False
        def ours(row):
            note = str((row or {}).get("note") or "")
            return note.startswith("Expedition: ") if was_active else note == f"Expedition: {name}"
        kept = [row for row in list(manager.waypoints or []) if not ours(row)]
        if len(kept) == len(manager.waypoints or []):
            return False
        manager.waypoints = kept
        manager.save()
        for refresh in ("update_hud", "_update_galaxy_minimap_safely"):
            action = getattr(self, refresh, None)
            if callable(action):
                action()
        return True

    def _expedition_use_route(self, expedition_id, leg_id=""):
        """Fly a leg: its plotted stops become the waypoint route (the HUD,
        the minimap and COPY NEXT follow it). Without a plot, the legs left."""
        expedition = self.expedition_manager.get(expedition_id) or {}
        legs = expedition.get("legs") or []
        leg = next((row for row in legs if row.get("id") == leg_id), None) or next((row for row in legs if not row.get("reached")), None)
        if leg is None:
            return False
        plotted = (leg.get("plot") or {}).get("waypoints")
        if plotted:
            rows = plotted
        else:
            rows = [{"system": row["system"], "coords": row.get("coords")} for row in legs[legs.index(leg):] if not row.get("reached")]
        done = self._expedition_set_waypoints(rows, f"Expedition: {expedition.get('name') or 'leg'}")
        if done:
            self._expedition_job_state(f"The route is now {leg['system']}: {len(rows):,} waypoint{'s' if len(rows) != 1 else ''}.")
        return done

    def _expedition_route_to(self, system, note):
        """Plot from here to one system and make it the waypoint route."""
        from voidcompass.services.spansh import neutron_route
        here = getattr(self, "current_sys", "") or ""
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        jump_range = float(loadout.get("MaxJumpRange") or 0)
        if not system:
            return False
        if not here or jump_range <= 0:
            return self._expedition_set_waypoints([{"system": system, "coords": self._expedition_coords_of(system)}], note)
        self._expedition_job_state(f"Spansh is plotting {here} to {system}…", busy=True)

        def done(result, error):
            if error is not None:
                self._expedition_set_waypoints([{"system": system, "coords": self._expedition_coords_of(system)}], note)
                self._expedition_job_state(f"Spansh couldn't plot it ({error}); {system} is the next waypoint instead.", "warn")
                return
            self._expedition_set_waypoints(result.get("waypoints") or [], note)
            self._expedition_job_state(f"Route to {system}: {int(result.get('total_jumps') or 0):,} jumps.")

        self._expedition_worker("route", lambda: neutron_route(here, system, jump_range), done)
        return True

    def _expedition_go_home(self, expedition_id):
        expedition = self.expedition_manager.get(expedition_id) or {}
        home = next((leg["system"] for leg in expedition.get("legs") or () if leg.get("kind") == "home"), None) \
            or expedition.get("return_system") or expedition.get("start_system")
        if not home:
            self._expedition_job_state("Set the way home first: add a HOME leg.", "warn")
            return False
        return self._expedition_route_to(home, f"Expedition: home to {home}")

    def _expedition_find_sellers(self):
        """The nearest Universal Cartographics and Vista Genomics."""
        from voidcompass.services.spansh import service_stations
        here = getattr(self, "current_sys", "") or ""
        coords = self._galaxy_minimap_position() if hasattr(self, "_galaxy_minimap_position") else None
        if not here and not coords:
            return False
        self._expedition_job_state("Looking for the nearest places to sell…", busy=True)

        def work():
            found = []
            for service, label in SELL_SERVICES:
                for row in service_stations(here, service, size=3, coords=coords)[:3]:
                    found.append({**row, "service": label})
            return found

        def done(result, error):
            if error is not None:
                self._expedition_job_state(f"Spansh couldn't search: {error}", "warn")
                return
            self._expedition_sell = result or []
            self._expedition_job_state(f"{len(result or [])} places to sell found." if result else "Nowhere to sell found nearby.")

        self._expedition_worker("sell", work, done)
        return True

    def _expedition_import(self, expedition_id, text):
        """A community expedition's waypoints: a CSV, a pasted list or a
        Spansh link. What's found becomes the legs; unknown names are said."""
        from voidcompass.services.spansh import plotted_systems
        manager = self.expedition_manager
        parsed = expedition_plan.parse_import(text)
        if parsed.get("payload"):
            try:
                created = manager.import_payload(parsed["payload"])
            except (ValueError, TypeError) as exc:
                self._expedition_job_state(f"That expedition file couldn't be read: {exc}", "warn")
                return False
            self._expedition_job_state(f"Added {created.get('name') or 'the expedition'} to your expeditions, paused.")
            return True
        if parsed["spansh_job"]:
            self._expedition_job_state("Reading the Spansh route…", busy=True)

            def done(result, error):
                if error is not None:
                    self._expedition_job_state(f"Couldn't read it from Spansh: {error}", "warn")
                    return
                count = manager.replace_legs(expedition_id, [{"name": row["name"], "coords": row.get("coords")} for row in result])
                self._expedition_job_state(f"Imported {count:,} stops from Spansh." if count else "Nothing to import.")

            self._expedition_worker("import", lambda: plotted_systems(parsed["spansh_job"]), done)
            return True
        systems = parsed["systems"]
        if not systems:
            self._expedition_job_state("No systems found in that: one per line, a CSV with a System column, or a Spansh link.", "warn")
            return False
        for row in systems:
            row["coords"] = row.get("coords") or self._expedition_coords_of(row["name"])
        count = manager.replace_legs(expedition_id, systems)
        places = [row for row in systems if row.get("body") or row.get("lat") is not None or row.get("title")]
        for row in systems:
            if not row.get("body") and row.get("lat") is None:
                manager.add_objective(expedition_id, "reach_system", target=row["name"])
        if places and not any(objective.get("kind") == "places_all" for objective in (manager.get(expedition_id) or {}).get("objectives") or ()):
            manager.add_objective(expedition_id, "places_all")
        self._expedition_places_changed(expedition_id)
        extra = f", {len(places):,} of them places (landing sites and points of interest)" if places else ", each a Reach system objective"
        self._expedition_job_state(f"Imported {count:,} stops{extra}. Checking where they are…")
        self._expedition_locate(expedition_id)
        return bool(count)

    def _expedition_open_wrapped(self, expedition_id):
        previous = getattr(self, "_wrapped_trip_request", None) or {"seq": 0}
        self._wrapped_trip_request = {"seq": int(previous.get("seq") or 0) + 1, "id": expedition_id}
        request = getattr(self, "_request_html_dashboard_page", None)
        return bool(request("wrapped")) if callable(request) else True

    # -- milestones and nudges -----------------------------------------------------------------------
    def _expedition_after_event(self, result, event):
        """After a live journal event: say the milestones, and nudge when the
        data aboard passes the line you set."""
        manager = getattr(self, "expedition_manager", None)
        if manager is None:
            return
        self._expedition_overlay_refresh()
        # The expedition the event belonged to: an Ironman death has just
        # ended it, so it may no longer be the active one.
        active = manager.get((result or {}).get("expedition_id")) if (result or {}).get("expedition_id") else manager.active()
        if not active or active.get("status") not in {"active", "failed"}:
            return
        heartbeat = getattr(self, "heartbeat_hud", None)

        def say(topic, fields):
            if heartbeat is not None and hasattr(heartbeat, "note"):
                try:
                    heartbeat.note(topic, {"name": active.get("name") or "the expedition", **fields})
                except Exception as exc:
                    logging.debug("Watcher expedition note skipped: %s", exc)

        for milestone in (result or {}).get("milestones") or ():
            if milestone == "set_out" and manager.note_milestone(active["id"], "set_out"):
                say("expedition_set_out", {})
            elif milestone.startswith("region_"):
                from voidcompass.exploration.galactic_regions import region_names
                names, index = region_names(), int(milestone.split("_")[1])
                say("expedition_region", {"region": names[index - 1] if 0 < index <= len(names) else "a new region"})
            elif milestone.startswith("furthest_") and manager.note_milestone(active["id"], milestone):
                say("expedition_furthest", {"ly": f"{int(milestone.split('_')[1]) * 1000:,}"})
            elif milestone == "close_call":
                say("expedition_close_call", {})
                if active.get("status") == "failed":
                    self.add_event_feed_entry("EXPEDITION", f"Ironman over: {active.get('name')} ended with the ship", severity="WARN")
            elif milestone == "home" and manager.note_milestone(active["id"], "home"):
                say("expedition_home", {})
        if active.get("status") != "active":
            return
        if event in {"FSDJump", "CarrierJump"}:
            live = self._expedition_live(active)
            if expedition_plan.milestone_due(live.get("progress"), active.get("stats") or {}) and manager.note_milestone(active["id"], "halfway"):
                say("expedition_halfway", {})
        threshold = self._expedition_risk_threshold()
        if threshold and event in {"Scan", "SAAScanComplete", "ScanOrganic", "FSDJump"}:
            state = getattr(self, "companion_state", None) or {}
            from voidcompass.core.companion_features import unsold_bio_value
            value = int(state.get("unsold_exploration_cr") or 0) + int(unsold_bio_value(state) or 0)
            step = value // threshold
            if step >= 1 and manager.note_milestone(active["id"], f"risk_{step}"):
                text = f"{value / 1e6:,.0f} M CR" if value < 1e9 else f"{value / 1e9:,.2f} BN CR"
                say("expedition_risk", {"value": text})
                toast = getattr(self, "toast_hud", None)
                if toast is not None and hasattr(toast, "push"):
                    toast.push("DATA AT RISK", f"{text} of unsold data aboard. Expeditions › SELL NOW finds the nearest cartographer.",
                               severity="warning", duration_s=10.0)

    # -- the Nav HUD's page --------------------------------------------------------------------------
    def _hud_page_expedition(self):
        manager = getattr(self, "expedition_manager", None)
        active = manager.active() if manager is not None else None
        if not active or active.get("status") != "active":
            return None
        return hud_pages.expedition_page(active, self._expedition_live(active))

    # -- the Local API -------------------------------------------------------------------------------
    def api_expeditions(self):
        manager = getattr(self, "expedition_manager", None)
        if manager is None:
            return {"expeditions": []}
        return {"active_id": (manager.active() or {}).get("id"),
                "expeditions": [{key: view[key] for key in ("id", "name", "status", "started", "ended", "destination", "stats", "ironman")}
                                for view in (self._expedition_view(row) for row in manager.expeditions())]}

    def api_expedition(self):
        from voidcompass.services.local_api import ApiError
        manager = getattr(self, "expedition_manager", None)
        active = manager.active() if manager is not None else None
        if not active:
            raise ApiError(404, "No expedition is active: start one on the Expeditions page")
        view = self._expedition_view(active, live=active.get("status") == "active")
        view.pop("album", None)
        # EDAstro's points of interest stay on the page, credited there.
        view.pop("nearby", None)
        return view
