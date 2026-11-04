"""The Crew Register: Aster learns how this commander wishes to be known."""
import re

from voidcompass.overlays import watcher_name

TITLE = "THE CREW REGISTER"
UNLOCK_HOURS = .25
SETTLE_S = 120
GAP_S = 180
ORDER = ("notice", "ask", "first")
_ADDRESS = re.compile(r"\bCommander\b(?=\s*[,.:;!?]|$)")

LINES = {
    "notice": (
        "A manifest officer learns to put the names before the numbers. The journal gives me yours: {name}. On this posting, I should rather like to know the person behind the command chair.",
        "The crew register has your name, {name}, beside your rank. An accurate entry, but a brief one. I am learning that serving with someone means rather more than keeping their details in order.",
    ),
    "ask": (
        "The register says {name}, but a crew gets to choose how it is known. May I use your name, keep Commander, or call you something you prefer?",
        "A small matter for our crew register. Would you like me to call you {name}, retain Commander, or use a name of your own choosing?",
    ),
    "first": (
        "{called}, then. I shall use that in our reports as well. Here aboard this ship, it is good to know the person I am serving with.",
        "Very well, {called}. Your entry in my register is in order. I rather prefer a crew made of people to one made entirely of titles.",
    ),
    "commander": (
        "Commander, then. A title can be a proper choice as well. The register is yours; I shall keep it that way.",
        "Of course, Commander. The form of address is your decision. We need no further ceremony over it.",
    ),
    "other": (
        "Certainly. Tell me, call me followed by the name you prefer, or enter it under YOUR NAME on my YOU page. I shall amend the register.",
        "A name of your choosing. Say call me and the name, or write it under YOUR NAME on my YOU page. I shall take the entry from you.",
    ),
    "renamed": (
        "The journal now gives your name as {name}, where it previously said {old}. I have amended the crew register. Your preferred form of address remains your decision.",
        "A change in the register, Commander: {old} is now {name}. I shall keep the record current and leave the choice of address with you.",
    ),
}


def record(memory):
    return watcher_name.record(memory).setdefault("aster_arc", {})


def words(kind, rng, **fields):
    line = rng.dialogue_choice("crew:" + kind, LINES[kind])
    formatter = getattr(rng, "format_words", None)
    if kind == "renamed" and callable(formatter):
        return formatter(line, fields)
    return line.format(**fields)


def format_words(memory, template, fields):
    """Personalise authored addresses before inserting journal/user facts."""
    called = watcher_name.call_name(memory)
    if called:
        template = _ADDRESS.sub("{aster_address}", template)
    # Values are inserted once. Braces in a nickname are ordinary text,
    # and a system or command whose name contains Commander stays intact.
    return template.format(**{**fields, "aster_address": called or "Commander"})


def heading(topic):
    step = topic.removeprefix("aster_name_")
    return f"{TITLE} · {ORDER.index(step) + 1} OF {len(ORDER)}" if step in ORDER else TITLE


def page(memory):
    result = watcher_name.page(memory)
    passages = record(memory).get("passages", {})
    result.update(told=[step for step in ORDER if step in passages], steps=len(ORDER),
                  story={"title": TITLE, "complete": "first" in passages,
                         "told": [{"id": step, **passages[step]} for step in ORDER if step in passages]})
    return result


def response(text):
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
