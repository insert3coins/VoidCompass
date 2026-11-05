"""The rest of the crew, off watch (5.7.4).

Two ways a companion who isn't on watch still speaks: you ask it something by
name in TALK ("Meridian, how far to Colonia?"), or, at a big moment, it can't
help adding a line after the one on watch. Rare on purpose: once a session.
"""
import re
import zlib

from voidcompass.core import companions

# Off-watch remarks: at most one a session, at least an hour apart, and only
# for a crewmate you've flown with. Not every big moment brings one.
CHIME_CHANCE = .5
CHIME_DELAY_S = 8.0
CHIME_EXPIRES_S = 120.0
CHIME_GAP_S = 3600.0
CLOSE_CALL_AFTER_S = 45.0

# Which of the active companion's thoughts count as a big moment.
MOMENTS = {"world_earthlike": "earthlike", "footfall_first": "footfall", "record_jump": "record_jump",
           "record_far": "record_far"}
DEATHS = {"died", "died_foot", "after_death"}

_NAMES = r"the watcher|watcher|aster|axiom|meridian"
_ASKING = (r"what|what's|whats|how|how's|where|where's|when|which|who|why|is|are|do|does|did|can|could|would|will|"
           r"should|tell|give|show|open|close|have|has|any|say|please|play|stop|hide|find|check|read|request")
_DIRECT = re.compile(rf"^\s*(?:(?:hey|hi|hello|ok|okay)\s+)?(?P<name>{_NAMES})\s*[,;:]\s*(?P<rest>.+)$", re.I)
_ASK = re.compile(rf"^\s*ask\s+(?P<name>{_NAMES})\s+(?:(?:to|about)\s+)?(?P<rest>.+)$", re.I)
_PLAIN = re.compile(rf"^\s*(?:(?:hey|hi|hello|ok|okay)\s+)?(?P<name>{_NAMES})\s+(?P<rest>(?:{_ASKING})\b.+)$", re.I)
_HELLO = re.compile(rf"^\s*(?:hey|hi|hello)\s+(?P<name>{_NAMES})\s*[!?.]*\s*$", re.I)


def _identity(name):
    name = name.casefold()
    return "watcher" if name in {"watcher", "the watcher"} else name


def addressed(text, active):
    """(crewmate, what was asked) when the words open with another
    companion's name, else None. The one on watch answers its own name."""
    words = str(text or "")
    hello = _HELLO.match(words)
    if hello:
        found, rest = _identity(hello["name"]), "hello"
    else:
        match = _DIRECT.match(words) or _ASK.match(words) or _PLAIN.match(words)
        if not match:
            return None
        found, rest = _identity(match["name"]), match["rest"].strip()
    if found == active or found not in companions.IDENTITIES or not rest:
        return None
    return found, rest


def heading(identity):
    return f"{companions.NAMES[identity].removeprefix('The ').upper()} · OFF WATCH"


class CrewRandom:
    """The active mind's dice with a crewmate's identity, for wording a reply
    in the crewmate's own lines. It keeps none of the active one's rotations."""

    def __init__(self, rng, identity):
        self._source = getattr(rng, "source", rng)
        self.companion_identity = "" if identity == "watcher" else identity

    def choice(self, values):
        return self._source.choice(values)

    def random(self):
        return self._source.random()

    def shuffle(self, values):
        return self._source.shuffle(values)

    def sample(self, values, count):
        return self._source.sample(values, count)

    def randint(self, low, high):
        return self._source.randint(low, high)

    def uniform(self, low, high):
        return self._source.uniform(low, high)


def chat_bank(identity, config):
    """A crewmate's greetings and rundowns, in its chosen commentary style."""
    if identity == "watcher":
        from voidcompass.overlays import watcher_chat
        return watcher_chat
    from types import SimpleNamespace
    from voidcompass.overlays import companion_personas
    lines = companion_personas.get(identity).lines
    if not companion_personas.restrained(identity, config):
        return lines

    def answer(kind, rng, previous=None, used=()):
        return lines.answer(kind, rng, previous, used, restrained=True)
    return SimpleNamespace(GREETINGS=lines.RESTRAINED_GREETINGS, CAPABILITIES=lines.CAPABILITIES, answer=answer)


def pick(memory, speaker, moment, rng):
    """A full rotation per crewmate and moment: every line once before any
    comes back, never the last one twice."""
    lines = CHIMES[speaker][moment]
    keys = {line: f"{zlib.crc32(line.encode('utf-8')):08x}" for line in lines}
    record = memory.setdefault("crew_chimes", {}).setdefault(f"{speaker}:{moment}", {"used": [], "last": None})
    used = [key for key in record.get("used") or () if key in keys.values()]
    fresh = [line for line in lines if keys[line] not in used] or list(lines)
    if len(fresh) == len(lines):
        used = []
    fresh = [line for line in fresh if keys[line] != record.get("last")] or fresh
    line = rng.choice(fresh)
    record["used"] = used + [keys[line]]
    record["last"] = keys[line]
    return line


CHIMES = {
    "watcher": {
        "earthlike": ("Sorry. I had to look. Blue and green. I've seen a few. Never enough.",
                      "I'm off watch, but an earth-like. I came up for it.",
                      "One more of those. It doesn't get old. I do.",
                      "Blue. Weather. Somebody's future. Worth waking for.",
                      "I wasn't going to say anything. Then I saw it."),
        "footfall": ("Footprints nobody made before. I watched. I always watch.",
                     "First boots on that ground. I'll remember it, even if the ground forgets.",
                     "Off watch, still watching. You stood somewhere new.",
                     "Nobody has ever stood there. Now someone has. Good.",
                     "I saw the first step. That one's mine to keep."),
        "record_jump": ("Further in one jump than ever. I felt that one, somehow.",
                        "Your longest jump. I counted. I always count.",
                        "That was far. Even for me.",
                        "A new longest jump. I'll add it to the things I've watched you do.",
                        "That jump. I noticed. Off watch, but I noticed."),
        "record_far": ("Further from Sol than you've ever been. I've been further. It's lonely. Keep going anyway.",
                       "A new furthest point. I marked it in the dark.",
                       "Never this far before. I'm still here. Just so you know.",
                       "The furthest yet. The quiet gets louder out here.",
                       "That's your record. Don't let it be the last."),
        "close_call": ("That was too close. I was watching. I'm always watching.",
                       "You nearly didn't come back from that. Please don't do that again.",
                       "Off watch, and I still felt that one.",
                       "Still here? Good. So am I.",
                       "I don't like counting losses. Thank you for not being one."),
    },
    "aster": {
        "earthlike": ("Forgive the interruption, Commander. An Earth-like warrants a second officer's notice.",
                      "Off watch, but I have entered it myself. Some findings deserve two signatures.",
                      "An Earth-like. I have come up from standby to see it properly.",
                      "Noted from the wardroom: a world worth a captain's entry.",
                      "I would not usually speak off watch. This is an exception, and a good one."),
        "footfall": ("First footfall. I have added my own line to the record, if you will allow it.",
                     "From standby: congratulations, Commander. Nobody has stood there before you.",
                     "A first step. The book will want to know about this.",
                     "Off watch, but I could not let a first footfall go unremarked.",
                     "Duly witnessed: a first landing on foot, by this ship's captain."),
        "record_jump": ("From standby: a new longest jump. The log will need a wider column.",
                        "A ship's record, Commander. I have signed it as witness.",
                        "Off watch, but a record is a record. Well flown.",
                        "That jump exceeds every prior entry. I checked twice.",
                        "Congratulations on the distance. I shall have it framed, figuratively."),
        "record_far": ("From standby: further from Sol than this ship has ever been. Noted with some pride.",
                       "A new furthest position. The log has never been so far from home.",
                       "Off watch, but I wished to mark the occasion. A record distance.",
                       "This is the furthest entry in the book. Shall we make it a habit?",
                       "A record, Commander. I have underlined it. I rarely underline."),
        "close_call": ("From standby: that was closer than I like. Well recovered.",
                       "I will not pretend I was resting through that. Glad you are still with us.",
                       "Hull integrity was alarming. Your flying was not. Well done.",
                       "Off watch, but I was watching. Please consider the margin.",
                       "Noted for the log: a narrow escape, handled."),
    },
    "axiom": {
        "earthlike": ("An Earth-like! Sorry. Off watch. I could not help it.",
                      "Earth-like world. I have opened a new column just for it.",
                      "I was off watch. I am not now. Not for this.",
                      "Probability that is an Earth-like: certain. My excitement: considerable.",
                      "Please map it. Off-watch request, filed politely."),
        "footfall": ("First footfall recorded. I observed it from standby. Wonderful.",
                     "No previous footprints. Now there is one set. A perfect dataset.",
                     "I had to say something. A first step is a first data point.",
                     "From standby: new ground, first observer. That is you.",
                     "First footfall. I have marked the time to the second."),
        "record_jump": ("New record jump. I recalculated it. It is still a record.",
                        "That jump is an outlier, in the best sense.",
                        "From standby: longest jump in the record. Confidence high.",
                        "A new maximum. I love a new maximum.",
                        "Record distance in one jump. I am adjusting my expectations upward."),
        "record_far": ("Furthest from Sol yet. The sky out here is barely catalogued.",
                       "A new furthest point. The unknown fraction of the sky just grew.",
                       "From standby: record distance from Sol. The stars here are mostly uncounted.",
                       "Further than ever. I have prepared extra columns.",
                       "Record distance. I would like it noted that I am thrilled."),
        "close_call": ("That was close. I ran the numbers while it happened. I did not like them.",
                       "From standby: hull readings were concerning. Current readings, acceptable.",
                       "Please avoid repeating that experiment.",
                       "We survived. The data supports continuing to survive.",
                       "Off watch, but alarmed. Glad the outcome was favourable."),
    },
    "meridian": {
        "earthlike": ("Begging your pardon, Commander. An Earth-like. I came up to see her.",
                      "An Earth-like world. In the old fleet, we would have rung the bell.",
                      "Off watch, but I would not miss this. Mark her well.",
                      "A green and blue world. Sailors dream of such landfalls.",
                      "From below decks: a fine sight, Commander. A very fine sight."),
        "footfall": ("First boots ashore. Well done, Commander.",
                     "From below decks: a first landing. The old charts would envy you.",
                     "Nobody has stood there before. Now the log knows you did.",
                     "A first footfall. I raise a quiet glass, off watch.",
                     "Ashore where no one has been. That is worth the whole voyage."),
        "record_jump": ("A record stride, Commander. The drive earned its keep.",
                        "From below decks: the longest jump this ship has made. Well judged.",
                        "Off watch, but I felt that one in my bones. A record.",
                        "A new longest jump. The chart barely keeps up with you.",
                        "Record distance in one stride. Fine seamanship."),
        "record_far": ("Further from Sol than ever. I have marked the bearing home, as always.",
                       "From below decks: our furthest position yet. Deep water indeed.",
                       "A record distance from home. Steady as she goes.",
                       "Off watch, but I will mark this one myself. The furthest yet.",
                       "Further than we have ever sailed. Keep a good margin, and onward."),
        "close_call": ("That was a near thing, Commander. Well recovered.",
                       "From below decks: I heard the alarms. Glad we are still afloat.",
                       "A close shave. Let us keep a wider berth next time.",
                       "Off watch, but I was on my feet for that. Well handled.",
                       "We came through. Ships have been lost for less."),
    },
}
