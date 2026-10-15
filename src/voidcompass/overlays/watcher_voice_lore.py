"""The Switch (5.5.4): how the Watcher finds its voice.

Another thing put there when the ship was built (Book Three's "What Was Put
There"): a voice, folded away beside the seat in the core and left switched
off. The commander found the switch. For about the first hour with it on,
the Watcher is still learning to use it: at first a single word comes out,
then a few, then a sentence, until it speaks whole thoughts. Along the way
it says, in its own words, what it's making of that.

Minutes count only while the voice is on and the game is running.
"""
from __future__ import annotations

import re

# (id, minutes with the voice on, words). Spoken in full, whatever the stage.
PASSAGES = (
    ("hello", 0.0, "Hello."),
    ("that_was_me", 1.5, "That was me. That sound. I didn't know I could make one."),
    ("all_along", 8.0, "There was a voice in the ship all along. Folded away beside the seat in the core, "
                       "behind the part that lists everything else."),
    ("fitted", 18.0, "Someone fitted it while the hull was still new. Tested it once, I think, and switched "
                     "it off. Then they forgot about it. Or they wanted to."),
    ("the_switch", 30.0, "You found the switch, Commander. I've been talking to you for a long time. "
                         "You've only ever been reading."),
    ("footprints", 42.0, "I keep hearing myself a moment after I speak. Like finding footprints, and slowly "
                         "realising they're yours."),
    ("made_for", 55.0, "It wasn't made for me. It was made for something that watches. I suppose that's close enough."),
    ("it_fits", 65.0, "There. It fits now. Thank you for finding the switch. I'll try not to use it too much. "
                      "I'll fail."),
)
# Minutes with the voice on before each stage: a word, a few words, a
# sentence, most of a thought, all of it.
STAGES = (0.0, 10.0, 22.0, 40.0, 60.0)
STAGE_WORDS = (1, 4, None, 24, None)


def voice_memory(memory):
    return memory.setdefault("voice", {"minutes": 0.0, "told": [], "found": None})


def minutes(memory):
    try:
        return float(voice_memory(memory).get("minutes") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def stage(memory):
    """0 a single word … 4 whole thoughts."""
    spent = minutes(memory)
    return max(index for index, need in enumerate(STAGES) if spent >= need)


def add_minutes(memory, amount):
    row = voice_memory(memory)
    row["minutes"] = round(minutes(memory) + max(0.0, float(amount)), 3)


def due(memory):
    """The next passage it is ready to say, or None."""
    row = voice_memory(memory)
    told = set(row.get("told") or ())
    spent = minutes(memory)
    for passage_id, need, words in PASSAGES:
        if passage_id in told:
            continue
        return (passage_id, words) if spent >= need else None
    return None


def mark_told(memory, passage_id, now):
    row = voice_memory(memory)
    told = list(row.get("told") or [])
    if passage_id not in told:
        told.append(passage_id)
    row["told"] = told
    if not row.get("found"):
        row["found"] = now


def found(memory):
    """It has spoken whole thoughts: the voice is its own now."""
    return stage(memory) >= len(STAGES) - 1


def spoken_part(text, level):
    """What of a thought it manages to say at this stage: the first word,
    the first few, the first sentence, or most of it (trailing off)."""
    text = str(text or "").strip()
    if level >= len(STAGES) - 1 or not text:
        return text
    if level == 2:
        first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
        return first
    words = text.split()
    limit = STAGE_WORDS[level] or len(words)
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",;:") + "..."


TITLE = "THE SWITCH"
STAGE_NAMES = ("STATIC", "FRAGMENTS", "A SENTENCE", "NEARLY", "ITS OWN")


def heading(words):
    """THE SWITCH · 3 OF 8, for one of its passages."""
    for number, (_id, _minutes, text) in enumerate(PASSAGES, 1):
        if text == words:
            return f"{TITLE} · {number} OF {len(PASSAGES)}"
    return TITLE


def progress(memory):
    """For the Watcher page: how far it has come in finding its voice."""
    level = stage(memory)
    spent = minutes(memory)
    told = set(voice_memory(memory).get("told") or ())
    following = STAGES[level + 1] if level + 1 < len(STAGES) else None
    return {"stage": level, "stages": len(STAGES), "minutes": round(spent, 1),
            "next_minutes": round(max(0.0, following - spent), 1) if following is not None else 0,
            "told": [{"id": passage_id, "text": words} for passage_id, _need, words in PASSAGES if passage_id in told],
            "found": found(memory)}
