"""The live, journal-led System Map (5.6.9)."""

import logging

from voidcompass.core.config import get_active_profile
from voidcompass.exploration import bio_reference
from voidcompass.exploration.stellar_cartography import build_orrery
from voidcompass.exploration.system_map import SystemMapCatalogue, finite, merge_system


def _flag(value):
    return bool(value) if value is not None else False


class HtmlSystemMapMixin:
    def _html_system_map_workspace(self):
        self._system_map_opened = True
        catalogue = getattr(self, "_system_map_catalogue", None)
        if catalogue is None:
            catalogue = self._system_map_catalogue = SystemMapCatalogue()
        name = str(getattr(self, "current_sys", None) or "")
        address = getattr(self, "current_system_address", None)
        public = catalogue.request(name, address)
        system = merge_system(name, address, getattr(self, "scan_items", None) or (),
                              getattr(self, "system_barycentres", None) or (), public.get("system"),
                              self._html_local_body_target(),
                              getattr(self, "total", None) if getattr(self, "scan_total_confirmed", False) else None)
        if name:
            self._system_map_extras(system)
        return {"profile_key": get_active_profile(self.config), "system": system,
                "catalogue": {k: v for k, v in public.items() if k != "system"}}

    def _system_map_extras(self, system):
        """Where you are, your places, carriers, ring hotspots and the facts Explore already knows."""
        for key, build in (("you", self._system_map_you), ("places", self._system_map_places),
                           ("carriers", self._system_map_carriers)):
            try:
                system[key] = build(system["name"]) if key != "you" else build()
            except Exception as exc:
                logging.debug("System map %s skipped: %s", key, exc)
        try:
            self._system_map_hotspots(system)
        except Exception as exc:
            logging.debug("System map hotspots skipped: %s", exc)
        try:
            self._system_map_facts(system)
        except Exception as exc:
            logging.debug("System map facts skipped: %s", exc)

    def _system_map_you(self):
        station = None
        if getattr(self, "current_docked", False):
            station = {"name": str(getattr(self, "current_station_name", "") or ""),
                       "type": str(getattr(self, "current_station_type", "") or ""),
                       "dist_ls": finite(getattr(self, "current_station_dist_ls", None))}
        lat, lon = finite(getattr(self, "current_latitude", None)), finite(getattr(self, "current_longitude", None))
        body_id = finite(getattr(self, "current_body_id", None))
        return {
            "state": str(getattr(self, "hud_flight_state", "") or ""),
            "body": str(getattr(self, "current_body_name", "") or ""),
            "body_id": int(body_id) if body_id is not None and body_id >= 0 else None,
            "docked": _flag(getattr(self, "current_docked", False)), "landed": _flag(getattr(self, "current_landed", False)),
            "on_foot": _flag(getattr(self, "current_on_foot", False)), "srv": _flag(getattr(self, "current_in_srv", False)),
            "station": station,
            "lat": lat if lon is not None else None, "lon": lon if lat is not None else None,
            "altitude_m": finite(getattr(self, "current_altitude_m", None)) if lat is not None and lon is not None else None,
        }

    def _system_map_places(self, system_name):
        """Your saved surface sites and the active expedition's stops in this system."""
        prefix = f"{system_name} ".casefold()
        places = []
        store = getattr(self, "_planet_materials_store", None)
        if callable(store):
            for row in store().rows():
                body = str(row.get("body") or "")
                lat, lon = finite(row.get("latitude")), finite(row.get("longitude"))
                if body.casefold().startswith(prefix) and lat is not None and lon is not None:
                    places.append({"kind": "site", "label": str(row.get("name") or "Saved site"), "body": body, "lat": lat, "lon": lon})
        manager = getattr(self, "expedition_manager", None)
        active = manager.active() if manager is not None else None
        for index, leg in enumerate((active or {}).get("legs") or ()):
            if str(leg.get("system") or "").casefold() != system_name.casefold():
                continue
            places.append({"kind": "stop", "label": str(leg.get("note") or f"Expedition stop {index + 1}"),
                           "body": str(leg.get("body") or ""), "lat": finite(leg.get("lat")), "lon": finite(leg.get("lon")),
                           "reached": bool(leg.get("reached")), "expedition": str(active.get("name") or "")})
        return places[:80]

    def _system_map_carriers(self, system_name):
        tracker = getattr(self, "carrier_tracker", None)
        if tracker is None:
            return []
        return [{"name": str(row.get("name") or ""), "callsign": str(row.get("callsign") or ""),
                 "body": str(row.get("body") or "")}
                for row in tracker.carriers() if str(row.get("system") or "").casefold() == system_name.casefold()]

    def _system_map_hotspots(self, system):
        store = getattr(self, "_html_mining_store", None)
        if not callable(store):
            return
        found = {}
        for row in store().hotspots_in(system["name"]):
            found.setdefault(str(row.get("body_name") or "").casefold(), []).append(
                {"material": str(row.get("material_name") or ""), "count": int(finite(row.get("hotspot_count")) or 0)})
        for body in system["bodies"]:
            for ring in body.get("rings") or ():
                spots = found.get(str(ring.get("name") or "").casefold())
                if spots:
                    ring["hotspots"] = spots[:8]

    def _system_map_facts(self, system):
        scans = [row for row in getattr(self, "scan_items", None) or () if isinstance(row, dict)]
        if not scans:
            return
        orrery = build_orrery(scans, None, getattr(self, "system_barycentres", None) or [])
        codex = getattr(self, "codex_index", None)
        address = getattr(self, "current_system_address", None)
        facts = {}
        for body in orrery.get("bodies") or ():
            if body.get("body_id") is None or not isinstance(body.get("facts"), dict):
                continue
            row = dict(body["facts"])
            if codex is not None and address is not None and hasattr(codex, "entries_on"):
                names = [bio_reference.english_name(entry) or entry for entry in codex.entries_on(address, body.get("body_id"))]
                if names:
                    row["codex"] = names[:12]
            if body.get("value") is not None:
                row["estimated_value"] = body.get("value")
            facts[int(body["body_id"])] = row
        # Surface materials, straight from the scan.
        for scan in scans:
            body_id = finite(scan.get("body_id"))
            rows = [{"name": str(row.get("Name_Localised") or row.get("Name") or row.get("name") or "").title(),
                     "percent": finite(row.get("Percent", row.get("percent")))}
                    for row in scan.get("materials") or () if isinstance(row, dict)]
            rows = sorted((row for row in rows if row["name"] and row["percent"] is not None), key=lambda row: -row["percent"])
            if body_id is not None and rows:
                facts.setdefault(int(body_id), {})["materials"] = rows[:12]
        for body in system["bodies"]:
            if body["bodyId"] in facts:
                body["_facts"] = facts[body["bodyId"]]
