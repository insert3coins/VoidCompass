"""Stories told entry by entry, each with its own requirement (5.8.6, Nova).

Nyx Evera's design for Nova: every entry unlocks on something done after the
entry before it unlocked (a number of jumps, light years, first maps, data
sold, samples, a phenomenon investigated, or time together), counting from
zero each time, strictly in order, from the moment she's activated. Unlocking
and telling are separate: an entry that unlocks mid-fight is told later, in a
quiet moment, but the next entry starts counting at once. Nothing done before
counts, and there is no time alternative.

Some entries ask the commander something. A reply through TALK (typed or
spoken) within ASK_S gets her answer to it; silence gets the other one.

Her first question ("Who are you?") is a gate: it never expires, and until it
is answered she says nothing else and her story stands still (gate()). Silence
gets its line once; the next thing said through TALK is the answer.

Chapters still being written are listed as pending: the book shows them, the
story isn't complete while they're missing, and nothing can be heard in them.
"""
import math
import re
import time

from voidcompass.core.discovery import our_first
from voidcompass.overlays.companion_story import Story

# How long a question waits for a reply before she lets it go: long enough to
# finish a landing or a scan and answer (5.8.6: three minutes was too short).
ASK_S = 600.0
# After docking is asked for, or arriving at a planet, she waits this long at
# most for the docking or landing to finish before an entry may be told.
BUSY_S = 240.0

UNITS = {
    "play": ("minute", "minutes", "of active play together"),
    "jumps": ("hyperspace jump", "hyperspace jumps", ""),
    "ly": ("light year", "light years", "travelled"),
    "first_maps": ("first map", "first maps", "of previously unmapped planets or moons"),
    "new_systems": ("complete survey", "complete surveys", "of previously undiscovered systems (every body found)"),
    "first_systems": ("previously undiscovered system", "previously undiscovered systems", "discovered"),
    "fss_systems": ("complete system survey", "complete system surveys", "(every body found)"),
    "uc_credits": ("Cr", "Cr", "from Universal Cartographics"),
    "species": ("species", "species", "sampled completely"),
    "genera": ("genus", "genera", "sampled completely"),
    "bio_bodies": ("planet or moon", "planets or moons", "with a complete biological sample"),
    "vista_credits": ("Cr", "Cr", "from Vista Genomics"),
    "nsp": ("Notable Stellar Phenomenon", "Notable Stellar Phenomena", "investigated"),
    "visit": ("visit", "visits", ""),
}
HOW = {
    "play": "Fly together with her on watch.",
    "jumps": "Make hyperspace jumps with her on watch.",
    "ly": "Travel by hyperspace with her on watch.",
    "first_maps": "Map planets or moons nobody had mapped before (the Detailed Surface Scanner).",
    "new_systems": "Find every body in systems nobody had discovered (the Full Spectrum System Scanner).",
    "first_systems": "Jump to systems nobody had discovered: their main star counts as yours.",
    "fss_systems": "Find every body in a system with the Full Spectrum System Scanner (already discovered systems count).",
    "uc_credits": "Sell exploration data to Universal Cartographics. Data gathered earlier counts when it's sold now.",
    "species": "Complete the genetic sampling of different species.",
    "genera": "Complete samples from different genera.",
    "bio_bodies": "Complete a biological sample on different planets or moons.",
    "vista_credits": "Sell biological data to Vista Genomics. Samples taken earlier count when they're sold now.",
    "nsp": "Drop in at a Notable Stellar Phenomenon (known ones count) and scan something there.",
    "visit": "Fly there: approaching it, landing, docking or logging in there counts, whoever controls it now.",
}
# What says you're at a place: arriving at a settlement or port, docking, or
# the game starting with you docked there.
VISIT_EVENTS = frozenset({"ApproachSettlement", "Docked", "Location", "Touchdown", "Disembark"})
# Leaving wherever you were: a visit that becomes due after these needs you to come back.
LEAVE_EVENTS = frozenset({"Undocked", "LeaveBody", "SupercruiseEntry", "FSDJump", "CarrierJump", "StartJump", "Died"})
_HERE_FIELDS = ("MarketID", "StationName", "Name", "Name_Localised", "NearestDestination", "NearestDestination_Localised",
                "StarSystem", "Docked")


def at_place(place, event, raw, system=""):
    """Whether this journal event is you at ``place`` ({name, system, market})."""
    if not place or event not in VISIT_EVENTS:
        return False
    if event == "Location" and not raw.get("Docked"):
        return False
    market = raw.get("MarketID")
    if market is not None and place.get("market") is not None:
        try:
            if int(market) == int(place["market"]):
                return True
        except (TypeError, ValueError):
            pass
    name = str(raw.get("Name_Localised") or raw.get("Name") or raw.get("StationName") or raw.get("NearestDestination_Localised")
               or raw.get("NearestDestination") or "")
    here = str(raw.get("StarSystem") or system or "")
    # A megaship (The Gnosis) moves: no system to match, its name anywhere.
    anywhere = not str(place.get("system") or "")
    return bool(name) and name.casefold() == str(place.get("name") or "").casefold() \
        and (anywhere or here.casefold() == str(place.get("system") or "").casefold())
_DISTINCT = {"first_maps", "new_systems", "first_systems", "fss_systems", "species", "genera", "bio_bodies"}
NEGATIVE = re.compile(r"\b(no|nope|nah|not|don'?t|never|stop|rather not|creepy|uncomfortable|unsure|dunno|maybe|"
                      r"perhaps|i guess|not sure)\b", re.I)
POSITIVE = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|deal|agreed?|absolutely|definitely|of course|certainly|"
                      r"i'?d like|i would|sounds good|let'?s|happy to|why not|please|great|good|useful)\b", re.I)


def amount_text(kind, value):
    one, many, after = UNITS[kind]
    if kind in {"uc_credits", "vista_credits"}:
        words = f"{int(value):,} Cr"
    elif kind == "ly":
        words = f"{value:,.0f} {one if round(value) == 1 else many}"
    else:
        words = f"{int(value):,} {one if int(value) == 1 else many}"
    return f"{words} {after}".strip()


_NAMED = (
    re.compile(r"\b(?:cmdr|commander)\.?\s+([A-Za-z0-9][\w'.-]*(?:\s+[A-Za-z0-9][\w'.-]*)?)", re.I),
    re.compile(r"\b(?:i'?m|i am|my name is|my name's|name's|call me|this is|it's|its)\s+(?:cmdr\.?\s+|commander\s+)?"
               r"([A-Za-z0-9][\w'.-]*)", re.I),
)
_NOT_NAMES = {"a", "an", "the", "your", "you", "just", "here", "fine", "good", "well", "ok", "okay", "nova", "not", "sure",
              "commander", "cmdr", "pilot", "captain", "me", "it", "this", "that", "hello", "hi", "hey", "yes", "no",
              "and", "with", "of", "is", "was", "nice", "glad", "happy", "very", "so", "too", "also", "busy", "back"}


_FILLER = {"here", "reporting", "speaking", "online", "again", "aboard", "present"}


def introduced_name(text, known=""):
    """The name someone gave when asked who they are, or "". The commander's
    own name (from the journal) is recognised anywhere in the reply."""
    words = " ".join(str(text or "").split())
    known = " ".join(str(known or "").split())
    if known and re.search(r"(?<![\w])" + re.escape(known) + r"(?![\w])", words, re.I):
        return known
    for pattern in _NAMED:
        match = pattern.search(words)
        if match:
            name = match.group(1).strip(" .,!?'-")
            parts = [part for part in name.split() if part.casefold() not in _NOT_NAMES]
            if parts and parts[0].casefold() == name.split()[0].casefold():
                name = " ".join(parts)[:30]
                return name[:1].upper() + name[1:]
    # A bare name: "Jeff", "Jeff here", "insert3coins reporting".
    parts = words.strip(" .,!?").split()
    while parts and parts[-1].casefold().strip(" .,!?") in _FILLER:
        parts.pop()
    bare = " ".join(parts)
    if bare and len(parts) <= 2 and re.fullmatch(r"[A-Za-z0-9][\w'.-]*(?:\s+[A-Za-z0-9][\w'.-]*)?", bare) \
            and not any(part.casefold() in _NOT_NAMES for part in parts):
        return bare[:1].upper() + bare[1:30]
    return ""


def tone(text):
    """'yes', 'no' or '' for a reply: the branch it takes."""
    words = str(text or "")
    if NEGATIVE.search(words):
        return "no"
    return "yes" if POSITIVE.search(words) else ""


class ProgressStory(Story):
    """A Story whose passages are entries, each unlocked by its own requirement."""

    def __init__(self, *, entries, pending=(), key="story_progress", paused_note="", personality=None, opens_up=None,
                 **kwargs):
        self.opens_up = opens_up
        self.paused_note = paused_note or "The rest of the story is still being written."
        chapters, order = [], []
        for entry in entries:
            if not chapters or chapters[-1]["numeral"] != entry["chapter"]:
                chapters.append({"numeral": entry["chapter"], "title": entry["chapter_title"],
                                 "about": (personality or {}).get(entry["chapter"], ""),
                                 "hours": (0, 0), "gate": None, "passages": [], "recall": entry.get("recall", ())})
            # A line opening with a blank line is a pause before it (Entry 48C).
            chapters[-1]["passages"].append(" ".join(entry["lines"]).replace(" \n\n", "\n\n"))
            order.append(entry)
        for chapter in chapters:
            chapter["passages"] = tuple(chapter["passages"])
        super().__init__(chapters=chapters, **kwargs)
        self.key = key
        self.pending = tuple(pending)
        self.entries = {row[0]: entry for row, entry in zip(self.passages, order)}
        self.order = tuple(row[0] for row in self.passages)

    # -- progress -------------------------------------------------------------
    def state(self, memory):
        state = memory.setdefault(self.key, {})
        state.setdefault("stage", 0)
        state.setdefault("unlocked", {})
        state.setdefault("counts", {})
        state.setdefault("seen", {})
        state.setdefault("scratch", {})
        state.setdefault("replies", {})
        return state

    def activate(self, memory, hours, now):
        """Her activation: progress counts from here, never from before."""
        state = self.state(memory)
        if state.get("activated") is None:
            state.update(activated=float(now), stage_hours=float(hours or 0), stage_at=float(now))
            return True
        return False

    def stage_entry(self, memory):
        state = self.state(memory)
        stage = int(state["stage"])
        return self.order[stage] if stage < len(self.order) else None

    def _needs(self, entry_id):
        need = self.entries[entry_id]["need"]
        return list(need["any"]) if isinstance(need, dict) else [need]

    def _met(self, memory, entry_id, hours):
        state = self.state(memory)
        for kind, amount in self._needs(entry_id):
            if self._value(state, kind, hours) >= amount:
                return True
        return False

    @staticmethod
    def _value(state, kind, hours):
        if kind == "play":
            return max(0.0, (float(hours or 0) - float(state.get("stage_hours") or 0)) * 60.0)
        if kind in _DISTINCT:
            return len(state["seen"].get(kind) or ())
        return float(state["counts"].get(kind) or 0)

    def gate(self, memory):
        """Her first question ("Who are you?") told and not yet answered: its
        entry id, else None. Until it's answered nothing else is said and her
        story doesn't move (5.8.6, the commander's wish)."""
        entry_id = next((key for key in self.order if self.entries[key].get("learn_name")), None)
        if entry_id is None or entry_id not in self.told(memory):
            return None
        return None if (self.state(memory)["replies"].get(entry_id) or {}).get("you") else entry_id

    def _restart(self, state, hours, now):
        """Answered at last: the next entry counts from the answer, not from
        the question."""
        if state.pop("restart", False):
            state.update(counts={}, seen={}, stage_hours=float(hours or 0), stage_at=float(now))

    def _advance(self, memory, hours, now):
        """Unlock every entry whose requirement is met, in order: their ids."""
        state, opened = self.state(memory), []
        if self.gate(memory) is not None:
            return opened
        self._restart(state, hours, now)
        while True:
            entry_id = self.stage_entry(memory)
            if entry_id is None or state.get("activated") is None or not self._met(memory, entry_id, hours):
                return opened
            state["unlocked"][entry_id] = float(now)
            state["stage"] = int(state["stage"]) + 1
            following = self.stage_entry(memory)
            carried = {}
            if following is not None and self.entries[following].get("carry"):
                # Stages sharing one counter (Entry 48): what went past this one's
                # mark counts toward the next.
                for kind, amount in self._needs(entry_id):
                    if kind not in _DISTINCT and kind != "play":
                        over = float(state["counts"].get(kind) or 0) - float(amount)
                        if over > 0:
                            carried[kind] = over
            state.update(counts=carried, seen={}, stage_hours=float(hours or 0), stage_at=float(now))
            opened.append(entry_id)
            if following is not None:
                self._already_there(state, following)

    def _already_there(self, state, entry_id):
        """A visit that becomes due while you're at that place counts at once,
        without leaving and coming back (Nyx Evera's guidelines, 6)."""
        here = state["scratch"].get("here")
        place = self.entries[entry_id].get("place")
        if place and isinstance(here, dict) and any(kind == "visit" for kind, _amount in self._needs(entry_id)) \
                and at_place(place, here.get("event"), here.get("raw") or {}, here.get("system", "")):
            state["counts"]["visit"] = 1.0

    def tick(self, memory, hours, now):
        return self._advance(memory, hours, now)

    def observe(self, memory, event, raw, hours, now):
        """A journal event: counted toward the current entry. The ids it unlocked."""
        state = self.state(memory)
        if state.get("activated") is None:
            return []
        raw = raw if isinstance(raw, dict) else {}
        scratch = state["scratch"]
        self._busy(scratch, event, raw, now)
        if self.gate(memory) is not None:
            return []  # nothing counts while "Who are you?" waits
        self._restart(state, hours, now)
        entry_id = self.stage_entry(memory)
        if entry_id is None:
            return []
        kinds = {kind for kind, _amount in self._needs(entry_id)}
        counts, seen = state["counts"], state["seen"]

        def add(kind, amount=1.0):
            if kind in kinds:
                counts[kind] = float(counts.get(kind) or 0) + float(amount)

        def once(kind, key):
            if kind in kinds and key:
                rows = seen.setdefault(kind, [])
                if key not in rows:
                    rows.append(key)

        if event in {"FSDJump", "Location", "CarrierJump"} and raw.get("StarSystem"):
            scratch["system"] = str(raw["StarSystem"])
        # Where you are now, should a visit there become due while you stay.
        if event in LEAVE_EVENTS:
            scratch.pop("here", None)
        elif event in VISIT_EVENTS and not (event == "Location" and not raw.get("Docked")):
            scratch["here"] = {"event": event, "system": scratch.get("system", ""),
                               "raw": {key: raw[key] for key in _HERE_FIELDS if key in raw}}
        if "visit" in kinds and at_place(self.entries[entry_id].get("place"), event, raw, scratch.get("system", "")):
            add("visit")
        if event == "FSDJump":
            add("jumps")
            try:
                add("ly", max(0.0, float(raw.get("JumpDist") or 0)))
            except (TypeError, ValueError):
                pass
            scratch["unmapped"], scratch["new_system"], scratch["nsp"] = [], None, False
        elif event == "Scan":
            body = str(raw.get("BodyName") or "")
            if raw.get("StarType") and not raw.get("DistanceFromArrivalLS") and our_first(raw):
                address = raw.get("SystemAddress")
                scratch["new_system"] = str(address if address is not None else raw.get("StarSystem") or raw.get("BodyName") or "")
                once("first_systems", scratch["new_system"])
            if raw.get("PlanetClass") and body and raw.get("WasMapped") is False:
                unmapped = scratch.setdefault("unmapped", [])
                if body not in unmapped:
                    unmapped.append(body)
        elif event == "SAAScanComplete":
            body = str(raw.get("BodyName") or "")
            if body in (scratch.get("unmapped") or ()):
                scratch["unmapped"].remove(body)
                once("first_maps", body)
        elif event == "FSSAllBodiesFound":
            address = raw.get("SystemAddress")
            system = str(address if address is not None else raw.get("SystemName") or "")
            if system and system == scratch.get("new_system"):
                once("new_systems", system)
            once("fss_systems", system)
        elif event in {"SellExplorationData", "MultiSellExplorationData"}:
            add("uc_credits", _credits(raw.get("TotalEarnings"), raw.get("BaseValue"), raw.get("Bonus")))
        elif event == "SellOrganicData":
            total = 0.0
            for row in raw.get("BioData") or ():
                if isinstance(row, dict):
                    total += _credits(row.get("Value")) + _credits(row.get("Bonus"))
            add("vista_credits", total)
        elif event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
            once("species", str(raw.get("Species") or raw.get("Species_Localised") or ""))
            once("genera", str(raw.get("Genus") or raw.get("Genus_Localised") or ""))
            once("bio_bodies", f"{raw.get('SystemAddress')}:{raw.get('Body')}")
        elif event == "SupercruiseDestinationDrop":
            kind = str(raw.get("Type") or "")
            scratch["nsp"] = kind.startswith("$Fixed_Event_Life_") or "notable stellar" in str(raw.get("Type_Localised") or "").casefold()
        elif event == "CodexEntry" and scratch.get("nsp"):
            scratch["nsp"] = False
            add("nsp")
        elif event in {"SupercruiseEntry", "StartJump"}:
            scratch["nsp"] = False
        return self._advance(memory, hours, now)

    @staticmethod
    def _busy(scratch, event, raw, now):
        """Docking asked for, or arriving at a planet: no story until it's done."""
        if event in {"DockingRequested", "DockingGranted"}:
            scratch["docking"] = now
        elif event in {"Docked", "DockingCancelled", "DockingTimeout", "DockingDenied", "Undocked", "FSDJump", "Died"}:
            scratch["docking"] = None
        if event == "ApproachBody":
            scratch["approach"] = now
        elif event in {"Touchdown", "LeaveBody", "Docked", "FSDJump", "SupercruiseEntry", "Died"}:
            scratch["approach"] = None

    def busy(self, memory, now):
        scratch = self.state(memory)["scratch"]
        return any(scratch.get(key) and now - float(scratch[key]) < BUSY_S for key in ("docking", "approach"))

    # -- telling ---------------------------------------------------------------
    def reserved(self, memory):
        """Before the chapter she opens up in has begun: short, reserved lines."""
        if not self.opens_up:
            return False
        index = next((i for i, chapter in enumerate(self.chapters) if chapter["numeral"] == self.opens_up), None)
        return index is not None and self.chapter_ids(index)[0] not in self.told(memory)

    def unlocked(self, memory, entry_id):
        return entry_id in self.state(memory)["unlocked"]

    def due(self, memory, hours=None, now=None):
        row = self.next_passage(memory)
        return row if row is not None and self.unlocked(memory, row[0]) else None

    def complete(self, memory):
        return not self.pending and super().complete(memory)

    def ask(self, memory, entry_id, now):
        """After an entry that asks something: wait for the reply."""
        if self.entries[entry_id].get("ask"):
            self.state(memory)["question"] = {"entry": entry_id, "at": float(now)}

    def question(self, memory, now):
        """The entry waiting on a reply, or None (one asked too long ago is let go)."""
        state = self.state(memory)
        question = state.get("question")
        if not isinstance(question, dict) or question.get("entry") not in self.entries:
            gate = self.gate(memory)
            if gate is None:
                return None
            # Let go before 5.8.6 (or a reply that never came): still waiting.
            question = state["question"] = {"entry": gate, "at": float(self.told(memory).get(gate) or now), "lapsed": True}
        return question

    def _waits(self, question, now):
        """Still open: in time, or the gate (which never closes unanswered)."""
        return now - float(question["at"]) <= ASK_S or bool(self.entries[question["entry"]].get("learn_name"))

    def ask_again(self, memory, now):
        """Asking the gate's question again (a new session): the clock restarts,
        but the silence line isn't said twice."""
        question = self.question(memory, now)
        if question and self.entries[question["entry"]].get("learn_name"):
            question["at"] = question["lapsed_at"] = float(now)
            return question["entry"]
        return None

    def asks_name(self, memory, now):
        """Whether the question waiting is who you are (its answer is your name)."""
        question = self.question(memory, now)
        return bool(question and self.entries[question["entry"]].get("learn_name"))

    def reply(self, memory, text, now, fields=None):
        """Her answer to what was said (None: nothing to say to it). ``fields``
        fill her lines' {placeholders} (``commander``: how she greets you)."""
        question = self.question(memory, now)
        if not question or not self._waits(question, now):
            return None
        ask = self.entries[question["entry"]]["ask"]
        if self.entries[question["entry"]].get("learn_name"):
            self.state(memory)["restart"] = True
        mood = tone(text)
        lines = ask.get("yes" if mood == "yes" else "no" if mood == "no" else "reply")
        lines = lines if lines else ask.get("reply") or ask.get("yes") or ()
        fill = {"commander": "Commander", **(fields or {})}
        lines = tuple(line.format_map(fill) if "{" in line else line for line in lines)
        return self._close(memory, question["entry"], lines, you=text)

    def lapse(self, memory, now):
        """No reply in time: her line for that, if the entry has one."""
        question = self.question(memory, now)
        if not question or now - float(question["at"]) <= ASK_S:
            return None
        silent = self.entries[question["entry"]]["ask"].get("silent") or ()
        if self.entries[question["entry"]].get("learn_name"):
            # The gate stays open: its silence line once, then she waits.
            if question.get("lapsed"):
                return None
            question["lapsed"], question["lapsed_at"] = True, float(now)
            return question["entry"], " ".join(silent)
        return self._close(memory, question["entry"], silent, you=None)

    def _close(self, memory, entry_id, lines, you):
        state = self.state(memory)
        state.pop("question", None)
        words = " ".join(lines)
        if words or you:
            state["replies"][entry_id] = {"you": (str(you)[:400] if you else None), "her": words}
        return (entry_id, words) if words else (entry_id, "")

    def words(self, memory, passage_id):
        said = super().words(memory, passage_id)
        after = (self.state(memory)["replies"].get(passage_id) or {}).get("her") if isinstance(memory, dict) else None
        return f"{said}\n\n{after}" if after else said

    # -- headings ----------------------------------------------------------------
    def entry_number(self, passage_id):
        return int(self.entries[passage_id].get("number") or self.order.index(passage_id) + 1)

    def entry_label(self, passage_id):
        """Its number as the book shows it: "07", or "48A" for a stage of one."""
        return f"{self.entry_number(passage_id):02}{self.entries[passage_id].get('stage') or ''}"

    def _counted(self, ids):
        """How many entries these passages make: a stage that continues into the
        next isn't an entry of its own (Entry 48 counts once, when it's done)."""
        return sum(1 for key in ids if not self.entries[key].get("continues"))

    def passage_heading(self, passage_id):
        row = self._by_id[passage_id]
        entry = self.entries[passage_id]
        return f"{row[1]}. {row[2].upper()} · {self.entry_label(passage_id)} {entry['title'].upper()}"

    def heading(self, text, memory=None):
        row = self._by_words.get(str(text or ""))
        if row is None:
            return "memory", self.title.upper()
        return "memory", self.passage_heading(row[0])

    # -- the page ------------------------------------------------------------------
    def requirement(self, memory, entry_id, hours):
        """[(text, done, needed)] for an entry's requirement (alternatives: any one)."""
        state = self.state(memory)
        current = self.stage_entry(memory) == entry_id
        rows = []
        for kind, amount in self._needs(entry_id):
            value = self._value(state, kind, hours) if current else 0.0
            place = self.entries[entry_id].get("place") or {}
            where = f", {place.get('system')}" if place.get("system") else " (wherever it is now)"
            text = f"a visit to {place.get('name')}{where}" if kind == "visit" else amount_text(kind, amount)
            rows.append({"kind": kind, "text": text, "done": min(value, amount), "needed": amount, "how": HOW[kind]})
        return rows

    def status(self, memory, hours, now):
        """Where her story stands, for "what's next?": {"state": "asking" |
        "waiting" (an entry unlocked, not yet told) | "paused" | "complete" |
        "next", and for "next" the requirement rows and the entry's place}."""
        if self.question(memory, now):
            return {"state": "asking"}
        if self.due(memory) is not None:
            return {"state": "waiting"}
        entry_id = self.stage_entry(memory)
        if entry_id is None:
            return {"state": "paused" if self.pending else "complete"}
        return {"state": "next", "entry": self.entry_number(entry_id), "needs": self.requirement(memory, entry_id, hours),
                "place": self.entries[entry_id].get("place") or {}}

    def entry_place(self, entry_id):
        """The place an entry names or takes you to: {name, system} (system ""
        when it's yours to find), or None."""
        entry = self.entries[entry_id]
        if entry.get("place"):
            return {"name": entry["place"].get("name", ""), "system": entry["place"].get("system", "")}
        if entry.get("objective"):
            return {"name": entry["objective"][0], "system": entry["objective"][1]}
        return None

    def objective(self, memory):
        """The place her story has asked you to take her, until the visit to it
        (or a later request) replaces it: (place, system) or None."""
        heard, current = self.told(memory), None
        for key in self.order:
            if key not in heard:
                break
            if any(kind == "visit" for kind, _amount in self._needs(key)):
                current = None
            if self.entries[key].get("objective"):
                current = self.entries[key]["objective"]
        return current

    def page(self, memory, hours, now=None):
        now = time.time() if now is None else now
        heard = self.told(memory)
        state = self.state(memory)
        stage_entry = self.stage_entry(memory)
        nxt = self.next_passage(memory)
        chapters = []
        for index, chapter in enumerate(self.chapters):
            rows = [row for row in self.passages if row[4] == index]
            told = [{"id": row[0], "text": self.words(memory, row[0]), "at": heard[row[0]],
                     "entry": self.entry_number(row[0]), "label": self.entry_label(row[0]),
                     "title": self.entries[row[0]]["title"], "place": self.entry_place(row[0])}
                    for row in rows if row[0] in heard]
            entry = {"numeral": chapter["numeral"], "title": chapter["title"] if told else "Unopened",
                     "book": 1, "begun": bool(told), "complete": len(told) == len(rows), "told": told,
                     "told_count": self._counted(row["id"] for row in told),
                     "total": self._counted(row[0] for row in rows), "about": chapter.get("about", "") if told else "",
                     "account": "\n\n".join(row["text"] for row in told) if len(told) == len(rows) else ""}
            if not told:
                first = rows[0][0]
                needs = self.requirement(memory, first, hours)
                entry["unlock"] = ["Opens in order, after the chapter before"] + [
                    f"Entry {self.entry_label(first)} needs {' or '.join(row['text'] for row in needs)}"]
                if stage_entry == first:
                    entry["waits_for"] = " or ".join(row["text"] for row in needs)
            chapters.append(entry)
        for row in self.pending:
            # (numeral, title[, note]): a later chapter, not yet reachable.
            note = row[2] if len(row) > 2 else "Still being written"
            chapters.append({"numeral": row[0], "title": "Unopened", "book": 1, "begun": False, "complete": False,
                             "told": [], "total": 6, "about": "", "account": "", "pending": True, "unlock": [note]})
        next_ = None
        if nxt:
            ready = self.due(memory) is not None
            next_ = {"ready": ready, "strict": True, "hours": 0, "days": 0, "opening": nxt[0] == self.chapter_ids(nxt[4])[0],
                     "entry": self.entry_number(nxt[0]), "label": self.entry_label(nxt[0])}
            if not ready and stage_entry:
                needs = self.requirement(memory, stage_entry, hours)
                next_.update(waits_for=" or ".join(row["text"] for row in needs),
                             progress=[{"text": row["text"], "done": row["done"], "needed": row["needed"]} for row in needs],
                             how=" ".join(dict.fromkeys(row["how"] for row in needs)))
        complete = nxt is None and not self.pending
        books = []
        if complete:
            books.append({"name": "One", "title": self.book_title,
                          "chapters": [{"numeral": row["numeral"], "title": row["title"], "account": row["account"]}
                                       for row in chapters]})
        question = self.question(memory, now)
        objective = self.objective(memory)
        return {"identity": self.identity, "title": self.title, "unit": self.unit, "told": self._counted(heard),
                "objective": {"place": objective[0], "system": objective[1]} if objective else None,
                "total": self._counted(self.order), "planned": len(self.chapters) + len(self.pending), "chapters": chapters,
                "next": next_, "complete": complete, "paused": nxt is None and bool(self.pending),
                "echoes": [], "echo_total": 0, "echo_labels": {}, "echo_how": {}, "books": books,
                "asking": bool(question and self._waits(question, now)),
                "empty_note": self.empty_note,
                "complete_note": self.complete_note if complete else self.paused_note}


def _credits(*values):
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            return number
    return 0.0
