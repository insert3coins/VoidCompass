"""The Rig Tracker (5.5.10), for MainDashboard: the rig hotkeys, and the
overlay kept up to date as you drive (overlays/rig_tracker.py)."""
from __future__ import annotations

import logging

from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.overlays.rig_tracker import RigStore, build_rig_model, surface_distance_m


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
        return outcome

    def _rig_clear_here(self):
        place = self._rig_place()
        if place is None:
            return False
        cleared = self.rig_store().clear(place[0], place[1])
        if cleared:
            self._rig_say("RIGS FORGOTTEN", place[1])
        self._rig_update_overlay()
        return cleared

    def _rig_model(self):
        place = self._rig_place()
        if place is None:
            return None
        system, body, lat, lon, radius = place
        rigs = self.rig_store().rigs(system, body)
        heading = getattr(self, "current_heading", None)
        in_rhino = bool(getattr(self, "current_in_srv", False)) and \
            str(getattr(self, "current_vehicle_name", "") or "").upper() == "RHINO"
        key = str((getattr(self, "config", None) or {}).get("overlay_hotkey_rig_1") or "").upper()
        hint = f"{key} AS YOU DEPLOY RIG 1 · AGAIN AS YOU COLLECT IT" if key else "SET THE RIG KEYS IN SETTINGS › HOTKEYS"
        return build_rig_model(rigs, lat, lon, heading, radius, body, in_rhino=in_rhino, hint=hint)

    # -- the Local API (5.5.10) ------------------------------------------------
    def api_rigs(self):
        place = self._rig_place()
        in_rhino = bool(getattr(self, "current_in_srv", False)) and \
            str(getattr(self, "current_vehicle_name", "") or "").upper() == "RHINO"
        here = (place[0], place[1]) if place else None
        elsewhere = [{"system": row["system"], "body": row["body"], "rigs": sorted(row["rigs"])}
                     for row in self.rig_store().everywhere()
                     if not here or (row["system"].casefold(), row["body"].casefold()) != (here[0].casefold(), here[1].casefold())]
        model = self._rig_model() if place else None
        rigs = [{key: value for key, value in row.items() if key != "tracked"}
                for row in (model or {}).get("slots") or () if row.get("tracked")]
        return {"on_surface": place is not None, "in_rhino": in_rhino,
                "system": place[0] if place else None, "body": place[1] if place else None,
                "rigs": rigs, "collect_order": (model or {}).get("order") or [], "elsewhere": elsewhere}

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
