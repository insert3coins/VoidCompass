"""Functional welcome/voice companions; their original stories are still pending."""
from types import SimpleNamespace

from voidcompass.core import companions
from voidcompass.overlays import aster_lines, watcher_name
from voidcompass.overlays.aster_mind import AsterMind, _fingerprint

WELCOMES = {
    "axiom": (
        "Axiom online, Commander. Your instruments and commands are ready.",
        "Welcome back. Axiom is listening. What shall we examine first?",
        "Axiom here. Ready for a clear question and a useful answer.",
        "Good to have you aboard, Commander. Axiom is standing by.",
        "Axiom, ready. We can begin with the next instruction.",
        "Welcome, Commander. The next observation is yours to choose.",
    ),
    "meridian": (
        "Meridian, on watch. Welcome aboard, Commander.",
        "Welcome back. Meridian is ready when you are.",
        "Meridian here, Commander. Let us attend to the next task.",
        "Good to hear you, Commander. Meridian is standing by.",
        "Meridian, reporting ready. Where shall we begin?",
        "Another watch, Commander. Meridian is at your service.",
    ),
}
TEST_LINES = {
    "axiom": "Axiom online. This is my voice. Ready to assist with your next observation, Commander.",
    "meridian": "Meridian, on watch. This is my voice. Ready when you are, Commander.",
}
CAPABILITIES = (
    "I can answer from the ship's recorded information, operate your configured commands and sequences, manage overlays and music, and use the market uplink. Configure hearing in Settings, under Voice.",
    "Ask for a ship report, a configured action, a map or panel, an overlay, music, or a commodity market search. My voice and display can be adjusted on this companion page and in Overlay Studio.",
)


def command_reply(outcome, rng, fields):
    """Shared factual control acknowledgements, with no character fiction."""
    template = aster_lines.COMMANDS.get(outcome, aster_lines.COMMANDS["unavailable"])[0]
    try:
        return rng.format_words(template, fields)
    except (KeyError, ValueError, IndexError):
        return "That control is unavailable at present."


class CrewMind(AsterMind):
    def __init__(self, memory_path=None, config=None, **kwargs):
        self.identity = companions.identity(config)
        super().__init__(memory_path, config, **kwargs)
        self._question = None

    @property
    def chat_bank(self):
        def answer(kind, rng, previous=None, used=()):
            pool = WELCOMES[self.identity] if kind == "greeting" else CAPABILITIES
            return rng.format_words(rng.dialogue_choice(kind, pool), {})
        return SimpleNamespace(GREETINGS=WELCOMES[self.identity], CAPABILITIES=CAPABILITIES, answer=answer)

    def command_words(self, words):
        return companions.addressed(words, self.identity) or "hello"

    def event_lines(self, topic):
        label = companions.NAMES[self.identity]
        own = {
            "greet_new": WELCOMES[self.identity], "greet_away": WELCOMES[self.identity],
            "quiet": (f"{label}, standing by.", "Ready to assist when you need a report.", "No further report at present, Commander."),
            "poked": (f"{label} is listening, Commander.", "Ready. What would you like to know?", "At your service, Commander."),
            "poked_again": ("Still here, Commander. Ready for your instruction.", "Listening. What shall we do?", "A question or an instruction, Commander?"),
            "sign_off": (f"{label}, signing off. Completed this session: {{summary}}. Until next time, Commander.",
                         "This watch's record: {summary}. Rest well, Commander.", "Session complete. Recorded this session: {summary}. Take care, Commander."),
            "sign_off_quiet": (f"{label}, standing down. Until next time, Commander.", "The watch ends here. Take care, Commander.", "Until the next watch, Commander."),
        }
        if topic in own:
            return own[topic]
        if topic in {"danger", "fuel_low", "fuel_critical", "heat", "overheating", "hull_low", "hull_critical", "died", "died_foot"}:
            return aster_lines.event_lines(topic, True)[:1]
        return ()

    def _variant(self, topic, fields):
        if topic in {"greet_new", "greet_away"}:
            # First-time and returning welcomes share one pool and one saved
            # cycle, so a second login cannot replay the first welcome.
            line = self.random.welcome_choice("crew_welcome", WELCOMES[self.identity])
            return f"{self.identity}:{topic}:{_fingerprint(line)}", self.random.format_words(line, fields)
        return super()._variant(topic, fields)

    def _plain_answer(self, words):
        from voidcompass.overlays import watcher_copilot
        lines = []
        if watcher_copilot.PLAIN_QUESTION.search(words) and callable(self.lookup_provider):
            try:
                lines = [str(line) for line in self.lookup_provider(self.command_words(words)) or () if line]
            except Exception:
                pass
        return watcher_copilot.plain_answer(lines) or CAPABILITIES[0]

    def _utter(self, topic, key, script, now):
        thought = super()._utter(topic, key, script, now)
        thought["heading"] = companions.NAMES[self.identity].upper()
        return thought

    def remember(self):
        return None

    def _name_step(self, now):
        return None

    def _idle_choices(self, now, known):
        return []

    def pending_question(self):
        return None

    def ask(self, question_id, fields=None, force=False):
        return None

    def name_page(self):
        return watcher_name.page(self.memory)

    def memories_page(self, now=None):
        return []

    def note(self, kind, fields=None):
        if kind != "sign_off":
            return None
        return super().note(kind, fields)
