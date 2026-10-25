"""The Hatchling's chatter (5.6.4): a few words now and then, never a thought.

The Watcher is the one that thinks aloud. The pet only chatters: six words at
most, rarely, and never while the Watcher has something on screen. Each kind
talks its own way: a larva hums between its words, a bot beeps and clips
them, a sample speaks soft and slow. Its personality picks some of what it
says. The deck asks for a line when something happens (a jump, docking, a
toy) and now and then when nothing does; most of the time it stays quiet.

{toy}, {food}, {dream}, {body}, {ship} and {to} (the expedition's
destination) come from the pet; a line needing one it
hasn't got is skipped.
"""

from __future__ import annotations

import random

# Off, quiet (the default) or chatty: the least gap between lines, and how
# often it speaks up when it could.
MODES = {"off": None, "quiet": {"gap": 300.0, "cue": .35, "idle": .08},
         "chatty": {"gap": 90.0, "cue": .7, "idle": .25}}
SHOWN_S = 8.0

LINES = {
    "jump": ("Here we go!", "Hold on, hold on…", "Bye, star!", "Ooh, the swirly bit.", "I don't like this part."),
    "arrive": ("Where are we?", "New star!", "Ooh. Different light.", "Are we there yet?", "That was a big one."),
    "dock": ("Lights! People!", "Can I come out?", "It smells of station.", "We're inside now.", "Hello, station."),
    "undock": ("Bye, station!", "Back to the black.", "Out we go.", "I'll miss the lights."),
    "touchdown": ("We landed!", "Ground! Real ground!", "Bump. We're down.", "Can I go outside?"),
    "liftoff": ("Up, up!", "Bye, ground.", "Going up!"),
    "cruise": ("Fast now!", "Wheee.", "Stars go whoosh.", "So fast."),
    "drop": ("Whoa. Stopped.", "Where did the fast go?", "We slowed down."),
    "danger": ("Scary! Scary!", "Make it stop!", "I'm hiding.", "Is it gone?", "Too loud!"),
    "discovery": ("Nobody's seen that!", "We found it first!", "Ooh! New!", "Ours! That's ours!", "Write it down!"),
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
    "answer": ("…yes.", "Mm-hm.", "Okay, Watcher.", "I heard.", "Hello, Watcher.", "…true."),
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
    return f"{text} hmm…" if rng.random() < .3 else f"hmm… {text}" if rng.random() < .3 else text


def _fields(pet):
    toys = pet.get("toys") or []
    world = pet.get("world") or {}
    dreams = pet.get("dreams") or []
    return {
        "toy": str(toys[-1].get("label") or "").removeprefix("a ").removeprefix("an ") if toys else "",
        "food": str(pet.get("favourite_food") or ""),
        "dream": str(dreams[0]) if dreams else "",
        "body": str(world.get("body") or ""),
        "ship": str(pet.get("ship") or ""),
        "to": str((pet.get("trip") or {}).get("to") or ""),
    }


def _pool(pet, situation):
    species = pet.get("species") or "larva"
    lines = list(LINES.get(situation, ())) + list(OWN.get(species, {}).get(situation, ()))
    if situation == "idle":
        # Idle chatter leans on what it knows and who it is.
        for extra in ("idle_toy", "idle_food", "idle_dream", "idle_world", "idle_ship", "idle_trip", pet.get("trait") or ""):
            lines += list(LINES.get(extra, ())) * 2
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
    said = str((pet.get("chat") or {}).get("text") or "")
    pool = [line for line in pool if voiced(view_pet.get("species"), line, random.Random(0)) != said] or pool
    if not pool:
        return None
    text = voiced(view_pet.get("species"), rng.choice(pool), rng)
    pet["chat"] = {"text": text, "at": now, "situation": situation}
    return text


def shown(pet, now):
    """Its last words, while they're still on screen."""
    chat = (pet or {}).get("chat")
    if isinstance(chat, dict) and now - float(chat.get("at") or 0) < SHOWN_S:
        return {"text": str(chat.get("text") or ""), "at": float(chat.get("at") or 0)}
    return None
