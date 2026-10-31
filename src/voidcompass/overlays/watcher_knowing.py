"""What the Watcher's own mind knows of you and of itself (5.7.1).

Everything here is real and the commander's to see (the Watcher page's
LIBRARY):

* what it has learned of how you play (watcher_habits) and your answers to
  its questions;
* notes it took from your talks: only what you said about yourself, each one
  checked against your own words, and each one yours to delete;
* what you taught it yourself (TEACH IT);
* the passages of its story it has already told you, so it can speak of
  them in its own way. Never the ones still to come, and the model is told
  never to add to them.
"""
from __future__ import annotations

import re
import zlib

from voidcompass.overlays import watcher_habits, watcher_lore, watcher_questions

NOTES_KEPT = 40
TAUGHT_KEPT = 40
TAUGHT_LIMIT = 200
STORY_KEPT = 5
# Condensing what it knows of you: at least this many lines, at most once a
# day, with its last few diary entries.
ABOUT_MINIMUM = 6
ABOUT_EVERY_S = 20 * 3600
ABOUT_DIARY = 10


def profile(memory):
    """What it has learned of how you play, as plain lines."""
    lines = []
    try:
        summary = watcher_habits.summary(memory, 0)
    except Exception:
        summary = {}
    for row in summary.get("facts") or []:
        lines.append(f"{str(row.get('label') or '').capitalize()}: {str(row.get('value') or '').lower()}")
    if summary.get("style"):
        lines.append(f"Plays mostly as: {str(summary['style']).lower()}")
    sessions = int(memory.get("sessions") or 0)
    hours = int(float(memory.get("hours") or 0))
    if sessions:
        lines.append(f"Sessions together: {sessions}, about {hours} hours")
    return lines


def answers(memory):
    """Your answers to its questions (not its story's), as plain lines."""
    lines = []
    for question_id, record in (memory.get("questions") or {}).items():
        spec = watcher_questions.QUESTIONS.get(question_id)
        if not spec or spec.get("story") or not isinstance(record, dict) or not record.get("answer"):
            continue
        label = dict(spec["answers"]).get(record.get("answer"), "")
        asked = spec["ask"]["normal"][0]
        try:
            asked = asked.format(**(record.get("fields") or {}))
        except (KeyError, IndexError):
            pass
        if label:
            lines.append(f"Asked \"{asked}\", the commander answered: {label}")
    return lines[-8:]


def story_told(memory, limit=STORY_KEPT):
    """The passages of its story it has told, the latest few, as
    (chapter, words). Nothing it hasn't told yet."""
    told = watcher_lore.told(memory)
    rows = [watcher_lore.fragment(passage_id) for passage_id, _when in sorted(told.items(), key=lambda item: item[1])]
    return [(row[1], row[2]) for row in rows if row][-limit:]


# -- notes from your talks ------------------------------------------------------
def notes(memory):
    return [row for row in memory.get("told_me") or [] if isinstance(row, dict) and row.get("text")]


# Questions and asks aren't facts about you ("The commander wants to know
# which vessel they are currently operating under.").
_QUESTION = re.compile(r"^\s*(what|where|when|who|whom|whose|why|how|which|is|are|am|was|were|can|could|do|does|did|"
                       r"will|would|should|shall|may|tell me|show me|give me|explain|describe|hi|hello|hey)\b", re.I)
_FIRST_PERSON = re.compile(r"\b(i|i'm|im|i've|i'll|i'd|me|my|mine|we|we're|our|ours)\b", re.I)
_ASKING_NOTE = re.compile(r"^the commander (wants to know|would like to know|asks|asked|is asking|is curious|"
                          r"wonders|plans to (determine|find out|know|identify|learn)|seeks to (identify|know|find|learn))",
                          re.I)


def tells_something(said):
    """Whether what you said could tell it something about you: not a plain
    question or ask ("Which ship am I in?" says nothing new about you)."""
    said = " ".join(str(said or "").split())
    if not said or _QUESTION.match(said):
        return False
    # "I'm heading to Colonia, is that far?" still tells it something.
    return not said.endswith("?") or bool(_FIRST_PERSON.search(said))


def forget_questions(memory):
    """Notes that were only your questions, taken as facts by an earlier
    build: gone, and what it condensed from them with them. How many went."""
    rows = memory.get("told_me") or []
    kept = [row for row in rows if not (isinstance(row, dict) and _ASKING_NOTE.match(str(row.get("text") or "")))]
    gone = len(rows) - len(kept)
    if gone:
        memory["told_me"] = kept
        memory.pop("about_you", None)
    return gone


def add_note(memory, text, when):
    text = " ".join(str(text or "").split())
    rows = memory.setdefault("told_me", [])
    if not text or _ASKING_NOTE.match(text) or any(str(row.get("text") or "").casefold() == text.casefold() for row in rows if isinstance(row, dict)):
        return False
    rows.append({"at": round(float(when), 1), "text": text})
    del rows[:-NOTES_KEPT]
    return True


def forget(memory, key, index):
    """Delete one of its notes ("told_me") or one of yours ("taught")."""
    rows = memory.get(key) or []
    if isinstance(index, int) and 0 <= index < len(rows):
        del rows[index]
        return True
    return False


def parse_notes(text):
    """The note lines in the model's reply: each starts "The commander", one
    per line; "NONE" (or anything else) keeps nothing."""
    found = []
    for line in str(text or "").splitlines():
        line = re.sub(r"^[\s\-*•\d.)]+", "", line).strip()
        if line.casefold().startswith("the commander") and 12 < len(line) <= 160:
            found.append(line if line.endswith((".", "!", "?")) else f"{line}.")
    return found[:2]


# -- what you teach it ------------------------------------------------------------
def taught(memory):
    return [row for row in memory.get("taught") or [] if isinstance(row, dict) and row.get("text")]


def teach(memory, text, when):
    """Something you taught it, kept as written. "" when kept, else why not."""
    text = " ".join(str(text or "").split())
    if not text:
        return "Write something for it to know."
    if len(text) > TAUGHT_LIMIT:
        return f"Keep it under {TAUGHT_LIMIT} characters."
    rows = memory.setdefault("taught", [])
    if any(str(row.get("text") or "").casefold() == text.casefold() for row in rows if isinstance(row, dict)):
        return "It knows that already."
    rows.append({"at": round(float(when), 1), "text": text})
    del rows[:-TAUGHT_KEPT]
    return ""


# -- what it knows of you, condensed ---------------------------------------------
def about_you(memory):
    """Its few sentences about you (condensed from its notes and diary), or None."""
    row = memory.get("about_you")
    return row if isinstance(row, dict) and row.get("text") else None


def about_sources(memory):
    """What it condenses: its notes of what you said, your answers, its diary."""
    lines = [row["text"] for row in notes(memory)]
    lines += answers(memory)
    lines += [str(row.get("text") or "") for row in (memory.get("diary") or [])[-ABOUT_DIARY:]
              if isinstance(row, dict) and row.get("text")]
    return lines


def about_due(memory, now):
    """(lines, source) when it's time to condense again: enough to go on,
    something new since last time, and a day or so since then. Else None."""
    lines = about_sources(memory)
    if len(lines) < ABOUT_MINIMUM:
        return None
    source = f"{zlib.crc32(chr(10).join(lines).encode('utf-8')):08x}"
    row = about_you(memory) or {}
    if row.get("from") == source or now - float(row.get("at") or 0) < ABOUT_EVERY_S:
        return None
    return lines, source


def for_prompt(memory, limit=12):
    """What it knows of you, for its own words: what you taught it, its few
    sentences about you (and any notes since), your answers and what it has
    learned, the most personal first."""
    lines = [row["text"] for row in taught(memory)][-6:]
    about = about_you(memory)
    if about:
        lines.append(about["text"])
        since = float(about.get("at") or 0)
        lines += [row["text"] for row in notes(memory) if float(row.get("at") or 0) > since][-4:]
    else:
        lines += [row["text"] for row in notes(memory)][-8:]
    lines += answers(memory)[-3:]
    lines += profile(memory)[:6]
    return lines[:limit]
