"""What the Watcher thinks about when nothing is happening (5.5.3.2).

It follows the commander's surroundings from the journal (the star, the
system's size, the distance from Sol, docked, landed or on foot) and keeps
a few memories of the session (rare worlds, species analysed, first
discoveries). When the quiet comes, it offers idle topics built from those
facts; the mind decides whether to say one. Nothing is invented: every
{field} is something the journal said.
"""

from __future__ import annotations

import math
from datetime import datetime

# Idle topics, besides the plain "quiet" mutter. watcher_lines has the words.
IDLE_TOPICS = (
    "idle_star", "idle_star_odd", "idle_big_system", "idle_small_system",
    "idle_far", "idle_home", "idle_recall", "idle_session", "idle_night",
    "idle_morning", "idle_docked", "idle_landed", "idle_on_foot",
    # Alive across the app: the music playing, Galnet's latest, and its own
    # history with the commander (5.5.3.2).
    "idle_music", "idle_galnet", "idle_self", "idle_deaths",
    # Flying and walking about (5.5.3.2): the ship, supercruise, the SRV, a
    # settlement, a taxi, a fleet carrier, a station concourse, a world below.
    "idle_ship", "idle_supercruise", "idle_srv", "idle_settlement", "idle_taxi",
    "idle_carrier", "idle_station_foot", "idle_near_body",
    # The bond (5.5.3.2): known, a companion, an old friend.
    "idle_bond_1", "idle_bond_2", "idle_bond_3",
    # Its past, in passing (5.5.3.5; watcher_lore.MUSINGS); after its story
    # is told, its later musings; and a look back at a chapter it told you.
    "idle_lore", "idle_after", "lore_recall",
)

# Star classes in plain words (journal StarClass / StarType).
_STARS = {
    "O": "blue O-type star", "B": "blue-white B-type star", "A": "white A-type star",
    "F": "yellow-white F-type star", "G": "yellow G-type star", "K": "orange K-type star",
    "M": "red dwarf", "L": "brown dwarf", "T": "brown dwarf", "Y": "brown dwarf",
    "TTS": "T Tauri star", "AEBE": "Herbig Ae/Be star",
}
# The odd ones get their own remarks.
_ODD = {
    "N": "neutron star", "H": "black hole", "SUPERMASSIVEBLACKHOLE": "supermassive black hole",
    "X": "exotic star",
}


def star_words(star_class):
    """(plain name, odd) for a journal star class, or ("", False)."""
    key = str(star_class or "").strip().upper()
    if not key:
        return "", False
    if key in _ODD:
        return _ODD[key], True
    if key.startswith("D"):
        return "white dwarf", True
    if key.startswith("W"):
        return "Wolf-Rayet star", True
    if key in {"C", "CN", "CJ", "CH", "CHD", "CS", "MS", "S"}:
        return "carbon star", True
    if key.endswith("_BLUEWHITESUPERGIANT") or key.endswith("SUPERGIANT"):
        return "supergiant", True
    return _STARS.get(key, ""), False


def _capital(text):
    return text[:1].upper() + text[1:] if text else text


class Surroundings:
    """The commander's surroundings and the session's memories."""

    def __init__(self):
        self.reset_session()
        self.system = ""
        self.star_class = ""
        self._pending_star = ""
        self.star_pos = None
        self.bodies = None
        self.station = ""
        self.docked = False
        self.landed_body = ""
        self.on_foot = False
        self.on_station = False
        self.supercruise = False
        self.srv = False
        self.settlement = ""
        self.near_body = ""
        self.taxi = False
        self.carrier = False
        self.ship = ""
        self.ship_name = ""
        self.suit = ""

    def reset_session(self):
        self.jumps = 0
        self.distance_ly = 0.0
        self.firsts = 0
        self.analysed = 0
        self.memories = []        # noun phrases: "the green gas giant in X"

    @staticmethod
    def _readable(raw, *keys):
        """The first readable name among ``keys`` (skips $symbols)."""
        for key in keys:
            value = str(raw.get(key) or "").strip()
            if value and not value.startswith("$"):
                return value
        return ""

    def _remember(self, phrase):
        if phrase and phrase not in self.memories:
            self.memories.append(phrase)
            del self.memories[:-12]

    def observe(self, event, raw, rarity=None, green=False):
        """Follow one journal event. ``rarity`` is (level, label) for a Scan;
        ``green`` marks a green gas giant's Codex entry."""
        raw = raw if isinstance(raw, dict) else {}
        if event == "StartJump" and raw.get("JumpType") == "Hyperspace":
            self._pending_star = str(raw.get("StarClass") or "")
        elif event in {"FSDJump", "CarrierJump", "Location"}:
            system = str(raw.get("StarSystem") or "")
            if system and system != self.system:
                self.system = system
                self.star_class = self._pending_star if event == "FSDJump" else ""
                self.bodies = None
            self._pending_star = ""
            position = raw.get("StarPos")
            if isinstance(position, (list, tuple)) and len(position) >= 3:
                try:
                    self.star_pos = tuple(float(value) for value in position[:3])
                except (TypeError, ValueError):
                    pass
            if event == "FSDJump":
                self.supercruise = True
                self.near_body = self.settlement = ""
                self.jumps += 1
                try:
                    self.distance_ly += float(raw.get("JumpDist") or 0)
                except (TypeError, ValueError):
                    pass
            self.docked = bool(raw.get("Docked")) if event == "Location" else False
            self.landed_body = ""
        elif event == "Scan":
            if raw.get("StarType") and not raw.get("DistanceFromArrivalLS"):
                self.star_class = str(raw.get("StarType"))
            if raw.get("WasDiscovered") is False and raw.get("PlanetClass"):
                self.firsts += 1
                if self.firsts in {1, 5, 10, 25}:
                    self._remember(f"{raw.get('BodyName')}, the first world nobody had seen" if self.firsts == 1
                                   else f"{raw.get('BodyName')}, first discovery number {self.firsts}")
            level, label = rarity or (0, "")
            if level and raw.get("BodyName"):
                self._remember(f"{raw.get('BodyName')}, the {label.lower()}")
        elif event == "FSSDiscoveryScan":
            try:
                self.bodies = int(raw.get("BodyCount"))
            except (TypeError, ValueError):
                pass
        elif event == "CodexEntry" and green:
            self._remember(f"the green gas giant in {raw.get('System') or 'that system'}")
        elif event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
            self.analysed += 1
            species = raw.get("Species_Localised") or raw.get("Genus_Localised")
            if species:
                self._remember(f"the {species} on {self.landed_body}" if self.landed_body else f"the {species}")
        elif event == "Docked":
            self.docked, self.station = True, str(raw.get("StationName") or "")
            self.carrier = str(raw.get("StationType") or "").casefold() == "fleetcarrier"
            self.supercruise = self.taxi = False
        elif event == "Undocked":
            self.docked = self.carrier = False
        elif event == "Touchdown" and raw.get("PlayerControlled", True):
            self.landed_body = str(raw.get("Body") or self.near_body or "")
            self.supercruise = False
        elif event == "Liftoff":
            self.landed_body = ""
        elif event == "Disembark":
            self.on_foot, self.taxi = True, False
            self.on_station = bool(raw.get("OnStation"))
        elif event == "Embark":
            self.on_foot = self.on_station = False
            self.taxi = bool(raw.get("Taxi"))
        elif event == "BookTaxi":
            self.taxi = True
        elif event == "SupercruiseEntry":
            self.supercruise = True
        elif event == "SupercruiseExit":
            self.supercruise = False
            self.near_body = str(raw.get("Body") or "") if raw.get("BodyType") == "Planet" else self.near_body
        elif event == "ApproachBody":
            self.near_body = str(raw.get("Body") or "")
        elif event == "LeaveBody":
            self.near_body = self.settlement = ""
        elif event == "ApproachSettlement":
            self.settlement = self._readable(raw, "Name_Localised", "Name")
        elif event == "LaunchSRV":
            self.srv = True
        elif event == "DockSRV":
            self.srv = False
        elif event in {"LoadGame", "Loadout"}:
            self.ship = self._readable(raw, "Ship_Localised") or self.ship
            name = str(raw.get("ShipName") or "").strip()
            self.ship_name = name or self.ship_name
        elif event in {"SuitLoadout", "SwitchSuitLoadout"}:
            self.suit = self._readable(raw, "SuitName_Localised") or self.suit

    def sol_distance(self):
        if not self.star_pos:
            return None
        return math.sqrt(sum(value * value for value in self.star_pos))

    def choices(self, now, rng, context=None):
        """Idle topics that fit right now, as (topic, fields), most fitting
        first, shuffled within their rank so it varies. ``context`` is what
        the rest of the app and its memory know: music {title, artist},
        galnet (a headline), thoughts, sessions and deaths (counts)."""
        context = context or {}
        where, here, world, session, time_of_day = [], [], [], [], []
        suit = {"suit": self.suit} if self.suit else {}
        music = context.get("music") or {}
        if music.get("title"):
            fields = {"title": str(music["title"])}
            if music.get("artist"):
                fields["artist"] = str(music["artist"])
            world.append(("idle_music", fields))
        # Its past, in passing (5.5.3.5): any quiet moment will do; once its
        # story is told, how it is since; and now and then a chapter recalled.
        world.append(("idle_lore", {}))
        if context.get("story_done"):
            world.append(("idle_after", {}))
        if context.get("recall"):
            session.append(("lore_recall", dict(context["recall"])))
        if context.get("galnet"):
            world.append(("idle_galnet", {"headline": str(context["galnet"]).rstrip(". ")}))
        thoughts = int(context.get("thoughts") or 0)
        if thoughts >= 20:
            fields = {"count": f"{thoughts:,}"}
            if int(context.get("sessions") or 0) >= 2:
                fields["sessions"] = int(context["sessions"])  # lines about sessions wait for a second one
            session.append(("idle_self", fields))
        bond = int(context.get("bond") or 0)
        if bond >= 1:
            fields = {"hours": f"{int(context.get('hours') or 0):,}"}
            if int(context.get("sessions") or 0) >= 2:
                fields["sessions"] = int(context["sessions"])
            session.append((f"idle_bond_{min(3, bond)}", fields))
        deaths = int(context.get("deaths") or 0)
        if deaths:
            times = {1: "once", 2: "twice"}.get(deaths, f"{deaths:,} times")
            session.append(("idle_deaths", {"times": times}))
        if self.on_foot and self.on_station and self.station:
            where.append(("idle_station_foot", {"station": self.station, **suit}))
        elif self.on_foot:
            where.append(("idle_on_foot", {**({"body": self.landed_body} if self.landed_body else {}), **suit}))
        elif self.taxi:
            where.append(("idle_taxi", {}))
        elif self.srv:
            where.append(("idle_srv", {"body": self.landed_body or self.near_body} if (self.landed_body or self.near_body) else {}))
        elif self.landed_body:
            where.append(("idle_landed", {"body": self.landed_body}))
        elif self.docked and self.station:
            where.append(("idle_carrier" if self.carrier else "idle_docked", {"station": self.station}))
        elif self.supercruise and self.system:
            where.append(("idle_supercruise", {"system": self.system}))
        elif self.near_body:
            where.append(("idle_near_body", {"body": self.near_body}))
        if self.settlement and not self.docked:
            where.append(("idle_settlement", {"settlement": self.settlement}))
        if self.ship and not self.on_foot and not self.taxi:
            fields = {"ship": self.ship}
            if self.ship_name:
                fields["ship_name"] = self.ship_name
            session.append(("idle_ship", fields))
        if not self.docked:
            star, odd = star_words(self.star_class)
            if star and self.system:
                article = "an" if star[:1].lower() in "aeiou" else "a"
                here.append(("idle_star_odd" if odd else "idle_star", {
                    "star": star, "system": self.system,
                    "a_star": f"{article} {star}", "A_star": f"{article.capitalize()} {star}"}))
            if self.bodies is not None and self.system:
                if self.bodies >= 20:
                    here.append(("idle_big_system", {"count": self.bodies, "system": self.system}))
                elif self.bodies <= 2:
                    here.append(("idle_small_system", {"count": self.bodies, "system": self.system}))
            distance = self.sol_distance()
            if distance is not None:
                if distance >= 1000:
                    here.append(("idle_far", {"dist": f"{distance:,.0f}"}))
                elif distance <= 250:
                    here.append(("idle_home", {"dist": f"{distance:,.0f}"}))
        if self.memories:
            thing = rng.choice(self.memories)
            session.append(("idle_recall", {"thing": thing, "Thing": _capital(thing)}))
        if self.jumps >= 5:
            fields = {"jumps": self.jumps, "ly": f"{self.distance_ly:,.0f}"}
            if self.firsts:
                fields["firsts"] = self.firsts  # lines quoting it are skipped otherwise
            session.append(("idle_session", fields))
        hour = datetime.fromtimestamp(now).hour
        clock = datetime.fromtimestamp(now).strftime("%H:%M")
        if 0 <= hour < 5:
            time_of_day.append(("idle_night", {"clock": clock}))
        elif 5 <= hour < 9:
            time_of_day.append(("idle_morning", {"clock": clock}))
        out = []
        for group in (where, here, world, session, time_of_day):
            rng.shuffle(group)
            out.extend(group)
        # Mix the ranks a little, so it doesn't always open with the same kind.
        if len(out) > 2 and rng.random() < .5:
            out.insert(0, out.pop(rng.randrange(len(out))))
        return out
