"""The smaller things from ED-Outrider (5.7.8, github.com/weslocke/ED-Outrider,
GPLv3), each a line from the companion on watch:

- before you jump: what's at the system you've targeted, and money you'd leave behind;
- a potential green gas giant as you scan it (always "potential": the community's
  ladder model, CMDR Regza, Dr. K. Ross, CMDR Arcanic and Canonn);
- where your landing pad is, with a small diagram on the Dashboard (bgol's LandingPad tables);
- fuel from your own jumps: per hop, jumps left at your pace, seconds to a full tank;
- crew warnings: wanted, the wrong suit for biology, oxygen or health low with data
  aboard, no limpets on undock;
- the best rock of a mining stint and a recap after it;
- a sound as you target a system (a fanfare, an upbeat pair or a thud);
- "sell here" at a station that buys the data you carry;
- a sample run you'd lose, and the one you just lost;
- modules the AFMU left switched off after a repair (tried in game by Outrider, 2026-11-09).

Nothing here has been tried in a live game by Outrider either for pads, the
wrong suit, wanted, ring timing; treat them as untested.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time

from voidcompass.core import companions
from voidcompass.core.config import get_active_profile
from voidcompass.outrider import fsd, ggg, pads

logger = logging.getLogger(__name__)

FUEL_SAMPLES = 40
FLAG_SHIELDS_UP = 1 << 3
FLAG_IN_DANGER = 1 << 22
# Modules worth a word when the AFMU leaves them off, in the order they're said.
MODULE_WORDS = (("lifesupport", "life support"), ("hyperdrive", "frame shift drive"), ("engine", "thrusters"),
                ("powerdistributor", "power distributor"), ("sensors", "sensors"), ("fuelscoop", "fuel scoop"),
                ("shieldgenerator", "shields"))
MODULES_SETTLE_S = 20


def module_rank(item):
    return next((n for n, (part, _) in enumerate(MODULE_WORDS) if str(item).startswith(f"int_{part}")), len(MODULE_WORDS))


def module_words(item, label=None):
    import re
    rank = module_rank(item)
    if rank < len(MODULE_WORDS):
        return MODULE_WORDS[rank][1]
    return re.sub(r"\s*\([^)]*\)", "", str(label or "")).strip().lower() or "a module"


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DashboardSmallsMixin:

    def _small_say(self, text, heading="", topic="small_moment", key=None):
        """A line from whoever's on watch; a toast too when it matters."""
        mind = getattr(self, "_orders_mind", lambda: None)()
        if mind is not None and hasattr(mind, "crew_say"):
            try:
                mind.crew_say(companions.identity(self.config), text, heading=heading, topic=topic, converse=False, key=key)
                return True
            except Exception:
                logger.debug("Line not said", exc_info=True)
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            try:
                toast.push(heading or "CREW", text)
            except Exception:
                pass
        return False

    def _small_once(self, key, within_s=None):
        said = self.__dict__.setdefault("_small_said", {})
        now = time.time()
        last = said.get(key)
        if last is not None and (within_s is None or now - last < within_s):
            return False
        said[key] = now
        if len(said) > 500:
            for old in sorted(said, key=said.get)[:100]:
                said.pop(old, None)
        return True

    # -- before you jump --------------------------------------------------------------------------
    def _smalls_on_target(self, raw):
        name = str(raw.get("Name") or "").strip()
        if not name or name.casefold() == str(getattr(self, "current_sys", "") or "").casefold():
            return
        self._smalls_leaving(name)
        mode = str(self.config.get("target_remarks") or "crew")
        if mode == "off" and not self.config.get("target_sounds", True):
            return
        root = getattr(self, "root", None)
        # Jump Info asked EDSM as you targeted it: give it a moment to answer.
        if root is not None and hasattr(root, "call_later"):
            root.call_later(2500, lambda: self._smalls_target_line(name, mode))
        else:
            self._smalls_target_line(name, mode)

    def _smalls_target_line(self, name, mode):
        key = name.casefold()
        if not self._small_once(f"target:{key}", within_s=1800):
            return
        history = getattr(self, "travel_history", None)
        visits = history.recall(name) if history is not None else None
        own = self._survey_own_items([name]).get(key, []) if hasattr(self, "_survey_own_items") else []
        cached = (getattr(self, "_jump_info_intel", None) or {}).get(key)
        intel = cached[1] if cached else None
        status = "done" if visits else "unreported" if intel is not None and not intel.get("known", True) else "known" if intel is not None else None
        if status and self.config.get("target_sounds", True):
            self._smalls_sound(status)
        if mode == "off":
            return
        if visits and own:
            left = sum(1 for item in own if int(item.get("bio_count") or 0) > int(item.get("organic_complete_count") or 0))
            text = (f"{name}: you've been there, and left biology on {left} world{'s' if left != 1 else ''}." if left
                    else f"{name}: you've been there before.")
        elif visits:
            text = f"{name}: you've been there, but scanned nothing."
        elif intel is not None and not intel.get("known", True):
            text = f"{name}: nobody's reported it. Yours to discover."
        elif intel is not None:
            text = f"{name}: known, but you haven't scanned it."
        else:
            return
        if mode == "tone":
            toast = getattr(self, "toast_hud", None)
            if toast is not None and hasattr(toast, "push"):
                toast.push("TARGET", text)
            return
        self._small_say(text, heading="TARGET", topic="target_remark")

    def _smalls_sound(self, status):
        """Outrider's targeting sound: a fanfare, an upbeat pair or a thud."""
        from voidcompass.voice import alert_sounds
        who = companions.identity(self.config)
        volume = _num(self.config.get(f"{who}_voice_volume", self.config.get("watcher_voice_volume", 80)))
        name = alert_sounds.TARGET_SOUNDS.get(status)
        if name:
            threading.Thread(target=alert_sounds.play, args=(name, (volume if volume is not None else 80) / 100),
                             name="TargetSound", daemon=True).start()

    def _smalls_leaving(self, target):
        """Targeting onward with mapping or biology undone, over the value you set."""
        threshold = int(_num(self.config.get("leave_behind_cr")) or 0)
        system = str(getattr(self, "current_sys", "") or "")
        if threshold <= 0 or not system:
            return
        map_left = bio_left = 0
        worlds = species = 0
        from voidcompass.overlays.survey_status_hud import _body_value_range
        for item in getattr(self, "scan_items", None) or ():
            if not isinstance(item, dict) or item.get("is_star"):
                continue
            table = item.get("value_table") or {}
            if not item.get("dss_complete") and item.get("planet_class"):
                worth = int(table.get("first_mapped" if item.get("was_mapped") is False else "mapped") or 0) - int(item.get("reward") or 0)
                if worth >= 300_000:
                    map_left += worth
                    worlds += 1
            bio, done = int(item.get("bio_count") or 0), int(item.get("organic_complete_count") or 0)
            if bio > done:
                try:
                    low, _high = _body_value_range(item)
                except Exception:
                    low = 0
                bio_left += max(0, low)
                species += bio - done
        total = map_left + bio_left
        if total < threshold or not self._small_once(f"leaving:{system.casefold()}"):
            return
        parts = []
        if worlds:
            parts.append(f"{worlds} world{'s' if worlds != 1 else ''} to map")
        if species:
            parts.append(f"{species} species to sample")
        self._small_say(f"Before you go: {' and '.join(parts)} here, worth about {total / 1e6:,.1f} million.",
                        heading="LEAVING MONEY BEHIND", topic="leave_behind")

    # -- scanning -------------------------------------------------------------------------------
    def _smalls_on_scan(self, raw):
        if "giant" not in str(raw.get("PlanetClass") or "").casefold():
            return
        guess = ggg.predict(raw)
        if not guess or not self._small_once(f"ggg:{raw.get('SystemAddress')}:{raw.get('BodyID')}"):
            return
        body = str(raw.get("BodyName") or "This giant")
        self._small_say(f"{body} could be a green gas giant: a potential one, {guess['chance']} by the community's model. "
                        "Have a look in the system map.", heading="POTENTIAL GREEN GAS GIANT", topic="ggg")

    # -- the landing pad ----------------------------------------------------------------------------
    def _smalls_on_docking_granted(self, raw):
        pad = raw.get("LandingPad")
        try:
            pad = int(pad)
        except (TypeError, ValueError):
            return
        kind = pads.layout(raw.get("StationType"), raw.get("StationName") or "", raw.get("MarketID"))
        info = pads.where(kind, pad) if kind else None
        self._pad_info = {"pad": pad, "station": raw.get("StationName"), "kind": kind,
                          "words": (info or {}).get("words"), "map": (info or {}).get("map"), "at": time.time()}
        say = (info or {}).get("say")
        if say and self.config.get("pad_location", True):
            self._small_say(f"Pad {pad}: {say}.", heading=f"PAD {pad}", topic="pad")

    # -- fuel from your own jumps ---------------------------------------------------------------------
    def _smalls_on_jump(self, raw):
        used, left, distance = _num(raw.get("FuelUsed")), _num(raw.get("FuelLevel")), _num(raw.get("JumpDist"))
        if not used or left is None or not distance or raw.get("BoostUsed"):
            return
        cargo = sum(int(row.get("count") or row.get("Count") or 0) for row in getattr(self, "current_cargo_inventory", None) or ()
                    if isinstance(row, dict))
        ship = str(((getattr(self, "companion_state", None) or {}).get("loadout") or {}).get("ShipID") or "")
        samples = self.__dict__.setdefault("_fuel_samples", {}).setdefault(ship, [])
        samples.append((distance, used, left, cargo))
        del samples[:-FUEL_SAMPLES]

    def _smalls_on_scoop(self, raw):
        now = time.time()
        last = getattr(self, "_scoop_last", None)
        scooped = _num(raw.get("Scooped"))
        if last and scooped and 0 < now - last < 60:
            rate = scooped / (now - last)
            previous = getattr(self, "_scoop_rate", None)
            self._scoop_rate = rate if previous is None else previous * .6 + rate * .4
        self._scoop_last = now

    def _fuel_from_jumps(self):
        """{per_hop, jumps, ly, range, to_full_s} from your own jumps, or {}."""
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        if not loadout.get("Modules"):
            return {}
        figures = fsd.fleet_figures(loadout)
        samples = (getattr(self, "_fuel_samples", None) or {}).get(str(loadout.get("ShipID") or "")) or []
        model = fsd.fuel_model({"unladen": figures.get("unladen"), "max_range": figures.get("max_range"),
                                "booster_ly": figures.get("booster_ly"), "fsd": figures.get("fsd"),
                                "max_fuel": figures.get("max_fuel")}, samples)
        fuel = _num(getattr(self, "current_fuel_main", None))
        capacity = _num(getattr(self, "fuel_capacity_main", None))
        if not model or fuel is None:
            return {}
        cargo = sum(int(row.get("count") or row.get("Count") or 0) for row in getattr(self, "current_cargo_inventory", None) or ()
                    if isinstance(row, dict))
        pace = statistics.median([s[0] for s in samples[-12:]]) if samples else None
        mass = model["unladen"] + fuel + cargo
        out = {"range": round(fsd.fsd_range(model, mass, fuel), 1)}
        hop = fsd.hop_fuel(model, pace, mass) if pace else None
        if hop:
            out["per_hop"] = round(hop, 2)
            left = fsd.jumps_left(model, fuel, cargo, d=pace)
            if left:
                out["jumps"], out["ly"] = left
            out["pace_ly"] = round(pace, 1)
        rate = getattr(self, "_scoop_rate", None)
        if rate and capacity and fuel < capacity:
            out["to_full_s"] = round((capacity - fuel) / rate)
        return out

    # -- crew warnings --------------------------------------------------------------------------------
    def _smalls_on_crime(self, raw):
        bounty = int(_num(raw.get("Bounty")) or 0)
        if not bounty or not self.config.get("crew_warnings", True):
            return
        faction = str(raw.get("Faction") or "")
        system = str(getattr(self, "current_sys", "") or "")

        def work():
            from voidcompass.services import spansh
            rows = spansh.service_stations(system, "Interstellar Factors Contact", size=1)
            return rows[0] if rows else None

        def done(result, error):
            near = ""
            if isinstance(result, dict):
                near = f" Nearest Interstellar Factors: {result.get('name') or result.get('station')} in {result.get('system')}."
            self._small_say(f"You're wanted{f' by {faction}' if faction else ''}: a {bounty:,} cr bounty.{near}",
                            heading="WANTED", topic="wanted")

        if hasattr(self, "_survey_task") and system:
            self._survey_task("factors", work, done)
        else:
            done(None, "")

    def _smalls_on_disembark(self, raw):
        if not raw.get("OnPlanet") or raw.get("SRV") or raw.get("OnStation") or not self.config.get("crew_warnings", True):
            return
        body_id = raw.get("BodyID")
        root = getattr(self, "root", None)
        # SuitLoadout lands 2 to 10 s after the Disembark (ED-Outrider's JOURNAL_REFERENCE).
        if root is not None and hasattr(root, "call_later"):
            root.call_later(12000, lambda: self._smalls_check_suit(body_id))

    def _smalls_check_suit(self, body_id):
        item = (getattr(self, "scan_items_by_id", None) or {}).get(body_id) or {}
        left = int(item.get("bio_count") or 0) - int(item.get("organic_complete_count") or 0)
        suit = str(((getattr(self, "companion_state", None) or {}).get("odyssey_loadout") or {}).get("suit") or "")
        if left <= 0 or not suit or "artemis" in suit.casefold() or not getattr(self, "current_on_foot", False):
            return
        if self._small_once(f"suit:{body_id}", within_s=3600):
            self._small_say(f"Biology here and you're in the {suit}: the Artemis suit samples faster and sees further.",
                            heading="WRONG SUIT", topic="wrong_suit")

    def _smalls_on_status(self, data):
        """On foot with oxygen or health low and data aboard: what a death would cost."""
        self._smalls_modules_check(data.get("Flags"))
        if not getattr(self, "current_on_foot", False) or not self.config.get("crew_warnings", True):
            return
        oxygen, health = _num(data.get("Oxygen")), _num(data.get("Health"))
        low = (oxygen is not None and oxygen < 0.25) or (health is not None and health < 0.3)
        if not low:
            return
        companion = getattr(self, "companion_state", None) or {}
        from voidcompass.core import companion_features
        bio = companion_features.unsold_bio_value(companion)
        carto = int(companion.get("unsold_exploration_cr") or 0)
        samples = int(companion.get("unsold_bio_samples") or 0)
        if bio + carto <= 0 or not self._small_once("vitals", within_s=120):
            return
        what = "Oxygen" if oxygen is not None and oxygen < 0.25 else "Health"
        figure = oxygen if what == "Oxygen" else health
        self._small_say(f"{what} at {round(figure * 100)}%. A death now loses {samples} sample{'s' if samples != 1 else ''} "
                        f"and {(bio + carto) / 1e6:,.1f} million of data. Get back to the ship.", heading=what.upper() + " LOW",
                        topic="vitals_data")

    def _smalls_on_undocked(self, raw):
        if not self.config.get("crew_warnings", True):
            return
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        controllers = [m for m in loadout.get("Modules") or () if "dronecontrol" in str(m.get("Item") or "").casefold()]
        if not controllers:
            return
        limpets = sum(int(row.get("count") or row.get("Count") or 0) for row in getattr(self, "current_cargo_inventory", None) or ()
                      if isinstance(row, dict) and str(row.get("name") or row.get("Name") or "").casefold() in ("drones", "limpet", "limpets"))
        if limpets:
            return
        mats = (getattr(self, "engineer_materials", None) or {}).get("raw") or {}
        iron = int((mats.get("iron") or {}).get("count") or 0)
        nickel = int((mats.get("nickel") or {}).get("count") or 0)
        could = min(iron // 10, nickel // 10) * 4
        extra = f" You could synthesise {could} from your iron and nickel." if could else ""
        self._small_say(f"No limpets aboard, and you've {len(controllers)} limpet controller{'s' if len(controllers) != 1 else ''}.{extra}",
                        heading="NO LIMPETS", topic="no_limpets")

    def _smalls_on_docked(self, raw):
        """A station that buys what you carry: say so as you dock."""
        if not self.config.get("crew_warnings", True):
            return
        services = {str(s).casefold() for s in raw.get("StationServices") or ()}
        companion = getattr(self, "companion_state", None) or {}
        from voidcompass.core import companion_features
        carto = int(companion.get("unsold_exploration_cr") or 0)
        bio = int(companion_features.unsold_bio_value(companion) or 0)
        samples = int(companion.get("unsold_bio_samples") or 0)
        parts = []
        if "exploration" in services and carto >= 100_000:
            parts.append(f"Universal Cartographics, for {carto / 1e6:,.1f} million of cartography")
        if "vistagenomics" in services and bio > 0:
            parts.append(f"Vista Genomics, for {samples} sample{'s' if samples != 1 else ''} worth {bio / 1e6:,.1f} million")
        station = str(raw.get("StationName") or "")
        if parts and self._small_once(f"sell:{station.casefold()}", within_s=1800):
            self._small_say(f"You can sell here: {' and '.join(parts)}.", heading="SELL HERE", topic="sell_here")

    def _smalls_on_organic(self, raw):
        """One sample run at a time: a first sample of another species discards
        the one in progress. Say which was lost."""
        runs = self.__dict__.setdefault("_sample_runs", {})
        key = (raw.get("SystemAddress"), raw.get("Body"), str(raw.get("Species") or ""))
        kind = raw.get("ScanType")
        species = str(raw.get("Species_Localised") or raw.get("Species") or "")
        if kind == "Log":
            lost = [(k, run) for k, run in runs.items() if k != key and 0 < run["samples"] < 3]
            runs.clear()
            for _k, run in lost:
                if self.config.get("crew_warnings", True):
                    self._small_say(f"Starting {species} discarded your {run['species']} run on {run['body']} "
                                    f"({run['samples']} of 3 samples).", heading="SAMPLE LOST", topic="sample_lost")
            runs[key] = {"species": species, "samples": 1, "body": self._smalls_body_name(raw.get("Body"))}
        elif kind == "Sample" and key in runs:
            runs[key]["samples"] = 2
        elif kind == "Analyse":
            runs.pop(key, None)

    def _smalls_body_name(self, body_id):
        item = (getattr(self, "scan_items_by_id", None) or {}).get(body_id) or {}
        return str(item.get("name") or item.get("full_name") or "another world")

    def _smalls_on_touchdown(self, raw):
        """Landing somewhere else with a run unfinished: a sample here would lose it."""
        runs = self.__dict__.get("_sample_runs") or {}
        here = (raw.get("SystemAddress"), raw.get("BodyID"))
        for (system, body, _species), run in runs.items():
            if (system, body) != here and 0 < run["samples"] < 3 and self.config.get("crew_warnings", True) \
                    and self._small_once(f"run:{system}:{body}:{run['species']}", within_s=1800):
                self._small_say(f"Your {run['species']} run on {run['body']} is at {run['samples']} of 3. "
                                "A sample of anything else discards it.", heading="UNFINISHED RUN", topic="sample_run_open")

    def _smalls_on_afmu(self, raw):
        """The AFMU switches a module off to repair it, and leaves it off."""
        item = str(raw.get("Module") or "").casefold()
        if not item:
            return
        off = self.__dict__.setdefault("_modules_off", {})
        off[item] = module_words(item, raw.get("Module_Localised"))
        self._modules_off_at = time.time()

    def _smalls_on_loadout(self, raw):
        """Loadout says what's on: a module it lists on isn't left off any more;
        a critical one it lists off is said once a login."""
        off = self.__dict__.setdefault("_modules_off", {})
        listed_off = set()
        for module in raw.get("Modules") or ():
            item = str(module.get("Item") or "").casefold()
            if module.get("On") is not False:
                off.pop(item, None)
            elif module_rank(item) < len(MODULE_WORDS):
                listed_off.add(item)
        said = self.__dict__.setdefault("_loadout_off_said", set())
        for item in listed_off - said:
            off[item] = module_words(item)
            self._modules_off_at = time.time() - MODULES_SETTLE_S
        self._loadout_off_said = listed_off

    def _smalls_modules_check(self, flags):
        off = self.__dict__.get("_modules_off") or {}
        if not off or time.time() - float(getattr(self, "_modules_off_at", 0) or 0) < MODULES_SETTLE_S:
            return
        self._modules_off = {}
        if not self.config.get("crew_warnings", True):
            return
        words = [w for item, w in sorted(off.items(), key=lambda kv: module_rank(kv[0]))
                 if not (isinstance(flags, int) and flags & FLAG_SHIELDS_UP and item.startswith("int_shieldgenerator"))]
        if not words:
            return
        listed = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
        urgent = words[0] == "life support"
        self._small_say(f"{listed[0].upper() + listed[1:]} may still be off after the repair. Check the modules panel."
                        + (" Life support off means you're on the emergency oxygen." if urgent else ""),
                        heading="MODULES OFF", topic="modules_off")

    # -- mining ---------------------------------------------------------------------------------------
    def _smalls_mining(self, event, raw):
        stint = self.__dict__.get("_mining_stint")
        if event == "ProspectedAsteroid":
            stint = stint or {"tons": 0, "refined": {}, "best": None, "prospected": 0, "start": time.time()}
            stint["prospected"] += 1
            for row in raw.get("Materials") or ():
                share = _num(row.get("Proportion")) or 0
                if not stint["best"] or share > stint["best"][1]:
                    stint["best"] = (str(row.get("Name_Localised") or row.get("Name") or ""), share)
            if raw.get("MotherlodeMaterial"):
                stint["motherlode"] = str(raw.get("MotherlodeMaterial_Localised") or raw.get("MotherlodeMaterial"))
            self._mining_stint = stint
        elif event == "MiningRefined":
            stint = stint or {"tons": 0, "refined": {}, "best": None, "prospected": 0, "start": time.time()}
            what = str(raw.get("Type_Localised") or raw.get("Type") or "")
            stint["tons"] += 1
            stint["refined"][what] = stint["refined"].get(what, 0) + 1
            self._mining_stint = stint
        elif event in ("FSDJump", "Docked", "SupercruiseEntry") and stint:
            self._mining_stint = None
            if stint["tons"] < 20 or not self.config.get("mining_recap", True):
                return
            top = sorted(stint["refined"].items(), key=lambda kv: -kv[1])[:2]
            hours = max(600.0, time.time() - stint["start"]) / 3600
            parts = [f"{stint['tons']} t refined in that stint ({', '.join(f'{n} {w}' for w, n in top)})",
                     f"about {stint['tons'] / hours:.0f} t an hour"]
            if stint["best"]:
                parts.append(f"best rock {stint['best'][1]:.0f}% {stint['best'][0]}")
            if stint.get("motherlode"):
                parts.append(f"and a {stint['motherlode']} motherlode")
            self._small_say(", ".join(parts) + ".", heading="MINING RECAP", topic="mining_recap")

    # -- the Nav HUD's system lines (ED-Outrider's system strip, #24) -------------------------------
    def _observe_standing(self, event, raw):
        """Who controls the system you arrive in, and your standing with them."""
        if event not in ("FSDJump", "Location", "CarrierJump") or not isinstance(raw, dict):
            return
        controlling = raw.get("SystemFaction")
        name = controlling.get("Name") if isinstance(controlling, dict) else controlling
        reputation = None
        for row in raw.get("Factions") or ():
            if isinstance(row, dict) and name and row.get("Name") == name:
                reputation = _num(row.get("MyReputation"))
        self._system_standing = {"system": str(raw.get("StarSystem") or ""), "faction": str(name or ""),
                                 "reputation": reputation}

    def _hud_system_lines(self):
        """The distance from Sol (or your home system), and in a populated system
        your standing with whoever controls it."""
        lines = []
        coords = getattr(self, "current_coords", None)
        try:
            here = [float(v) for v in coords[:3]] if coords else None
        except (TypeError, ValueError):
            here = None
        if here and any(here):
            import math
            reference, origin = "SOL", [0.0, 0.0, 0.0]
            home = self.config.get("home_system_pos")
            if self.config.get("hud_distance_from") == "home" and home and self.config.get("home_system"):
                reference, origin = str(self.config["home_system"]).upper()[:24], [float(v) for v in home[:3]]
            lines.append(f"{reference} {math.dist(here, origin):,.0f} LY")
        standing = getattr(self, "_system_standing", None) or {}
        current = str(getattr(self, "current_sys", "") or "")
        rep = standing.get("reputation")
        if standing.get("faction") and rep is not None and standing.get("system", "").casefold() == current.casefold():
            level = ("HOSTILE" if rep <= -90 else "UNFRIENDLY" if rep <= -35 else "NEUTRAL" if rep < 4
                     else "CORDIAL" if rep < 35 else "FRIENDLY" if rep < 90 else "ALLIED")
            lines.append(f"{level} WITH {standing['faction'].upper()}")
        return lines

    # -- the Dashboard's pad diagram -----------------------------------------------------------------
    def _pad_panel(self):
        info = getattr(self, "_pad_info", None)
        if not info or time.time() - float(info.get("at") or 0) > 900 or getattr(self, "current_docked", False):
            return None
        return {k: info.get(k) for k in ("pad", "station", "kind", "words", "map")}

    # -- one entry for the journal --------------------------------------------------------------------
    def _smalls_event(self, event, raw, startup_replay=False):
        if startup_replay or not isinstance(raw, dict):
            return
        try:
            if event == "FSDTarget":
                self._smalls_on_target(raw)
            elif event == "Scan":
                self._smalls_on_scan(raw)
            elif event == "DockingGranted":
                self._smalls_on_docking_granted(raw)
            elif event == "FSDJump":
                self._smalls_on_jump(raw)
            elif event == "FuelScoop":
                self._smalls_on_scoop(raw)
            elif event == "CommitCrime":
                self._smalls_on_crime(raw)
            elif event == "Disembark":
                self._smalls_on_disembark(raw)
            elif event == "Undocked":
                self._smalls_on_undocked(raw)
            elif event == "Docked":
                self._smalls_on_docked(raw)
            elif event == "ScanOrganic":
                self._smalls_on_organic(raw)
            elif event == "Touchdown":
                self._smalls_on_touchdown(raw)
            elif event == "AfmuRepairs":
                self._smalls_on_afmu(raw)
            elif event == "Loadout":
                self._smalls_on_loadout(raw)
            elif event in ("LoadGame", "Died", "Shutdown"):
                self._modules_off, self._loadout_off_said = {}, set()
            if event in ("ProspectedAsteroid", "MiningRefined", "FSDJump", "Docked", "SupercruiseEntry"):
                self._smalls_mining(event, raw)
        except Exception:
            logger.debug("Small moment skipped [%s]", event, exc_info=True)
