"""Compose a companion's authored banks into the shape the mind expects."""
import random



def merge(*banks):
    """Topic -> lines from several banks, adding up rather than replacing."""
    merged = {}
    for bank in banks:
        for topic, lines in bank.items():
            merged[topic] = tuple(merged.get(topic, ())) + tuple(lines)
    return merged


class Bank:
    """Standard mode uses plain + characterful wording; restrained mode keeps
    the plain set, so a quieter tone still has several variants per topic."""

    def __init__(self, *, greetings, restrained_greetings, capabilities, plain, voiced, commands, story=None):
        self.GREETINGS = tuple(greetings)
        self.RESTRAINED_GREETINGS = tuple(restrained_greetings)
        self.CAPABILITIES = tuple(capabilities)
        self.COMMANDS = {key: tuple(dict.fromkeys(lines)) for key, lines in commands.items()}
        restrained, events = {}, {}
        for topic in dict.fromkeys((*plain, *voiced)):
            restrained[topic] = tuple(dict.fromkeys(plain.get(topic, ()) or voiced.get(topic, ())[:2]))
            events[topic] = tuple(dict.fromkeys(plain.get(topic, ()) + voiced.get(topic, ())))
        if story is not None:
            extra = {"idle_aster_lore": story.musings, "aster_lore_recall": story.recall_lines(),
                     "aster_after": story.after, **story.echo_topics()}
            for topic, lines in extra.items():
                if lines:
                    events[topic] = tuple(dict.fromkeys(events.get(topic, ()) + tuple(lines)))
                    restrained[topic] = tuple(dict.fromkeys(restrained.get(topic, ()) + tuple(lines)))
        self.EVENTS, self.RESTRAINED_EVENTS = events, restrained

    def event_lines(self, topic, restrained=False):
        return (self.RESTRAINED_EVENTS if restrained else self.EVENTS).get(topic, ())

    def answer(self, kind, rng=None, previous=None, used=(), restrained=False):
        pool = (self.RESTRAINED_GREETINGS if restrained else self.GREETINGS) if kind == "greeting" else self.CAPABILITIES
        picker = getattr(rng, "dialogue_choice", None)
        if callable(picker):
            line = picker(kind, pool)
            formatter = getattr(rng, "format_words", None)
            return formatter(line, {}) if callable(formatter) else line
        choices = [line for line in pool if line != previous and line not in used]
        return (rng or random).choice(choices or list(pool))

    def command_reply(self, outcome, rng, fields):
        candidates = {}
        formatter = getattr(rng, "format_words", None)
        for line in self.COMMANDS.get(outcome, ()):
            try:
                candidates[line] = formatter(line, fields) if callable(formatter) else line.format(**fields)
            except (KeyError, IndexError, ValueError):
                continue
        if not candidates:
            outcome = "unavailable"
            candidates = {line: formatter(line, {}) if callable(formatter) else line for line in self.COMMANDS[outcome]}
        picker = getattr(rng, "command_choice", None)
        line = picker(outcome, tuple(candidates)) if callable(picker) else (rng or random).choice(tuple(candidates))
        return candidates[line]


def missing(bank, required):
    """Topics a persona has not written yet (used by the regression tests)."""
    return sorted(topic for topic in required if not bank.EVENTS.get(topic))
