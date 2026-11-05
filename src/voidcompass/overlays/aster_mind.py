"""Aster's officer on watch: original dialogue and a separate paced memory."""
import re
import zlib
from types import SimpleNamespace

from voidcompass.core import companions
from datetime import datetime

from voidcompass.overlays import (
    aster_dockside, companion_idle, companion_personas, companion_story,
    watcher_mind, watcher_name, watcher_copilot, watcher_questions, watcher_habits,
    watcher_deeper, watcher_places, crew_voices,
)


HATCHLING_PASSIVE = {"hatchling_idle", "hatchling_said"}
# Keepsakes and the deeper company (5.7.4), headed as the Watcher heads them.
KEEPSAKE_HEADINGS = {
    **{topic: watcher_mind.HEADED_TOPICS[topic] for topic in
       ("capsule", "capsule_shared", "capsule_early", "on_this_day", "constellation_named", "dream_told")},
    "anniversary_us": ("recall", "AN ANNIVERSARY"),
    "watchers_meet": ("memory", "ANOTHER COMMANDER'S COMPANION"),
    "companion_wish": ("memory", "A REQUEST"),
    "companion_wish_reached": ("memory", "A REQUEST, KEPT"),
}
# Said in the next quiet moment once queued (a note from last watch, an anniversary).
QUEUED_TOPICS = {"dream_told", "anniversary_us", "companion_wish_reached"}
DATA_SALES = {"SellExplorationData", "MultiSellExplorationData", "SellOrganicData"}
HATCHLING_MOMENT_AGE_S = 120


def _fingerprint(words):
    return f"{zlib.crc32(words.encode('utf-8')):08x}"


def _text_key(script):
    return _fingerprint(" ".join(watcher_mind.plain_text(script).casefold().split()))


class OfficerRandom:
    @property
    def companion_identity(self):
        return self.mind.identity

    def __init__(self, source, mind):
        self.source, self.mind = source, mind

    def __getattr__(self, attribute):
        return getattr(self.source, attribute)

    def command_choice(self, outcome, lines):
        return self._choice("aster_commands", outcome, lines)

    def dialogue_choice(self, kind, lines):
        return self._choice("aster_dialogue", kind, lines)

    def farewell_choice(self, topic, lines):
        return self._choice("aster_farewells", topic, lines)

    def welcome_choice(self, topic, lines):
        return self._choice("aster_welcomes", topic, lines)

    def format_words(self, template, fields):
        return self.mind.persona.naming.format_words(self.mind.memory, template, fields)

    def _choice(self, collection, outcome, lines):
        keys = {line: _fingerprint(line) for line in lines}
        with self.mind.lock:
            history = self.mind.memory.setdefault(collection, {})
            if outcome not in history and collection == "aster_dialogue":
                # Existing installations already have conversation records.
                heard = [keys[row["it"]] for row in self.mind.memory.get("talk", []) if row.get("it") in keys]
                history[outcome] = list(dict.fromkeys(reversed(heard)))[::-1]
            if outcome not in history and collection in {"aster_farewells", "aster_welcomes"}:
                heard = [line for line in lines
                         if f"aster:{outcome}:{keys[line]}" in self.mind.memory["aster_wording"]]
                heard.sort(key=lambda line: self.mind._last_said(f"aster:{outcome}:{keys[line]}"))
                previous = self.mind.memory["aster_event_last"].get(outcome)
                heard.sort(key=lambda line: f"aster:{outcome}:{keys[line]}" == previous)
                history[outcome] = [keys[line] for line in heard]
            used = [key for key in history.get(outcome, []) if key in keys.values()]
            last_key = collection + ":" + outcome
            previous = self.mind.memory.setdefault("aster_choice_last", {}).get(last_key) or (used[-1] if used else None)
            fresh = [line for line in lines if keys[line] not in used]
            if not fresh:
                used = []
                fresh = list(lines)
            # The previous cycle's final line still belongs to the new cycle;
            # only exclude it from this first draw, rather than marking it used.
            fresh = [line for line in fresh if keys[line] != previous] or fresh
            line = self.source.choice(fresh)
            history[outcome] = (used + [keys[line]])[-len(lines):]
            self.mind.memory["aster_choice_last"][last_key] = keys[line]
            self.mind._unsaved = True
        return line


class AsterMind(watcher_mind.WatcherMind):
    identity = "aster"

    @property
    def persona(self):
        return companion_personas.get(self.identity)

    @property
    def restrained(self):
        return self.config.get(self.persona.humour_key, "dry") == "off"

    @property
    def chat_bank(self):
        lines = self.persona.lines
        if not self.restrained:
            return lines
        def answer(kind, rng, previous=None, used=()):
            return lines.answer(kind, rng, previous, used, restrained=True)
        return SimpleNamespace(GREETINGS=lines.RESTRAINED_GREETINGS, CAPABILITIES=lines.CAPABILITIES, answer=answer)

    def __init__(self, memory_path=None, config=None, **kwargs):
        super().__init__(memory_path, companions.settings(config if config is not None else {}, self.identity), **kwargs)
        self.random = OfficerRandom(self.random, self)
        # Keep event wording independently of the shared, bounded activity log.
        # A busy spell of direct commands must not make earlier reports new again.
        wording = self.memory.setdefault("aster_wording", {})
        last = self.memory.setdefault("aster_event_last", {})
        headlines = self.memory.setdefault("aster_headlines", {})
        previous = {}
        for key, at in self.memory["said"]:
            if str(key).startswith("aster:") and str(key).split(":")[1] in self.persona.lines.EVENTS:
                topic = str(key).split(":")[1]
                wording[key] = max(wording.get(key, 0), at)
                wording[topic] = max(wording.get(topic, 0), at)
                previous[topic] = key
            elif str(key).startswith("aster:galnet:"):
                headlines[key] = max(headlines.get(key, 0), at)
        for topic, key in previous.items():
            last.setdefault(topic, key)
        wording["aster:hatchling"] = max((at for topic, at in wording.items() if topic.startswith("hatchling_")),
                                         default=wording.get("aster:hatchling", 0))
        texts = self.memory.setdefault("aster_texts", {})
        for at, topic, words in self.memory.get("log", []):
            if topic in self.persona.lines.EVENTS:
                key = _text_key(words)
                texts[key] = max(texts.get(key, 0), at)
        question = (self.memory.get("questions") or {}).get("your_name", {})
        if (question.get("asked") is not None and not question.get("answer") and not question.get("cancelled")
                and not watcher_name.record(self.memory).get("call")
                and 0 <= self.clock() - question["asked"] <= watcher_questions.UNANSWERED_S
                and question.get("fields", {}).get("name") == watcher_name.record(self.memory).get("known")):
            self._question = {"id": "your_name", "asked": question["asked"], "fields": question["fields"],
                              "text": question.get("text", "")}

    @staticmethod
    def _fresh_memory():
        memory = watcher_mind.WatcherMind._fresh_memory()
        memory.update(aster_marks={}, aster_systems=[], aster_arrivals=[], aster_moments=[],
                      aster_wording={}, aster_event_last={}, aster_texts={},
                      aster_commands={}, aster_dialogue={}, aster_choice_last={}, aster_headlines={},
                      aster_hatchling_seen={}, aster_idle_recalled={}, aster_farewells={}, aster_lore_words={},
                      aster_welcomes={}, aster_load_game=None)
        return memory

    def _fresh_state(self):
        super()._fresh_state()
        self._aster_game_session = False

    def command_words(self, words):
        return companions.addressed(words, self.identity) or "hello " + self.identity

    def event_lines(self, topic):
        return self.persona.lines.event_lines(topic, self.restrained)

    def _importance(self, topic):
        """The shared importance, raised for what this companion's role cares about."""
        return max(watcher_mind.IMPORTANCE.get(topic, 1), self.persona.interests.get(topic, 0))

    def _variant(self, topic, fields):
        lines = self.event_lines(topic)
        candidates = []
        eligible = {}
        for line in lines:
            try:
                noticed = watcher_mind.noticed(fields)
                factual = line.format(**noticed)
                words = self.random.format_words(line, noticed)
            except (KeyError, IndexError, ValueError):
                continue
            key = f"aster:{topic}:{_fingerprint(line)}"
            candidates.append((key, words, factual != line))
            eligible[line] = (key, words)
        if not candidates:
            return None
        if topic in {"sign_off", "sign_off_quiet"}:
            return eligible[self.random.farewell_choice(topic, tuple(eligible))]
        if topic in {"greet_new", "greet_away"}:
            return eligible[self.random.welcome_choice(topic, tuple(eligible))]
        def text_fresh(row, window):
            at = self.memory["aster_texts"].get(_text_key(row[1]))
            return at is None or self.clock() - at >= window
        fresh = [row for row in candidates if not self._said_recently(row[0], 30 * 86400) and text_fresh(row, 3 * 86400)]
        if fresh:
            return self.random.choice(fresh)[:2]
        # Its interests make it speak up more, not repeat itself: once the
        # lines for an everyday topic are used, it still goes quiet on it.
        if watcher_mind.IMPORTANCE.get(topic, 1) < 2:
            fresh = [row for row in candidates
                     if not self._said_recently(row[0], 86400 if row[2] else 3 * 86400)
                     and text_fresh(row, 86400 if row[2] else 3 * 86400)]
            return self.random.choice(fresh)[:2] if fresh else None
        # Important reports and direct calls still answer after exhaustion.
        # Avoid the immediately preceding wording even when timestamps tie.
        previous = self.memory["aster_event_last"].get(topic)
        different = [row for row in candidates if row[0] != previous]
        candidates = different or candidates
        unheard_text = [row for row in candidates if text_fresh(row, 3 * 86400)]
        candidates = unheard_text or candidates
        order = {key: index for index, key in enumerate(self.memory["aster_wording"])}
        candidates.sort(key=lambda row: (self._last_said(row[0]), order.get(row[0], -1)))
        return self.random.choice(candidates[:max(1, len(candidates) // 3)])[:2]

    def _last_said(self, key):
        at = self.memory["aster_wording"].get(key)
        return at if at is not None else super()._last_said(key)

    def _said_recently(self, key, within):
        at = self.memory["aster_wording"].get(key)
        return self.clock() - at < within if at is not None else super()._said_recently(key, within)

    def _hatchling_allowed(self, topic, fields, setting, now):
        at = fields.get("_moment_at")
        if at is not None:
            try:
                if now - float(at) > HATCHLING_MOMENT_AGE_S:
                    return False
            except (TypeError, ValueError):
                return False
        moment = fields.get("_moment_id")
        if moment:
            with self.lock:
                seen = self.memory["aster_hatchling_seen"]
                key = _fingerprint(str(moment))
                if key in seen:
                    return False
                # Consume a real notice even if we stay quiet. A restart must
                # not turn a previously deferred moment into a fresh milestone.
                seen[key] = now
                while len(seen) > 128:
                    del seen[next(iter(seen))]
                self._unsaved = True
        if self._in_danger:
            return False
        if topic in HATCHLING_PASSIVE:
            return (not self._said_recently("aster:hatchling", watcher_mind.IDLE_REST_S)
                    and not self._said_recently("idle", setting["mutter"])
                    and now - self._last_spoke >= setting["quiet"]
                    and now - self._last_interesting >= setting["quiet"])
        # Tricks arrive through a forced event path, but ordinary pet chatter
        # must still leave room between reports. A new growth stage is rare.
        return topic == "hatchling_grown" or not self._said_recently("aster:hatchling", max(600, setting["rest"]))

    def consider(self, topic, fields=None, force=False):
        setting = watcher_mind.FREQUENCIES.get(watcher_mind.frequency(self.config))
        if setting is None or topic not in self.persona.lines.EVENTS:
            return None
        importance = self._importance(topic)
        if topic.startswith("echo_"):
            importance = 2
        if topic.startswith("companion_wish"):
            importance = 3
        at_port = aster_dockside.active(self.surroundings)
        if topic in aster_dockside.TOPICS and not at_port:
            return None
        if companion_idle.casual(topic):
            if self._in_danger:
                return None
            # Like Watcher's quiet musings, company remains eligible on
            # Rare. Its wording still has minor-remark rests and voice level.
            importance = max(importance, 2)
        now = self.clock()
        fields = dict(fields or {})
        if topic.startswith("hatchling_") and not self._hatchling_allowed(topic, fields, setting, now):
            return None
        if not force:
            if importance < setting["minimum"] or (importance < 3 and now - self._last_spoke < setting["gap"]):
                return None
            rest = setting.get("rest", 1200)
            if topic.startswith("idle_"):
                rest = max(rest, watcher_mind.IDLE_REST_S)
            if topic == "idle_galnet":
                rest = max(rest, watcher_mind.GALNET_REST_S)
            rest = max(rest, companion_idle.RESTS.get(topic, 0), self.persona.story.echo_rests().get(topic, 0))
            if topic.startswith("habit_") and topic != "habit_milestone":
                rest = max(rest, watcher_habits.HABIT_REST_S)
            if importance < 3 and self._said_recently(topic, rest):
                return None
            if importance < 3 and self.random.random() > .35 + .25 * importance:
                return None
        if self._in_danger and importance < 2:
            return None
        headline = None
        if topic == "idle_galnet":
            words = str((fields or {}).get("headline") or "").strip().casefold()
            headline = f"aster:galnet:{zlib.crc32(words.encode('utf-8')):08x}"
            at = self.memory["aster_headlines"].get(headline)
            if at is not None and now - at < watcher_mind.GALNET_HEADLINE_REST_S:
                return None
        recall = fields.get("_recall")
        if recall is not None:
            previous = self.memory.get("aster_idle_recalled", {}).get(recall)
            if previous is not None and now - previous < companion_idle.RECALL_REST_S:
                return None
        chosen = self._variant(topic, fields)
        if not chosen:
            return None
        thought = self._utter(topic, *chosen, now)
        if recall is not None:
            with self.lock:
                recalled = self.memory.setdefault("aster_idle_recalled", {})
                recalled.pop(recall, None)
                recalled[recall] = now
                while len(recalled) > 256:
                    del recalled[next(iter(recalled))]
        if headline:
            with self.lock:
                self.memory["said"].append([headline, now])
                headlines = self.memory["aster_headlines"]
                headlines.pop(headline, None)
                headlines[headline] = now
                while len(headlines) > 128:
                    del headlines[next(iter(headlines))]
        return thought

    def _utter(self, topic, key, script, now):
        thought = super()._utter(topic, key, script, now)
        if companion_idle.casual(topic):
            thought["importance"] = 1
        if topic in self.persona.lines.EVENTS:
            with self.lock:
                self.memory["aster_wording"].pop(key, None)
                self.memory["aster_wording"].update({key: now, topic: now})
                self.memory["aster_event_last"][topic] = key
                texts = self.memory["aster_texts"]
                texts.pop(_text_key(script), None)
                texts[_text_key(script)] = now
                while len(texts) > 512:
                    del texts[next(iter(texts))]
                if topic.startswith("hatchling_"):
                    self.memory["aster_wording"]["aster:hatchling"] = now
                if topic in HATCHLING_PASSIVE:
                    self.memory["aster_wording"]["idle"] = now
        persona = self.persona
        if topic == "aster_lore":
            passage = key.rsplit(":", 1)[-1]
            heading = persona.story.passage_heading(passage) if passage in {row[0] for row in persona.story.passages} else None
            thought["kind"], thought["heading"] = ("memory", heading) if heading else persona.story.heading(thought["text"], self.memory)
            thought["importance"] = 3
        elif topic.startswith("echo_"):
            thought.update(kind="memory", heading=persona.story.title.upper())
            self._story_changed = True
        elif topic.startswith("aster_name_"):
            thought.update(kind="memory", heading=persona.naming.heading(topic), importance=3)
        elif topic.startswith("handover_from_"):
            thought.update(kind="", heading="CHANGE OF WATCH")
        elif topic in KEEPSAKE_HEADINGS:
            kind, heading = KEEPSAKE_HEADINGS[topic]
            thought.update(kind=kind, heading=persona.keepsakes.NOTES_TITLE if topic == "dream_told" else heading)
        elif topic == "talk":
            thought["heading"] = persona.reply_heading
        elif topic != "relay":
            thought["kind"] = ""
            thought["heading"] = persona.advisory_heading if thought["importance"] >= 3 else persona.watch_heading
        return thought

    def event_lines_known(self, topic):
        return topic in self.persona.lines.EVENTS

    def _voice_feel(self, topic, key):
        return {"pace": self.persona.lore_pace if topic == "aster_lore" else 1.0, "gain": 1.0}

    def _plain_answer(self, words):
        lines = []
        if watcher_copilot.PLAIN_QUESTION.search(words) and callable(self.lookup_provider):
            try:
                lines = [str(line) for line in self.lookup_provider(self.command_words(words)) or () if line]
            except Exception:
                pass
        return watcher_copilot.plain_answer(lines) or self.persona.lines.command_reply("plain", self.random, {})

    def load_game(self, raw):
        stamp = str(raw.get("timestamp") or "").strip()
        login = [stamp, str(raw.get("FID") or ""), str(raw.get("Commander") or "")]
        if stamp and login == self.memory.get("aster_load_game"):
            return None
        now = self.clock()
        # Rank/Location or a fresh docked snapshot may wake us just before
        # LoadGame. That single welcome belongs to this login, not two watches.
        just_woke = (not self._aster_game_session and self._session_start is not None
                     and 0 <= now - self._session_start <= 5
                     and (self.thought or {}).get("topic") in {"greet_new", "greet_away"})
        if just_woke:
            self._aster_game_session = True
            watcher_name.count_session(self.memory, self._session_start)
            thought = None
        else:
            thought = self.session_start(login=True)
        if stamp:
            self.memory["aster_load_game"] = login
        self._unsaved = True
        self.save()
        return thought

    def session_start(self, *, login=False):
        now = self.clock()
        if not login and self._session_start is not None and now - (getattr(self, "_last_event_at", now) or now) < 900:
            return None
        self._session_start = self._counted_until = now
        self._aster_game_session = login
        self._record_said = set()
        self.surroundings.reset_session()
        with self.lock:
            first = not int(self.memory.get("sessions") or 0)
            self._persona_extras(now)
            self.memory["sessions"] = int(self.memory.get("sessions") or 0) + 1
            self.memory["session_started"] = now
            self.memory["first_seen"] = self.memory.get("first_seen") or now
            watcher_name.count_session(self.memory, now)
        return self.consider("greet_new" if first else "greet_away", force=True)

    def _persona_extras(self, now):
        """After the welcome: last watch's note, perhaps, and an anniversary."""
        last = self.memory.get("last_seen")
        if last:
            watcher_deeper.settle(self.memory, max(0.0, now - float(last)) / 86400)
        note = next((row for row in reversed(self.memory.get("dreams") or []) if isinstance(row, dict) and not row.get("told")), None)
        if note and self.random.random() < .6:
            note["told"] = now
            self._say_next.append(("dream_told", {"dream": note["text"]}))
        first = self.memory.get("first_seen")
        if first:
            then, today = datetime.fromtimestamp(float(first)), datetime.fromtimestamp(now)
            years = today.year - then.year
            if years >= 1 and (then.month, then.day) == (today.month, today.day):
                what = f"{years} year{'s' if years != 1 else ''} since we first flew together"
                self._say_next.append(("anniversary_us", {"What": what[:1].upper() + what[1:], "what": what, "what_lower": what}))

    def observe(self, event, raw=None):
        raw = raw if isinstance(raw, dict) else {}
        previous_name = watcher_name.record(self.memory).get("known")
        marks = self.memory.setdefault("aster_marks", {})
        found = companion_story.signals(event, raw)
        if event == "FSDJump":
            system = str(raw.get("StarSystem") or "")
            known = self.memory.setdefault("aster_systems", [])
            if system and system in known:
                found.add("return")
            elif system:
                known.append(system)
                del known[:-3000]
            if system:
                self.memory["last_system"] = system
        for name in found:
            marks[name] = int(marks.get(name, 0) or 0) + 1
        # Story echoes only answer the event that stirred them.
        self._story_signals = found
        if event in {"Location", "CarrierJump"} and raw.get("StarSystem"):
            self.memory["last_system"] = str(raw["StarSystem"])
        if event in {"Docked", "FSDJump", "MissionCompleted", "SellExplorationData", "MultiSellExplorationData", "SellOrganicData"}:
            moments = self.memory.setdefault("aster_moments", [])
            moments.append({"event": event, "at": self.clock(), "system": str(raw.get("StarSystem") or self.memory.get("last_system") or ""),
                            "station": str(raw.get("StationName") or "")})
            del moments[:-100]
        self._unsaved = True
        thought = super().observe(event, raw)
        if previous_name and previous_name != watcher_name.record(self.memory).get("known") and self._question:
            self._question = None
            self.memory["questions"]["your_name"]["cancelled"] = self.clock()
        return thought

    def _event_echo(self, event, raw):
        key = self.persona.story.echo_for(getattr(self, "_story_signals", set()), self.memory)
        return "echo_" + key if key else None

    def _dream(self):
        """Signing off: a note in its own after-watch log (5.7.4)."""
        if self._session_start is None:
            return None
        moments = [row for row in self.memory.get("aster_moments") or () if isinstance(row, dict)
                   and float(row.get("at") or 0) >= self._session_start]
        thing = ""
        if moments:
            row = moments[-1]
            place, station = row.get("system") or "", row.get("station") or ""
            thing = {"Docked": f"our docking at {station or place}", "FSDJump": f"the jump to {place}",
                     "MissionCompleted": f"a mission completed in {place}"}.get(row.get("event"), f"the data we sold in {place}")
        notes = [line for line in self.persona.keepsakes.NOTES if thing or "{thing}" not in line]
        line = self.random.choice(notes)
        text = line.format(place=self.memory.get("last_system") or "the last system we saw", thing=thing)
        text = re.sub(r"(^|[.!?] )([a-z])", lambda match: match[1] + match[2].upper(), text)
        with self.lock:
            dreams = self.memory.setdefault("dreams", [])
            dreams.append({"at": self.clock(), "text": text, "told": None})
            del dreams[:-watcher_deeper.DREAMS_KEPT]
        return text

    def _observe_deeper(self, event, raw, now):
        """Places reached and what moves its confidence (5.7.4). The Watcher's
        books, shutter and dreams stay its own."""
        system = raw.get("StarSystem") or raw.get("SystemName")
        with self.lock:
            memory = self.memory
            if event in {"FSDJump", "Location", "CarrierJump"} and system and not memory.get("first_system"):
                memory["first_system"] = str(system)
            kind = watcher_places.place_of(event, raw)
            if event in {"FSDJump", "Location", "CarrierJump"} and system and memory.get("first_system") \
                    and str(system).casefold() == str(memory["first_system"]).casefold() and memory.get("sessions", 0) > 1:
                kind = kind or "first_place"
            if kind:
                places = memory.setdefault("places", {})
                places[kind] = [int((places.get(kind) or [0])[0] or 0) + 1, now]
                wanted = memory.get("pilgrimage") or {}
                if wanted.get("kind") == kind and wanted.get("asked") and not wanted.get("reached"):
                    wanted["reached"] = now
                    watcher_deeper.shift(memory, "pilgrimage")
                    self._story_changed = True
                    self._say_next.append(("companion_wish_reached", self._wish_fields()))
            if event == "Died":
                watcher_deeper.shift(memory, "death")
            elif event == "HullDamage" and raw.get("PlayerPilot", True) and not raw.get("Fighter"):
                try:
                    low = float(raw.get("Health", 1.0)) < .25
                except (TypeError, ValueError):
                    low = False
                if low and not getattr(self, "_scared", False):
                    self._scared = True
                    watcher_deeper.shift(memory, "scare")
            elif event in {"RepairAll", "Repair"}:
                self._scared = False
                watcher_deeper.shift(memory, "repair")
            elif event in DATA_SALES:
                watcher_deeper.shift(memory, "sold")
        return None

    def _wish_fields(self):
        place = self.persona.keepsakes.WISH["place"]
        return {"place": place, "Place": place[:1].upper() + place[1:]}

    def _wish(self, now):
        """Once its story reaches the right chapter, it asks to go somewhere."""
        spec = self.persona.keepsakes.WISH
        if self.memory.get("pilgrimage"):
            return None
        story = self.persona.story
        index = next((i for i, chapter in enumerate(story.chapters) if chapter["numeral"] == spec["after"]), None)
        if index is None or index not in story.complete_chapters(self.memory):
            return None
        heard = story.told(self.memory)
        if now - max(heard[key] for key in story.chapter_ids(index)) < 3600:
            return None
        with self.lock:
            self.memory["pilgrimage"] = {"kind": spec["kind"], "asked": now, "accepted": None, "reached": None}
        self._unsaved = True
        return self.consider("companion_wish", self._wish_fields(), force=True)

    def remember(self):
        if watcher_mind.frequency(self.config) == "off" or self._session_start is None or self._in_danger:
            return None
        now = self.clock()
        story = self.persona.story
        if now - self._session_start < story.settle_s:
            return None
        shared = story.told(self.memory)
        if shared and now - max(shared.values()) < story.gap_s:
            return None
        self._account_time()
        hours = float(self.memory.get("hours") or 0)
        row = story.due(self.memory, hours, now)
        if row is None:
            return self._crew_passage(now, max(shared.values()) if shared else 0.0)
        with self.lock:
            self.memory.setdefault("lore", []).append([row[0], now])
            words = self.random.format_words(row[5], {})
            self.memory.setdefault("aster_lore_words", {})[row[0]] = words
        self._story_changed = True
        return self._utter("aster_lore", "aster:story:" + row[0], words, now)

    def learn(self, context):
        super().learn(context)
        port = (context or {}).get("port")
        if not isinstance(port, dict) or port.get("live") is not True:
            return
        surroundings = self.surroundings
        surroundings.docked = bool(port.get("docked"))
        if surroundings.docked:
            surroundings.station = str(port.get("station") or "")
            surroundings.carrier = bool(port.get("carrier"))
            surroundings.supercruise = surroundings.taxi = False
        elif not (surroundings.on_foot and surroundings.on_station):
            surroundings.station = ""
            surroundings.carrier = False
        if port.get("commander") and port["commander"] != watcher_name.record(self.memory).get("known"):
            old = watcher_name.observe(self.memory, "Commander", {"Name": port["commander"], "FID": port.get("fid")})
            if self._session_start is not None:
                watcher_name.count_session(self.memory, self._session_start)
            if old:
                self._say_next.append(("name_renamed", {"old": old, "name": watcher_name.record(self.memory)["known"]}))
                if self._question:
                    self._question = None
                    self.memory["questions"]["your_name"]["cancelled"] = self.clock()
            self._unsaved = True

    def tick(self, context=None):
        self.learn(context)
        if self._session_start is None:
            port = (context or {}).get("port")
            if isinstance(port, dict) and port.get("live") is True and not self._in_danger and aster_dockside.active(self.surroundings):
                return self.awake()
            return None
        now = self.clock()
        self._account_time()
        calm = self._calm(now)
        if calm:
            return calm
        chime = self._crew_chime_due(now)
        if chime:
            return chime
        if self._in_danger:
            return None
        named = self._name_step(now)
        if named:
            return named
        if self._question:
            return None
        name_passages = self.persona.naming.record(self.memory).get("passages", {})
        if "notice" in name_passages and "ask" not in name_passages and not watcher_name.record(self.memory).get("call"):
            return None
        if now - self._last_spoke >= 20:
            for index, (topic, fields) in enumerate(self._say_next):
                if topic in QUEUED_TOPICS:
                    self._say_next.pop(index)
                    thought = self.consider(topic, fields, force=True)
                    if thought:
                        return thought
                    break
        if now - self._last_spoke >= self.persona.story.lull_s and now - self._last_interesting >= self.persona.story.lull_s:
            thought = self.remember() or self._wish(now)
            if thought:
                return thought
        setting = watcher_mind.FREQUENCIES.get(watcher_mind.frequency(self.config))
        if (setting and now - self._last_spoke >= setting["quiet"] and now - self._last_interesting >= setting["quiet"]
                and not self._said_recently("idle", setting["mutter"])):
            known = dict(context or {})
            known.update(thoughts=self.memory.get("thoughts") or 0, sessions=self.memory.get("sessions") or 0,
                         deaths=self.memory.get("deaths") or 0, bond=self.bond(), hours=int(self.memory.get("hours") or 0))
            choices = self._idle_choices(now, known)
            fallback = "aster_after" if self.persona.story.complete(self.memory) else "quiet"
            if not choices or self.random.random() < .25:
                choices.insert(0, (fallback, {}))
            else:
                choices.append((fallback, {}))
            choices.sort(key=lambda row: row[0] not in companion_idle.FACT_TOPICS)
            # A long-watch reminder joins the idle interval rather than
            # interrupting a recent report or generating a second voice line.
            if now - self._session_start > 3 * 3600 and not self._said_recently("long_session", 3600):
                choices.insert(0, ("long_session", {"hours": int((now - self._session_start) // 3600)}))
            for topic, fields in choices:
                thought = self.consider(topic, fields)
                if thought:
                    with self.lock:
                        self.memory["aster_wording"]["idle"] = now
                        if topic in companion_idle.FACT_TOPICS:
                            self._say_next = [(key, values) for key, values in self._say_next if key != topic]
                    return thought
        return None

    def _idle_choices(self, now, known):
        choices = [(topic, fields) for topic, fields in self.surroundings.choices(now, self.random, known)
                   if topic in self.persona.lines.EVENTS]
        if aster_dockside.active(self.surroundings):
            surroundings = self.surroundings
            contextual = "idle_station_foot" if surroundings.on_foot else "idle_carrier" if surroundings.carrier else "idle_docked"
            port = [(topic, {"station": surroundings.station}) for topic in (*aster_dockside.TOPICS, contextual)]
            self.random.shuffle(port)
            port.sort(key=lambda row: self._last_said(row[0]))
            choices = port + [(topic, fields) for topic, fields in choices if topic not in aster_dockside.CONTEXT_TOPICS]
        extra = companion_idle.choices(self.memory, self.random, now, self.persona.story) + self._crew_choices()
        self.random.shuffle(extra)
        # Occasionally lead with something learned, including in port where
        # a perpetually eligible berth topic used to hide the entire archive.
        if extra and self.random.random() < .35:
            choices[:0] = extra[:1]
            extra = extra[1:]
        choices.extend(extra)
        queued = [(topic, fields) for topic, fields in self._say_next if topic in companion_idle.FACT_TOPICS
                  and not self._said_recently(topic, watcher_name.FACT_REST_S)]
        return queued + choices

    def poke(self, context=None):
        now = self.clock()
        if self._session_start is None:
            self._session_start = self._counted_until = now
        self._pokes = self._pokes + 1 if now - self._poked_at < 20 else 1
        self._poked_at = now
        if self._pokes < 3 and not self._in_danger and self.random.random() < .5:
            self.learn(context)
            for topic, fields in self._idle_choices(now, dict(context or {})):
                thought = self.consider(topic, fields, force=True)
                if thought:
                    with self.lock:
                        self.memory["aster_wording"]["idle"] = now
                        if topic in companion_idle.FACT_TOPICS:
                            self._say_next = [(key, values) for key, values in self._say_next if key != topic]
                    return thought
        return self.consider("poked_again" if self._pokes > 2 else "poked", force=True)

    def find_voice(self):
        return None

    def voice_stage(self):
        return 4

    def spoken_words(self, thought):
        words = str((thought or {}).get("text") or "")
        for shown, said in self.persona.naming.spoken(self.memory).items():
            if shown and said:
                words = re.sub(r"(?<!\w)" + re.escape(shown) + r"(?!\w)", lambda _match: said, words)
        return words

    def story_marks(self):
        return {}

    def story_progress(self):
        """For the achievements, once each time the story moves on (5.7.4)."""
        if not getattr(self, "_story_changed", False):
            return None
        self._story_changed = False
        story = self.persona.story
        said = self.memory.get("aster_wording") or {}
        name = self.identity.capitalize()
        return {"Companion": self.identity, f"{name}Told": len(story.told(self.memory)),
                f"{name}Complete": int(story.complete(self.memory)),
                f"{name}Echoes": sum(1 for key in story.echoes if said.get("echo_" + key)),
                f"{name}Request": int(bool((self.memory.get("pilgrimage") or {}).get("reached")))}

    def pending_question(self):
        if not self._question:
            return None
        now = self.clock()
        record = self.memory["questions"]["your_name"]
        if watcher_name.record(self.memory).get("call"):
            self._question = None
            record["cancelled"] = now
            self._unsaved = True
            return None
        if now - self._question["asked"] > watcher_questions.UNANSWERED_S:
            self._question = None
            record["unanswered"] = now
            watcher_deeper.shift(self.memory, "unanswered")
            self._unsaved = True
            return None
        return {"id": "your_name", "text": self._question["text"], "answers": watcher_questions.choices("your_name")}

    def _name_say(self, step, words, now, remember=True):
        thought = self._utter("aster_name_" + step, "aster:name:" + step, words, now)
        if remember:
            with self.lock:
                self.persona.naming.record(self.memory).setdefault("passages", {})[step] = {"text": words, "at": now}
        self.save()
        return thought

    def _name_step(self, now):
        self.pending_question()
        if watcher_mind.frequency(self.config) == "off":
            return None
        if (self._question or self._in_danger or self._session_start is None
                or now - self._session_start < self.persona.naming.SETTLE_S
                or now - self._last_spoke < self.persona.naming.SETTLE_S
                or now - self._last_interesting < self.persona.naming.SETTLE_S):
            return None
        row = watcher_name.record(self.memory)
        if not row.get("known"):
            return None
        for index, (topic, fields) in enumerate(self._say_next):
            if topic == "name_renamed":
                self._say_next.pop(index)
                return self._name_say("renamed", self.persona.naming.words("renamed", self.random, **fields), now, remember=False)
        passages = self.persona.naming.record(self.memory).get("passages", {})
        if "first" in passages:
            return None
        if "notice" not in passages:
            # An explicitly chosen preference already answers the question.
            if row.get("call") or float(self.memory.get("hours") or 0) < self.persona.naming.UNLOCK_HOURS:
                return None
            return self._name_say("notice", self.persona.naming.words("notice", self.random, name=row["known"]), now)
        if row.get("call"):
            if row["call"] == "commander" or watcher_name.call_name(self.memory):
                return self._name_finish(now)
            return None
        if now - passages["notice"]["at"] < self.persona.naming.GAP_S:
            return None
        return self.ask("your_name")

    def ask(self, question_id, fields=None, force=False):
        if (question_id != "your_name" or self._question or self._in_danger
                or watcher_mind.frequency(self.config) == "off"):
            return None
        row = watcher_name.record(self.memory)
        if not row.get("known") or row.get("call"):
            return None
        now = self.clock()
        previous = self.memory.setdefault("questions", {}).get("your_name", {})
        same_name = previous.get("fields", {}).get("name") == row["known"]
        if same_name and previous.get("asked") is not None and now - previous["asked"] < watcher_questions.ASK_REST_S:
            return None
        fields = {"name": row["known"]}
        text = self.persona.naming.words("ask", self.random, **fields)
        self._question = {"id": "your_name", "asked": now, "fields": fields, "text": text}
        self.memory["questions"]["your_name"] = {"asked": now, "answer": None, "answered": None,
            "fields": fields, "text": text, "times": int(previous.get("times") or 0) + 1}
        thought = self._name_say("ask", text, now)
        thought["question"] = {"id": "your_name", "answers": watcher_questions.choices("your_name")}
        thought["until"] = now + watcher_questions.ASK_SECONDS
        return thought

    def _name_finish(self, now):
        called = watcher_name.call_name(self.memory)
        kind = "first" if called else "commander"
        words = self.persona.naming.words(kind, self.random, called=called)
        return self._name_say("first", words, now)

    def answer(self, answer):
        if not self.pending_question():
            return None
        key = watcher_questions.answer_key("your_name", answer)
        if key is None:
            return None
        now = self.clock()
        self._question = None
        with self.lock:
            self.memory["questions"]["your_name"].update(answer=key, answered=now)
            watcher_deeper.shift(self.memory, "answered")
            watcher_name.set_call(self.memory, {"yes": "name", "commander": "commander", "other": "nickname"}[key])
        if key != "other" or watcher_name.call_name(self.memory):
            return self._name_finish(now)
        return self._name_say("choice", self.persona.naming.words("other", self.random), now, remember=False)

    def talk(self, text, voice=False):
        if crew_voices.addressed(" ".join(str(text or "").split()), self.identity):
            return super().talk(text, voice)  # a crewmate answers this one
        row = watcher_name.record(self.memory)
        waiting_for_nickname = (row.get("call") == "nickname" and not row.get("nickname")
                                and "ask" in self.persona.naming.record(self.memory).get("passages", {}))
        response = self.persona.naming.response(self.command_words(text)) if self.pending_question() or waiting_for_nickname else None
        if not response:
            return super().talk(text, voice)
        key, nickname = response
        with self.lock:
            if nickname:
                watcher_name.set_nickname(self.memory, nickname)
            history = self.memory.setdefault("talk", [])
            history.append({"at": self.clock(), "you": str(text)[:400], "it": "", **({"voice": True} if voice else {})})
            del history[:-50]
        if self._question:
            thought = self.answer(key)
        else:
            watcher_name.set_call(self.memory, "commander" if key == "commander" else "name" if key == "yes" else "nickname")
            thought = self._name_finish(self.clock()) if key != "other" or nickname else self._name_say(
                "choice", self.persona.naming.words("other", self.random), self.clock(), remember=False)
        with self.lock:
            history[-1]["it"] = (thought or {}).get("text", "")
        self.save()
        return bool(thought)

    def name_page(self):
        return self.persona.naming.page(self.memory)

    def share_card(self, commander=""):
        """This companion, in short, for a share code (5.7.4)."""
        story = self.persona.story
        heard = story.told(self.memory)
        chapter = next((chapter["numeral"] for index, chapter in reversed(list(enumerate(story.chapters)))
                        if any(key in heard for key in story.chapter_ids(index))), "")
        return {"name": str(commander or "")[:60], "nature": self.identity, "book": 1, "chapter": chapter, "road": None,
                "bond": self.bond(), "hours": int(self.memory.get("hours") or 0), "companion": self.identity}

    def meet(self, card):
        """Another commander's companion, of any kind, from a shared code."""
        if not isinstance(card, dict):
            return None
        key = f"{card.get('name')}|{card.get('nature')}|{card.get('hours')}"
        with self.lock:
            met = self.memory.setdefault("met", [])
            if any(row.get("key") == key for row in met if isinstance(row, dict)):
                return None
            met.append({**card, "key": key, "at": self.clock()})
            watcher_deeper.shift(self.memory, "met")
        self._unsaved = True
        other = companions.NAMES.get(card.get("companion") or "watcher", "Watcher")
        who = f"Another commander's {other.removeprefix('The ')}"
        if card.get("chapter"):
            who += f", at chapter {card['chapter']} of its story"
        return self.consider("watchers_meet", {"who": who, "Who": who}, force=True)

    def memories_page(self, now=None):
        rows = [{"at": row["at"], "text": f"{row['event']}: {row['station'] or row['system']}", "kind": "service"}
                for row in self.memory.get("aster_moments", [])]
        rows.extend({"at": row["at"], "text": row["text"], "kind": "crew"}
                    for row in self.persona.naming.record(self.memory).get("passages", {}).values())
        return sorted(rows, key=lambda row: row["at"], reverse=True)

    def _queue_session_extras(self, now):
        return None
