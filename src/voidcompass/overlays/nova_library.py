"""Nova's Scientific Knowledge Library (5.8.6): Nyx Evera's permanent reward
for completing her story (Chapter VIII, Entry 48C). Short, fact-checked
explanations in her voice, his file as he wrote it (data/nova_library.json).

Each commander has their own copy, nova_library.json in their profile folder
beside Nova's memory. It starts as the copy shipped in data/ and is brought up
to date when a newer one ships (its entries replace those with the same id;
anything only in the commander's copy stays). Edits to it are read at once.

She answers only when asked: a question through TALK, typed or spoken, or a
question picked from the library in her book. Nothing is looked up online,
generated, or said on a journal event. Matching follows his integration
handoff: exact questions first, then a topic asked about by name; the most
specific topic wins; a topic that could be several gets "did you mean";
questions about something here and now (this body, our scan, a payout) are
not the library's to answer."""
import json
import logging
import re
from pathlib import Path

from voidcompass.core.paths import resource_path

FILE_NAME = "nova_library.json"
# Asking about a subject (after any exact question has been tried).
ASKING = re.compile(r"^(?:what (?:is|are|was|were|does|do|kind of|type of)|whats|tell me (?:more )?about|explain|describe|define|"
                    r"what do you know about|do you know (?:about|what)|teach me about|how (?:do|does|is|are)|why (?:is|are|do|does)|"
                    r"where (?:is|are))\b\s*", re.I)
# About something here and now: this body, our scans, a value. The text
# library can't see the game; those go to the app's own answers.
HERE_AND_NOW = re.compile(r"\b(?:this|these|that one|here|we|our|us|my|current|currently|payout|worth|price|cost|how much|"
                          r"how far|nearest|closest|distance|route|jumps?|scanned|sampled)\b", re.I)
LIBRARY_MODE = re.compile(r"^(?:library|look up|lookup|look it up|search (?:the )?library for|in the library|from the library|"
                          r"library entry(?: for)?)\b\s*", re.I)
ADDRESS = re.compile(r"^(?:hey |ok |okay )?(?:nova|n o v a)\b[\s,]*", re.I)
QUALIFIERS = re.compile(r"(?:\s+(?:in elite dangerous|in elite|in the game|in game|in odyssey|on the system map|genus|please))+$")
GAME_WORDS = re.compile(r"\b(?:elite dangerous|elite|in the game|in game|odyssey)\b")
SPELLINGS = (("colour", "color"), ("centre", "center"), ("grey", "gray"), ("catalogue", "catalog"), ("ionised", "ionized"),
             ("neighbour", "neighbor"), ("organise", "organize"), ("metre", "meter"))
# A word said again this soon after the same answer is the same utterance (two transcripts of one).
REPEAT_S = 4.0

_CACHE = {}


def normal(text):
    """Trimmed, case-folded, hyphens and punctuation evened out, British and
    American spellings alike, Sagittarius A* however it's said."""
    said = str(text or "").casefold().replace("’", "'").replace("‘", "'")
    said = re.sub(r"\bsag(?:ittarius)?\s*a\s*(?:\*|-\s*star\b|\s+star\b)", "sagittarius a star", said)
    said = re.sub(r"\b(what|where|who|that|it|there)'s\b", r"\1 is", said)
    said = said.replace("'", "")
    said = re.sub(r"[-_/–—]", " ", said)
    said = re.sub(r"[^\w\s]", " ", said)
    for british, american in SPELLINGS:
        said = re.sub(rf"\b{american}", british, said)
    return " ".join(said.split())


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _shelf(data):
    """The entries ready to match: exact questions and topic names, normalised."""
    data = data or {}
    entries = [row for row in data.get("entries") or () if isinstance(row, dict) and row.get("id") and _spoken(row)]
    questions, topics = {}, {}
    for row in entries:
        for question in [row.get("question")] + list(row.get("alternatives") or ()):
            if question:
                questions.setdefault(normal(question), row)
        names = list(row.get("keywords") or ())
        subject = _subject(normal(row.get("question") or ""))
        if subject:
            names.append(subject)
        for name in names:
            key = normal(name)
            if key:
                topics.setdefault(key, [])
                if row not in topics[key]:
                    topics[key].append(row)
    return {"entries": entries, "questions": questions, "topics": topics, "version": data.get("version"),
            "categories": data.get("categories") or {}, "title": data.get("library_id") or "nova_scientific_knowledge"}


def _spoken(row):
    return str(row.get("answer") or "").strip() or " ".join(str(line) for line in row.get("lines") or ()).strip()


def _merged(shipped, mine):
    """The commander's copy brought up to the shipped version: shipped entries
    replace those with the same id, the commander's own are kept."""
    out = {key: value for key, value in (mine or {}).items() if key != "entries"}
    out.update({key: value for key, value in shipped.items() if key != "entries"})
    rows = [row for row in shipped.get("entries") or () if isinstance(row, dict)]
    ids = {row.get("id") for row in rows}
    rows += [row for row in (mine or {}).get("entries") or () if isinstance(row, dict) and row.get("id") not in ids]
    out["entries"] = rows
    out.pop("context", None)  # journal-triggered remarks aren't part of the library (his handoff)
    return out


def library(folder=None):
    """The library for a commander's profile folder (their own copy, made or
    brought up to date from the shipped one), or the shipped one alone."""
    shipped_path = resource_path("data", FILE_NAME)
    if folder is None:
        key = (str(shipped_path), None)
        if key not in _CACHE:
            _CACHE[key] = _shelf(_read(shipped_path))
        return _CACHE[key]
    path = Path(folder) / FILE_NAME
    mine = _read(path) if path.exists() else None
    shipped = _read(shipped_path) or {}
    if mine is None or (shipped and str(mine.get("version")) != str(shipped.get("version"))):
        mine = _merged(shipped, mine)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(mine, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            logging.warning("Nova's library couldn't be saved to the profile: %s", exc)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        stamp = None
    key = (str(path), stamp)
    if key not in _CACHE:
        for old in [cached for cached in _CACHE if cached[0] == str(path)]:
            del _CACHE[old]
        _CACHE[key] = _shelf(mine)
    return _CACHE[key]


def words(row):
    """What she says for an entry."""
    return _spoken(row)


def _subject(said):
    """What a question asks about: "what is a neutron star in elite
    dangerous" -> "neutron star"."""
    rest = ASKING.sub("", said, count=1) if ASKING.match(said) else said
    rest = re.sub(r"^(?:a|an|the|some)\s+", "", rest)
    return QUALIFIERS.sub("", rest).strip()


def _forms(subject):
    """The subject and its singular, so "neutron stars" and "nebulae" find theirs."""
    forms = [subject]
    if subject.endswith("ae"):
        forms.append(subject[:-1])
    if subject.endswith("ies"):
        forms.append(subject[:-3] + "y")
    if subject.endswith("es"):
        forms.append(subject[:-2])
    if subject.endswith("s") and not subject.endswith("ss"):
        forms.append(subject[:-1])
    return forms


def _choose(rows, said):
    """Several entries share a name: the game's sense when the game is
    mentioned, the real one otherwise; else still several."""
    if len(rows) <= 1:
        return rows
    game = bool(GAME_WORDS.search(said))
    preferred = [row for row in rows if (row.get("scope") in ("game", "mixed")) == game]
    return preferred if len(preferred) == 1 else rows


def answer(text, shelf=None):
    """{"entry", "reason"} for the entry asked about, {"choices"} when it
    could be several, or None (not a library question)."""
    shelf = shelf or library()
    said = ADDRESS.sub("", normal(text)).strip()
    if not said:
        return None
    hit = shelf["questions"].get(said)
    if hit is not None:
        return {"entry": hit, "reason": "question"}
    browsing = bool(LIBRARY_MODE.match(said))
    if browsing:
        said = LIBRARY_MODE.sub("", said, count=1).strip()
        hit = shelf["questions"].get(said)
        if hit is not None:
            return {"entry": hit, "reason": "question"}
    elif not ASKING.match(said) or HERE_AND_NOW.search(said):
        return None
    subject = _subject(said)
    if not subject:
        return None
    for form in _forms(subject):
        rows = _choose(shelf["topics"].get(form) or [], said)
        if len(rows) == 1:
            return {"entry": rows[0], "reason": "library topic" if browsing else "topic"}
        if rows:
            return {"choices": rows}
    # A word that's part of several topics ("what is a dwarf?"): which one?
    if len(subject.split()) == 1:
        named = []
        for form in _forms(subject):
            for key, rows in shelf["topics"].items():
                if len(key.split()) > 1 and re.search(rf"\b{re.escape(form)}\b", key):
                    named += [row for row in rows if row not in named]
            if named:
                break
        if len(named) > 1:
            return {"choices": named[:4]}
    return None


def choice_words(rows):
    """Her "did you mean" for a question that could be several entries."""
    names = [str(row.get("question") or "").rstrip("?") for row in rows]
    names = [name[:1].lower() + name[1:] if name else name for name in names]
    if len(names) == 2:
        listed = f"{names[0]}, or {names[1]}"
    else:
        listed = ", ".join(names[:-1]) + f", or {names[-1]}"
    return f"That could be more than one thing, Commander. Did you mean {listed}?"


def page(shelf):
    """Her library for the book: categories and their questions (no answers;
    picking one asks her)."""
    groups = {}
    for row in shelf["entries"]:
        groups.setdefault(str(row.get("category") or "Other"), []).append(
            {"id": row["id"], "question": str(row.get("question") or row["id"])})
    return {"title": "Scientific Knowledge Library", "version": str(shelf.get("version") or ""),
            "total": len(shelf["entries"]),
            "categories": [{"name": name, "entries": rows} for name, rows in groups.items()]}


def entry(shelf, entry_id):
    return next((row for row in shelf["entries"] if row["id"] == entry_id), None)
