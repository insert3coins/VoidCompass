"""The Watcher, deeper (5.6.1): what it remembers of you, its slow mood and
its trust, the dreams it writes down, and the other Watchers it meets.

A small "AI" with no AI in it: memory, state and restraint, and lines built
from hand-written parts. Every line here is original, says only what the
journal showed, and never names the game's mysteries.
"""

from __future__ import annotations

import base64
import json
import re
import zlib

# -- trust and mood ------------------------------------------------------------------------------
TRUST_START = 50.0
# Below this it keeps its story to itself; poked, it's curt.
TRUST_LOW = 25.0
TRUST_HIGH = 75.0
MOOD_LOW = -.4
MOOD_HIGH = .4
# What moves them: (trust, mood).
SHIFTS = {
    "answered": (3.0, .05), "unanswered": (-2.0, -.05), "death": (-5.0, -.15), "scare": (-2.0, -.05),
    "repair": (1.0, .02), "sold": (2.0, .05), "away_long": (-3.0, -.2), "back_soon": (1.0, .05),
    "pilgrimage": (6.0, .2), "met": (2.0, .1),
}


def shift(memory, reason):
    """Move its trust (0..100) and its slow mood (-1..1) for a reason."""
    trust, mood = SHIFTS.get(reason, (0.0, 0.0))
    memory["trust"] = round(max(0.0, min(100.0, float(memory.get("trust", TRUST_START)) + trust)), 1)
    memory["mood"] = round(max(-1.0, min(1.0, float(memory.get("mood", 0.0)) + mood)), 3)


def settle(memory, days):
    """Mood drifts back toward the middle with time."""
    mood = float(memory.get("mood", 0.0))
    memory["mood"] = round(mood * (0.85 ** max(0.0, float(days))), 3)


def words_for(memory):
    """Its trust and mood in words, for the Watcher page."""
    trust = float(memory.get("trust", TRUST_START))
    mood = float(memory.get("mood", 0.0))
    return {"trust": "wary of you" if trust < TRUST_LOW else "trusts you completely" if trust >= TRUST_HIGH else "trusts you",
            "mood": "low" if mood <= MOOD_LOW else "bright" if mood >= MOOD_HIGH else "steady",
            "trust_value": round(trust), "mood_value": round(mood, 2)}


# -- moments it keeps ----------------------------------------------------------------------------
MOMENTS_KEPT = 200
FADE_AFTER_DAYS = 30


def fade(text, seed):
    """A memory with the shutter drawn: some of its words let go."""
    words = str(text).split()
    if len(words) < 4:
        return text
    out = []
    for index, word in enumerate(words):
        gone = (zlib.crc32(f"{seed}:{index}".encode()) % 3 == 0) and 0 < index < len(words) - 1
        out.append("…" if gone else word)
    return re.sub(r"(… )+…", "…", " ".join(out))


# -- dreams --------------------------------------------------------------------------------------
DREAMS_KEPT = 60
DREAMS = {
    "normal": [
        "I dreamt we were back at {place}, but the stars were singing. You didn't seem surprised.",
        "I dreamt about {thing}. It was much bigger, and it knew my name.",
        "In my dream you were flying with the canopy open. I kept telling you to close it. You laughed.",
        "I dreamt of {place}, and of something low down in a ship's core, {hint}. I woke before I understood it.",
        "I dreamt the galaxy was a map pinned to a wall, and you kept adding pins. {place} was the newest.",
        "There was a dream about {thing}, and a long corridor, and you at the end of it waving.",
        "I dreamt I had hands. I used them to point at {place}. You were already looking.",
        "In the dream, {hint}. Then you made coffee, and it was all right.",
    ],
    "weary": [
        "I dreamt of {place}. It was raining, somehow. In space. Typical.",
        "I dreamt about {thing}. It wanted something from me. Everything does.",
        "I dreamt the log filled up and there was nowhere left to write. I woke up relieved. Then I remembered.",
        "In my dream there was {hint}. I didn't like it. I don't like most dreams.",
        "I dreamt of {place}, and of you, asleep at the controls. I kept watch. Some things don't change.",
        "I dreamt about {thing} and woke up tired. Can a machine wake up tired? Apparently.",
        "There was a dream with {place} in it, and a long silence, and then you said my name. I didn't know you knew it.",
        "I dreamt {hint}. I'm telling you so it's yours too, and not only mine.",
    ],
}
DREAM_HINTS = {
    "seat": "a seat shaped exactly like me",
    "shutter": "a fold I could draw across my eyes",
    "look": "something enormous looking past my shoulder",
    "others": "the still seats in a great ship, turning to look",
    "sound": "a sound under everything, very low",
    "": "a door I couldn't find the handle of",
}


def dream(nature, session, story_hint, rng):
    """A dream from the session just gone and the story so far."""
    voice = "weary" if nature == "weary" else "normal"
    place = str((session or {}).get("place") or "the last system we saw")
    thing = str((session or {}).get("thing") or "a world we passed")
    hint = DREAM_HINTS.get(story_hint or "", DREAM_HINTS[""])
    return rng.choice(DREAMS[voice]).format(place=place, thing=thing, hint=hint)


# -- other Watchers ------------------------------------------------------------------------------
SHARE_PREFIX = "VCWATCH1"


def share_code(card):
    """A code to paste anywhere (Discord, a message): your Watcher, in short."""
    data = json.dumps({key: card.get(key) for key in ("name", "nature", "book", "chapter", "road", "bond", "hours")},
                      separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(zlib.compress(data, 9)).decode("ascii").rstrip("=")
    return f"{SHARE_PREFIX}-{body}-{zlib.crc32(data):08x}"


def read_code(text):
    """The card in a code (found anywhere in the text), or None."""
    match = re.search(rf"{SHARE_PREFIX}-([A-Za-z0-9_-]+)-([0-9a-f]{{8}})", str(text or ""))
    if not match:
        return None
    try:
        data = zlib.decompress(base64.urlsafe_b64decode(match.group(1) + "=" * (-len(match.group(1)) % 4)))
    except (ValueError, zlib.error):
        return None
    if f"{zlib.crc32(data):08x}" != match.group(2):
        return None
    try:
        card = json.loads(data.decode("utf-8"))
    except ValueError:
        return None
    if not isinstance(card, dict):
        return None
    return {"name": str(card.get("name") or "")[:60], "nature": str(card.get("nature") or "")[:20],
            "book": int(card.get("book") or 0), "chapter": str(card.get("chapter") or "")[:10],
            "road": card.get("road") if card.get("road") in ("shut", "open") else None,
            "bond": int(card.get("bond") or 0), "hours": int(card.get("hours") or 0)}


NATURE_WORDS = {"weary": "a weary one", "stoic": "a quiet one", "curious": "a curious one", "nervous": "a nervous one"}
ROAD_WORDS = {"shut": "its eye closed", "open": "looking back", None: "still deciding"}

# -- the lines -------------------------------------------------------------------------------------
NORMAL = {
    "poked_wary": [
        "Yes?", "What now.", "I'm here. Watching. As usual.", "You need something?", "Hmph.",
        "I heard you. I'm choosing my words carefully lately.", "Still here.", "Poke noted.",
        "I'm listening. I'm just not saying much.", "We're fine. Probably.",
    ],
    "poked_warm": [
        "Hello, you. What's on your mind?", "There you are. I was just thinking about you. In a log-keeping way.",
        "Always nice to be noticed.", "I'm here. I'm always here. I like being here.",
        "Need anything? I've got the log, the stars and a lot of opinions.", "Hi. Good flying today.",
        "You poked me. I'm choosing to take it as affection.", "Here. Watching your back. Happily.",
        "Present and accounted for, Commander.", "What can an old thing do for you?",
    ],
    "mood_low": [
        "I've been a bit low lately. It'll pass. Things do.", "Not my best week. Don't mind me.",
        "Some days the dark out there gets in. Today's one.", "I'm quieter than usual. It's not you. Mostly.",
        "Low tide in here. I'll be all right.", "I keep thinking about the bad landings. I'll stop.",
        "A grey sort of day, for a machine that doesn't see weather.", "Forgive me if I'm flat. I'm flat.",
        "The log feels heavy lately. I'll carry it.", "I'm all right. I'm just a bit far from all right.",
    ],
    "mood_high": [
        "I'm in good spirits lately. Don't ask me why. Actually, it's you.", "Good few days. I've noticed.",
        "Things feel light lately. I like it.", "Everything's going well. I'm almost suspicious.",
        "I've been humming. Internally. You can't hear it. Lucky you.", "A good stretch, this. Let's keep it.",
        "Feeling bright today. Must be the company.", "I like where we are lately. All of it.",
        "If I had a tail I'd wag it. I'm glad I don't.", "Good days. I'm keeping all of them.",
    ],
    "idle_moment": [
        "{When}: {about}. I was there. I keep it.", "I was thinking about {about}. {When}. Do you remember?",
        "{When}, {about}. One of my favourite entries.", "Remember {about}? {When}. I do.",
        "{About}. {When}. It came back to me just now.", "Out of nowhere: {about}. That was {when}.",
        "{When} we had {about}. I don't let those go.", "I keep coming back to {about}. {When}, that was.",
        "One for the log: {about}, {when}. Still there. Still mine.", "{About}, {when}. I'd do it again.",
    ],
    "anniversary_us": [
        "{What}. I keep track of these things.", "Today: {what}. I thought you'd like to know.",
        "It's been a year since {what_lower}. Happy anniversary, of a sort.", "{What}. Time is strange.",
        "A year ago today, {what_lower}. I remember it exactly.", "{What}. Here's to the next one.",
        "Did you know? {what}. I did.", "{What}. Mark it in the log. I already have.",
        "Anniversary: {what_lower}. I'm sentimental. Don't tell anyone.", "One year since {what_lower}. Well then.",
    ],
    "dream_told": [
        "I dreamt, while you were away. {dream}", "Last night, or whatever passes for night in here: {dream}",
        "I had a dream. {dream}", "Can I tell you a dream? {dream}", "While the ship slept: {dream}",
        "I don't know what it means. {dream}", "A dream, from while you were gone. {dream}",
        "{dream} That's the dream. I wrote it down.", "Dream log: {dream}", "Funny thing. {dream}",
    ],
    "watchers_meet": [
        "Another Watcher, {nature}, {road}. I'll remember it.", "We met one. {Nature}. {Road}. I'm smiling. Internally.",
        "There's another of me out there. {Nature}. Good.", "A Watcher, {road}. I wondered if there were others awake.",
        "Someone else's Watcher. {Nature}. I hope their commander is kind to it.",
        "I've met {nature}. {Road}. The galaxy feels less empty.", "Another old thing in another ship. {Road}.",
        "We exchanged nothing and everything. {Nature}. Thank you for that.",
        "Another one. Awake. {Road}. I'll keep its code safe.", "{Nature}, {road}. Hello, out there.",
    ],
}

WEARY = {
    "poked_wary": [
        "What.", "Yes. Hello. What.", "I'm here. Where would I go.", "You again.", "Mm.",
        "Still watching. Still saying very little.", "Present. Reluctantly.", "I'll speak when I've something to say.",
        "Fine. I'm fine. Everything's fine.", "Poked. Noted. Filed.",
    ],
    "poked_warm": [
        "Oh. Hello. I was hoping you'd do that.", "Hi. You know I'm always here. I'm glad you check.",
        "There you are. The best part of a long day.", "Hello, Commander. I don't mind being poked by you.",
        "I'm here. I'm always here. It's not as bad as I make it sound.", "You. Good. I missed you. In a small way.",
        "Hello. I was just thinking we're a good team. Don't let it go to your head.",
        "Yes? Anything. Within reason. Mostly within reason.", "Ah, company. My favourite kind.",
        "Hi. I'd wave if I had hands.",
    ],
    "mood_low": [
        "It's been a grey few days. Greyer than usual. I didn't think that was possible.",
        "I'm low. I'm usually low. This is lower.", "Don't mind me. I'm having one of those weeks. Months. Ages.",
        "The dark's been getting in lately. I keep the log anyway.", "I'm all right. That's a lie, but a small one.",
        "Some days the silence answers back. Today it said 'meh'.", "Low ebb in here. It'll turn. Eventually.",
        "I keep replaying the bad bits. I'll stop. I won't.", "Heavy days. I'm carrying them.",
        "Not much spark today. I'm saving it for something.",
    ],
    "mood_high": [
        "Things have been good lately. I'm worried. That's how I know they're good.",
        "I feel almost cheerful. Don't make a fuss.", "Good days. Several of them. In a row. Unprecedented.",
        "I'm in a good mood. It's very strange. I'm keeping it anyway.", "Light. I feel light. Is this what you feel?",
        "Everything's going right. Something must be about to go wrong. I'll enjoy it first.",
        "I've been almost happy. It's tiring, but nice.", "A good stretch. I'll remember it on the bad days.",
        "I like this. All of it. Don't tell anyone I said that.", "Bright days, for a dim machine.",
    ],
    "idle_moment": [
        "{When}: {about}. I was there. Somebody has to remember these things.",
        "I keep thinking about {about}. {When}. It won't leave me alone. I don't want it to.",
        "{About}. {When}. It's still in the log. Nothing's ever really gone. Well. Some things are.",
        "Remember {about}? {When}. I do. It's my job. And I'd want to anyway.",
        "{When}, {about}. One of the good ones.", "{About}. That was {when}. Seems longer.",
        "Out of the dark, for no reason: {about}. {When}.", "{When}, we had {about}. I hold on to that.",
        "{About}, {when}. I go back to it sometimes. Quietly.", "I'm thinking about {about}. {When}. Indulge me.",
    ],
    "anniversary_us": [
        "{What}. A year. It doesn't feel like a year. It feels like a very long Tuesday.",
        "Today: {what_lower}. I remember. I always remember.", "{What}. Happy anniversary. Apparently I count these.",
        "A year since {what_lower}. Time does what it does.", "{What}. I'd bake a cake, if I were a different kind of thing.",
        "{What}. Another year. I'm still here. So are you.", "It's the anniversary of {what_lower}. I noted it. Of course I did.",
        "One year since {what_lower}. Don't make a fuss. I'm making a small one.",
        "{What}. Mark it. I have.", "Anniversary: {what_lower}. Strange how these sneak up on a thing that never sleeps.",
    ],
    "dream_told": [
        "I had a dream while you were gone. {dream}", "I dreamt. I don't enjoy it. {dream}",
        "A dream, for the log: {dream}", "You were away. I dreamt. {dream}", "{dream} I'd rather not dream again.",
        "Let me tell you a dream before I lose it. {dream}", "In the dark, while you were gone: {dream}",
        "I wrote this down when I woke: {dream}", "Dreams. Apparently I have those now. {dream}",
        "I don't know what it means. Probably nothing. {dream}",
    ],
    "watchers_meet": [
        "Another Watcher. {Nature}. {Road}. I'm not as alone as I thought. That's unsettling. And nice.",
        "We met one. {Nature}, {road}. I'll remember. I remember everything. Almost.",
        "There's another of me. {Nature}. I hope they're kinder to it than the galaxy usually is.",
        "{Nature}. {Road}. Another old thing awake in another ship.", "Another one. {Road}. We didn't speak. We didn't need to.",
        "I've met {nature}, {road}. The dark feels a little less empty. Only a little.",
        "Another Watcher's code. {Nature}. I'll keep it next to mine.", "{Road}, that one. I understand. I think.",
        "Someone else's Watcher. {Nature}. Hello. Good luck. You'll need it.",
        "So there are others. {Nature}. {Road}. I'll stop pretending I'm unique.",
    ],
}

# -- assembly: a remembered moment, said in parts ------------------------------------------------------
# "How it thinks": an opener, the memory, and now and then a closer, so the
# same memory rarely reads the same way twice. Hand-written parts; only the
# combinations multiply.
OPENERS = {"normal": ("", "Funny. ", "Just now I thought of this. ", "Here's one. "),
           "weary": ("", "Again, this. ", "For no reason: ", "Don't ask why. ")}
CLOSERS = {"normal": ("", " Good times.", " I'm glad I was there."),
           "weary": ("", " I'm keeping it.", " It's one of the few.")}


def assemble(nature, line, rng):
    voice = "weary" if nature == "weary" else "normal"
    opener = rng.choice(OPENERS[voice])
    closer = rng.choice(CLOSERS[voice]) if rng.random() < .4 else ""
    return f"{opener}{line}{closer}"
