"""A full system scan, reported (5.7.5).

When the FSS has found every body, the companion says what the system holds,
from the scans themselves: how many bodies, which are worth mapping, where
there's biology, and how much of it nobody has discovered before.
"""

IMPORTANCE = {"survey_report": 2}

_WORTH = (("Earthlike body", "an Earth-like", "Earth-likes"), ("Water world", "a water world", "water worlds"),
          ("Ammonia world", "an ammonia world", "ammonia worlds"))


def _count(number, one, many):
    return one if number == 1 else f"{number} {many}"


def _join(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


class SurveyTally:
    """This system's scans, until you jump."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.bodies = {}     # body name -> (planet class, terraformable, discovered)
        self.biology = {}    # body name -> biological signals

    def observe(self, event, raw):
        if event in ("FSDJump", "CarrierJump"):
            self.reset()
        elif event == "Scan" and raw.get("BodyName") and (raw.get("PlanetClass") or raw.get("StarType")):
            self.bodies[str(raw["BodyName"])] = (str(raw.get("PlanetClass") or ""),
                                                 str(raw.get("TerraformState") or "") == "Terraformable",
                                                 raw.get("WasDiscovered") is not False)
        elif event in ("FSSBodySignals", "SAASignalsFound") and raw.get("BodyName"):
            for signal in raw.get("Signals") or ():
                if isinstance(signal, dict) and "Biological" in str(signal.get("Type") or ""):
                    self.biology[str(raw["BodyName"])] = int(signal.get("Count") or 0)

    def summary(self, count=None):
        """One plain sentence or three about the system, or "" with nothing scanned."""
        if not self.bodies:
            return ""
        total = int(count or 0) or len(self.bodies)
        parts = [f"{total} bodies." if total != 1 else "One body."]
        worth = []
        for planet_class, one, many in _WORTH:
            found = sum(1 for kind, _terra, _seen in self.bodies.values() if kind == planet_class)
            if found:
                worth.append(_count(found, one, many))
        terraformable = sum(1 for kind, terra, _seen in self.bodies.values()
                            if terra and kind not in {row[0] for row in _WORTH})
        if terraformable:
            worth.append(_count(terraformable, "a terraformable", "terraformables"))
        parts.append(f"Worth mapping: {_join(worth)}." if worth else "Nothing worth mapping.")
        signals = sum(self.biology.values())
        if signals:
            worlds = sum(1 for value in self.biology.values() if value)
            parts.append(f"Biology on {_count(worlds, 'one world', 'worlds')}, {_count(signals, 'one signal', 'signals')}.")
        firsts = sum(1 for _kind, _terra, seen in self.bodies.values() if not seen)
        if firsts and firsts == len(self.bodies):
            parts.append("Every one a first discovery.")
        elif firsts:
            parts.append(f"{_count(firsts, 'One first discovery', 'first discoveries')}.")
        return " ".join(parts)

    def notable(self):
        """Whether there's more to say than a body count."""
        return bool(self.biology or any(kind in {row[0] for row in _WORTH} or terra
                                        for kind, terra, _seen in self.bodies.values()))


def persona_banks(identity):
    """({topic: plain lines}, {topic: voiced lines}) for an officer-style companion."""
    banks = PERSONAS[identity]
    return {"survey_report": banks["plain"]}, {"survey_report": banks["voiced"]}


# {system} the system, {summary} the facts above (always ends with a full stop).
WATCHER_NORMAL = (
    "{system}, all found. {summary}", "That's {system} done. {summary}", "Every body in {system}. {summary}",
    "{system}: the whole system. {summary}", "Scan complete. {summary}", "{system} has no secrets left from up here. {summary}",
    "All of {system}. {summary}", "There it is, all of it. {summary}", "{system}, counted. {summary}",
    "Done. Here's {system}: {summary}",
)
WATCHER_WEARY = (
    "{system}, all found. {summary} Thrilling.", "That's {system}. {summary}", "Every body in {system}. {summary} There you go.",
    "{system}, scanned. {summary} I'll try to sound pleased.", "All of it. {summary}", "{system}. {summary} As expected.",
    "Scan complete. {summary} Don't let me stop you.", "The whole system. {summary}", "{system}, done. {summary}",
    "Found them all. {summary} Not that anyone asked me.",
)
PERSONAS = {
    "aster": {
        "plain": ("{system} surveyed. {summary}", "Survey complete: {system}. {summary}", "All bodies found. {summary}",
                  "{system}: full survey. {summary}"),
        "voiced": ("Survey of {system} complete, Commander. For the log: {summary}",
                   "{system}, fully surveyed. My summary, briefly: {summary}",
                   "Every body in {system} accounted for. {summary} Entered in the log.",
                   "The {system} survey is closed. {summary}",
                   "All found. I have taken the liberty of a summary. {summary}",
                   "{system}, complete. {summary} I shall file it under promising, or otherwise."),
    },
    "axiom": {
        "plain": ("{system}: survey complete. {summary}", "All bodies found in {system}. {summary}",
                  "Full survey: {system}. {summary}", "Count closed. {summary}"),
        "voiced": ("{system}, fully counted. The results: {summary}", "Complete census of {system}. {summary} I checked twice.",
                   "Every body in {system} found. Summary follows. {summary}",
                   "{system}: count closed. {summary} My favourite kind of paragraph.",
                   "Survey complete. Here is what {system} holds. {summary}",
                   "All found. {summary} I have already started a page for the interesting ones."),
    },
    "meridian": {
        "plain": ("{system} charted. {summary}", "All bodies on the chart. {summary}", "Survey done: {system}. {summary}",
                  "{system}: fully charted. {summary}"),
        "voiced": ("{system}, fully charted, Commander. {summary}", "Every body of {system} on the chart. {summary}",
                   "The survey's done. Here's {system}: {summary}",
                   "{system} sounded end to end. {summary}",
                   "All charted. {summary} A good night's survey.",
                   "{system}, complete. {summary} I'll mark the ones worth a visit."),
    },
}
