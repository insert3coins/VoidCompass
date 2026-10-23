"""The Rig Tracker (5.5.10), for MainDashboard: the rig hotkeys, and the
overlay kept up to date as you drive (overlays/rig_tracker.py)."""
from __future__ import annotations

import logging

from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.overlays.cargo_hud import VEHICLE_CARGO_CAPACITIES
from voidcompass.overlays.rig_tracker import RigStore, build_rig_model, hold_row, rig_here_m, surface_distance_m


def _tons(inventory):
    total = 0
    for item in inventory or ():
        if isinstance(item, dict):
            try:
                total += int(item.get("Count", item.get("count", 0)) or 0)
            except (TypeError, ValueError):
                pass
    return total


def _distance_text(metres):
    return f"{metres / 1000:.1f} km" if metres >= 1000 else f"{metres:.0f} m"


class DashboardRigsMixin:
    def rig_store(self):
        key = get_active_profile(getattr(self, "config", None) or {})
        store = getattr(self, "_rig_store_instance", None)
        if store is None or getattr(self, "_rig_store_key", None) != key:
            store = RigStore(get_profile_file(key, "rigs.json"))
            self._rig_store_instance, self._rig_store_key = store, key
        return store

    def _rig_place(self):
        """(system, body, lat, lon, radius) on a planet's surface, or None."""
        lat, lon = getattr(self, "current_latitude", None), getattr(self, "current_longitude", None)
        radius = getattr(self, "current_planet_radius", None)
        body = getattr(self, "current_body_name", None)
        if not getattr(self, "on_planet", False) or lat is None or lon is None or not radius or not body:
            return None
        return str(getattr(self, "current_sys", "") or ""), str(body), float(lat), float(lon), float(radius)

    def _rig_say(self, title, message, severity="info"):
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push(title, message, severity=severity, duration_s=4.0)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("MINING", f"{title.title()}: {message}", severity="INFO")

    def _rig_mark(self, slot):
        """A rig hotkey: track rig ``slot`` here, or stop tracking it."""
        place = self._rig_place()
        if place is None:
            self._rig_say(f"RIG {slot}", "Rigs are marked on a planet's surface", severity="warn")
            return None
        system, body, lat, lon, radius = place
        store = self.rig_store()
        try:
            outcome = store.mark(slot, system, body, lat, lon)
        except Exception as exc:
            logging.warning("Rig %s not marked: %s", slot, exc)
            return None
        if outcome == "placed":
            others = [(other, surface_distance_m(lat, lon, rig["lat"], rig["lon"], radius))
                      for other, rig in store.rigs(system, body).items() if other != slot]
            nearest = min(others, key=lambda pair: pair[1]) if others else None
            self._rig_say(f"RIG {slot} DEPLOYED", f"{body}" + (f" · {_distance_text(nearest[1])} from rig {nearest[0]}" if nearest else ""),
                          severity="success")
        else:
            left = len(store.rigs(system, body))
            self._rig_say(f"RIG {slot} COLLECTED", f"{left} still out" if left else "All rigs collected")
        self._rig_update_overlay()
        self._update_rhino_map()
        return outcome

    def _rig_clear_here(self):
        place = self._rig_place()
        if place is None:
            return False
        cleared = self.rig_store().clear(place[0], place[1])
        if cleared:
            self._rig_say("RIGS FORGOTTEN", place[1])
        self._rig_update_overlay()
        self._update_rhino_map()
        return cleared

    def _rig_in_rhino(self):
        return bool(getattr(self, "current_in_srv", False)) and \
            str(getattr(self, "current_vehicle_name", "") or "").upper() == "RHINO"

    def _rig_holds(self):
        """The Rhino's hold while you drive it, and the mothership's (5.5.11).
        Cargo.json only describes what you're in, so out in the Rhino the
        ship's hold is the one kept from its last Cargo."""
        vessel = str(getattr(self, "current_cargo_vessel", "Ship") or "Ship").strip().casefold()
        inventory = getattr(self, "current_cargo_inventory", None) or []
        ship_capacity = getattr(self, "cargo_capacity", 0) or 0
        holds = []
        if vessel == "srv":
            if self._rig_in_rhino():
                holds.append(hold_row("RHINO", _tons(inventory), VEHICLE_CARGO_CAPACITIES["RHINO"]))
            kept = (getattr(self, "_cargo_inventory_by_hold", None) or {}).get("Ship")
            if kept is not None:
                holds.append(hold_row("SHIP", _tons(kept), ship_capacity,
                                      partial=bool(getattr(self, "_ship_hold_partial", False))))
        else:
            holds.append(hold_row("SHIP", _tons(inventory), ship_capacity))
        return [row for row in holds if row["capacity"]]

    def _rig_model(self):
        place = self._rig_place()
        if place is None:
            return None
        system, body, lat, lon, radius = place
        rigs = self.rig_store().rigs(system, body)
        heading = getattr(self, "current_heading", None)
        key = str((getattr(self, "config", None) or {}).get("overlay_hotkey_rig_1") or "").upper()
        hint = f"{key} AS YOU DEPLOY RIG 1 · AGAIN AS YOU COLLECT IT" if key else "SET THE RIG KEYS IN SETTINGS › HOTKEYS"
        config = getattr(self, "config", None) or {}
        show_holds = bool(config.get("rig_tracker_show_holds", True))
        return build_rig_model(rigs, lat, lon, heading, radius, body, in_rhino=self._rig_in_rhino(), hint=hint,
                               holds=self._rig_holds() if show_holds else (), here_m=rig_here_m(config))

    # -- the Local API (5.5.10) ------------------------------------------------
    def api_rigs(self):
        place = self._rig_place()
        in_rhino = self._rig_in_rhino()
        here = (place[0], place[1]) if place else None
        elsewhere = [{"system": row["system"], "body": row["body"], "rigs": sorted(row["rigs"])}
                     for row in self.rig_store().everywhere()
                     if not here or (row["system"].casefold(), row["body"].casefold()) != (here[0].casefold(), here[1].casefold())]
        model = self._rig_model() if place else None
        rigs = [{key: value for key, value in row.items() if key != "tracked"}
                for row in (model or {}).get("slots") or () if row.get("tracked")]
        return {"on_surface": place is not None, "in_rhino": in_rhino,
                "system": place[0] if place else None, "body": place[1] if place else None,
                "rigs": rigs, "collect_order": (model or {}).get("order") or [], "elsewhere": elsewhere,
                "holds": self._rig_holds()}

    def api_rig_mark(self, slot):
        from voidcompass.services.local_api import ApiError
        if self._rig_place() is None:
            raise ApiError(409, "Rigs are marked on a planet's surface: you're not on one")
        outcome = self._rig_mark(int(slot))
        if outcome is None:
            raise ApiError(409, f"Rig {slot} couldn't be marked")
        return {"rig": int(slot), "done": outcome, **self.api_rigs()}

    def api_rigs_clear(self):
        from voidcompass.services.local_api import ApiError
        if self._rig_place() is None:
            raise ApiError(409, "Forgetting rigs works on the planet they're on: you're not on a planet's surface")
        return {"forgotten": bool(self._rig_clear_here()), **self.api_rigs()}

    # -- the Rhino map in the Galaxy Minimap (5.5.17) ----------------------------------
    def _surface_note_pulse(self, raw):
        """A refining pulse in the SRV: where you were, for the map's deposits."""
        place = self._rig_place()
        if place is None or not getattr(self, "current_in_srv", False):
            return False
        system, body, lat, lon, _radius = place
        spots = getattr(self, "_surface_pulses", None)
        if spots is None or spots.get("body") != (system, body):
            spots = self._surface_pulses = {"body": (system, body), "spots": []}
        material = str((raw or {}).get("Type_Localised") or (raw or {}).get("Type") or "").strip()
        spots["spots"].append((lat, lon, material[:40]))
        del spots["spots"][:-2000]
        return True

    def _surface_mining_signals(self, body):
        for signals in (getattr(self, "body_signals", None) or {}).values():
            if str(signals.get("body_name") or "").casefold() == str(body or "").casefold():
                return int(signals.get("mining") or 0)
        return 0

    def _surface_map_model(self):
        from voidcompass.overlays.rig_tracker import rig_here_m as here_m, rig_spacing_m, rig_warn_m
        from voidcompass.overlays.surface_map import build_surface_map, surface_options, wants_surface
        options = surface_options(getattr(self, "config", None) or {})
        vehicle = ("RHINO" if self._rig_in_rhino() else "ON FOOT" if getattr(self, "current_on_foot", False)
                   else "SRV" if getattr(self, "current_in_srv", False) else "SHIP")
        place = self._rig_place()
        rigs_here = bool(place and self.rig_store().rigs(place[0], place[1]))
        if not wants_surface(options["mode"], on_planet=bool(getattr(self, "on_planet", False)),
                             in_srv=bool(getattr(self, "current_in_srv", False)),
                             vehicle=str(getattr(self, "current_vehicle_name", "") or ""),
                             on_foot=bool(getattr(self, "current_on_foot", False)), rigs_here=rigs_here):
            return None
        planetary = getattr(self, "_planetary_map", None)
        plane_map = planetary() if callable(planetary) and place else None
        plane = getattr(self, "_planetary_plane", None)
        if not plane_map or plane is None:
            return None
        system, body = place[0], place[1]
        rigs = self.rig_store().rigs(system, body)
        pulses = getattr(self, "_surface_pulses", None) or {}
        spots = pulses.get("spots") or [] if pulses.get("body") == (system, body) else []
        return build_surface_map(
            plane_map, plane, rig_model=self._rig_model(),
            rig_points={slot: (rig["lat"], rig["lon"]) for slot, rig in rigs.items()},
            here_m=here_m(getattr(self, "config", None) or {}), spots=spots,
            signals=self._surface_mining_signals(body), vehicle=vehicle, options=options,
            spacing_m=rig_spacing_m(getattr(self, "config", None) or {}), warn_m=rig_warn_m(getattr(self, "config", None) or {}))

    def _rig_range_watch(self):
        """A rig getting too far away: said once a trip, as the game destroys
        it at 5 km (after EDSMT). Said again only after you've been back near."""
        from voidcompass.overlays.rig_tracker import LOST_M, rig_advice, rig_warn_m
        warn = rig_warn_m(getattr(self, "config", None) or {})
        model = self._rig_model() if warn else None
        far = {row["slot"]: row for row in rig_advice((model or {}).get("slots"), warn_m=warn)["too_far"]} if model else {}
        warned = getattr(self, "_rig_far_warned", None)
        if warned is None:
            warned = self._rig_far_warned = set()
        for slot, row in far.items():
            if slot not in warned:
                warned.add(slot)
                left = max(0, round((LOST_M - row["distance"]) / 100) / 10)
                self._rig_say(f"RIG {slot} TOO FAR", f"{row['distance'] / 1000:.1f} km away · lost at 5 km ({left:.1f} km to go)",
                              severity="warn")
        rows = {row["slot"]: row for row in (model or {}).get("slots") or () if row.get("tracked")}
        place = self._rig_place()
        lost = [slot for slot, row in rows.items() if (row.get("distance_m") or 0) >= LOST_M]
        if lost and place:
            # The game has destroyed these: stop showing them.
            for slot in lost:
                self.rig_store().forget(place[0], place[1], slot)
                warned.discard(slot)
                self._rig_say(f"RIG {slot} LOST", "More than 5 km behind: the game takes it back", severity="warn")
            self._rig_update_overlay()
            self._update_rhino_map()
        for slot in list(warned):
            row = rows.get(slot)
            if row is None or row["distance_m"] < warn - 200:
                warned.discard(slot)
        return bool(far)

    def _rig_left_body(self, body):
        """Leaving a planet takes you far past 5 km, so any rigs left on it are
        gone. Kept, they'd bring the ground map back on the next visit."""
        system = str(getattr(self, "current_sys", "") or "")
        if not body or not self.rig_store().clear(system, str(body)):
            return False
        self._rig_say("RIGS LEFT BEHIND", f"{body}: rigs still out there are lost", severity="warn")
        self._rig_update_overlay()
        self._update_rhino_map()
        return True

    def _rhino_map_next_range(self):
        """The Rhino map range hotkey (5.5.18): Your rigs, 300 m, 600 m, 1.2 km,
        2.5 km, round again. Kept like Overlay Studio's Rhino map range."""
        from voidcompass.overlays.surface_map import RANGE_NAMES, next_range, surface_options
        reach = next_range(surface_options(getattr(self, "config", None) or {})["range"])
        self.config["rhino_map_range"] = reach
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        self._update_rhino_map()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("SYSTEM", f"Rhino map range: {RANGE_NAMES[reach].capitalize()}", severity="INFO")
        return reach

    def _update_rhino_map(self):
        hud = getattr(self, "rhino_map_hud", None)
        if hud is None:
            return False
        try:
            return hud.update(self._surface_map_model())
        except Exception:
            logging.exception("Rhino map update failed")
            return False

    def _rig_update_overlay(self):
        hud = getattr(self, "rig_tracker_hud", None)
        if hud is None:
            return False
        try:
            hud.update(self._rig_model())
        except Exception:
            logging.exception("Rig Tracker overlay update failed")
            return False
        return True
