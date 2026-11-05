"""Paced, journal-gated stories for the officer-style companions (5.7.4).

A story is a list of chapters, told one passage at a time in quiet moments.
Each passage has an hours-together threshold. A chapter can also wait for
something real in the journal (a delivery, a first discovery, a neutron
star...) and for real days since the chapter before. Every gate has a time
alternative, so no play style is locked out of the ending.

Echoes are short asides that real events stir once the story has begun.
They only refer to chapters the commander has already heard.
"""
import math
import time

_SOL_FAR_LY = 10000.0
_SOL_DEEP_LY = 20000.0


def signals(event, raw):
    """What a journal event counts towards. Only real fields are used."""
    raw = raw if isinstance(raw, dict) else {}
    out = set()
    star = str(raw.get("StarClass") or raw.get("StarType") or "")
    if event == "FSDJump":
        out.add("jump")
        try:
            if float(raw.get("JumpDist") or 0) >= 50:
                out.add("long_jump")
        except (TypeError, ValueError):
            pass
        position = raw.get("StarPos")
        try:
            if isinstance(position, (list, tuple)) and len(position) == 3:
                far = math.sqrt(sum(float(value) ** 2 for value in position))
                if far >= _SOL_FAR_LY:
                    out.add("far")
                if far >= _SOL_DEEP_LY:
                    out.add("deep")
        except (TypeError, ValueError):
            pass
    if event in {"StartJump", "Scan"} and star:
        if star == "N":
            out.add("neutron")
        elif star == "H":
            out.add("black_hole")
        elif star == "SupermassiveBlackHole":
            out.add("core")
        elif star.startswith("D") and len(star) <= 3:
            out.add("white_dwarf")
    if event == "JetConeBoost":
        out.add("neutron")
    if event == "Docked":
        out.add("arrival")
        if str(raw.get("StationType") or "").casefold() in {"megaship", "megashipsrv"}:
            out.add("megaship")
    if event == "FSSSignalDiscovered" and str(raw.get("SignalType") or "") in {"Megaship", "StationMegaShip"}:
        out.add("megaship")
    if event in {"MarketSell", "CargoDepot"} or event == "MissionCompleted":
        out.add("delivery")
    if event == "MissionCompleted":
        out.add("mission")
    if event == "Scan" and raw.get("BodyName"):
        out.add("scan")
        if raw.get("WasDiscovered") is False:
            out.add("first")
        planet = str(raw.get("PlanetClass") or "")
        if planet == "Earthlike body":
            out.add("earthlike")
        elif planet == "Water world":
            out.add("water_world")
        elif planet == "Ammonia world":
            out.add("ammonia")
        if raw.get("Rings") and planet:
            out.add("rings")
    if event == "SAAScanComplete":
        out.add("map")
    if event == "FSSAllBodiesFound":
        out.add("system_complete")
    if event == "ScanOrganic" and str(raw.get("ScanType") or "") == "Analyse":
        out.add("bio")
    if event == "Touchdown" and raw.get("PlayerControlled", True):
        out.add("landing")
    if event == "Disembark" and raw.get("OnPlanet"):
        out.add("footfall")
    if event in {"MiningRefined", "AsteroidCracked"}:
        out.add("mining")
    if event == "Bounty":
        out.add("bounty")
    if event == "FactionKillBond":
        out.add("bond")
    if event == "EscapeInterdiction":
        out.add("escape")
    if event == "CodexEntry" and raw.get("IsNewEntry"):
        out.add("codex")
    if event in {"SellExplorationData", "MultiSellExplorationData", "SellOrganicData"}:
        out.add("data_sale")
    if event in {"FuelScoop"}:
        out.add("scoop")
    if event == "CarrierJump":
        out.add("carrier_jump")
    if event in {"RepairAll", "Repair"}:
        out.add("repair")
    if event == "EngineerCraft":
        out.add("engineer")
    if event == "Resurrect":
        out.add("rebuy")
    return out


def _numeral_key(numeral):
    return "c" + str(numeral)


class Story:
    """One companion's story and its pacing rules."""

    def __init__(self, *, identity, title, prefix, unit, chapters, settle_s=10 * 60, gap_s=45 * 60,
                 lull_s=120, grace_hours=18.0, echoes=None, musings=(), after=(), first_hours=None,
                 empty_note="", complete_note="", book_title=None):
        self.identity, self.title, self.prefix, self.unit = identity, title, prefix, unit
        self.settle_s, self.gap_s, self.lull_s, self.grace_hours = settle_s, gap_s, lull_s, grace_hours
        self.chapters = tuple(chapters)
        self.echoes = dict(echoes or {})
        self.musings, self.after = tuple(musings), tuple(after)
        self.empty_note = empty_note or f"{title} begins after a little time together, in a quiet moment."
        self.complete_note = complete_note or f"{title} is complete."
        self.book_title = book_title or title
        rows = []
        for index, chapter in enumerate(self.chapters):
            first, last = chapter["hours"]
            lines = chapter["passages"]
            for number, words in enumerate(lines):
                if index == 0 and first_hours:
                    hours = first_hours[min(number, len(first_hours) - 1)]
                else:
                    hours = round(first + (last - first) * number / max(1, len(lines) - 1), 2)
                rows.append((f"{prefix}_{index + 1:02}_{number + 1:02}", chapter["numeral"], chapter["title"],
                             hours, index, words))
        self.passages = tuple(rows)
        self._by_id = {row[0]: row for row in rows}
        self._by_words = {row[5]: row for row in rows}

    # -- what has been heard --------------------------------------------------
    def told(self, memory):
        out = {}
        for row in (memory or {}).get("lore") or ():
            if isinstance(row, (list, tuple)) and len(row) >= 2 and str(row[0]) in self._by_id:
                out[str(row[0])] = float(row[1] or 0)
        return out

    def chapter_ids(self, index):
        return [row[0] for row in self.passages if row[4] == index]

    def complete_chapters(self, memory):
        heard = self.told(memory)
        return [index for index in range(len(self.chapters))
                if all(key in heard for key in self.chapter_ids(index))]

    def begun(self, memory):
        return self.passages[0][0] in self.told(memory)

    def complete(self, memory):
        return len(self.told(memory)) == len(self.passages)

    def words(self, memory, passage_id):
        row = self._by_id.get(passage_id)
        return (memory or {}).get("aster_lore_words", {}).get(passage_id) or (row[5] if row else "")

    # -- gates ---------------------------------------------------------------
    @staticmethod
    def marks(memory):
        return (memory or {}).get("aster_marks") or {}

    def _gate(self, chapter):
        gate = chapter.get("gate")
        return gate if isinstance(gate, dict) else None

    def gate_met(self, memory, index, hours):
        chapter = self.chapters[index]
        gate = self._gate(chapter)
        if not gate:
            return True
        found = sum(int(self.marks(memory).get(name, 0) or 0) for name in gate["signals"])
        return found >= int(gate.get("count", 1)) or float(hours or 0) >= chapter["hours"][0] + self.grace_hours

    def days_left(self, memory, index, now):
        days = float(self.chapters[index].get("days") or 0)
        if not days or index == 0:
            return 0.0
        heard = self.told(memory)
        before = [heard[key] for key in self.chapter_ids(index - 1) if key in heard]
        if not before:
            return days
        return max(0.0, days - (float(now) - max(before)) / 86400.0)

    def next_passage(self, memory, hours=None):
        heard = self.told(memory)
        return next((row for row in self.passages if row[0] not in heard), None)

    def due(self, memory, hours, now=None):
        """The next passage, if every gate allows it. Always in order."""
        now = time.time() if now is None else now
        row = self.next_passage(memory)
        if row is None or float(hours or 0) < row[3]:
            return None
        if row[0] == self.chapter_ids(row[4])[0]:
            if not self.gate_met(memory, row[4], hours) or self.days_left(memory, row[4], now) > 0:
                return None
        return row

    # Compatibility with the original Aster API.
    def gate_ready(self, memory, gate, hours):
        return True

    # -- echoes --------------------------------------------------------------
    def echo_for(self, found, memory):
        """The first echo stirred by these signals that the story allows."""
        if not self.begun(memory):
            return None
        complete = {self.chapters[index]["numeral"] for index in self.complete_chapters(memory)}
        for key, echo in self.echoes.items():
            after = echo.get("after")
            if found & set(echo["signals"]) and (not after or after in complete):
                return key
        return None

    def echo_topics(self):
        return {"echo_" + key: tuple(echo["lines"]) for key, echo in self.echoes.items()}

    def echo_rests(self):
        return {"echo_" + key: float(echo.get("rest_hours", 12)) * 3600 for key, echo in self.echoes.items()}

    # -- lines that look back --------------------------------------------------
    def recall_lines(self):
        """Lookbacks, each prefixed with a chapter placeholder that only
        formats once that chapter has been completely heard."""
        out = []
        for chapter in self.chapters:
            out.extend("{" + _numeral_key(chapter["numeral"]) + "}" + line for line in chapter.get("recall", ()))
        return tuple(out)

    def recall_fields(self, index):
        return {_numeral_key(self.chapters[index]["numeral"]): ""}

    def heading(self, text, memory=None):
        row = self._by_words.get(str(text or ""))
        if row is None and memory:
            words = (memory.get("aster_lore_words") or {})
            row = next((self._by_id.get(key) for key, said in words.items() if said == text and key in self._by_id), None)
        if row is None:
            return "memory", self.title.upper()
        same = self.chapter_ids(row[4])
        return "memory", f"{self.unit.upper()} · {row[1]}. {row[2].upper()} · {same.index(row[0]) + 1} OF {len(same)}"

    def passage_heading(self, passage_id):
        row = self._by_id[passage_id]
        same = self.chapter_ids(row[4])
        return f"{self.unit.upper()} · {row[1]}. {row[2].upper()} · {same.index(row[0]) + 1} OF {len(same)}"

    # -- the page ------------------------------------------------------------
    def _unlock(self, memory, index, hours, now):
        chapter = self.chapters[index]
        notes = [f"After about {self._hours_text(chapter['hours'][0])} together"]
        gate = self._gate(chapter)
        if gate:
            notes.append(f"Opens with {gate['label']}")
            notes.append(gate["how"])
            notes.append(f"Or after about {self._hours_text(chapter['hours'][0] + self.grace_hours)} together")
        if chapter.get("days") and index:
            notes.append(f"At least {self._days_text(chapter['days'])} after the chapter before")
        return notes

    @staticmethod
    def _hours_text(hours):
        hours = float(hours)
        if hours < 1:
            return f"{max(1, round(hours * 60))} minutes"
        return f"{hours:.0f} hour{'s' if round(hours) != 1 else ''}"

    @staticmethod
    def _days_text(days):
        days = float(days)
        return f"{days:.0f} day{'s' if round(days) != 1 else ''}"

    def page(self, memory, hours, now=None):
        now = time.time() if now is None else now
        heard = self.told(memory)
        hours = float(hours or 0)
        chapters = []
        nxt = self.next_passage(memory)
        for index, chapter in enumerate(self.chapters):
            rows = [row for row in self.passages if row[4] == index]
            told = [{"id": row[0], "text": self.words(memory, row[0]), "at": heard[row[0]]}
                    for row in rows if row[0] in heard]
            entry = {"numeral": chapter["numeral"], "title": chapter["title"] if told else "Unopened",
                     "book": 1, "begun": bool(told), "complete": len(told) == len(rows), "told": told,
                     "total": len(rows), "about": chapter.get("about", "") if told else "",
                     "account": "\n\n".join(row["text"] for row in told) if len(told) == len(rows) else ""}
            if not told:
                entry["unlock"] = self._unlock(memory, index, hours, now)
                gate = self._gate(chapter)
                if nxt and nxt[4] == index and gate and not self.gate_met(memory, index, hours):
                    entry["waits_for"] = gate["label"]
            chapters.append(entry)
        next_ = None
        if nxt:
            index = nxt[4]
            opening = nxt[0] == self.chapter_ids(index)[0]
            days = self.days_left(memory, index, now) if opening else 0.0
            gated = opening and not self.gate_met(memory, index, hours)
            next_ = {"hours": round(max(0.0, nxt[3] - hours), 2), "days": round(days, 2),
                     "ready": self.due(memory, hours, now) is not None, "opening": opening}
            if gated:
                gate = self._gate(self.chapters[index])
                next_.update(waits_for=gate["label"], how=gate["how"],
                             grace=round(max(0.0, self.chapters[index]["hours"][0] + self.grace_hours - hours), 1))
        found = self.marks(memory)
        complete_numerals = {self.chapters[index]["numeral"] for index in self.complete_chapters(memory)}
        echoes = []
        for key, echo in self.echoes.items():
            if echo.get("after") and echo["after"] not in complete_numerals:
                continue
            count = sum(int(found.get(name, 0) or 0) for name in echo["signals"])
            said = (memory or {}).get("aster_wording", {}).get("echo_" + key)
            if count:
                echoes.append({"topic": key, "count": count, "at": float(said or 0)})
        complete = nxt is None
        books = []
        if complete:
            books.append({"name": "One", "title": self.book_title,
                          "chapters": [{"numeral": row["numeral"], "title": row["title"], "account": row["account"]}
                                       for row in chapters]})
        return {"identity": self.identity, "title": self.title, "unit": self.unit, "told": len(heard),
                "total": len(self.passages), "chapters": chapters, "next": next_, "complete": complete,
                "echoes": echoes, "echo_total": len(self.echoes),
                "echo_labels": {key: echo["label"] for key, echo in self.echoes.items()},
                "echo_how": {key: echo["how"] for key, echo in self.echoes.items()},
                "books": books, "empty_note": self.empty_note, "complete_note": self.complete_note}
