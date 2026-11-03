"""Aster's officer on watch: original dialogue and a separate paced memory."""
import zlib
from types import SimpleNamespace

from voidcompass.core import companions
from voidcompass.overlays import aster_lines, aster_lore, watcher_mind, watcher_name, watcher_copilot


class OfficerRandom:
    companion_identity = "aster"

    def __init__(self, source):
        self.source = source

    def __getattr__(self, attribute):
        return getattr(self.source, attribute)


class AsterMind(watcher_mind.WatcherMind):
    identity = "aster"
    @property
    def chat_bank(self):
        if self.config.get("aster_humour", "dry") != "off":
            return aster_lines
        greetings = tuple(aster_lines.GREETINGS[index] for index in (1, 2, 5, 8, 10, 13, 14, 18, 22, 28))
        def answer(kind, rng, previous=None, used=()):
            pool = greetings if kind == "greeting" else aster_lines.CAPABILITIES
            fresh = [line for line in pool if line not in used and line != previous]
            return rng.choice(fresh or [line for line in pool if line != previous])
        return SimpleNamespace(GREETINGS=greetings, CAPABILITIES=aster_lines.CAPABILITIES, answer=answer)

    def __init__(self, memory_path=None, config=None, **kwargs):
        super().__init__(memory_path, companions.settings(config if config is not None else {}, "aster"), **kwargs)
        self.random = OfficerRandom(self.random)

    @staticmethod
    def _fresh_memory():
        memory = watcher_mind.WatcherMind._fresh_memory()
        memory.update(aster_marks={}, aster_systems=[], aster_arrivals=[], aster_moments=[])
        return memory

    def command_words(self, words):
        return companions.addressed(words, "aster") or "hello aster"

    def _variant(self, topic, fields):
        lines = aster_lines.EVENTS.get(topic, ())
        if self.config.get("aster_humour", "dry") == "off":
            lines = lines[:1]
        candidates = []
        for line in lines:
            try:
                words = line.format(**watcher_mind.noticed(fields))
            except (KeyError, IndexError, ValueError):
                continue
            key = f"aster:{topic}:{zlib.crc32(line.encode('utf-8')):08x}"
            candidates.append((key, words))
        if not candidates:
            return None
        fresh = [row for row in candidates if not self._said_recently(row[0], 3 * 86400)]
        if fresh:
            return self.random.choice(fresh)
        candidates.sort(key=lambda row: self._last_said(row[0]))
        return candidates[0]

    def consider(self, topic, fields=None, force=False):
        setting = watcher_mind.FREQUENCIES.get(watcher_mind.frequency(self.config))
        if setting is None or topic not in aster_lines.EVENTS:
            return None
        importance = watcher_mind.IMPORTANCE.get(topic, 1)
        now = self.clock()
        if not force:
            if importance < setting["minimum"] or (importance < 3 and now - self._last_spoke < setting["gap"]):
                return None
            if importance < 3 and self._said_recently(topic, setting.get("rest", 1200)):
                return None
        if self._in_danger and importance < 2:
            return None
        chosen = self._variant(topic, dict(fields or {}))
        return self._utter(topic, *chosen, now) if chosen else None

    def _utter(self, topic, key, script, now):
        preferred = watcher_name.may_name(self.memory, self._session_start) if topic in watcher_name.NAMED else None
        if preferred and "Commander" in script:
            script = script.replace("Commander", preferred, 1)
            watcher_name.mark_used(self.memory, self._session_start)
        thought = super()._utter(topic, key, script, now)
        if topic == "aster_lore":
            thought["kind"], thought["heading"] = aster_lore.heading(thought["text"])
            thought["importance"] = 3
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

    def session_start(self):
        now = self.clock()
        if self._session_start is not None and now - (getattr(self, "_last_event_at", now) or now) < 900:
            return None
        self._session_start = self._counted_until = now
        self._record_said = set()
        self.surroundings.reset_session()
        with self.lock:
            first = not self.memory.get("last_seen")
            self.memory["sessions"] = int(self.memory.get("sessions") or 0) + 1
            self.memory["session_started"] = now
            self.memory["first_seen"] = self.memory.get("first_seen") or now
            watcher_name.count_session(self.memory, now)
        return self.consider("greet_new" if first else "greet_away", force=True)

    def observe(self, event, raw=None):
        raw = raw if isinstance(raw, dict) else {}
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
        if event in {"Docked", "FSDJump", "MissionCompleted", "SellExplorationData", "MultiSellExplorationData"}:
            moments = self.memory.setdefault("aster_moments", [])
            moments.append({"event": event, "at": self.clock(), "system": str(raw.get("StarSystem") or self.memory.get("last_system") or ""),
                            "station": str(raw.get("StationName") or "")})
            del moments[:-100]
        self._unsaved = True
        return super().observe(event, raw)

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
        return self._utter("aster_lore", "aster:story:" + row[0], row[5], now)

    def tick(self, context=None):
        if self._session_start is None:
            return None
        now = self.clock()
        self.learn(context)
        self._account_time()
        calm = self._calm(now)
        if calm:
            return calm
        if self._in_danger:
            return None
        if now - self._last_spoke >= aster_lore.LULL_S and now - self._last_interesting >= aster_lore.LULL_S:
            thought = self.remember()
            if thought:
                return thought
        setting = watcher_mind.FREQUENCIES.get(watcher_mind.frequency(self.config))
        if setting and now - self._last_spoke >= setting["quiet"] and now - self._last_interesting >= setting["quiet"]:
            for topic, fields in self.surroundings.choices(now, self.random, context or {}):
                thought = self.consider(topic, fields)
                if thought:
                    return thought
            return self.consider("aster_after" if len(aster_lore.told(self.memory)) == len(aster_lore.PASSAGES) else "quiet", force=True)
        return None

    def poke(self, context=None):
        now = self.clock()
        if self._session_start is None:
            self._session_start = self._counted_until = now
        self._pokes = self._pokes + 1 if now - self._poked_at < 20 else 1
        self._poked_at = now
        return self.consider("poked_again" if self._pokes > 2 else "poked", force=True)

    def find_voice(self):
        return None

    def voice_stage(self):
        return 4

    def spoken_words(self, thought):
        words = str((thought or {}).get("text") or "")
        for shown, said in watcher_name.spoken(self.memory).items():
            if shown and said:
                words = words.replace(shown, said)
        return words

    def story_marks(self):
        return {}

    def story_progress(self):
        return None

    def pending_question(self):
        return None

    def ask(self, *args, **kwargs):
        return None

    def meet(self, card):
        return None

    def memories_page(self, now=None):
        return [{"at": row["at"], "text": f"{row['event']}: {row['station'] or row['system']}", "kind": "service"}
                for row in reversed(self.memory.get("aster_moments", []))]

    def _queue_session_extras(self, now):
        return None
