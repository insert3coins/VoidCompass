"""Surface station pads on the deck (5.8.3): learnt as you land
(core/surface_pads.py). 5.8.6: one you're given that's been learnt is shown on
the pad finder (the Nav HUD and the Bridge's pad card) with callouts as you
close in, rather than on the planet compass."""
from __future__ import annotations

import math

from voidcompass.core import surface_pads
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.outrider import pads as orbital_pads


class DashboardSurfacePadsMixin:
    def surface_pad_store(self):
        key = get_active_profile(getattr(self, "config", None) or {})
        store = getattr(self, "_surface_pad_store", None)
        if store is None or getattr(self, "_surface_pad_store_key", None) != key:
            store = surface_pads.SurfacePadStore(get_profile_file(key, "surface_pads.json"))
            self._surface_pad_store, self._surface_pad_store_key = store, key
        return store

    def _surface_pads_summary(self):
        try:
            return self.surface_pad_store().summary()
        except Exception:
            return {"stations": 0, "pads": 0, "designs": 0, "trusted": 0}

    def _surface_pads_export(self, folder):
        """Settings › EXPORT PAD LAYOUTS: the file written, or None."""
        import json
        from pathlib import Path
        from voidcompass.core.version import APP_VERSION
        target = Path(str(folder or "")).expanduser()
        if not target.is_dir():
            return None
        path = target / f"voidcompass_surface_pads_{__import__('time').strftime('%Y%m%d')}.json"
        payload = self.surface_pad_store().export(app=f"VoidCompass {APP_VERSION}")
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
        return path

    def _surface_pads_import(self, paths):
        """Settings › IMPORT PAD LAYOUTS: other commanders' exports pooled
        with yours. {"files", "pads", "stations", "designs"}."""
        import json
        from pathlib import Path
        total = {"files": 0, "pads": 0, "stations": 0, "designs": 0}
        for path in paths or ():
            try:
                data = json.loads(Path(str(path)).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            added = self.surface_pad_store().merge(data)
            if added is None:
                continue
            total["files"] += 1
            for key in ("pads", "stations", "designs"):
                total[key] += added[key]
        return total

    def api_surface_pads(self):
        """The Local API (5.8.3): what's been learnt, as the export gives it."""
        from voidcompass.core.version import APP_VERSION
        return self.surface_pad_store().export(app=f"VoidCompass {APP_VERSION}")

    def _surface_here(self):
        """(lat, lon, radius, heading) while you're over a planet, else None."""
        lat, lon = getattr(self, "current_latitude", None), getattr(self, "current_longitude", None)
        radius = getattr(self, "current_planet_radius", None)
        if not getattr(self, "on_planet", False) or lat is None or lon is None or not radius:
            return None
        return float(lat), float(lon), float(radius), getattr(self, "current_heading", None)

    def _surface_pad_granted(self, raw):
        """Docking granted at a station on a planet's surface: remember which
        pad and, if it's been learnt, where it and the station's other known
        pads are, for the pad finder. Its words for the pad card (and
        "surface", what the finder needs), or None (an orbital station, or not
        on a planet)."""
        try:
            pad = int(raw.get("LandingPad"))
        except (TypeError, ValueError):
            return None
        here = self._surface_here()
        market = raw.get("MarketID")
        if here is None or market is None or orbital_pads.layout(raw.get("StationType"), raw.get("StationName") or "", market):
            self._surface_pad_pending = None
            return None
        station = str(raw.get("StationName_Localised") or raw.get("StationName") or "")
        self._surface_pad_pending = {"market": market, "pad": pad, "station": station, "type": str(raw.get("StationType") or ""),
                                     "system": str(getattr(self, "current_sys", "") or ""),
                                     "body": str(getattr(self, "current_body_name", "") or "")}
        known = self.surface_pad_store().find(market, pad)
        if not known:
            return {"words": "not learnt yet: it's remembered as you land on it",
                    "say": f"Pad {pad}: I don't know where that one is here yet. I'll remember it as you land."}
        lat, lon, radius, heading = here
        distance = surface_pads.distance_m(lat, lon, known["lat"], known["lon"], radius)
        bearing = surface_pads.bearing_deg(lat, lon, known["lat"], known["lon"])
        words = surface_pads.way_words(distance, bearing, heading)
        source = " (worked out from this station's design)" if known.get("predicted") else ""
        store = self.surface_pad_store()
        others = store.known_pads(market) or {}
        pads = [(pad, float(known["lat"]), float(known["lon"]))]
        for number in (others.get("landed") or []) + (others.get("worked_out") or []):
            place = store.find(market, number) if number != pad else None
            if place:
                pads.append((int(number), float(place["lat"]), float(place["lon"])))
        surface = {"pad": pad, "pads": pads, "predicted": bool(known.get("predicted")),
                   "body": self._surface_pad_pending["body"], "start": distance, "called": []}
        return {"words": words + source, "say": f"Pad {pad}: {words}{source}.", "surface": surface}

    def _surface_pad_live(self, surface):
        """The pad finder at a surface station, from where you are now:
        {words, distance, map: {kind "surface", pad, pads [[number, metres
        right, metres ahead]], heading_up, predicted}}, or None off the planet."""
        here = self._surface_here()
        if here is None or not surface or not surface.get("pads"):
            return None
        body = str(surface.get("body") or "")
        if body and body.casefold() != str(getattr(self, "current_body_name", "") or "").casefold():
            return None
        lat, lon, radius, heading = here
        facing = float(heading) if heading is not None else 0.0
        rows, words, distance = [], "", None
        for number, pad_lat, pad_lon in surface["pads"]:
            far = surface_pads.distance_m(lat, lon, pad_lat, pad_lon, radius)
            bearing = surface_pads.bearing_deg(lat, lon, pad_lat, pad_lon)
            turn = math.radians(bearing - facing)
            rows.append([int(number), round(far * math.sin(turn), 1), round(far * math.cos(turn), 1)])
            if number == surface["pad"]:
                distance, words = far, surface_pads.way_words(far, bearing, heading)
        if distance is None:
            return None
        return {"words": words, "distance": distance,
                "map": {"kind": "surface", "pad": surface["pad"], "pads": rows, "heading_up": heading is not None,
                        "predicted": bool(surface.get("predicted"))}}

    # Callouts on the way in: (metres, said once each when you close within it).
    PAD_CALLOUTS = (1000.0, 300.0, 45.0)

    def _surface_pad_on_position(self):
        """Status.json moved you: a callout as you close on a learnt surface pad."""
        info = getattr(self, "_pad_info", None)
        surface = (info or {}).get("surface")
        if not surface or getattr(self, "current_docked", False):
            return None
        live = self._surface_pad_live(surface)
        if not live:
            return None
        distance, pad = live["distance"], surface["pad"]
        due = [mark for mark in self.PAD_CALLOUTS if distance <= mark and mark not in surface["called"]]
        if not due:
            return None
        # The closest mark you're inside; any further out are past now too.
        mark = min(due)
        surface["called"].extend(due)
        if surface.get("start", 0.0) <= mark:
            return None  # granted inside it already: nothing to call
        say = f"Pad {pad} is below you." if mark == self.PAD_CALLOUTS[-1] else f"Pad {pad}: {live['words']}."
        if self.config.get("pad_location", True) and hasattr(self, "_small_say"):
            self._small_say(say, heading=f"PAD {pad}", topic="pad")
        return say

    def _surface_settlement_approach(self, raw, now=None):
        """Coming in to a settlement or surface port (ApproachSettlement): how
        far it is, and which of its pads are known already, before docking's
        even asked for. Its words to say, or None: a settlement without a
        landing pad, or one said in the last half hour."""
        import time
        market = raw.get("MarketID")
        if market is None or raw.get("Latitude") is None or raw.get("Longitude") is None:
            return None
        name = str(raw.get("Name_Localised") or raw.get("Name") or "The settlement")
        body = str(raw.get("BodyName") or getattr(self, "current_body_name", "") or "")
        on_it = body.casefold() == str(getattr(self, "current_body_name", "") or "").casefold()
        store = self.surface_pad_store()
        store.note_settlement(market, raw["Latitude"], raw["Longitude"], name=name, body=body,
                              system=str(getattr(self, "current_sys", "") or ""),
                              radius_m=getattr(self, "current_planet_radius", None) if on_it else None)
        known = store.known_pads(market) or {"landed": [], "worked_out": [], "pads": None}
        services = {str(item).casefold() for item in raw.get("StationServices") or ()}
        if not known["landed"] and not known["worked_out"] and "dock" not in services:
            return None
        said = self.__dict__.setdefault("_settlement_said", {})
        now = time.time() if now is None else now
        if now - said.get(str(market), -1e9) < 1800:
            return None
        said[str(market)] = now
        here = self._surface_here() if on_it else None
        where = ""
        if here is not None:
            lat, lon, radius, heading = here
            target = (float(raw["Latitude"]), float(raw["Longitude"]))
            where = surface_pads.way_words(surface_pads.distance_m(lat, lon, target[0], target[1], radius),
                                           surface_pads.bearing_deg(lat, lon, target[0], target[1]), heading)
        head = f"{name}, {where}" if where else name
        pads = lambda numbers: ", ".join(str(number) for number in numbers[:-1]) + (" and " if len(numbers) > 1 else "") + str(numbers[-1])
        if known["landed"] or known["worked_out"]:
            parts = []
            if known["landed"]:
                parts.append(f"you've landed on pad{'s' if len(known['landed']) > 1 else ''} {pads(known['landed'])}")
            if known["worked_out"]:
                count = len(known["worked_out"])
                parts.append(f"{count} more {'is' if count == 1 else 'are'} worked out from its design")
            total = len(known["landed"]) + len(known["worked_out"])
            of = f" of {known['pads']}" if known["pads"] else ""
            words = f"{head}. I know {total}{of} pad{'s' if total != 1 else ''} here: {' and '.join(parts)}."
        else:
            words = f"{head}. I don't know its pads yet: they're learnt as you land."
        return {"words": words, "say": words}

    def _surface_pad_docked(self, raw):
        """Docked on a surface pad: learn where it is, and clear the compass
        if it was pointing at it."""
        pending = getattr(self, "_surface_pad_pending", None)
        here = self._surface_here()
        if pending and here and raw.get("MarketID") == pending["market"]:
            lat, lon, radius, heading = here
            # Which way you face on it too: the station's design learns from that.
            self.surface_pad_store().learn(pending["market"], pending["pad"], lat, lon, radius, name=pending["station"],
                                           system=pending["system"], body=pending["body"],
                                           kind=str(raw.get("StationType") or pending["type"]), heading=heading,
                                           counts=raw.get("LandingPads") if isinstance(raw.get("LandingPads"), dict) else None,
                                           economy=str(raw.get("StationEconomy") or ""))
        self._surface_pad_forget()

    def _surface_pad_forget(self):
        """Docked, or the pad's no longer yours: nothing more to learn from it."""
        self._surface_pad_pending = None
