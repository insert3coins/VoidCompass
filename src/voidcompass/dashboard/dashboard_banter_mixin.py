"""Crew banter (5.7.7): the deck's side of the crew talking to each other.

Journal events and the deck's own clock turn into moments (crew_banter.py
has the words and the rules). Only companions whose voice is on take part:
the one on watch, and crewmates you've flown with. What's been heard is kept
per commander, so a long session, or a long career, doesn't repeat itself.
"""

from __future__ import annotations

import json
import logging
import random
import time

from voidcompass.core.discovery import new_ground, our_first
from voidcompass.core import companions, discovery, home_anchor
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.core.persistence_queue import persistence_queue
from voidcompass.orders.generators import spoken_credits
from voidcompass.overlays import crew_banter, watcher_mind

JUMP_RUN_EVERY = 15
FAR_STEP_LY = 1000
LONG_SESSION_HOURS = (2, 4, 6, 8)
HEAT_FLAG = 1 << 20
WORTHY = {"earthlike body", "water world", "ammonia world"}
DATA_SOLD_MIN = 1_000_000
TRADE_PROFIT_MIN = 500_000
HEARD_LIMIT = 3000


def _fresh():
    return {"heard": {}, "last": 0.0, "moments": {}, "far": None}


class DashboardBanterMixin:
    # -- setup -----------------------------------------------------------------
    def _banter_init(self, profile_key=None):
        key = profile_key or get_active_profile(self.config)
        self._banter_path = get_profile_file(key, "crew_banter.json")
        data = _fresh()
        try:
            with open(self._banter_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                data.update({name: loaded[name] for name in data if name in loaded and loaded[name] is not None})
        except (OSError, ValueError):
            pass
        self._banter_data = data
        self._banter_reset_session()
        self._banter_why = ""
        # The crew wait for each other's voices (watcher_mind.order_line/crew_say).
        watcher_mind.VOICE_BUSY = self._banter_voice_busy
        # And only ask you to scan where it's worth it (EDSM traffic).
        if hasattr(self, "_system_quiet"):
            watcher_mind.SYSTEM_QUIET = self._system_quiet
        # And only call a discovery yours when no other commander is on record.
        if hasattr(self, "_someone_else_found"):
            discovery.SOMEONE_ELSE = self._someone_else_found
            discovery.WALKED_BEFORE = self._walked_before

    def _banter_reset_session(self):
        self._banter_session = {"jumps": 0, "star": "", "mined": False, "low_fuel": False, "heat": False, "danger": False,
                                "hours": 0, "idle_rolled": 0.0, "scooped": False}

    def _banter_switch_profile(self, profile_key):
        self._banter_save(immediate=True)
        self._banter_init(profile_key)

    def _banter_save(self, immediate=False):
        path = getattr(self, "_banter_path", None)
        if not path:
            return
        try:
            persistence_queue().submit_json(path, dict(self._banter_data), indent=None, delay_s=0.0 if immediate else 2.0)
        except Exception:
            logging.debug("Crew banter memory not saved", exc_info=True)

    def _banter_voice_busy(self):
        speaker = getattr(self, "_watcher_voice", None)
        try:
            return bool(speaker is not None and speaker.busy())
        except Exception:
            return False

    # -- who can talk --------------------------------------------------------------
    def _banter_mind(self):
        return getattr(getattr(self, "heartbeat_hud", None), "mind", None)

    def _banter_speakers(self):
        """The one on watch, then each crewmate you've flown with, all with
        their voices on. Banter is heard, never just read."""
        on_watch = companions.identity(self.config)
        try:
            if not self._watcher_voice_on():
                return []
        except Exception:
            return []
        mind = self._banter_mind()
        flown = set(getattr(mind, "_crew_flown", ()) or ())
        crew = [on_watch]
        for identity in crew_banter.SPEAKERS:
            if identity == on_watch or identity not in flown:
                continue
            try:
                if self._crewmate_voice_on(identity):
                    crew.append(identity)
            except Exception:
                continue
        return crew

    # -- one exchange -----------------------------------------------------------------
    def _banter(self, moment, fields=None, now=None, roll=True):
        """Start an exchange for this moment, if the rules allow: True when one
        was queued."""
        now = time.time() if now is None else now
        mind = self._banter_mind()
        if mind is None or not hasattr(mind, "crew_say"):
            return False
        if getattr(mind, "_crew_queue", None):
            self._banter_why = "The crew already have something to say"
            return False
        speakers = self._banter_speakers()
        facts = {"session_start": getattr(mind, "_session_start", None), "in_danger": bool(getattr(mind, "_in_danger", False)),
                 "speakers": len(speakers)}
        allowed, why = crew_banter.may_talk(self.config, moment, now, self._banter_data, facts)
        self._banter_why = why
        if not allowed:
            return False
        if roll and random.random() > crew_banter.chance(self.config):
            return False
        chosen = crew_banter.choose(moment, speakers, speakers[0], self._banter_data["heard"], random, fields,
                                    most=crew_banter.size(self.config),
                                    lines=crew_banter.LENGTHS[crew_banter.length(self.config)])
        if chosen is None:
            self._banter_why = "Nothing fits these companions just now"
            return False
        exchange, lines = chosen
        for speaker, text in lines:
            mind.crew_say(speaker, text, heading=crew_banter.NAMES.get(speaker, speaker.upper()), topic="crew_banter")
        data = self._banter_data
        data["heard"][exchange] = now
        if len(data["heard"]) > HEARD_LIMIT:
            for old in sorted(data["heard"], key=data["heard"].get)[:len(data["heard"]) - HEARD_LIMIT]:
                data["heard"].pop(old, None)
        data["last"] = now
        data["moments"][moment] = now
        self._banter_save()
        return True

    # -- moments from the journal -----------------------------------------------------
    def _banter_observe(self, event, raw, startup_replay=False):
        if startup_replay or not isinstance(raw, dict) or not hasattr(self, "_banter_data"):
            return
        try:
            self._banter_event(str(event or raw.get("event") or ""), raw)
        except Exception:
            logging.debug("Crew banter skipped [%s]", event, exc_info=True)

    def _banter_event(self, event, raw):
        session = self._banter_session
        if event == "LoadGame":
            self._banter_reset_session()
            return
        if event == "StartJump" and raw.get("JumpType") == "Hyperspace":
            session["star"] = str(raw.get("StarClass") or "")
            return
        if event in {"FSDJump", "CarrierJump"}:
            if event == "FSDJump":
                session["jumps"] += 1
                if session["jumps"] % JUMP_RUN_EVERY == 0 and self._banter("jump_run", {"jumps": session["jumps"]}):
                    return
            star, session["star"] = session.get("star") or "", ""
            if star.upper().startswith("H") and self._banter("black_hole"):
                return
            if star.upper() == "N" and self._banter("neutron"):
                return
            self._banter_far(raw)
            return
        if event == "Scan":
            if raw.get("StarType") and float(raw.get("DistanceFromArrivalLS") or 0) == 0 and our_first(raw):
                self._banter("first_discovery", {"system": raw.get("StarSystem") or getattr(self, "current_sys", "")})
            elif str(raw.get("PlanetClass") or "").casefold() in WORTHY and not self._banter_mapped(raw):
                self._banter("worthy_world", {"body": raw.get("BodyName")})
            return
        if event == "CodexEntry" and raw.get("IsNewEntry"):
            self._banter("codex")
        elif event == "ScanOrganic" and raw.get("ScanType") == "Analyse":
            self._banter("bio_done", {"species": raw.get("Species_Localised") or raw.get("Variant_Localised")})
        elif event == "Touchdown" and raw.get("PlayerControlled") is not False:
            self._banter("landing", {"body": raw.get("Body")})
        elif event == "Disembark" and raw.get("OnPlanet"):
            bodies = (getattr(self, "_orders_place", None) or {}).get("bodies") or {}
            if (bodies.get(str(raw.get("Body") or "").casefold()) or {}).get("footfalled") is False and new_ground(raw):
                self._banter("footfall", {"body": raw.get("Body")})
        elif event in {"SellExplorationData", "MultiSellExplorationData"}:
            total = int(raw.get("TotalEarnings") or 0) or int(raw.get("BaseValue") or 0) + int(raw.get("Bonus") or 0)
            if total >= DATA_SOLD_MIN:
                self._banter("data_sold", {"credits": spoken_credits(total)})
        elif event == "Docked":
            self._banter("docked", {"station": raw.get("StationName")})
        elif event == "Undocked":
            self._banter("launch")
        elif event == "MarketSell" and not raw.get("StolenGoods"):
            paid = int(raw.get("AvgPricePaid") or 0)
            profit = (int(raw.get("SellPrice") or 0) - paid) * int(raw.get("Count") or 0) if paid else 0
            if profit >= TRADE_PROFIT_MIN:
                self._banter("trade_profit", {"credits": spoken_credits(profit)})
        elif event == "MiningRefined" and not session["mined"]:
            session["mined"] = True
            self._banter("mined")
        elif event == "FuelScoop":
            capacity = float(getattr(self, "fuel_capacity_main", 0) or 0)
            full = capacity > 0 and float(raw.get("Total") or 0) >= capacity * .99
            if full and not session["scooped"]:
                session["scooped"] = True
                self._banter("scooped")
            elif not full:
                session["scooped"] = False
        elif event == "Resurrect":
            self._banter("ship_lost", roll=False)

    def _banter_mapped(self, raw):
        """Already mapped: by anyone before (the Scan says so), or by you just
        now. The game writes a fresh Scan right after your own probes finish,
        and the crew asked you to map a world you'd just mapped (8 November)."""
        if raw.get("WasMapped") is True:
            return True
        bodies = (getattr(self, "_orders_place", None) or {}).get("bodies") or {}
        return bool((bodies.get(str(raw.get("BodyName") or "").casefold()) or {}).get("mapped"))

    def _banter_far(self, raw):
        """A new furthest from home, at each thousand light years."""
        home = home_anchor.home(self.config).get("pos")
        pos = raw.get("StarPos")
        if not home or not pos:
            return
        try:
            gap = sum((float(a) - float(b)) ** 2 for a, b in zip(pos, home)) ** .5
        except (TypeError, ValueError):
            return
        data = self._banter_data
        if data.get("far") is None:
            # The first fix sets the mark; only going past it later is news.
            data["far"] = gap
            self._banter_save()
            return
        if gap > float(data["far"]):
            step = int(gap // FAR_STEP_LY)
            crossed = step > int(float(data["far"]) // FAR_STEP_LY)
            data["far"] = gap
            self._banter_save()
            if crossed:
                self._banter("far_record", {"distance": f"{step * FAR_STEP_LY:,} ly"})

    # -- moments from the clock -----------------------------------------------------------
    def _banter_tick(self, now=None):
        if not hasattr(self, "_banter_data") or crew_banter.frequency(self.config) == "off":
            return
        now = time.time() if now is None else now
        mind = self._banter_mind()
        if mind is None:
            return
        session = self._banter_session
        # Low fuel and heat: once each time they happen.
        try:
            capacity = float(getattr(self, "fuel_capacity_main", 0) or 0)
            fuel = float(getattr(self, "current_fuel_main", 0) or 0)
            percent = fuel * 100 / capacity if capacity else None
        except (TypeError, ValueError, ZeroDivisionError):
            percent = None
        threshold = float(self.config.get("low_fuel_threshold_pct") or .25) * 100
        docked = bool(getattr(self, "current_docked", False))
        if percent is not None and not docked:
            if percent <= threshold and not session["low_fuel"]:
                session["low_fuel"] = True
                self._banter("low_fuel", {"fuel": round(percent)}, now)
            elif percent > threshold + 5:
                session["low_fuel"] = False
        hot = bool(int(getattr(self, "current_status_flags", 0) or 0) & HEAT_FLAG)
        if hot and not session["heat"]:
            session["heat"] = True
            self._banter("heat", now=now)
        elif not hot:
            session["heat"] = False
        # Out of danger: a breath, together.
        danger = bool(getattr(mind, "_in_danger", False))
        if session["danger"] and not danger:
            self._banter("escaped", now=now)
        session["danger"] = danger
        # A long session, at two, four, six and eight hours.
        started = getattr(mind, "_session_start", None)
        if started:
            hours = int((now - float(started)) // 3600)
            due = [mark for mark in LONG_SESSION_HOURS if mark <= hours and mark > session["hours"]]
            if due:
                session["hours"] = due[-1]
                self._banter("long_session", {"hours": due[-1]}, now)
        # A quiet stretch: one roll of the dice per stretch.
        quiet_since = max(float(getattr(mind, "_last_spoke", 0) or 0), float(self._banter_data.get("last") or 0))
        if now - quiet_since >= crew_banter.IDLE_AFTER_S and session["idle_rolled"] < quiet_since:
            session["idle_rolled"] = now
            self._banter("idle", now=now)

    # -- the companion page ---------------------------------------------------------------
    def _banter_settings(self):
        config = self.config
        return {
            "crew_banter": crew_banter.frequency(config),
            "crew_banter_gap": str(int(crew_banter.gap_s(config) // 60)),
            "crew_banter_size": next((name for name, count in crew_banter.SIZES.items() if count == crew_banter.size(config)),
                                     crew_banter.DEFAULT_SIZE),
            "crew_banter_length": crew_banter.length(config),
            **{f"crew_banter_{group}": config.get(f"crew_banter_{group}", True) is not False for group in crew_banter.GROUPS},
            "banter_status": self._banter_status(),
        }

    def _banter_status(self):
        speakers = self._banter_speakers() if hasattr(self, "_banter_data") else []
        names = [crew_banter.NAMES.get(name, name).title().replace("The Watcher", "the Watcher") for name in speakers]
        if crew_banter.frequency(self.config) == "off":
            return "Banter is off."
        if len(speakers) < 2:
            return "Needs two companions with their voices on (the one on watch, and a crewmate you've flown with)."
        return f"Can talk now: {', '.join(names)}."

    def _banter_save_settings(self, values):
        """The companion page's Crew banter settings. Returns the values it
        didn't handle, or None when one was bad."""
        values = dict(values)
        if "crew_banter" in values:
            choice = str(values.pop("crew_banter") or "").casefold()
            if choice not in crew_banter.FREQUENCIES:
                return None
            self.config["crew_banter"] = choice
        if "crew_banter_gap" in values:
            try:
                minutes = int(float(values.pop("crew_banter_gap")))
            except (TypeError, ValueError):
                return None
            if minutes not in crew_banter.GAPS:
                return None
            self.config["crew_banter_gap"] = minutes
        if "crew_banter_size" in values:
            choice = str(values.pop("crew_banter_size") or "").casefold()
            if choice not in crew_banter.SIZES:
                return None
            self.config["crew_banter_size"] = choice
        if "crew_banter_length" in values:
            choice = str(values.pop("crew_banter_length") or "").casefold()
            if choice not in crew_banter.LENGTHS:
                return None
            self.config["crew_banter_length"] = choice
        for group in crew_banter.GROUPS:
            key = f"crew_banter_{group}"
            if key in values:
                self.config[key] = bool(values.pop(key))
        return values
