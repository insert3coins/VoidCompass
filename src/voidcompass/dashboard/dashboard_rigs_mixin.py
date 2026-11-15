"""The Rig Tracker (5.5.10), for MainDashboard: the rig hotkeys, and the
overlay kept up to date as you drive (overlays/rig_tracker.py)."""
from __future__ import annotations

import logging
import math
import threading
import time
from pathlib import Path

from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.overlays import rhino_survey, rig_planner
from voidcompass.overlays.cargo_hud import VEHICLE_CARGO_CAPACITIES
from voidcompass.overlays.rig_tracker import (
    RigStore, booking_rig, build_rig_model, drop_point, hold_row, rig_commodity, rig_drop_m, rig_here_m, rig_spacing_m,
    surface_distance_m,
)


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


_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def _compass(bearing):
    return _POINTS[int(((float(bearing or 0) + 22.5) % 360) // 45)]


# A traced plan this close to a marked deposit is that deposit's (and gives its rig count).
PLAN_DEPOSIT_M = 150.0


def runs_rate(run):
    """A run's tonnes an hour, or None when it was too short to say."""
    minutes = float((run or {}).get("minutes") or 0)
    return round(float(run.get("refined_t") or 0) / (minutes / 60)) if minutes >= 1 else None


def runs_summary(runs):
    """A saved site's runs in a line's worth: how many, tonnes in all, the
    best and usual rate, the commodity that gave most, the last one's date."""
    runs = [run for run in runs or () if run.get("refined_t")]
    if not runs:
        return None
    rates = sorted(rate for rate in (runs_rate(run) for run in runs) if rate)
    totals = {}
    for run in runs:
        for name, tonnes in (run.get("taken") or {}).items():
            totals[name] = totals.get(name, 0) + int(tonnes or 0)
    return {"count": len(runs), "tonnes": sum(int(run.get("refined_t") or 0) for run in runs),
            "best_tph": rates[-1] if rates else None, "usual_tph": rates[len(rates) // 2] if rates else None,
            "best_commodity": max(totals, key=totals.get) if totals else "", "last": runs[-1].get("docked"),
            "runs": [{**run, "tph": runs_rate(run)} for run in reversed(runs)]}


def rhino_surface_commodity(row):
    """A marked deposit's commodity: the first of its materials."""
    from voidcompass.overlays.surface_map import primary_material
    return primary_material((row or {}).get("materials"))


class DashboardRigsMixin:
    def rig_store(self):
        key = get_active_profile(getattr(self, "config", None) or {})
        store = getattr(self, "_rig_store_instance", None)
        if store is None or getattr(self, "_rig_store_key", None) != key:
            store = RigStore(get_profile_file(key, "rigs.json"))
            self._rig_store_instance, self._rig_store_key = store, key
        return store

    def survey_store(self):
        """The Rhino surveys and pulses (5.7.6), kept beside the rigs."""
        rigs_path = getattr(self.rig_store(), "path", None)
        path = str(Path(rigs_path).with_name("rhino_survey.json")) if isinstance(rigs_path, str) and rigs_path else None
        store = getattr(self, "_survey_store_instance", None)
        if store is None or store.path != path:
            store = self._survey_store_instance = rhino_survey.SurveyStore(path)
        return store

    def _rig_place(self):
        """(system, body, lat, lon, radius) on a planet's surface, or None."""
        lat, lon = getattr(self, "current_latitude", None), getattr(self, "current_longitude", None)
        radius = getattr(self, "current_planet_radius", None)
        body = getattr(self, "current_body_name", None)
        if not getattr(self, "on_planet", False) or lat is None or lon is None or not radius or not body:
            return None
        place = str(getattr(self, "current_sys", "") or ""), str(body), float(lat), float(lon), float(radius)
        self._rig_last_place = (place, time.monotonic())
        return place

    def _rig_place_recent(self, within_s=120.0):
        """Where you are, or where you last were on a surface a moment ago:
        the game's Status can drop its position for a moment as the Rhino docks."""
        place = self._rig_place()
        if place is not None:
            return place
        last = getattr(self, "_rig_last_place", None)
        if last and time.monotonic() - last[1] <= within_s:
            return last[0]
        return None

    def _rig_say(self, title, message, severity="info"):
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push(title, message, severity=severity, duration_s=4.0)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("MINING", f"{title.title()}: {message}", severity="INFO")

    def _rig_tell(self, kind, **fields):
        """5.7.5: a rig moment for the companion on watch. Rigs aren't in the
        journal, so only these hotkeys can tell it."""
        hud = getattr(self, "heartbeat_hud", None)
        if hud is None or not hasattr(hud, "note"):
            return None
        try:
            return hud.note(kind, {key: str(value) for key, value in fields.items()})
        except Exception:
            logging.debug("Rig note for the companion skipped", exc_info=True)
            return None

    def _rig_mark(self, slot, from_key=False):
        """A rig hotkey: track rig ``slot`` here, or stop tracking it. The keys
        only work from the SRV, where rigs go down and come up; the Rhino
        page's buttons (and the Local API) work anywhere on the planet."""
        place = self._rig_place()
        if place is None:
            self._rig_say(f"RIG {slot}", "Rigs are marked on a planet's surface", severity="warn")
            return None
        if from_key and not getattr(self, "current_in_srv", False):
            self._rig_say(f"RIG {slot}", "Rigs go down and come up from the Rhino: the Rhino page's buttons put them right from here",
                          severity="warn")
            return None
        system, body, lat, lon, radius = place
        store = self.rig_store()
        if getattr(self, "current_in_srv", False):
            lat, lon = drop_point(lat, lon, getattr(self, "current_heading", None), radius,
                                  rig_drop_m(getattr(self, "config", None) or {}))
        on = self._deposit_near(system, body, lat, lon, radius, within_m=60.0)
        known = rhino_surface_commodity(on[1]) if on else ""
        try:
            outcome = store.mark(slot, system, body, lat, lon, commodity="" if known in ("", "Unknown") else known,
                                 density=str((on[1] if on else {}).get("density") or ""))
        except Exception as exc:
            logging.warning("Rig %s not marked: %s", slot, exc)
            return None
        if outcome == "placed":
            others = [(other, surface_distance_m(lat, lon, rig["lat"], rig["lon"], radius))
                      for other, rig in store.rigs(system, body).items() if other != slot]
            nearest = min(others, key=lambda pair: pair[1]) if others else None
            on_what = f" · on {known}" if known and known != "Unknown" else ""
            self._rig_say(f"RIG {slot} DEPLOYED", f"{body}{on_what}" + (f" · {_distance_text(nearest[1])} from rig {nearest[0]}" if nearest else ""),
                          severity="success" if not nearest or nearest[1] >= rig_spacing_m(getattr(self, "config", None) or {}) else "warn")
            self._rig_tell("rig_placed", slot=slot)
        else:
            left = len(store.rigs(system, body))
            self._rig_say(f"RIG {slot} COLLECTED", f"{left} still out" if left else "All rigs collected")
            self._rig_tell("rig_collected", slot=slot, left=left) if left else self._rig_tell("rig_all_collected")
        ready = getattr(self, "_rig_ready_said", None)
        if ready is not None:
            ready.discard(slot)  # placed again or collected: its time starts again
        self._rhino_site_keep()
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
        holds = self._rig_holds() if show_holds else ()
        store = self.rig_store()
        model = build_rig_model(rigs, lat, lon, heading, radius, body, in_rhino=self._rig_in_rhino(), hint=hint,
                                holds=holds, here_m=rig_here_m(config), ready_for=lambda rig: store.ready_s(rig.get("density") or ""))
        aboard = self._rhino_aboard_summary(model)
        if aboard is None:
            return model
        if model is None:
            model = {"body": str(body), "slots": [], "tracked": 0, "order": [], "heading_known": heading is not None,
                     "hint": "", "holds": [dict(row) for row in self._rig_holds() if row.get("capacity")]}
        model["aboard"] = aboard
        return model

    # -- back aboard ---------------------------------------------------------------------
    @staticmethod
    def _journal_seconds(when):
        """A journal timestamp as epoch seconds (now when there isn't one)."""
        from datetime import datetime
        try:
            return datetime.fromisoformat(str(when).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return time.time()

    def _rhino_launched(self, vehicle_name, when=None):
        """The Rhino's out: a new run starts, and any back-aboard card goes."""
        self._rhino_aboard = None
        if "RHINO" in str(vehicle_name or "").upper():
            self._rhino_run_started = self._journal_seconds(when)

    def _rhino_docked(self, vehicle_name, when=None, quiet=False):
        """The Rhino's back in the ship: the Rig Tracker shows the run's summary
        until you leave the planet or take the Rhino out again. ``quiet`` while
        the journals are read at startup: kept, nothing redrawn."""
        if "RHINO" not in str(vehicle_name or "").upper():
            return None
        place = self._rig_place_recent()
        body = place[1] if place else str(getattr(self, "current_body_name", "") or "")
        system = place[0] if place else str(getattr(self, "current_sys", "") or "")
        if not body:
            return None
        self._rhino_aboard = {"system": system, "body": body, "docked": self._journal_seconds(when),
                              "launched": getattr(self, "_rhino_run_started", None),
                              "at": [place[2], place[3]] if place else None, "radius": place[4] if place else None}
        if quiet:
            return self._rhino_aboard
        self._rhino_site_keep(place=place)
        self._rhino_run_kept()
        self._rig_update_overlay()
        self._rhino_page_refresh(now=True)
        return self._rhino_aboard

    def _rhino_run_kept(self):
        """The run just docked, kept with the saved site it was worked at:
        its length and what it gave, by commodity. Only a run that refined
        something, at a site that's saved."""
        aboard = getattr(self, "_rhino_aboard", None)
        if not aboard or not aboard.get("launched"):
            return None
        system, body = aboard["system"], aboard["body"]
        taken = self.rig_store().tonnes_on(system, body, since=aboard["launched"])
        run = self._rhino_run() if callable(getattr(self, "_rhino_run", None)) else None
        refined = int(round(float((run or {}).get("refined_t") or 0))) or sum(taken.values())
        where = aboard.get("at")
        site = self._rhino_site_here(place=(system, body, where[0], where[1], aboard.get("radius"))
                                     if where and aboard.get("radius") else None)
        if not refined or not site:
            return None
        minutes = max(1, round((aboard["docked"] - aboard["launched"]) / 60))
        record = {"launched": round(aboard["launched"], 1), "docked": round(aboard["docked"], 1), "minutes": minutes,
                  "refined_t": refined, "taken": {name: tonnes for name, tonnes in taken.items() if tonnes}}
        self.survey_store().add_run(system, body, site["id"], record)
        return record

    def _rhino_aboard_summary(self, model=None):
        """What the run gave, what's still out, and what's next; for the Rig
        Tracker and the Rhino page while you're back in the ship."""
        aboard = getattr(self, "_rhino_aboard", None)
        if not aboard or getattr(self, "current_in_srv", False):
            return None
        place = self._rig_place()
        if place and (place[0].casefold(), place[1].casefold()) != (aboard["system"].casefold(), aboard["body"].casefold()):
            return None
        system, body = aboard["system"], aboard["body"]
        since = aboard.get("launched")
        taken = self.rig_store().tonnes_on(system, body, since=since)
        run = self._rhino_run() if callable(getattr(self, "_rhino_run", None)) else None
        refined = int(round(float((run or {}).get("refined_t") or 0))) or sum(taken.values())
        out = [{"slot": row["slot"], "distance_m": row.get("distance_m"), "commodity": row.get("commodity") or ""}
               for row in (model or {}).get("slots") or () if row.get("tracked")]
        site = None
        try:
            site = self._rhino_site_here() if place else None
        except Exception:
            site = None
        minutes = round((aboard["docked"] - since) / 60) if since else None
        if out:
            following = f"Rig {out[0]['slot']} is still out: take the Rhino back for it, or it's lost when you leave"
        else:
            following = "Take the Rhino out for the next deposit, or lift off"
        history = None
        if site:
            earlier = [kept for kept in site.get("runs") or () if not since or float(kept.get("launched") or 0) < since - 1]
            best = max((runs_rate(kept) for kept in earlier), default=None)
            history = {"run": len(earlier) + 1, "best_tph": best}
        return {"minutes": minutes, "refined_t": refined, "taken": [{"commodity": name, "t": tonnes} for name, tonnes in
                                                                    sorted(taken.items(), key=lambda pair: -pair[1]) if tonnes],
                "out": out, "site": {"name": site.get("name"), "swept": ((site.get("survey") or {}).get("percent"))} if site else None,
                "tph": round(refined / (minutes / 60)) if minutes and refined else None, "history": history,
                "next": following}

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
                "holds": self._rig_holds(), "aboard": (model or {}).get("aboard")}

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

    def api_rhino(self):
        from voidcompass.overlays.surface_map import rig_words
        place = self._rig_place()
        facts = self._survey_facts() if place else None
        surface = None
        if place:
            try:
                surface = self._surface_map_model()
            except Exception:
                logging.debug("Local API: Rhino map model skipped", exc_info=True)
        words = rig_words(surface)
        deposits = [{key: row.get(key) for key in ("commodity", "rigs", "amount", "density", "depleted", "distance", "bearing", "n", "signal", "value")}
                    for row in (surface or {}).get("deposits") or ()]
        groups = [{key: group.get(key) for key in ("n", "rigs", "deposits", "credits", "cr_per_h", "distance", "bearing", "materials")}
                  for group in (surface or {}).get("groups") or ()]
        site = self._rhino_site_here() if place else None
        return {"on_surface": place is not None, "body": place[1] if place else None, "facts": facts or {},
                "site": {key: site.get(key) for key in ("id", "name", "signal", "deposits", "tonnes", "updated")} if site else None,
                "rig_spot": words[0] if words else None, "deposits": deposits, "patches": groups,
                "value": (surface or {}).get("value")}

    def api_rhino_action(self, action):
        from voidcompass.services.local_api import ApiError
        if self._rig_place() is None:
            raise ApiError(409, "Rhino mining is on a planet's surface: you're not on one")
        run = {"deposit": self._deposit_mark_key, "mined-out": self._deposit_mined_out_key,
               "trace": self._rig_trace_key, "circle": self._rig_circle_key, "save": self._rhino_site_save}[action]
        done = run()
        return {"action": action, "done": bool(done), **self.api_rhino()}

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
        rigs = self.rig_store().rigs(system, body)
        slot = booking_rig(rigs, lat, lon, _radius)
        if slot is not None:
            self.rig_store().book(system, body, slot, material)
            self._deposit_named_by_rig(system, body, slot, _radius)
            self._deposit_regrown_by_rig(system, body, slot, _radius, material)
        # 5.7.6: kept per planet too, for the best patch after a restart.
        try:
            self.survey_store().note_pulse(system, body, lat, lon, material)
            self._survey_patch_watch()
        except Exception:
            logging.debug("Pulse not kept for the survey", exc_info=True)
        return True

    def _deposit_regrown_by_rig(self, system, body, slot, radius, material):
        """Its own commodity refined by a rig on a worked-out deposit: it's back.
        A by-product doesn't count."""
        rig = self.rig_store().rigs(system, body).get(slot)
        if not rig or not material:
            return False
        on = self._deposit_near(system, body, rig["lat"], rig["lon"], radius, within_m=60.0)
        if not on or not on[1].get("depleted") or rhino_surface_commodity(on[1]).casefold() != str(material).casefold():
            return False
        return self._deposit_grown_back(dict(on[1]), by_rig=True)

    def _deposit_named_by_rig(self, system, body, slot, radius):
        """A deposit marked before anything was refined there is "Unknown":
        the rig working it names it once its tonnes come in."""
        rig = self.rig_store().rigs(system, body).get(slot)
        commodity = rig_commodity(rig) if rig else ""
        if not commodity or commodity == "Unknown":
            return False
        on = self._deposit_near(system, body, rig["lat"], rig["lon"], radius, within_m=60.0)
        if not on or rhino_surface_commodity(on[1]) not in ("", "Unknown"):
            return False
        row = on[1]
        try:
            self._planet_materials_store().save({**row, "materials": commodity,
                                                 "name": commodity if row.get("name") in (None, "", "Unknown") else row["name"]})
        except Exception:
            logging.debug("Deposit not named from its rig", exc_info=True)
            return False
        self._rhino_after_change()
        return True

    def _surface_mining_signals(self, body):
        for signals in (getattr(self, "body_signals", None) or {}).values():
            if str(signals.get("body_name") or "").casefold() == str(body or "").casefold():
                return int(signals.get("mining") or 0)
        return 0

    def _rhino_prices(self):
        """What each commodity sells for: what you've been paid, else the mining
        sheet's median. Kept two minutes (the map asks every status tick)."""
        cached = getattr(self, "_rhino_price_cache", None)
        if cached and time.time() - cached[0] < 120:
            return cached[1]
        prices = {}
        try:
            from voidcompass.dashboard.html_mining import typical_prices
            prices.update({name: value for name, value in typical_prices().items() if value})
        except Exception:
            logging.debug("Rhino prices: mining sheet skipped", exc_info=True)
        income = getattr(self, "_mining_income", None)
        if callable(income):
            try:
                for name, row in (income().get("prices") or {}).items():
                    if row.get("avg"):
                        prices[name] = row["avg"]
            except Exception:
                logging.debug("Rhino prices: your sales skipped", exc_info=True)
        self._rhino_price_cache = (time.time(), prices)
        return prices

    def _surface_map_model(self, force=False):
        from voidcompass.overlays.rig_tracker import rig_here_m as here_m, rig_spacing_m, rig_warn_m
        from voidcompass.overlays.surface_map import build_surface_map, surface_options, wants_surface
        options = surface_options(getattr(self, "config", None) or {})
        vehicle = ("RHINO" if self._rig_in_rhino() else "ON FOOT" if getattr(self, "current_on_foot", False)
                   else "SRV" if getattr(self, "current_in_srv", False) else "SHIP")
        place = self._rig_place()
        rigs_here = bool(place and self.rig_store().rigs(place[0], place[1]))
        if not force and not wants_surface(options["mode"], on_planet=bool(getattr(self, "on_planet", False)),
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
        kept = self.survey_store().pulses(system, body)
        if len(kept) > len(spots):
            spots = [(row[0], row[1], row[2] if len(row) > 2 else "") for row in kept]
        lat, lon, radius = place[2], place[3], place[4]
        spots = [spot for spot in spots if self._rhino_within(lat, lon, spot[0], spot[1], radius)]
        everywhere = self._deposit_rows(system, body)
        sites = self._deposit_rows(system, body, near=(lat, lon, radius))
        trace = getattr(self, "_rig_trace", None)
        tracing = trace["trace"].outline() if trace and trace["body"] == (system, body) else None
        return build_surface_map(
            plane_map, plane, rig_model=self._rig_model(),
            rig_points={slot: (rig["lat"], rig["lon"]) for slot, rig in rigs.items()},
            here_m=here_m(getattr(self, "config", None) or {}), spots=spots,
            signals=self._surface_mining_signals(body), vehicle=vehicle, options=options,
            spacing_m=rig_spacing_m(getattr(self, "config", None) or {}), warn_m=rig_warn_m(getattr(self, "config", None) or {}),
            survey=self.survey_store().survey(system, body), sites=sites,
            plan_record=rig_planner.plan_here(self.survey_store().plans(system, body), lat, lon, radius),
            circle=self.survey_store().circle(system, body), trace=tracing, signal=self._rhino_signal_here(),
            prices=self._rhino_prices(), per_rig=self.rig_store().tonnes_per_rig()[0]) | {
                "elsewhere": len(everywhere) - len(sites)}

    # -- the Rhino survey (5.7.6) -------------------------------------------------------
    def _survey_mark(self, what):
        """The survey keys: "centre" here, "edge" here, or "clear"."""
        place = self._rig_place()
        if place is None:
            self._rig_say("RHINO SURVEY", "Surveys are marked on a planet's surface", severity="warn")
            return None
        system, body, lat, lon, radius = place
        store = self.survey_store()
        if what == "centre":
            store.mark_centre(system, body, lat, lon, signal=self._rhino_signal_here(), planet_radius_m=radius)
            self._rig_say("SURVEY CENTRE MARKED", f"{body} · now drive out and mark the edge", severity="success")
            outcome = "centre"
        elif what == "edge":
            size = store.mark_edge(system, body, lat, lon, radius)
            if size is None:
                self._rig_say("RHINO SURVEY", "Mark the survey's centre first", severity="warn")
                return None
            if not size:
                self._rig_say("RHINO SURVEY", f"Still by the centre: drive out {_distance_text(rhino_survey.MIN_EDGE_M)} or more, then mark the edge",
                              severity="warn")
                return None
            self._rig_say("SURVEY AREA SET", f"{body} · {_distance_text(size)} round the centre", severity="success")
            self._rig_tell("survey_marked", km=f"{size / 1000:.1f}", body=body)
            outcome = "edge"
        else:
            outcome = "cleared" if store.clear(system, body) else None
            if outcome:
                self._rig_say("SURVEY CLEARED", body)
        self._survey_tick()
        if outcome in ("centre", "edge"):
            self._rhino_site_keep()
        self._rig_update_overlay()
        self._update_rhino_map()
        return outcome

    def _survey_tick(self):
        """In the SRV inside a survey: what the scanner has reached is covered.
        Half and done are said once each."""
        place = self._rig_place()
        if place is None or not getattr(self, "current_in_srv", False):
            return None
        system, body, lat, lon, radius = place
        store = self.survey_store()
        try:
            result = store.drive(system, body, lat, lon, radius)
        except Exception:
            logging.debug("Survey coverage skipped", exc_info=True)
            return None
        self._rhino_site_keep(force=False)
        if not result or not result[0]:
            return result
        percent = result[1]
        for milestone, kind in ((rhino_survey.DONE_PERCENT, "survey_done"), (rhino_survey.HALF_PERCENT, "survey_half")):
            if percent >= milestone and store.said(system, body, milestone):
                if kind == "survey_done":
                    store.said(system, body, rhino_survey.HALF_PERCENT)
                    self._rig_say("SURVEY COMPLETE", f"{body} · {percent:.0f}% covered", severity="success")
                else:
                    self._rig_say("SURVEY HALF DONE", f"{body} · {percent:.0f}% covered")
                self._rig_tell(kind, percent=f"{percent:.0f}", body=body)
                break
        return result

    def _survey_facts(self):
        """The survey, best patch and next rig spot round where you stand, in
        metres from you: for the Rig Tracker and the Mining page."""
        place = self._rig_place()
        if place is None:
            return None
        from voidcompass.overlays.rig_tracker import placed_order, rig_spacing_m, rig_warn_m
        from voidcompass.overlays.surface_map import cluster_deposits
        system, body, lat, lon, radius = place
        plane = lambda point: list(rhino_survey.offset_m((lat, lon), point, radius))
        store = self.survey_store()
        survey = store.survey(system, body)
        area = rhino_survey.survey_model(survey, plane, (0.0, 0.0)) if survey else None
        from voidcompass.overlays.surface_map import deposit_patch, marked_deposits
        deposits = marked_deposits(self._deposit_rows(system, body, near=(lat, lon, radius)), plane, (0.0, 0.0))
        patch = deposit_patch(deposits, (0.0, 0.0)) or rhino_survey.best_patch(
            cluster_deposits(self._pulses_near(system, body, lat, lon, radius), plane), (0.0, 0.0))
        rigs = self.rig_store().rigs(system, body)
        points = [plane((rigs[slot]["lat"], rigs[slot]["lon"])) for slot in placed_order(rigs)]
        config = getattr(self, "config", None) or {}
        anchor = points[0] if points else (patch or {}).get("at")
        plan = rhino_survey.rig_plan(anchor, points, rig_spacing_m(config), (0.0, 0.0), warn_m=rig_warn_m(config)) if anchor else []
        spot = next((row for row in plan if row.get("next")), None)
        from voidcompass.overlays.surface_map import traced_plan
        traced, pins = traced_plan(rig_planner.plan_here(store.plans(system, body), lat, lon, radius), plane, points,
                                   rig_spacing_m(config), (0.0, 0.0))
        centre = store.circle(system, body)
        if not area and not patch and not spot and not pins and not deposits and not centre:
            return None
        out = {"body": body, "signal": self._rhino_signal_here(), "tracing": bool(getattr(self, "_rig_trace", None))}
        if pins:
            waiting = next((pin for pin in pins if pin.get("next")), None)
            out["plan"] = {"pins": len(pins), "filled": sum(1 for pin in pins if pin["filled"]), "fits": traced["fits"],
                           "next": {"n": waiting["n"], "distance": waiting["distance"], "bearing": waiting["bearing"],
                                    "compass": _compass(waiting["bearing"])} if waiting else None}
            spot = None
        if centre:
            out["circle"] = {"room": round(rig_planner.CIRCLE_M - surface_distance_m(lat, lon, centre[0], centre[1], radius))}
        if deposits:
            live = [item for item in deposits if not item["depleted"]]
            following = next((item for item in live if item.get("n") == 1), None)
            out["deposits"] = {"marked": len(deposits), "live": len(live),
                               "next": {"commodity": following["commodity"], "rigs": following["rigs"],
                                        "distance": following["distance"], "bearing": following["bearing"],
                                        "compass": _compass(following["bearing"])} if following else None}
        if area:
            out["survey"] = {"percent": area["percent"], "edge": area["edge"], "radius_m": area["radius_m"],
                             "stops": len(area["stops"]), "swept": area["swept"], "inside": area["inside"],
                             "centre_m": area["centre_m"], "edge_ok": area["edge_ok"],
                             "centre_compass": _compass(area["centre_bearing"]) if area["centre_bearing"] is not None else "",
                             "next": {**area["next"], "compass": _compass(area["next"]["bearing"])} if area["next"] else None}
        if patch:
            out["patch"] = {**patch, "compass": _compass(patch.get("bearing"))}
            out["patch"].pop("at", None)
        if spot:
            out["rig_spot"] = {"distance": spot["distance"], "bearing": spot["bearing"], "compass": _compass(spot["bearing"]),
                               "far": bool(spot.get("far"))}
        return out

    def _survey_patch_watch(self):
        """Said when a best patch first shows, and when another patch takes the
        lead; not for one that was already there before a restart."""
        place = self._rig_place()
        if place is None:
            return False
        from voidcompass.overlays.surface_map import cluster_deposits
        system, body, lat, lon, radius = place
        pulses = self._pulses_near(system, body, lat, lon, radius)
        if not pulses:
            return False
        origin = (pulses[0][0], pulses[0][1])
        patch = rhino_survey.best_patch(cluster_deposits(pulses, lambda point: list(rhino_survey.offset_m(origin, point, radius))))
        if not patch:
            return False
        said = getattr(self, "_survey_patch_said", None)
        same_body = bool(said) and said[0] == (system, body)
        self._survey_patch_said = ((system, body), patch["at"])
        if same_body and math.hypot(said[1][0] - patch["at"][0], said[1][1] - patch["at"][1]) <= rhino_survey.PATCH_M:
            return False
        if not same_body and patch["pulses"] > rhino_survey.MIN_PATCH_PULSES:
            return False
        self._rig_tell("best_patch", pulses=patch["pulses"])
        return True

    # -- the mining location, marked deposits, rig plans, the planning circle ---------------
    def _rhino_signal_here(self):
        """The numbered mining location: the one targeted in the game, else the
        one you touched down by on this body."""
        from voidcompass.mining.planet_materials import PlanetMaterialsStore, location_index
        targeted = location_index(getattr(self, "current_destination_details", None))
        if targeted is not None:
            return targeted
        landed = getattr(self, "_rhino_touchdown_location", None) or {}
        system = str(getattr(self, "current_sys", "") or "")
        body = str(getattr(self, "current_body_name", "") or "")
        if (landed.get("location_index") is not None and str(landed.get("system") or "").casefold() == system.casefold()
                and PlanetMaterialsStore._body_key(system, landed.get("body")) == PlanetMaterialsStore._body_key(system, body)):
            return int(landed["location_index"])
        return None

    @staticmethod
    def _rhino_within(lat, lon, other_lat, other_lon, radius, reach=None):
        try:
            return surface_distance_m(lat, lon, float(other_lat), float(other_lon), radius) <= (reach or rhino_survey.LOCATION_REACH_M)
        except (TypeError, ValueError):
            return False

    def _pulses_near(self, system, body, lat, lon, radius):
        """The refining spots kept at the mining location you're at."""
        return [row for row in self.survey_store().pulses(system, body) if self._rhino_within(lat, lon, row[0], row[1], radius)]

    def _deposit_rows(self, system, body, near=None):
        """The deposits you've marked on this body (planet-materials sites);
        with ``near`` (lat, lon, planet radius), only the mining location
        you're at: those within LOCATION_REACH_M."""
        from voidcompass.mining.planet_materials import PlanetMaterialsStore
        store = getattr(self, "_planet_materials_store", None)
        if not callable(store):
            return []
        try:
            rows = store().rows()
        except Exception:
            logging.debug("Marked deposits skipped", exc_info=True)
            return []
        here = PlanetMaterialsStore._body_key(system, body)
        rows = [row for row in rows if str(row.get("system") or "").casefold() == str(system).casefold()
                and PlanetMaterialsStore._body_key(system, row.get("body")) == here
                and str(row.get("site_type") or "site") == "site"]
        if near:
            rows = [row for row in rows if self._rhino_within(near[0], near[1], row.get("latitude"), row.get("longitude"), near[2])]
        return rows

    def _deposit_near(self, system, body, lat, lon, radius, within_m=60.0):
        """(distance, row) of the nearest marked deposit within reach, or None."""
        best = None
        for row in self._deposit_rows(system, body):
            try:
                distance = surface_distance_m(lat, lon, float(row["latitude"]), float(row["longitude"]), radius)
            except (KeyError, TypeError, ValueError):
                continue
            if distance <= within_m and (best is None or distance < best[0]):
                best = (distance, row)
        return best

    def _refined_here(self, system, body, lat, lon, radius):
        """What's being refined round here: a rig's commodity close by, else the
        commonest tonne refined within 100 m."""
        from voidcompass.overlays.rig_tracker import rig_commodity
        rigs = self.rig_store().rigs(system, body)
        near = [(surface_distance_m(lat, lon, rig["lat"], rig["lon"], radius), rig) for rig in rigs.values()]
        near = sorted((pair for pair in near if pair[0] <= 60.0), key=lambda pair: pair[0])
        for _distance, rig in near:
            if rig_commodity(rig):
                return rig_commodity(rig)
        counts = {}
        for row in self.survey_store().pulses(system, body):
            if len(row) > 2 and row[2] and surface_distance_m(lat, lon, row[0], row[1], radius) <= 100.0:
                counts[row[2]] = counts.get(row[2], 0) + 1
        return max(counts, key=lambda name: (counts[name], name)) if counts else ""

    def _rhino_after_change(self):
        refresh = getattr(self, "_refresh_planet_materials_overlay", None)
        if callable(refresh):
            refresh()
        self._rig_update_overlay()
        self._update_rhino_map()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)

    def _deposit_mark_key(self):
        """Mark a deposit where you stand. Its commodity comes from what's
        refined round it; rigs, density and amount are set on the Planetary page."""
        place = self._rig_place()
        if place is None:
            self._rig_say("DEPOSIT", "Deposits are marked on a planet's surface", severity="warn")
            return None
        system, body, lat, lon, radius = place
        near = self._deposit_near(system, body, lat, lon, radius, within_m=40.0)
        if near:
            self._rig_say("DEPOSIT ALREADY MARKED", f"{near[1].get('name') or 'Deposit'} · {_distance_text(near[0])} away")
            return None
        store = getattr(self, "_planet_materials_store", None)
        if not callable(store):
            return None
        commodity = self._refined_here(system, body, lat, lon, radius)
        signal = self._rhino_signal_here()
        plan = rig_planner.plan_here(self.survey_store().plans(system, body), lat, lon, radius, within_m=PLAN_DEPOSIT_M)
        try:
            saved = store().save({"system": system, "body": body, "name": commodity or "Deposit",
                                  "latitude": lat, "longitude": lon, "materials": commodity or "Unknown", "notes": "",
                                  "site_type": "site", "planet_radius": radius, "location_index": signal,
                                  "rigs": min(64, int((plan or {}).get("fits") or 0))})
        except Exception as exc:
            logging.warning("Deposit not marked: %s", exc)
            self._rig_say("DEPOSIT", "Couldn't mark the deposit here", severity="warn")
            return None
        where = f" · signal {signal}" if signal is not None else ""
        fits = f" · {int(plan['fits'])} rigs, from your trace" if plan and plan.get("fits") else ""
        self._rig_say("DEPOSIT MARKED", f"{commodity or 'Named by the first rig to work it'}{where}{fits}", severity="success")
        self._rhino_site_keep()
        self._rhino_after_change()
        return saved

    def _deposit_mined_out_key(self):
        """The marked deposit you're on is worked out."""
        place = self._rig_place()
        if place is None:
            return None
        system, body, lat, lon, radius = place
        near = self._deposit_near(system, body, lat, lon, radius, within_m=100.0)
        if not near:
            self._rig_say("MINED OUT", "No marked deposit within 100 m", severity="warn")
            return None
        return near[1].get("id") if self._deposit_worked_out(dict(near[1])) else None

    def _deposit_worked_out(self, row):
        """MINED OUT on a deposit: worked out for the first time (or since it
        grew back), a look that found it still empty, or nothing new."""
        from voidcompass.mining import regrowth
        changes, kind = regrowth.mined_out_changes(row)
        name = row.get("name") or rhino_surface_commodity(row) or "Deposit"
        if kind != "same":
            try:
                self._planet_materials_store().save({**row, **changes})
            except Exception as exc:
                logging.warning("Deposit not marked worked out: %s", exc)
                return None
        if kind == "new":
            self._rig_say("MINED OUT", f"{name} · worth a look again in {regrowth.HOLD_DAYS} days", severity="success")
        elif kind == "recheck":
            self._rig_say("STILL WORKED OUT", f"{name} · the mark comes off in {regrowth.RECHECK_DAYS} days", severity="success")
        else:
            self._rig_say("ALREADY WORKED OUT", f"{name} · {regrowth.standing(row)['text']}")
        self._rhino_site_keep()
        self._rhino_after_change()
        return kind

    def _deposit_grown_back(self, row, by_rig=False):
        """A worked-out deposit is back: the mark off, its dates cleared."""
        from voidcompass.mining import regrowth
        if not regrowth.depleted(row):
            return False
        age = regrowth.standing(row)["age_days"]
        try:
            self._planet_materials_store().save({**row, **regrowth.regrown_changes(row)})
        except Exception as exc:
            logging.warning("Deposit not marked grown back: %s", exc)
            return False
        name = row.get("name") or rhino_surface_commodity(row) or "Deposit"
        when = f" · worked out {age} days ago" if age is not None else ""
        self._rig_say("DEPOSIT GROWN BACK", f"{name}{when}" + (" · your rig's refining it again" if by_rig else ""), severity="success")
        self._rhino_site_keep()
        self._rhino_after_change()
        return True

    def _deposit_due_watch(self):
        """Near a worked-out deposit that's due a look: said once a session.
        Marks due to come off come off (at most once an hour)."""
        from voidcompass.mining import regrowth
        place = self._rig_place()
        if place is None:
            return None
        system, body, lat, lon, radius = place
        moment = time.monotonic()
        if moment - getattr(self, "_deposit_expiry_at", -1e9) > 3600:
            self._deposit_expiry_at = moment
            self._deposit_expire_marks()
        said = getattr(self, "_deposit_due_said", None)
        if said is None:
            said = self._deposit_due_said = set()
        for row in self._deposit_rows(system, body, near=(lat, lon, radius)):
            info = regrowth.standing(row)
            if not info["due"] or row.get("id") in said:
                continue
            try:
                away = surface_distance_m(lat, lon, float(row["latitude"]), float(row["longitude"]), radius)
            except (KeyError, TypeError, ValueError):
                continue
            if away <= regrowth.DUE_NEAR_M:
                said.add(row.get("id"))
                name = row.get("name") or rhino_surface_commodity(row) or "Deposit"
                self._rig_say("RECHECK DUE", f"{name} · worked out {info['age_days']} days ago: MINED OUT if it's still empty, "
                                              "or put a rig on it if it's back", severity="warn")
                return row.get("id")
        return None

    def _deposit_expire_marks(self):
        """Every deposit looked at a week ago or more has its mark taken off."""
        from voidcompass.mining import regrowth
        store = self._planet_materials_store() if callable(getattr(self, "_planet_materials_store", None)) else None
        if store is None:
            return 0
        count = 0
        for row in store.rows():
            changes = regrowth.expiry_changes(row)
            if changes:
                try:
                    store.save({**row, **changes})
                    count += 1
                except Exception:
                    logging.debug("Depleted mark not taken off", exc_info=True)
        return count

    def _rig_trace_key(self):
        """Start tracing a deposit's edge, or close the trace where you are."""
        place = self._rig_place()
        if place is None or not getattr(self, "current_in_srv", False):
            self._rig_say("RIG PLANNER", "Trace a deposit's edge from the SRV", severity="warn")
            return None
        system, body, lat, lon, radius = place
        trace = getattr(self, "_rig_trace", None)
        if trace and trace["body"] == (system, body):
            if trace["trace"].close():
                return self._rig_trace_finish()
            self._rig_trace = None
            self._rig_say("RIG PLANNER", "Trace cancelled: drive round the deposit's edge first", severity="warn")
            self._update_rhino_map()
            return None
        self._rig_trace = {"body": (system, body), "trace": rig_planner.Trace(lat, lon, radius)}
        self._rig_say("TRACING THE DEPOSIT", "Drive round its edge back to here; the key again closes it early")
        self._update_rhino_map()
        return "tracing"

    def _rig_trace_tick(self):
        trace = getattr(self, "_rig_trace", None)
        if not trace:
            return None
        place = self._rig_place()
        if place is None or trace["body"] != (place[0], place[1]):
            self._rig_trace = None
            return None
        if trace["trace"].add(place[2], place[3]):
            return self._rig_trace_finish()
        if trace["trace"].too_big:
            self._rig_trace = None
            self._rig_say("RIG PLANNER", "That went over 3 km from the start: not a deposit's edge. Trace stopped", severity="warn")
            self._update_rhino_map()
        return None

    def _rig_trace_finish(self):
        """The trace is closed: the pins are worked out off the UI thread (a big
        deposit takes most of a second), then kept and shown."""
        trace = self._rig_trace
        self._rig_trace = None
        place = self._rig_place()
        if not trace or place is None:
            return None
        system, body, lat, lon, radius = place
        spacing = rig_spacing_m(getattr(self, "config", None) or {})
        self._rig_say("RIG PLANNER", "Working out where the rigs fit…")

        def work():
            try:
                record = rig_planner.plan_record(trace["trace"], spacing, start=(lat, lon), now=time.time())
            except Exception:
                logging.exception("Rig plan failed")
                return
            post = getattr(self, "_ui_post", None)
            if callable(post):
                post(lambda: self._rig_plan_ready(system, body, radius, spacing, record), key="rig-plan")
            else:
                self._rig_plan_ready(system, body, radius, spacing, record)

        threading.Thread(target=work, name="RigPlan", daemon=True).start()
        return "planning"

    def _rig_plan_ready(self, system, body, radius, spacing, record):
        self.survey_store().add_plan(system, body, record, radius)
        count = len(record["pins"])
        more = f" ({record['fits']} fit in all)" if record["fits"] > count else ""
        self._rig_say("RIG PLAN READY", f"{count} rig{'s' if count != 1 else ''} at {spacing} m{more} · P1 first", severity="success")
        self._deposit_rigs_from_plan(system, body, radius, record)
        self._rhino_site_keep()
        self._rhino_after_change()
        return record

    def _deposit_rigs_from_plan(self, system, body, radius, record):
        """The deposit a traced plan is on takes its rig count (how many fit,
        which can be more than the Rhino's six), if you haven't set one. One
        you've set is left alone; you're told when they differ."""
        middle = record.get("middle") or ()
        fits = int(record.get("fits") or 0)
        if len(middle) != 2 or fits <= 0:
            return None
        on = self._deposit_near(system, body, middle[0], middle[1], radius, within_m=PLAN_DEPOSIT_M)
        if not on:
            return None
        row = dict(on[1])
        name = row.get("name") or rhino_surface_commodity(row) or "Deposit"
        if int(row.get("rigs") or 0) == fits:
            return fits
        if int(row.get("rigs") or 0):
            self._rig_say("RIGS IT TAKES", f"Your trace fits {fits} on {name}; it's set to {int(row['rigs'])} (the Rhino page changes it)")
            return None
        try:
            self._planet_materials_store().save({**row, "rigs": min(64, fits)})
        except Exception:
            logging.debug("Deposit rigs not set from the plan", exc_info=True)
            return None
        self._rig_say("RIGS IT TAKES", f"{name} · {fits} rig{'s' if fits != 1 else ''}, from your trace", severity="success")
        return fits

    def _rig_forget_plan(self):
        place = self._rig_place()
        if place is None:
            return False
        system, body, lat, lon, radius = place
        record = rig_planner.plan_here(self.survey_store().plans(system, body), lat, lon, radius)
        done = bool(record) and self.survey_store().forget_plan(system, body, record.get("middle"))
        if done:
            self._rig_say("RIG PLAN FORGOTTEN", body)
            self._rhino_after_change()
        return done

    def _rig_circle_key(self):
        """The planning circle: 4.5 km round here, or cleared when you're by its centre."""
        place = self._rig_place()
        if place is None:
            self._rig_say("PLANNING CIRCLE", "Set it on a planet's surface", severity="warn")
            return None
        system, body, lat, lon, radius = place
        store = self.survey_store()
        centre = store.circle(system, body)
        if centre and surface_distance_m(lat, lon, centre[0], centre[1], radius) <= 200.0:
            store.clear_circle(system, body)
            self._rig_say("PLANNING CIRCLE CLEARED", body)
            outcome = "cleared"
        else:
            store.set_circle(system, body, lat, lon)
            self._rig_say("PLANNING CIRCLE", "4.5 km round here: rig and drive inside it and no rig gets left 5 km behind",
                          severity="success")
            outcome = "set"
        self._circle_out_said = False
        self._rhino_after_change()
        return outcome

    def _rig_circle_watch(self):
        """Said once when you drive out of the planning circle, again only after
        you've been back well inside."""
        place = self._rig_place()
        if place is None or not getattr(self, "current_in_srv", False):
            return False
        system, body, lat, lon, radius = place
        centre = self.survey_store().circle(system, body)
        if not centre:
            return False
        room = rig_planner.CIRCLE_M - surface_distance_m(lat, lon, centre[0], centre[1], radius)
        if room < 0 and not getattr(self, "_circle_out_said", False):
            self._circle_out_said = True
            self._rig_say("OUTSIDE THE PLANNING CIRCLE", f"{_distance_text(-room)} past its edge", severity="warn")
            return True
        if room > 200:
            self._circle_out_said = False
        return False

    def _rig_range_watch(self):
        """A rig getting too far away: said once a trip, as the game destroys
        it at 5 km. Said again only after you've been back near."""
        self._rig_circle_watch()
        from voidcompass.overlays.rig_tracker import LOST_M, rig_advice, rig_warn_m
        warn = rig_warn_m(getattr(self, "config", None) or {})
        model = self._rig_model()
        advice = rig_advice((model or {}).get("slots"), warn_m=warn) if model else {"too_far": [], "ready": []}
        far = {row["slot"]: row for row in advice["too_far"]} if warn else {}
        # 5.7.5: a rig that has had its time (learnt from your rigs), with you beside it, once.
        ready_said = getattr(self, "_rig_ready_said", None)
        if ready_said is None:
            ready_said = self._rig_ready_said = set()
        for slot in advice["ready"]:
            if slot not in ready_said:
                ready_said.add(slot)
                self._rig_tell("rig_ready", slot=slot)
        warned = getattr(self, "_rig_far_warned", None)
        if warned is None:
            warned = self._rig_far_warned = set()
        for slot, row in far.items():
            if slot not in warned:
                warned.add(slot)
                left = max(0, round((LOST_M - row["distance"]) / 100) / 10)
                self._rig_say(f"RIG {slot} TOO FAR", f"{row['distance'] / 1000:.1f} km away · lost at 5 km ({left:.1f} km to go)",
                              severity="warn")
                self._rig_tell("rig_far", slot=slot, km=f"{row['distance'] / 1000:.1f}")
        rows = {row["slot"]: row for row in (model or {}).get("slots") or () if row.get("tracked")}
        place = self._rig_place()
        lost = [slot for slot, row in rows.items() if (row.get("distance_m") or 0) >= LOST_M]
        if lost and place:
            # The game has destroyed these: stop showing them.
            for slot in lost:
                self.rig_store().forget(place[0], place[1], slot)
                warned.discard(slot)
                self._rig_say(f"RIG {slot} LOST", "More than 5 km behind: the game takes it back", severity="warn")
                self._rig_tell("rig_lost", slot=slot)
                ready_said.discard(slot)
            self._rig_update_overlay()
            self._update_rhino_map()
        for slot in list(warned):
            row = rows.get(slot)
            if row is None or row["distance_m"] < warn - 200:
                warned.discard(slot)
        return bool(far)

    # -- moving on to another mining location -----------------------------------------
    def _rhino_location_watch(self):
        """Far from the survey (or the planning circle), or at another signal
        a couple of km off: you've moved on. The location you left is saved
        and its survey and circle put away, so this one starts clean. Returns
        the site saved, True when only a circle went, or None."""
        place = self._rig_place()
        if place is None:
            return None
        system, body, lat, lon, radius = place
        store = self.survey_store()
        survey = store.survey(system, body)
        circle = store.circle(system, body)
        anchor = (survey or {}).get("centre") or circle
        if not anchor:
            return None
        away = surface_distance_m(lat, lon, anchor[0], anchor[1], radius)
        signal = self._rhino_signal_here()
        other = (signal is not None and (survey or {}).get("signal") is not None
                 and int(signal) != int(survey["signal"]) and away > rhino_survey.SITE_SAME_M)
        if away <= rhino_survey.LOCATION_REACH_M and not other:
            return None
        site = None
        if survey:
            try:
                site = self._rhino_site_save(auto=True, system=system, body=body, quiet=True)
            except Exception:
                logging.debug("Rhino site not saved on moving on", exc_info=True)
            store.clear(system, body)
        if circle:
            store.clear_circle(system, body)
        trace = getattr(self, "_rig_trace", None)
        if trace and trace.get("body") == (system, body):
            self._rig_trace = None
        words = f"{site['name']} saved · SITES on the Rhino page" if site else "the last one's survey and circle put away"
        self._rig_say("NEW MINING LOCATION", words, severity="info")
        self._rhino_after_change()
        return site or True

    # -- saved mining locations --------------------------------------------------------
    def _rhino_site_snapshot(self, system, body, radius, here=None):
        """Everything worth keeping about the mining location here: its survey,
        the deposits inside it, the rig plans and what your rigs got."""
        from voidcompass.mining.planet_materials import PlanetMaterialsStore
        store = self.survey_store()
        survey = store.survey(system, body)
        centre = list(survey["centre"]) if survey else None
        if centre is None and radius:
            # No survey: the middle of the deposits marked round here (or, once
            # you've left, round the last one marked).
            rows = []
            for row in self._deposit_rows(system, body):
                try:
                    rows.append((float(row["latitude"]), float(row["longitude"]), str(row.get("updated_at") or ""), row))
                except (KeyError, TypeError, ValueError):
                    continue
            anchor = tuple(here) if here else (max(rows, key=lambda item: item[2])[:2] if rows else None)
            near = [item for item in rows if anchor and surface_distance_m(anchor[0], anchor[1], item[0], item[1], radius)
                    <= rhino_survey.LOCATION_REACH_M]
            if near:
                centre = [sum(item[0] for item in near) / len(near), sum(item[1] for item in near) / len(near)]
            elif here:
                centre = list(here)
        if not centre or not radius:
            return None
        reach = (survey["radius_m"] if survey and survey.get("edge") else rhino_survey.DEFAULT_RADIUS_M) + 200.0
        inside = []
        for row in self._deposit_rows(system, body):
            try:
                if surface_distance_m(centre[0], centre[1], float(row["latitude"]), float(row["longitude"]), radius) <= reach:
                    inside.append(row)
            except (KeyError, TypeError, ValueError):
                continue
        live = [row for row in inside if not row.get("depleted")]
        kinds = {}
        for row in live:
            name = rhino_surface_commodity(row)
            if name and name != "Unknown":
                kinds[name] = kinds.get(name, 0) + 1
        commodities = sorted(kinds, key=lambda name: -kinds[name])
        plans = [plan for plan in store.plans(system, body) if len(plan.get("middle") or ()) == 2
                 and surface_distance_m(centre[0], centre[1], plan["middle"][0], plan["middle"][1], radius) <= reach]
        signal = (survey or {}).get("signal")
        if signal is None and str(getattr(self, "current_body_name", "") or "").casefold() == str(body).casefold():
            signal = self._rhino_signal_here()
        short = str(body)
        if short.casefold().startswith(f"{system} ".casefold()):
            short = short[len(system) + 1:]
        name = f"{short} · signal {signal}" if signal is not None else f"{short} · {commodities[0]}" if commodities else short
        record = {
            "name": name, "signal": signal, "centre": [round(centre[0], 6), round(centre[1], 6)], "planet_radius": radius,
            "deposits": {"ids": [row.get("id") for row in inside], "live": len(live), "mined": len(inside) - len(live),
                         "rigs": sum(int(row.get("rigs") or 0) for row in live), "commodities": commodities[:8]},
            "plans": plans[-4:], "tonnes": self.rig_store().tonnes_on(system, body),
        }
        if survey:
            percent = rhino_survey.progress(survey["covered"], survey["radius_m"], survey["grid"])[0] if survey["edge"] else 0.0
            record["survey"] = {"centre": list(survey["centre"]), "radius_m": survey["radius_m"], "edge": survey["edge"],
                                "grid": survey["grid"], "bits": rhino_survey.bits_text(survey["covered"]), "percent": percent,
                                "trail": survey.get("trail") or []}
        return record

    def _rhino_site_keep(self, force=True, place=None):
        """Keep the site you're working saved as you go, so it's in SITES
        however you leave (or if the game closes): after each piece of work,
        and at least every SITE_KEEP_S while you sweep."""
        place = place or self._rig_place()
        if place is None:
            return None
        key = (place[0].casefold(), place[1].casefold())
        kept = getattr(self, "_rhino_site_kept", None)
        if kept is None:
            kept = self._rhino_site_kept = {}
        now = time.monotonic()
        if not force and now - kept.get(key, -1e9) < rhino_survey.SITE_KEEP_S:
            return None
        kept[key] = now
        try:
            return self._rhino_site_save(auto=True, system=place[0], body=place[1], quiet=True, refresh=False)
        except Exception:
            logging.debug("Rhino site not kept", exc_info=True)
            return None

    def _rhino_site_save(self, auto=False, system=None, body=None, quiet=False, refresh=True):
        """SAVE THIS SITE (or leaving the planet): the mining location kept, or
        brought up to date. Returns the site, or None."""
        place = self._rig_place()
        if system is None:
            if place is None:
                self._rig_say("RHINO SITE", "Sites are saved on a planet's surface", severity="warn")
                return None
            system, body = place[0], place[1]
        on_it = bool(place) and (place[0].casefold(), place[1].casefold()) == (str(system).casefold(), str(body).casefold())
        radius = (place[4] if on_it else None) or self.survey_store().planet_radius(system, body)
        if not radius:
            radius = next((row.get("planet_radius") for row in self._deposit_rows(system, body) if row.get("planet_radius")), None)
        if not radius and str(getattr(self, "current_body_name", "") or "").casefold() == str(body).casefold():
            radius = getattr(self, "current_planet_radius", None)
        here = (place[2], place[3]) if on_it else None
        if auto and not self.survey_store().survey(system, body) and not self._deposit_rows(system, body):
            return None
        record = self._rhino_site_snapshot(system, body, radius, here)
        if record is not None and auto and not record.get("survey") and not record["deposits"]["ids"]:
            record = None
        if record is None:
            if not auto:
                self._rig_say("RHINO SITE", "Nothing to save here yet: mark the survey centre or a deposit", severity="warn")
            return None
        site = self.survey_store().save_site(system, body, record, radius)
        if quiet:
            pass
        elif auto:
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("MINING", f"Rhino site saved as you left: {site['name']}", severity="INFO")
        else:
            words = f"{site['deposits']['live']} deposit{'s' if site['deposits']['live'] != 1 else ''}"
            if site.get("survey"):
                words += f" · {int(site['survey']['percent'])}% swept"
            self._rig_say("SITE SAVED", f"{site['name']} · {words}", severity="success")
        if refresh:
            self._rhino_after_change()
        return site

    def _rhino_site_here(self, place=None):
        """The saved site you're at, if any: the one of this signal, else the
        nearest within the mining location's reach (a Rhino works a few km
        round its site's centre)."""
        place = place or self._rig_place()
        if place is None:
            return None
        system, body, lat, lon, radius = place
        signal = self._rhino_signal_here()
        near = []
        for site in self.survey_store().sites(system, body):
            centre = site.get("centre") or ()
            if len(centre) != 2:
                continue
            apart = surface_distance_m(lat, lon, centre[0], centre[1], radius)
            if apart > rhino_survey.LOCATION_REACH_M:
                continue
            if signal is not None and site.get("signal") is not None:
                if int(site["signal"]) == int(signal):
                    return site
                if apart > rhino_survey.SITE_SAME_M:
                    continue
            near.append((apart, site))
        return min(near, key=lambda item: item[0])[1] if near else None

    def _rig_left_body(self, body):
        """Leaving a planet takes you far past 5 km, so any rigs left on it are
        gone. Kept, they'd bring the ground map back on the next visit. A site
        surveyed or marked there is saved first."""
        system = str(getattr(self, "current_sys", "") or "")
        self._rhino_aboard = None
        if body:
            try:
                self._rhino_site_save(auto=True, system=system, body=str(body))
            except Exception:
                logging.debug("Rhino site not saved on leaving", exc_info=True)
        if not body or not self.rig_store().clear(system, str(body)):
            return False
        self._rig_say("RIGS LEFT BEHIND", f"{body}: rigs still out there are lost", severity="warn")
        self._rig_tell("rigs_left_behind", body=body)
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

    def _rhino_gravity(self):
        """The surface gravity of the body you're on, in g, from its scan."""
        item = (getattr(self, "scan_items_by_id", None) or {}).get(getattr(self, "current_body_id", None)) or {}
        try:
            return float(item["gravity_g"]) if item.get("gravity_g") is not None else None
        except (TypeError, ValueError):
            return None

    def _rhino_page_refresh(self, now=False):
        """Redraw the Rhino page while it's open: straight away when you change
        vehicle or hold, at most once a second as you drive."""
        if getattr(self, "_html_dashboard_active_page", "") != "rhino":
            return False
        moment = time.monotonic()
        if not now and moment - getattr(self, "_rhino_page_published", 0.0) < 1.0:
            return False
        self._rhino_page_published = moment
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=now)
        return True

    def _rhino_surface_fresh(self):
        """The Rhino map's model from this moment, or a new one."""
        last = getattr(self, "_rhino_surface_last", None)
        if last and time.monotonic() - last[0] < 1.5:
            return last[1]
        return self._surface_map_model(force=True)

    def _rig_sections_model(self, surface):
        """The Rig Tracker's Rhino sections (guide, deposit, targets, status)."""
        from voidcompass.overlays.rig_sections import section_options, sections_model
        config = getattr(self, "config", None) or {}
        options = section_options(config)
        if not any(options.values()):
            return None
        keys = self._rhino_keys() if callable(getattr(self, "_rhino_keys", None)) else {}
        try:
            threshold = float(config.get("gravity_warning_threshold_g") or 3.0)
        except (TypeError, ValueError):
            threshold = 3.0
        return sections_model(surface, keys=keys, holds=self._rig_holds(), gravity=self._rhino_gravity(),
                              threshold=threshold, options=options, prices=self._rhino_prices())

    def _update_rhino_map(self):
        hud = getattr(self, "rhino_map_hud", None)
        rigs = getattr(self, "rig_tracker_hud", None)
        if hud is None and rigs is None:
            return False
        try:
            model = self._surface_map_model()
            self._rhino_surface_last = (time.monotonic(), model) if model else None
            shown = hud.update(model) if hud is not None else False
            if rigs is not None:
                self._rig_update_overlay(surface=model)
            return shown
        except Exception:
            logging.exception("Rhino map update failed")
            return False

    def _rig_update_overlay(self, surface=None):
        hud = getattr(self, "rig_tracker_hud", None)
        if hud is None:
            return False
        try:
            model = self._rig_model()
            if model is not None and model.get("aboard"):
                # Back in the ship: the run's summary, not the working sections.
                model["survey"], model["sections"] = None, None
            elif model is not None:
                model["survey"] = self._survey_facts()
                if surface is None:
                    # The Rhino map's model from this tick, or one of our own
                    # (the map can be off while the Rig Tracker is up).
                    surface = self._rhino_surface_fresh()
                model["sections"] = self._rig_sections_model(surface)
            hud.update(model)
        except Exception:
            logging.exception("Rig Tracker overlay update failed")
            return False
        return True
