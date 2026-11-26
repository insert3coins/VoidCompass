"""Axiom, Meridian, Lyra and Nova: full companions on the shared officer-style mind (5.7.4, Lyra 5.7.6, Nova 5.8.6).

Nova's story (Nyx Evera's design, overlays/nova_lore.py) is told differently:
each entry unlocks on its own requirement, some entries ask the commander
something and wait for a reply through TALK, and for her first half hour
aboard she says nothing at all. She watches, then introduces herself."""
import logging
import re

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, crew_voices, nova_library, watcher_copilot, watcher_mind, watcher_name
from voidcompass.overlays.aster_mind import AsterMind
from voidcompass.overlays.progress_story import ProgressStory, introduced_name

TEST_LINES = {identity: companion_personas.get(identity).test_line for identity in companions.NEW_IDENTITIES}
# "What's next?" about her story (not the route: "what's the next system?").
STORY_QUESTION = re.compile(r"\b(?:what'?s next|what is next|what next|what now|how'?s (?:your|the) story|how is (?:your|the) story|"
                            r"your story|what are you working on|what do you need|how can i help|what can i do for you|"
                            r"what should we do next|story progress|where are we in your story)\b", re.I)
ROUTE_WORDS = re.compile(r"\b(?:system|jump|jumps|waypoint|star|route|destination|stop)\b", re.I)
# Said while she's still observing, before she's introduced herself: replies
# to the commander, words relayed from outside, and her introduction.
QUIET_TOPICS = frozenset({"talk", "relay", "aster_lore"})

_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")


def command_reply(outcome, rng, fields):
    """Control acknowledgements in the active persona's own words."""
    persona = companion_personas.get(getattr(rng, "companion_identity", "")) or companion_personas.get("aster")
    return persona.lines.command_reply(outcome, rng, fields)


class CrewMind(AsterMind):
    def __init__(self, memory_path=None, config=None, **kwargs):
        self.identity = companions.identity(config)
        super().__init__(memory_path, config, **kwargs)
        story = self.persona.story
        self._progress = story if isinstance(story, ProgressStory) else None
        if self._progress and self._progress.activate(self.memory, self._hours(), self.clock()):
            self._unsaved = True

    def _hours(self):
        return float(self.memory.get("hours") or 0)

    def story_progress(self):
        """Nova's request is kept in her story: the entry marked ``request``
        (Gorgon, Entry 47) reached, rather than a wish of her own."""
        progress = super().story_progress()
        story = self._progress
        if progress is not None and story is not None:
            progress[f"{self.identity.capitalize()}Request"] = int(any(
                story.entries[key].get("request") and story.unlocked(self.memory, key) for key in story.order))
            if self.identity == "nova":
                progress["NovaLibrary"] = int(bool(self.memory.get("library_announced")))
                news = getattr(self, "_library_news", None)
                if news:
                    progress["NovaLibraryNews"] = news
                    self._library_news = None
        return progress

    @property
    def restrained(self):
        """Her style setting, and for Nova her story too: friendly but slightly
        reserved, in short conversations, until Chapter III (Nyx Evera's
        chapter notes). Assistant keeps her short throughout."""
        story = getattr(self, "_progress", None)
        return AsterMind.restrained.fget(self) or bool(story and story.reserved(self.memory))

    def reset(self):
        """RESET on her page: she forgets everything and comes aboard again, so
        her story starts over from a fresh activation (without one, nothing
        would count and she'd never speak)."""
        backup = super().reset()
        if backup is not None and self._progress:
            self._progress.activate(self.memory, self._hours(), self.clock())
            self._unsaved = True
            self.save()
        return backup

    # -- her first half hour ------------------------------------------------------
    def observing(self):
        """Still watching, before her first words, or waiting on "Who are you?":
        Nova says nothing else until she's been answered (5.8.6)."""
        story = self._progress
        return bool(story) and (story.order[0] not in story.told(self.memory) or story.gate(self.memory) is not None)

    def _while_asking(self, story, now):
        """"Who are you?" unanswered: asked again in a new session, its silence
        line said once, and nothing else."""
        if self._in_danger or story.busy(self.memory, now) or now - self._session_start < 20:
            return None
        lapsed = story.lapse(self.memory, now)
        if lapsed and lapsed[1]:
            self._unsaved = True
            return self._follow(lapsed[0], lapsed[1], now)
        # Let go of ("We can talk later") before this session began: asked again.
        question = story.question(self.memory, now)
        if question and question.get("lapsed") and float(question.get("lapsed_at", question["at"])) < self._session_start:
            entry_id = story.ask_again(self.memory, now)
            if entry_id:
                self._unsaved = True
                thought = self._utter("aster_lore", f"story:ask_again:{entry_id}:{round(now, 1)}",
                                      story.words(self.memory, entry_id), now)
                if thought:
                    thought.update(kind="", heading="")
                return thought
        return None

    def _utter(self, topic, key, script, now):
        if self.observing() and topic not in QUIET_TOPICS:
            return {}  # nothing said yet
        return super()._utter(topic, key, script, now)

    def consider(self, topic, fields=None, force=False):
        if self.observing():
            return None
        return super().consider(topic, fields, force)

    def ask(self, question_id, fields=None, force=False):
        if self.observing():
            return None  # no question of hers waits behind "Who are you?"
        return super().ask(question_id, fields, force)

    def observe(self, event, raw=None):
        thought = super().observe(event, raw)
        story = self._progress
        if story and story.observe(self.memory, event, raw, self._hours(), self.clock()):
            self._unsaved = True
            self._story_changed = True
        if self.observing():
            return None
        self._library_unlock()
        context = self._dialogue_context(event, raw or {})
        if context:
            self._dialogue_context_next = (context, self.clock())
        return thought

    # -- her Scientific Knowledge Library (Nyx Evera's reward for Entry 48C) ----
    def _library_unlock(self):
        """Opened for good the moment Entry 48C is completed (unlocked, told or
        not): once, kept through restarts and replays, and found on load for a
        save where it already happened."""
        if self.identity != "nova" or self.memory.get("library_unlocked"):
            return bool(self.memory.get("library_unlocked"))
        story = getattr(self, "_progress", None)
        if story is not None and story.unlocked(self.memory, story.order[-1]):
            with self.lock:
                self.memory["library_unlocked"] = float(story.state(self.memory)["unlocked"][story.order[-1]])
            self._unsaved = True
            return True
        return False

    def _library_open(self):
        return self._library_unlock()

    # Her word that the library is open (ours until Nyx Evera sends one of his).
    LIBRARY_NEWS = ("Commander, I've finished organising the research we recovered. "
                    "If you're ever curious about something out there, a star, a world, something living, just ask me. "
                    "I'd be glad to tell you what I know.")

    def _library_announce(self, now):
        """Once, after her last story words (Entry 48C told) and a quiet
        moment: she says the library is open, and the deck shows it (a toast,
        an achievement). The library itself opened at 48C's completion."""
        story = self._progress
        if not self._library_unlock() or self.memory.get("library_announced"):
            return None
        told = story.told(self.memory).get(story.order[-1])
        if (told is None or now - told < 90 or now - self._last_spoke < 8 or self.current() or self._in_danger
                or story.busy(self.memory, now)):
            return None
        thought = self._utter("nova_library_open", f"library:open:{round(now, 1)}", self.LIBRARY_NEWS, now)
        if thought:
            thought.update(kind="", heading=f"{companions.name(self.config).upper()} · SCIENTIFIC KNOWLEDGE LIBRARY",
                           importance=3, mood="pleased")
            with self.lock:
                self.memory["library_announced"] = now
            self._library_news = len(self._library()["entries"])
            self._story_changed = True
            self._unsaved = True
        return thought

    def _library(self):
        """This commander's copy, in their profile folder beside her memory."""
        return nova_library.library(self.memory_path.parent if self.memory_path else None)

    def library_page(self):
        """Her library for the book, once it's open (nothing of it before)."""
        return nova_library.page(self._library()) if self._library_open() else None

    def library_play(self, entry_id):
        """A question picked from the library in her book: her answer to it."""
        if not self._library_open():
            return None
        row = nova_library.entry(self._library(), str(entry_id or ""))
        return self._library_say(row, "picked") if row else None

    def _library_say(self, row, reason):
        logging.debug("Nova's library: %s (%s)", row["id"], reason)  # never the commander's words
        thought = self._reply(nova_library.words(row))
        if thought:
            thought.update(kind="", heading=f"{companions.name(self.config).upper()} · {str(row.get('category') or 'LIBRARY').upper()}",
                           mood="curious")
            self._unsaved = True
        return thought

    def _library_answer(self, words, voice, now):
        """Her library's answer to what was asked through TALK: True when it
        answered (or asked which was meant), else False for the usual reply."""
        if not words or not self._library_open() or crew_voices.addressed(words, self.identity):
            return False
        found = nova_library.answer(words, self._library())
        if found is None:
            return False
        key = nova_library.normal(words)
        last = getattr(self, "_library_last", None)
        if last and last[0] == key and now - last[1] < nova_library.REPEAT_S:
            return True  # the same utterance twice (two transcripts of one): one answer
        self._library_last = (key, now)
        with self.lock:
            history = self.memory.setdefault("talk", [])
            history.append({"at": round(now, 1), "you": words, "it": "", **({"voice": True} if voice else {})})
            del history[:-50]
        if "choices" in found:
            self._reply(nova_library.choice_words(found["choices"]))
        else:
            self._library_say(found["entry"], found["reason"])
        return True

    # -- her Progressive Dialogue Library (Nyx Evera, Draft v0.1) ---------------
    DIALOGUE_GAP_S = {"rare": 75 * 60, "occasional": 40 * 60, "chatty": 25 * 60}
    DIALOGUE_REST_S = 8 * 3600

    def _dialogue_open(self):
        """The lines her completed chapters have opened (and not yet retired)."""
        story = getattr(self, "_progress", None)
        if self.identity != "nova" or story is None:
            return []
        from voidcompass.overlays import nova_lore
        labels = {story.entry_label(key): key for key in story.order}
        told = story.told(self.memory)
        rows = []
        for row in nova_lore.DIALOGUE:
            opens = labels.get(nova_lore.DIALOGUE_OPENS.get(row["chapter"], ""))
            if opens is None or not story.unlocked(self.memory, opens):
                continue
            until = labels.get(row.get("until") or "")
            if until is not None and until in told:
                continue
            rows.append(row)
        return rows

    def _dialogue_pick(self, now, context=None):
        """A line to say: one for this moment, or an everyday one; never one said
        in the last eight hours, newer chapters a little more likely."""
        said = self.memory.get("nova_dialogue") or {}
        rows = [row for row in self._dialogue_open()
                if row.get("context") == context and now - float(said.get(row["id"]) or 0) >= self.DIALOGUE_REST_S]
        if not rows:
            return None
        newest = max(_NUMERALS.index(row["chapter"]) for row in rows)
        weights = [2.0 if _NUMERALS.index(row["chapter"]) == newest else 1.0 for row in rows]
        return self.random.choices(rows, weights=weights, k=1)[0]

    def _dialogue_say(self, row, now):
        thought = self._utter("nova_dialogue", f"dialogue:{row['id']}:{round(now, 1)}", " ".join(row["lines"]), now)
        if thought:
            with self.lock:
                self.memory.setdefault("nova_dialogue", {})[row["id"]] = now
                self.memory["nova_dialogue_last"] = now
            thought.update(importance=2)
            self._unsaved = True
        return thought

    def _dialogue_due(self, now):
        gap = self.DIALOGUE_GAP_S.get(watcher_mind.frequency(self.config))
        return gap is not None and now - float(self.memory.get("nova_dialogue_last") or 0) >= gap

    @staticmethod
    def _dialogue_context(event, raw):
        """The moment a context line is for: a system nobody had discovered (its
        main star scanned first by us), a species completed, a first sample."""
        from voidcompass.core.discovery import our_first
        if event == "Scan" and raw.get("StarType") and not raw.get("DistanceFromArrivalLS") and our_first(raw):
            return "first_discovery"
        if event == "ScanOrganic":
            kind = str(raw.get("ScanType") or "").casefold()
            if kind == "analyse":
                return "biological_discovery"
            if kind == "log":
                return "surface_biology"
        return None

    def tick(self, context=None):
        story = self._progress
        if story is None:
            return super().tick(context)
        if self.observing():
            # Only the clock and the count move: nothing else is said, or used up.
            self.learn(context)
            if self._session_start is None:
                port = (context or {}).get("port")
                if isinstance(port, dict) and port.get("live") is True:
                    self.awake()
                return None
            self._account_time()
            now = self.clock()
            if story.tick(self.memory, self._hours(), now):
                self._unsaved = True
            if story.gate(self.memory) is not None:
                return self._while_asking(story, now)
            row = story.due(self.memory)
            if row and not self._in_danger and not story.busy(self.memory, now) and now - self._session_start >= 20:
                return self._tell(row, now)
            return None
        now = self.clock()
        if self._session_start is not None:
            self._account_time()
            if story.tick(self.memory, self._hours(), now):
                self._unsaved = True
            lapsed = story.lapse(self.memory, now)
            if lapsed:
                self._unsaved = True
                if lapsed[1] and not self._in_danger:
                    return self._follow(lapsed[0], lapsed[1], now)
            self._library_unlock()
            announced = self._library_announce(now)
            if announced:
                return announced
            waiting = getattr(self, "_dialogue_context_next", None)
            if waiting is not None:
                # A moment's line, said once things are quiet (within a few minutes of it).
                if now - waiting[1] > 300:
                    self._dialogue_context_next = None
                elif (now - self._last_spoke >= 8 and not self.current() and not self._in_danger
                      and not story.busy(self.memory, now)):
                    self._dialogue_context_next = None
                    row = self._dialogue_pick(now, waiting[0]) if self._dialogue_due(now) else None
                    if row is not None:
                        thought = self._dialogue_say(row, now)
                        if thought:
                            return thought
        return super().tick(context)

    # -- telling ---------------------------------------------------------------
    def remember(self):
        story = self._progress
        if story is None:
            return super().remember()
        if watcher_mind.frequency(self.config) == "off" or self._session_start is None or self._in_danger:
            return None
        now = self.clock()
        if now - self._session_start < story.settle_s or story.busy(self.memory, now) or story.question(self.memory, now):
            return None
        shared = story.told(self.memory)
        last = max(shared.values()) if shared else 0.0
        if shared and now - last < story.gap_s:
            return None
        self._account_time()
        row = story.due(self.memory)
        if row is None:
            # Nothing of her story due: now and then one of her everyday lines.
            if self._dialogue_due(now):
                line = self._dialogue_pick(now)
                if line is not None:
                    thought = self._dialogue_say(line, now)
                    if thought:
                        return thought
            return self._crew_passage(now, last)
        return self._tell(row, now)

    def _tell(self, row, now):
        story = self._progress
        with self.lock:
            self.memory.setdefault("lore", []).append([row[0], now])
            self.memory.setdefault("aster_lore_words", {})[row[0]] = row[5]
        story.ask(self.memory, row[0], now)
        self._story_changed = True
        self._unsaved = True
        thought = self._utter("aster_lore", "aster:story:" + row[0], row[5], now)
        if thought and story.entries[row[0]].get("plain"):
            # Her first words come without an announcement.
            thought.update(kind="", heading="")
        return thought

    def _follow(self, entry_id, words, now):
        """Her answer to a reply (or to silence), under the entry's heading."""
        thought = self._utter("talk", f"story:after:{entry_id}:{round(now, 1)}", words, now)
        if thought:
            thought.update(kind="memory", heading=self._progress.passage_heading(entry_id), importance=3)
        return thought

    # -- a reply ------------------------------------------------------------------
    def _introduction(self, words):
        """Answering "Who are you?": how she greets you, and what she calls you
        from now on. The name you gave, else the journal's, else Commander."""
        known = watcher_name.record(self.memory).get("known") or ""
        name = introduced_name(words, known)
        if name and known and name.casefold() == known.casefold():
            watcher_name.set_call(self.memory, "name")
        elif name:
            watcher_name.set_call(self.memory, "nickname", nickname=name)
        else:
            # No name in the answer: she's met you all the same, and the journal says who you are.
            watcher_name.set_call(self.memory, "name" if known else "commander")
        said = name or known
        return {"commander": f"Commander {said}" if said else "Commander"}

    def _name_step(self, now):
        """The User Profile question waits for hers: "Who are you?" comes first
        (Nyx Evera's First Contact), and while it's open nothing asks over it."""
        story = self._progress
        if story is not None:
            first = next((entry_id for entry_id in story.order if story.entries[entry_id].get("learn_name")), None)
            if first and (first not in story.told(self.memory) or story.question(self.memory, now)):
                return None
        return super()._name_step(now)

    def _profile_from_introduction(self, entry_id, reply, now):
        """Her first question answered: the user profile is filled in. Its
        arc keeps the introduction and never asks again."""
        story = self._progress
        with self.lock:
            passages = self.persona.naming.record(self.memory).setdefault("passages", {})
            passages.setdefault("notice", {"text": " ".join(story.entries[entry_id]["lines"]), "at": now})
            passages["first"] = {"text": reply, "at": now}

    def _story_status_words(self, words):
        """Her answer to "what's next?" (her story's next task, and how far
        along it is), or None when that isn't what was asked."""
        story = self._progress
        if not story or not STORY_QUESTION.search(words) or ROUTE_WORDS.search(words):
            return None
        from voidcompass.overlays import nova_lore
        if self.observing():
            # Not introduced yet: nothing. Waiting on "Who are you?": that, again
            # (not "what's next" taken for your name).
            gate = story.gate(self.memory)
            return story.words(self.memory, gate) if gate else None
        self._account_time()
        return nova_lore.next_words(story.status(self.memory, self._hours(), self.clock())) or None

    def talk(self, text, voice=False):
        story = self._progress
        now = self.clock()
        words = " ".join(str(text or "").split())[:400]
        status = self._story_status_words(self.command_words(words)) if words and not crew_voices.addressed(words, self.identity) else None
        # Her library, once her story's complete: "what is a neutron star?"
        if not status and self._library_answer(words, voice, now):
            return True
        if status:
            with self.lock:
                history = self.memory.setdefault("talk", [])
                history.append({"at": round(now, 1), "you": words, "it": "", **({"voice": True} if voice else {})})
                del history[:-50]
            self._unsaved = True
            self._reply(status)
            return True
        if not (story and words and story.question(self.memory, now)) or crew_voices.addressed(words, self.identity) \
                or self.pending_question():
            return super().talk(text, voice)
        # A command still does its job (tried once, here); a lookup still gets
        # its answer. Anything else answers her question.
        done = None
        if callable(self.action_provider):
            try:
                done = self.action_provider(words)
            except Exception:
                done = None
        if done is not None:
            with self.lock:
                history = self.memory.setdefault("talk", [])
                history.append({"at": round(now, 1), "you": words, "it": "", **({"voice": True} if voice else {})})
                del history[:-50]
                count = len(history)
            self._unsaved = True
            if isinstance(done, dict) and done.get("waiting"):
                self._uplink = {"said": words, "at": now, "who": None}
                thought = self._utter("talk", f"talk:uplink:{count}", str(done.get("say") or ""), now)
                thought["importance"] = 3
            else:
                self._reply(str(done))
            return True
        if watcher_copilot.PLAIN_QUESTION.search(words) and callable(self.lookup_provider):
            try:
                if any(self.lookup_provider(words) or ()):
                    return super().talk(text, voice)
            except Exception:
                pass
        fields = self._introduction(words) if story.asks_name(self.memory, now) else None
        answered = story.reply(self.memory, words, now, fields)
        if not answered:
            return super().talk(text, voice)
        entry_id, said = answered
        with self.lock:
            history = self.memory.setdefault("talk", [])
            history.append({"at": round(now, 1), "you": words, "it": said, **({"voice": True} if voice else {})})
            del history[:-50]
        if fields is not None:
            self._profile_from_introduction(entry_id, said, now)
        if said:
            self._follow(entry_id, said, now)
        self._unsaved = True
        self.save()
        return True
