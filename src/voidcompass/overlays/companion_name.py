"""How an officer-style companion learns the commander's preferred name.

Each persona supplies its own short introduction (notice -> ask -> first)
and wording; choices and pronunciation stay in the shared name record.
"""
import re

from voidcompass.overlays import watcher_name

ORDER = ("notice", "ask", "first")
_ADDRESS = re.compile(r"\bCommander\b(?=\s*[,.:;!?]|$)")


def format_words(memory, template, fields):
    """Personalise authored addresses before inserting journal/user facts."""
    called = watcher_name.call_name(memory)
    if called:
        template = _ADDRESS.sub("{aster_address}", template)
    # Values are inserted once. Braces in a nickname are ordinary text,
    # and a system or command whose name contains Commander stays intact.
    return template.format(**{**fields, "aster_address": called or "Commander"})


def response(text, names=()):
    """An answer within the naming conversation, not a new global command."""
    text = str(text or "")[:400].strip().rstrip(".!?").strip()
    text = re.sub(r"^please\s+", "", text, flags=re.I)
    simple = {"yes": "yes", "yes please": "yes", "sure": "yes", "use my name": "yes", "1": "yes",
              "no": "commander", "no thanks": "commander", "no thank you": "commander",
              "commander": "commander", "keep commander": "commander", "keep it commander": "commander",
              "call me commander": "commander", "2": "commander", "other": "other", "something else": "other",
              "call me something else": "other", "3": "other"}
    if text.casefold() in simple:
        return simple[text.casefold()], None
    match = re.fullmatch(r"(?:call me|my name is|you can call me)\s+(.+)", text, re.I)
    return ("other", re.sub(r",?\s+please$", "", match[1], flags=re.I)) if match else None


def spoken(memory):
    result = watcher_name.spoken(memory)
    row = watcher_name.record(memory)
    if row.get("call") == "nickname" and row.get("nickname") and row.get("spoken"):
        result[row["nickname"]] = row["spoken"]
    return result


class NameArc:
    def __init__(self, *, title, arc_key, lines, prefix="crew", unlock_hours=.25, settle_s=120, gap_s=180):
        self.title, self.arc_key, self.lines, self.prefix = title, arc_key, lines, prefix
        self.unlock_hours, self.settle_s, self.gap_s = unlock_hours, settle_s, gap_s
        self.order = ORDER

    UNLOCK_HOURS = property(lambda self: self.unlock_hours)
    SETTLE_S = property(lambda self: self.settle_s)
    GAP_S = property(lambda self: self.gap_s)
    TITLE = property(lambda self: self.title)

    def record(self, memory):
        return watcher_name.record(memory).setdefault(self.arc_key, {})

    def words(self, kind, rng, **fields):
        line = rng.dialogue_choice(f"{self.prefix}:{kind}", self.lines[kind])
        formatter = getattr(rng, "format_words", None)
        if kind == "renamed" and callable(formatter):
            return formatter(line, fields)
        return line.format(**fields)

    def heading(self, topic):
        step = str(topic).removeprefix("aster_name_")
        return f"{self.title} · {ORDER.index(step) + 1} OF {len(ORDER)}" if step in ORDER else self.title

    def page(self, memory):
        result = watcher_name.page(memory)
        passages = self.record(memory).get("passages", {})
        result.update(told=[step for step in ORDER if step in passages], steps=len(ORDER),
                      story={"title": self.title, "complete": "first" in passages,
                             "told": [{"id": step, **passages[step]} for step in ORDER if step in passages]})
        return result

    format_words = staticmethod(format_words)
    response = staticmethod(response)
    spoken = staticmethod(spoken)
