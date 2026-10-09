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

    def reset_session(self):
        self.jumps = 0
        self.distance_ly = 0.0
        self.firsts = 0
        self.analysed = 0
        self.memories = []        # noun phrases: "the green gas giant in X"

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
        elif event == "Undocked":
            self.docked = False
        elif event == "Touchdown" and raw.get("PlayerControlled", True):
            self.landed_body = str(raw.get("Body") or "")
        elif event == "Liftoff":
            self.landed_body = ""
        elif event == "Disembark":
            self.on_foot = True
        elif event == "Embark":
            self.on_foot = False

    def sol_distance(self):
        if not self.star_pos:
            return None
        return math.sqrt(sum(value * value for value in self.star_pos))

    def choices(self, now, rng):
        """Idle topics that fit right now, as (topic, fields), most fitting
        first, shuffled within their rank so it varies."""
        where, here, session, time_of_day = [], [], [], []
        if self.on_foot:
            where.append(("idle_on_foot", {"body": self.landed_body} if self.landed_body else {}))
        elif self.landed_body:
            where.append(("idle_landed", {"body": self.landed_body}))
        elif self.docked and self.station:
            where.append(("idle_docked", {"station": self.station}))
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
        for group in (where, here, session, time_of_day):
            rng.shuffle(group)
            out.extend(group)
        # Mix the ranks a little, so it doesn't always open with the same kind.
        if len(out) > 2 and rng.random() < .5:
            out.insert(0, out.pop(rng.randrange(len(out))))
        return out
