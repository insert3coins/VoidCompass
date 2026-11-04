"""Aster's officer on watch: original dialogue and a separate paced memory."""
import re
import zlib
from types import SimpleNamespace

from voidcompass.core import companions
from voidcompass.overlays import (
    aster_lines, aster_lore, aster_name, aster_dockside, aster_idle,
    watcher_mind, watcher_name, watcher_copilot, watcher_questions, watcher_habits,
)


HATCHLING_PASSIVE = {"hatchling_idle", "hatchling_said"}
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
        return aster_name.format_words(self.mind.memory, template, fields)

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
    def chat_bank(self):
        if self.config.get("aster_humour", "dry") != "off":
            return aster_lines
        def answer(kind, rng, previous=None, used=()):
            return aster_lines.answer(kind, rng, previous, used, restrained=True)
        return SimpleNamespace(GREETINGS=aster_lines.RESTRAINED_GREETINGS, CAPABILITIES=aster_lines.CAPABILITIES, answer=answer)

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
            if str(key).startswith("aster:") and str(key).split(":")[1] in aster_lines.EVENTS:
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
            if topic in aster_lines.EVENTS:
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
        return companions.addressed(words, "aster") or "hello aster"

    def event_lines(self, topic):
        return aster_lines.event_lines(topic, self.config.get("aster_humour", "dry") == "off")

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
        if setting is None or topic not in aster_lines.EVENTS:
            return None
        importance = watcher_mind.IMPORTANCE.get(topic, 1)
        at_port = aster_dockside.active(self.surroundings)
        if topic in aster_dockside.TOPICS and not at_port:
            return None
        if aster_idle.casual(topic):
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
            rest = max(rest, aster_idle.RESTS.get(topic, 0))
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
            if previous is not None and now - previous < aster_idle.RECALL_REST_S:
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
        if aster_idle.casual(topic):
            thought["importance"] = 1
        if topic in aster_lines.EVENTS:
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
        if topic == "aster_lore":
            thought["kind"], thought["heading"] = aster_lore.heading(thought["text"])
            thought["importance"] = 3
        elif topic.startswith("aster_name_"):
            thought.update(kind="memory", heading=aster_name.heading(topic), importance=3)
        elif topic == "talk":
            thought["heading"] = "OFFICER'S REPLY"
        elif topic != "relay":
            thought["kind"] = ""
            thought["heading"] = "FLIGHT ADVISORY" if thought["importance"] >= 3 else "OFFICER ON WATCH"
        return thought

    def _voice_feel(self, topic, key):
        return {"pace": 1.02 if topic == "aster_lore" else 1.0, "gain": 1.0}

    def _plain_answer(self, words):
        lines = []
        if watcher_copilot.PLAIN_QUESTION.search(words) and callable(self.lookup_provider):
            try:
                lines = [str(line) for line in self.lookup_provider(self.command_words(words)) or () if line]
            except Exception:
                pass
        return watcher_copilot.plain_answer(lines) or aster_lines.command_reply("plain", self.random, {})

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
            self.memory["sessions"] = int(self.memory.get("sessions") or 0) + 1
            self.memory["session_started"] = now
            self.memory["first_seen"] = self.memory.get("first_seen") or now
            watcher_name.count_session(self.memory, now)
        return self.consider("greet_new" if first else "greet_away", force=True)

    def observe(self, event, raw=None):
        raw = raw if isinstance(raw, dict) else {}
        previous_name = watcher_name.record(self.memory).get("known")
        marks = self.memory.setdefault("aster_marks", {})
        if event in {"MarketSell", "MissionCompleted", "CargoDepot"}:
            marks["deliveries"] = int(marks.get("deliveries", 0)) + 1
        if event == "Docked":
            marks["arrivals"] = int(marks.get("arrivals", 0)) + 1
        if event == "FSDJump":
            marks["jumps"] = int(marks.get("jumps", 0)) + 1
            system = str(raw.get("StarSystem") or "")
            known = self.memory.setdefault("aster_systems", [])
            if system and system in known:
                marks["returns"] = int(marks.get("returns", 0)) + 1
            elif system:
                known.append(system)
                del known[:-3000]
            if system:
                self.memory["last_system"] = system
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
        return None

    def _dream(self):
        return None

    def _observe_deeper(self, event, raw, now):
        # Watcher-specific dreams, trust shifts and its book choices never
        # become officer lore merely because telemetry routing is shared.
        return None

    def remember(self):
        if watcher_mind.frequency(self.config) == "off" or self._session_start is None or self._in_danger:
            return None
        now = self.clock()
        if now - self._session_start < aster_lore.SETTLE_S:
            return None
        shared = aster_lore.told(self.memory)
        if shared and now - max(shared.values()) < aster_lore.GAP_S:
            return None
        self._account_time()
        hours = float(self.memory.get("hours") or 0)
        row = aster_lore.next_passage(self.memory, hours)
        if row is None or hours < row[3] or not aster_lore.gate_ready(self.memory, row[4], hours):
            return None
        with self.lock:
            self.memory.setdefault("lore", []).append([row[0], now])
            words = self.random.format_words(row[5], {})
            self.memory.setdefault("aster_lore_words", {})[row[0]] = words
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
        if self._in_danger:
            return None
        named = self._name_step(now)
        if named:
            return named
        if self._question:
            return None
        name_passages = aster_name.record(self.memory).get("passages", {})
        if "notice" in name_passages and "ask" not in name_passages and not watcher_name.record(self.memory).get("call"):
            return None
        if now - self._last_spoke >= aster_lore.LULL_S and now - self._last_interesting >= aster_lore.LULL_S:
            thought = self.remember()
            if thought:
                return thought
        setting = watcher_mind.FREQUENCIES.get(watcher_mind.frequency(self.config))
        if (setting and now - self._last_spoke >= setting["quiet"] and now - self._last_interesting >= setting["quiet"]
                and not self._said_recently("idle", setting["mutter"])):
            known = dict(context or {})
            known.update(thoughts=self.memory.get("thoughts") or 0, sessions=self.memory.get("sessions") or 0,
                         deaths=self.memory.get("deaths") or 0, bond=self.bond(), hours=int(self.memory.get("hours") or 0))
            choices = self._idle_choices(now, known)
            fallback = "aster_after" if len(aster_lore.told(self.memory)) == len(aster_lore.PASSAGES) else "quiet"
            if not choices or self.random.random() < .25:
                choices.insert(0, (fallback, {}))
            else:
                choices.append((fallback, {}))
            choices.sort(key=lambda row: row[0] not in aster_idle.FACT_TOPICS)
            # A long-watch reminder joins the idle interval rather than
            # interrupting a recent report or generating a second voice line.
            if now - self._session_start > 3 * 3600 and not self._said_recently("long_session", 3600):
                choices.insert(0, ("long_session", {"hours": int((now - self._session_start) // 3600)}))
            for topic, fields in choices:
                thought = self.consider(topic, fields)
                if thought:
                    with self.lock:
                        self.memory["aster_wording"]["idle"] = now
                        if topic in aster_idle.FACT_TOPICS:
                            self._say_next = [(key, values) for key, values in self._say_next if key != topic]
                    return thought
        return None

    def _idle_choices(self, now, known):
        choices = [(topic, fields) for topic, fields in self.surroundings.choices(now, self.random, known)
                   if topic in aster_lines.EVENTS]
        if aster_dockside.active(self.surroundings):
            surroundings = self.surroundings
            contextual = "idle_station_foot" if surroundings.on_foot else "idle_carrier" if surroundings.carrier else "idle_docked"
            port = [(topic, {"station": surroundings.station}) for topic in (*aster_dockside.TOPICS, contextual)]
            self.random.shuffle(port)
            port.sort(key=lambda row: self._last_said(row[0]))
            choices = port + [(topic, fields) for topic, fields in choices if topic not in aster_dockside.CONTEXT_TOPICS]
        extra = aster_idle.choices(self.memory, self.random, now)
        # Occasionally lead with something learned, including in port where
        # a perpetually eligible berth topic used to hide the entire archive.
        if extra and self.random.random() < .35:
            choices[:0] = extra[:1]
            extra = extra[1:]
        choices.extend(extra)
        queued = [(topic, fields) for topic, fields in self._say_next if topic in aster_idle.FACT_TOPICS
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
                        if topic in aster_idle.FACT_TOPICS:
                            self._say_next = [(key, values) for key, values in self._say_next if key != topic]
                    return thought
        return self.consider("poked_again" if self._pokes > 2 else "poked", force=True)

    def find_voice(self):
        return None

    def voice_stage(self):
        return 4

    def spoken_words(self, thought):
        words = str((thought or {}).get("text") or "")
        for shown, said in aster_name.spoken(self.memory).items():
            if shown and said:
                words = re.sub(r"(?<!\w)" + re.escape(shown) + r"(?!\w)", lambda _match: said, words)
        return words

    def story_marks(self):
        return {}

    def story_progress(self):
        return None

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
            self._unsaved = True
            return None
        return {"id": "your_name", "text": self._question["text"], "answers": watcher_questions.choices("your_name")}

    def _name_say(self, step, words, now, remember=True):
        thought = self._utter("aster_name_" + step, "aster:name:" + step, words, now)
        if remember:
            with self.lock:
                aster_name.record(self.memory).setdefault("passages", {})[step] = {"text": words, "at": now}
        self.save()
        return thought

    def _name_step(self, now):
        self.pending_question()
        if watcher_mind.frequency(self.config) == "off":
            return None
        if (self._question or self._in_danger or self._session_start is None
                or now - self._session_start < aster_name.SETTLE_S
                or now - self._last_spoke < aster_name.SETTLE_S
                or now - self._last_interesting < aster_name.SETTLE_S):
            return None
        row = watcher_name.record(self.memory)
        if not row.get("known"):
            return None
        for index, (topic, fields) in enumerate(self._say_next):
            if topic == "name_renamed":
                self._say_next.pop(index)
                return self._name_say("renamed", aster_name.words("renamed", self.random, **fields), now, remember=False)
        passages = aster_name.record(self.memory).get("passages", {})
        if "first" in passages:
            return None
        if "notice" not in passages:
            # An explicitly chosen preference already answers the question.
            if row.get("call") or float(self.memory.get("hours") or 0) < aster_name.UNLOCK_HOURS:
                return None
            return self._name_say("notice", aster_name.words("notice", self.random, name=row["known"]), now)
        if row.get("call"):
            if row["call"] == "commander" or watcher_name.call_name(self.memory):
                return self._name_finish(now)
            return None
        if now - passages["notice"]["at"] < aster_name.GAP_S:
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
        text = aster_name.words("ask", self.random, **fields)
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
        words = aster_name.words(kind, self.random, called=called)
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
            watcher_name.set_call(self.memory, {"yes": "name", "commander": "commander", "other": "nickname"}[key])
        if key != "other" or watcher_name.call_name(self.memory):
            return self._name_finish(now)
        return self._name_say("choice", aster_name.words("other", self.random), now, remember=False)

    def talk(self, text, voice=False):
        row = watcher_name.record(self.memory)
        waiting_for_nickname = (row.get("call") == "nickname" and not row.get("nickname")
                                and "ask" in aster_name.record(self.memory).get("passages", {}))
        response = aster_name.response(self.command_words(text)) if self.pending_question() or waiting_for_nickname else None
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
                "choice", aster_name.words("other", self.random), self.clock(), remember=False)
        with self.lock:
            history[-1]["it"] = (thought or {}).get("text", "")
        self.save()
        return bool(thought)

    def name_page(self):
        return aster_name.page(self.memory)

    def meet(self, card):
        return None

    def memories_page(self, now=None):
        rows = [{"at": row["at"], "text": f"{row['event']}: {row['station'] or row['system']}", "kind": "service"}
                for row in self.memory.get("aster_moments", [])]
        rows.extend({"at": row["at"], "text": row["text"], "kind": "crew"}
                    for row in aster_name.record(self.memory).get("passages", {}).values())
        return sorted(rows, key=lambda row: row["at"], reverse=True)

    def _queue_session_extras(self, now):
        return None
