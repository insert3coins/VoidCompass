"""The Hatchling's chatter (5.6.4): a few words now and then, never a thought.

The Watcher is the one that thinks aloud. The pet chatters in text, rarely,
and never while the Watcher has something on screen. Each species and sample
family has its own words. Its growth, personality and memories also shape
what it says. The deck asks for a line on a journal cue or in a quiet moment.

{toy}, {food}, {dream}, {body}, {ship} and {to} (the expedition's
destination) come from the pet; a line needing one it
hasn't got is skipped.
"""

from __future__ import annotations

import random

from voidcompass.core.hatchling_growth_lines import FORM_LINES, STAGE_LINES
from voidcompass.core.hatchling_sample_lines import SAMPLE_LINES
from voidcompass.core.hatchling_species_lines import SPECIES_LINES
from voidcompass.core.hatchling_thargoid_lines import THARGOID_LINES, THARGOID_STAGE_LINES

# Off, quiet (the default) or chatty: the least gap between lines, and how
# often it speaks up when it could.
MODES = {"off": None, "quiet": {"gap": 300.0, "cue": .35, "idle": .08},
         "chatty": {"gap": 90.0, "cue": .7, "idle": .25}}
SHOWN_S = 8.0

LINES = {
    "jump": ("Here we go!", "Hold on, hold on…", "Bye, star!", "Ooh, the swirly bit.", "I don't like this part."),
    "arrive": ("Where are we?", "New star!", "Ooh. Different light.", "Are we there yet?", "That was a big one.",
               "Hello, {system}.", "Is this {system}?", "Another star in {system}."),
    "dock": ("Lights! People!", "Can I come out?", "It smells of station.", "We're inside now.", "Hello, station."),
    "undock": ("Bye, station!", "Back to the black.", "Out we go.", "I'll miss the lights."),
    "touchdown": ("We landed!", "Ground! Real ground!", "Bump. We're down.", "Can I go outside?"),
    "liftoff": ("Up, up!", "Bye, ground.", "Going up!"),
    "cruise": ("Fast now!", "Wheee.", "Stars go whoosh.", "So fast."),
    "drop": ("Whoa. Stopped.", "Where did the fast go?", "We slowed down."),
    "danger": ("Scary! Scary!", "Make it stop!", "I'm hiding.", "Is it gone?", "Too loud!"),
    "discovery": ("We found something new!", "Ooh! New!", "Look at that!", "Write it down!"),
    "heat": ("Too hot!", "Hot hot hot.", "Can we cool down?"),
    "lowfuel": ("Fuel's low…", "Are we stuck?", "We need a star.", "Hungry ship."),
    "scoop": ("Sunglasses on.", "Bright!", "Drinking the star.", "Warm and bright."),
    "srv": ("Bumpy!", "Drive faster!", "I like the buggy.", "Wheels!"),
    "leave": ("Where are you going?", "Don't be long.", "I'll wait here.", "Come back soon."),
    "welcome": ("You're back!", "Missed you!", "There you are!", "I waited!"),
    "toy": ("Look what I found!", "Mine now.", "I like {toy}.", "Shiny!", "Can I keep it?"),
    "trick": ("Did you see that?", "I can do it now!", "Watch me!", "Again? Again!"),
    "victory": ("Got them!", "We won!", "Take that!", "Is it over?"),
    "mission": ("Job done!", "We did it!", "Easy.", "Do we get paid?"),
    "sad": ("Oh no.", "We'll do better.", "That didn't work."),
    "party": ("You got promoted!", "Party!", "So proud of you!"),
    "newship": ("New ship!", "It smells new.", "Where's my spot?", "I like this one."),
    "paid": ("Credits!", "We're rich!", "Can we buy snacks?"),
    "upgrade": ("Upgrades!", "Faster now?", "Ooh, shiny bits."),
    "repaired": ("All fixed.", "Good as new.", "Feels safer now."),
    "phew": ("Phew!", "That was close.", "We got away!"),
    "boost": ("Super fast!", "Whoosh!", "Again!"),
    "pose": ("Cheese!", "My good side.", "Did you get me?"),
    "naughty": ("Naughty!", "I saw that.", "Are we in trouble?"),
    "rude": ("Rude!", "Let us in!", "Why not?"),
    "fighter": ("Little ship!", "Bye, little ship!", "Come back safe."),
    "allfound": ("All of them!", "Every single one!", "We found them all!"),
    "mapped": ("Perfect map!", "Neat probes.", "All mapped."),
    "settlement": ("People down there!", "A little town!", "Lights on the ground."),
    "honk": ("Did the stars hear us?", "The ship is singing.", "Listen to that sound.", "How many worlds?"),
    "biology": ("You found something alive.", "Does it know we're here?", "Another little life.", "Will you remember it?",
                "Something alive on {body}.", "What grows on {body}?"),
    "tripdone": ("We made it!", "All the way there!", "We did it, together.", "Where next?"),
    "idle_trip": ("Are we nearly at {to}?", "{to}, here we come!", "How far to {to}?", "I want to see {to}."),
    "music": ("Dance time!", "I love this one!", "Turn it up!", "Ooh, music.", "This one's good."),
    "cold": ("So cold…", "Brr. Cold world.", "My feet are freezing."),
    "hot": ("This world is hot.", "Too warm here.", "Everything's melting."),
    "idle": ("Hello.", "What's that light?", "Are we going far?", "I like it here.", "Hmm.",
             "Pod's nice today.", "Where next?", "Stars, stars, stars.", "Is it night?"),
    "idle_toy": ("Where's {toy}?", "I'll play with {toy}.", "{toy} is my favourite."),
    "idle_food": ("Is there {food}?", "I want {food}.", "{food}, please?"),
    "idle_dream": ("I dreamed of {dream}.", "Remember {dream}?", "{dream} was pretty."),
    "idle_world": ("{body} is big.", "What's on {body}?", "I can see {body}."),
    "idle_ship": ("I like the {ship}.", "The {ship} hums.", "Good ship, the {ship}."),
    # Its personality: what it brings up when nothing's happening.
    "curious": ("What's over there?", "Why is space black?", "What's that one called?", "Can we look closer?"),
    "brave": ("I'm not scared.", "Bring it on.", "I'd fight a Thargoid.", "Nothing scares me."),
    "lazy": ("Nap time?", "Just five more minutes.", "Too comfy to move.", "Sleepy…"),
    "greedy": ("Snack?", "Is it dinner?", "Something smells good.", "I could eat."),
    "clingy": ("Are you still there?", "Stay with me.", "I like it when you're here.", "Pat me?"),
    # The Watcher has just spoken; now and then it answers.
    "answer": ("…yes.", "Mm-hm.", "Okay, Watcher.", "I heard.", "Hello, Watcher.", "You found me.", "I'm still here.", "…true."),
}
# A few that belong to one kind alone.
OWN = {
    "larva": {"idle": ("The hive is singing.", "Hmm… hmm…"), "danger": ("Not the Guardians!",)},
    "bot": {"idle": ("Systems nominal.", "Running diagnostics."), "lowfuel": ("Power reserves low.",)},
    "sample": {"idle": ("I'm growing.", "Need light."), "scoop": ("Sun… lovely sun.",)},
}


def voiced(species, text, rng):
    """In its own voice: a larva hums, a bot beeps, a sample whispers."""
    if species == "bot":
        clipped = text.rstrip("!?.…").replace("I'm ", "").replace("I ", "")
        return f"{'BEEP. ' if rng.random() < .5 else ''}{clipped[:1].upper()}{clipped[1:]}."
    if species == "sample":
        return f"…{text[:1].lower()}{text[1:].rstrip('!').rstrip('.')}…"
    if species == "thargoid":
        return text
    return f"{text} hmm…" if rng.random() < .3 else f"hmm… {text}" if rng.random() < .3 else text


def _fields(pet):
    toys = pet.get("toys") or []
    world = pet.get("world") or {}
    dreams = pet.get("dreams") or []
    return {
        "toy": str(toys[-1].get("label") or "").removeprefix("a ").removeprefix("an ") if toys else "",
        "food": str(pet.get("favourite_food") or ""),
        "dream": str(dreams[0]) if dreams else "",
        "system": str(dreams[0]) if dreams else "",
        "body": str(world.get("body") or ""),
        "ship": str(pet.get("ship") or ""),
        "to": str((pet.get("trip") or {}).get("to") or ""),
    }


def _pool(pet, situation):
    species = pet.get("species") or "larva"
    if species == "thargoid":
        bank = {**THARGOID_LINES, **THARGOID_STAGE_LINES.get(pet.get("stage"), {})}
    else:
        bank = SAMPLE_LINES.get(pet.get("kind"), {}) if species == "sample" else SPECIES_LINES.get(species, {})

    def for_situation(key):
        # A family speaks in its own words whenever it has them. The older
        # common lines remain a fallback for cues added by future versions.
        return list(bank.get(key) or (list(LINES.get(key, ())) + list(OWN.get(species, {}).get(key, ()))))

    lines = for_situation(situation)
    if situation == "idle":
        # Idle chatter leans on what it knows and who it has become.
        for extra in ("idle_toy", "idle_food", "idle_dream", "idle_world", "idle_ship", "idle_trip", pet.get("trait") or ""):
            lines += for_situation(extra) * 2
        lines += list(STAGE_LINES.get(pet.get("stage"), ()))
        if pet.get("stage") == "adult":
            lines += list(FORM_LINES.get(species, {}).get(pet.get("form"), ()))
    fields = _fields(pet)
    usable = []
    for line in lines:
        try:
            text = line.format(**fields)
        except (KeyError, IndexError):
            continue
        if all(fields[key] for key in fields if "{" + key + "}" in line):
            usable.append(text)
    return usable


def _voice_key(text):
    text = str(text or "").casefold().strip()
    text = text.removeprefix("beep. ").removeprefix("hmm… ").removesuffix(" hmm…")
    return text.strip(" ….!?")


def chatter(state, view_pet, situation, now, mode="quiet", watcher_busy=False, rng=None, force=False):
    """Maybe a few words for ``situation`` (a cue's kind, "idle", "answer"…).
    The line, or None when it keeps quiet. ``view_pet`` is the pet as the
    pages see it (its traits, toys, dreams, world)."""
    pet = (state or {}).get("pet")
    setting = MODES.get(mode)
    if not pet or not view_pet or setting is None or watcher_busy:
        return None
    if pet.get("stage") == "egg" or pet.get("dormant_since") is not None or pet.get("asleep"):
        return None
    rng = rng or random.Random()
    last = float((pet.get("chat") or {}).get("at") or 0)
    if not force:
        if now - last < setting["gap"]:
            return None
        chance = setting["idle"] if situation == "idle" else setting["cue"]
        if rng.random() > chance:
            return None
    pool = _pool(view_pet, situation)
    previous = pet.get("chat") if isinstance(pet.get("chat"), dict) else {}
    recent = [line for line in previous.get("recent", ()) if isinstance(line, str)][-6:] if isinstance(previous.get("recent"), list) else []
    if previous.get("line") and previous["line"] not in recent:
        recent.append(previous["line"])
    # Old saves contain only the final text, potentially with a vocal prefix.
    if not recent and previous.get("text"):
        said = _voice_key(previous["text"])
        recent = [line for line in pool if _voice_key(voiced(view_pet.get("species"), line, random.Random(0))) == said]
    fresh = [line for line in pool if line not in recent]
    pool = fresh or [line for line in pool if line != previous.get("line")] or pool
    if not pool:
        return None
    line = rng.choice(pool)
    text = voiced(view_pet.get("species"), line, rng)
    pet["chat"] = {"text": text, "at": now, "situation": situation, "line": line, "recent": (recent + [line])[-6:]}
    return text


def shown(pet, now):
    """Its last words, while they're still on screen."""
    chat = (pet or {}).get("chat")
    if isinstance(chat, dict) and now - float(chat.get("at") or 0) < SHOWN_S:
        return {"text": str(chat.get("text") or ""), "at": float(chat.get("at") or 0)}
    return None
