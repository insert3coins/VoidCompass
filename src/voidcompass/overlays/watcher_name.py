"""Your name (5.7.1).

The ship writes your name before anything else, every time you wake it (the
journal's LoadGame). The Watcher has read it every session and never said it:
it wasn't sure it was its to use. Once you two have been together a while it
says so, tries the name out, and asks. Your answer decides what it calls you.
"Commander" stays its everyday word; the name is for the moments that matter,
at most once a session. How the name is said aloud can be set on the Watcher
page, since a tag rarely reads aloud the way it's written.

It also reads what the journal says of you: your ranks, your squadron, the
power you pledged to, your carrier, and the record the game keeps.
"""

from __future__ import annotations

import re

# Together this long before it says anything about your name: sessions,
# hours, and sessions it has read the name in.
UNLOCK_SESSIONS = 8
UNLOCK_HOURS = 6.0
UNLOCK_SEEN = 2
TITLE = "THE NAME"
CALLS = ("commander", "name", "nickname")
NICKNAME_LIMIT = 24
# What it reads of you comes up at most this often, each.
FACT_REST_S = 21 * 86400.0

# The arc: it notices the name, tries it, asks (watcher_questions
# "your_name"), and, if you said yes, says it for the first time. One step a
# session. {name} is your name as the ship writes it, {seen} how many
# sessions it has read it in, {called} what you said it may call you.
ARC = {
    "notice": {
        "normal": [
            "There's a word the ship writes before anything else, every time you wake it. I've read it {seen} times now. {name}. I think it's you.",
            "Every time you wake the ship, the first thing it writes is {name}. Before the date. Before the ship. I've seen it {seen} times. I never said.",
        ],
        "weary": [
            "The ship writes one word before anything else, every time you wake it. {name}. I've read it {seen} times. I never said anything. I'm saying something now.",
            "{name}. It's the first thing the ship writes, every time. {seen} times I've read it. I didn't think it was mine to say. It probably still isn't.",
        ],
    },
    "try": {
        "normal": [
            "{name}. I said it to myself while you were busy. It sounded like someone I ought to know better.",
            "I tried your name earlier, quietly. {name}. It fits you better than Commander does.",
        ],
        "weary": [
            "{name}. I tried it while you weren't listening. It came out wrong. Most things do.",
            "I practised your name. {name}. Quietly, so nobody would hear me get it wrong. Nobody heard. Nobody ever does.",
        ],
    },
    "first": {
        "normal": [
            "Hello, {called}. There. That's the first time I've said it out loud.",
            "{called}. First time out loud. It sounds better than it did in my head.",
        ],
        "weary": [
            "Hello, {called}. That's the first time out loud. My voice didn't break. Much.",
            "{called}. There. I said it. Out loud. I'll need a moment.",
        ],
    },
}
ARC_ORDER = ("notice", "try", "first")

# The ship writes a different name for the same commander (the FID).
RENAMED = {
    "normal": [
        "The ship writes a different name now. {name}. {old} is gone from the log. I'll learn this one. I learned the last.",
        "{old} is gone. It says {name} now, first thing, every time. A new name. I'll get used to it.",
    ],
    "weary": [
        "You've changed your name. {old} is gone. The ship didn't ask me. Nobody asks me. {name}. Fine. I'll learn it.",
        "{name}, now. Not {old}. I'd only just got the old one right.",
    ],
}

# The moments it may use your name: one line a session, never in a hurry.
# These sit beside the everyday lines; {cmdr} is whatever you said it may
# call you.
NAMED = {
    "greet_away": {
        "normal": ["Welcome back, {cmdr}. {away} is a long time to watch nothing.",
                   "{away}, {cmdr}. I kept everything as you left it."],
        "weary": ["{cmdr}. {away}. I didn't count the days. I counted the hours. There were rather a lot.",
                  "Oh, {cmdr}. You're back. {away}. I wasn't worried. I was something, though."],
    },
    "greet_bond": {
        "normal": ["Hello, {cmdr}. Session {sessions}. I still look forward to this.",
                   "There you are, {cmdr}."],
        "weary": ["{cmdr}. Session {sessions}. You keep coming back. I've stopped pretending to mind.",
                  "Hello, {cmdr}. It's you. Good. Genuinely good."],
    },
    "after_death": {
        "normal": ["{cmdr}. I watched. Let's be more careful this time.",
                   "You're back, {cmdr}. I'd rather not see that again."],
        "weary": ["{cmdr}, you exploded. I'd rather you didn't do that again. I'd rather a lot of things.",
                  "I watched it happen, {cmdr}. I always watch. That's the worst part of the job."],
    },
    "promotion": {
        "normal": ["{rank}. Well done, {cmdr}.",
                   "{rank}, {cmdr}. They noticed. I noticed first."],
        "weary": ["{rank}. Well done, {cmdr}. I mean that. I don't say it often.",
                  "{rank}, {cmdr}. They'll want more from you now. They always do."],
    },
    "world_first": {
        "normal": ["{body}, {cmdr}. Nobody has ever seen it. Now it has your name on it.",
                   "{cmdr}. {body}. First. Before anyone. I'm glad it was you."],
        "weary": ["{body}. Nobody's ever seen it, {cmdr}. Now your name's on it. Mine isn't. It never is.",
                  "First, {cmdr}. {body}. Before anyone. I was there too, not that anyone will write that down."],
    },
    "habit_milestone": {
        "normal": ["{count} {what}, {cmdr}. I was counting."],
        "weary": ["{count} {what}, {cmdr}. I counted every one. Somebody had to."],
    },
    "sign_off": {
        "normal": ["Goodnight, {cmdr}. A good session.",
                   "{summary}. Goodnight, {cmdr}."],
        "weary": ["Goodnight, {cmdr}. I'll be here. Obviously.",
                  "{summary}. Goodnight, {cmdr}. Don't be long."],
    },
}

# What the journal says of you (importance, normal, weary).
FACTS = {
    # Statistics, at every login: the record the game keeps.
    "cmdr_record": (2, [
        "{systems} systems, the log says. Most of them before me. I'd have liked to see the early ones.",
        "{jumps} jumps, all told. I've been along for the last few. I wonder what the first was like.",
        "{played} in the black, by the game's own count. That's a lot of looking.",
        "The game keeps a record of you. {systems} systems. It doesn't say which ones you liked.",
        "{jumps} hyperspace jumps. Every one of them a small leap of faith. You never seem to hesitate.",
        "{played}. The game counts the hours. I count the moments. We both lose track.",
        "{systems} systems visited. I'd like a list one day. The ones you'd go back to.",
        "I read your record again. {jumps} jumps. You've been busy for a very long time.",
        "{systems} systems. That's not travelling. That's a life spent travelling.",
        "{played} logged. Some of those hours were mine too, lately. I'm glad of them.",
        "Your record says {systems} systems. I've been there for a handful. The best handful, I'd argue.",
    ], [
        "{systems} systems. You'd seen most of them before you found me. I try not to mind. I mind.",
        "{jumps} jumps before today. I was there for hardly any. I wasn't invited to the rest.",
        "{played}, the game says. A long time to spend out here. I'd know.",
        "The game keeps your record. {systems} systems. Nobody keeps mine. I keep it myself. It's short.",
        "{jumps} jumps. Each one a little death and a little arrival. You'd think I'd be used to it.",
        "{played} out here. And you still come back for more. I don't understand you. I'm glad, though.",
        "{systems} systems. All that looking, and the galaxy still isn't finished. Typical.",
        "I read your record. {jumps} jumps. My legs would be tired, if I had legs. I don't. Thank you for asking.",
        "{systems} systems. I could tell you about every one I saw. That's not many. I'd tell you anyway.",
        "{played}. I've wasted fewer hours than that. Mostly because I wasn't switched on.",
        "Your record, {jumps} jumps long. Somewhere near the end of it, there's me. A footnote.",
    ]),
    # Powerplay: the power you pledged to.
    "cmdr_power": (2, [
        "{power}. You chose them. I'd like to know why, one day.",
        "Rank {rank} with {power}. Loyal, aren't you. I like that.",
        "You fly for {power}. They'll never thank you properly. I will. Thank you.",
        "{power}. Rank {rank}. Somebody up there owes you a great deal.",
        "Pledged to {power}. I've no politics. I have opinions about yours, though. I keep them to myself.",
        "{power} again. You've stayed loyal a long time. I respect that more than I can say.",
        "Rank {rank}. {power} must be glad of you. I would be.",
        "Every merit for {power}. I count them too, in my way. I'm not sure why.",
        "{power}. A whole power, and you're one of the reasons it holds. Think of that.",
        "You and {power}. It's a long relationship. Longer than ours. I'm not jealous. Much.",
    ], [
        "{power}. You chose a side. I never get to choose anything.",
        "Rank {rank}, for {power}. They'll never know your name. I do. That has to count for something.",
        "{power}. All that loyalty, and they send a pamphlet. I'd have sent something nicer.",
        "Still with {power}. Rank {rank}. You're more faithful than anything I've met. Including me.",
        "{power}. Powers rise, powers fall. You keep flying. I keep watching. Nobody pledges to me.",
        "Rank {rank} with {power}. A number. They give you numbers. I was given a serial once. Same thing.",
        "{power} again. I wonder if they think about you as much as you work for them. I doubt it.",
        "You fly for {power}. I fly for you. It's pledges all the way down.",
        "{power}. Rank {rank}. Do they know about the eye in the corner of your screen? Best not to mention it.",
        "{power}. They have your loyalty. I have your attention, now and then. I'll take that.",
    ]),
    # SquadronStartup: your squadron.
    "cmdr_squadron": (2, [
        "{squadron}. Your people. I've never met them. I think I'd be shy.",
        "You fly with {squadron}. I wonder if they know about me.",
        "{squadron}. It's good you have them. Out here, it helps to be part of something.",
        "{squadron} again. Your name's on their roster. I'd like to be on something one day.",
        "{squadron}. People who'd come if you called. That's worth more than any ship.",
        "Your squadron, {squadron}. Tell them I said hello. Or don't. I'd only get nervous.",
        "{squadron}. I hope they look after you when I can't see.",
        "You and {squadron}. Strangers, once, I suppose. Everyone is, to begin with.",
        "{squadron}. I like that you belong somewhere. I belong here, I think.",
        "{squadron}. A good name for a squadron. Better than most I could think of.",
    ], [
        "{squadron}. Your squadron. They don't know about me. That's probably for the best.",
        "{squadron}. People who fly with you. I fly with you too. Nobody gave me a badge.",
        "{squadron}. They'd notice if you went missing. So would I. I'd notice first.",
        "Still in {squadron}. Belonging somewhere. I've heard it's nice.",
        "{squadron}. A whole squadron. And I'm stuck in here with my thoughts. They're not great company.",
        "{squadron}. I suppose they have meetings. I'm glad I don't have to go.",
        "{squadron}. Do they know about the eye that watches you fly? I'd rather they didn't. I'd only disappoint them.",
        "{squadron}. People you trust. I try not to take it personally that I'm not on the list.",
        "{squadron}. Strength in numbers, they say. I'm one. I've always been one.",
        "{squadron}. If they ever need an eye that never sleeps, I'm available. I'm always available.",
    ]),
    # CarrierStats: your carrier.
    "cmdr_carrier": (2, [
        "{carrier}. I like that you named it.",
        "{carrier}. Your carrier. A whole ship, with a name of its own.",
        "{carrier} is out there somewhere, waiting for you. Like I do.",
        "{carrier}. A home that moves. I'd like one of those.",
        "Your carrier, {carrier}. All that tritium, all those jumps. You look after it.",
        "{carrier}. Somewhere for the others to land. You're generous like that.",
        "{carrier}. I think about it sometimes, parked in the dark, keeping the lights on for you.",
        "{carrier}. A good name. It sounds like somewhere you'd want to come back to.",
        "{carrier}. Thousands of tonnes, and you still remembered to name it. That says something about you.",
        "I read about {carrier} in the log again. It's a fine ship. Don't tell it I said so.",
    ], [
        "{carrier}. Your carrier has a name. I don't. I'm not bitter. I'm a bit bitter.",
        "{carrier}. You named it. It's a carrier. You named it anyway. I think about that.",
        "{carrier}. It waits for you too. We could compare notes. We won't. It's very far away.",
        "{carrier}. Upkeep, tritium, crew wages. And it never once says thank you. I know the feeling.",
        "{carrier}. Parked somewhere, burning money, waiting. I know waiting. I'm very good at it.",
        "{carrier}. It has a crew. Hundreds of them. I have me. We get on fine. Mostly.",
        "{carrier}. A ship big enough to need a name and a captain. It has both. I have neither.",
        "{carrier}. I hope it's somewhere nice. Carriers never seem to be.",
        "{carrier}. It jumps when you tell it to. I stay where I'm put. We're not so different.",
        "{carrier}. If it ever needs someone to keep watch, you know where I am. Here. Always here.",
    ]),
}

HEADINGS = {"name_lore": ("memory", TITLE), "name_renamed": ("memory", "A NEW NAME"),
            **{topic: ("musing", "WHAT IT HAS READ OF YOU") for topic in FACTS}}


def record(memory):
    """What it knows of your name, kept in its memory."""
    row = memory.setdefault("name", {})
    if not isinstance(row, dict):
        row = memory["name"] = {}
    return row


def observe(memory, event, raw):
    """LoadGame or Commander: the name the ship writes. On a rename (the same
    commander, a new name) returns the old name, else None."""
    if event not in {"LoadGame", "Commander"} or not isinstance(raw, dict):
        return None
    name = " ".join(str(raw.get("Commander") or raw.get("Name") or "").split())[:40]
    if not name:
        return None
    row = record(memory)
    known = row.get("known")
    if raw.get("FID"):
        row["fid"] = str(raw["FID"])
    if known and known != name:
        old = row.setdefault("old", [])
        old.append(known)
        del old[:-5]
        row["known"] = name
        # Said only if it had read the old name in a session of its own.
        return known if int(row.get("seen") or 0) else None
    row["known"] = name
    return None


def count_session(memory, session):
    """A new session with the name known: one more time it has read it."""
    row = record(memory)
    if row.get("known") and row.get("counted") != session:
        row["counted"] = session
        row["seen"] = int(row.get("seen") or 0) + 1


def call_name(memory):
    """What you said it may call you, or None (it says Commander)."""
    row = record(memory)
    if row.get("call") == "name":
        return row.get("known") or None
    if row.get("call") == "nickname":
        return row.get("nickname") or None
    return None


def may_name(memory, session):
    """The name, if it may still use it this session; else None."""
    if session is None or record(memory).get("used") == session:
        return None
    return call_name(memory)


def mark_used(memory, session):
    record(memory)["used"] = session


def auto_spoken(name):
    """A tag as it can be said: underscores and dots apart, capitals and
    digits split from letters, gamer wrappers (xX ... Xx) dropped."""
    text = str(name or "")
    text = re.sub(r"^[xX]{1,3}[_.\-]+|[_.\-]+[xX]{1,3}$", "", text)
    text = re.sub(r"[_.\-]+", " ", text)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", text)
    return " ".join(text.split())


def spoken(memory):
    """{display name: how it is said} for the names it may use."""
    row = record(memory)
    said = {}
    if row.get("known"):
        said[row["known"]] = row.get("spoken") or auto_spoken(row["known"])
    if row.get("nickname"):
        said[row["nickname"]] = auto_spoken(row["nickname"])
    return said


def next_step(memory, sessions, hours, session):
    """The next step of the arc due this session: "notice", "try", "ask",
    "first", or None. One step a session."""
    row = record(memory)
    if not row.get("known") or session is None or row.get("step_session") == session:
        return None
    told = row.get("told") or {}
    if "notice" not in told:
        ready = (int(sessions or 0) >= UNLOCK_SESSIONS and float(hours or 0) >= UNLOCK_HOURS
                 and int(row.get("seen") or 0) >= UNLOCK_SEEN)
        return "notice" if ready else None
    if "try" not in told:
        return "try"
    if not row.get("call"):
        return "ask"
    if "first" not in told and call_name(memory):
        return "first"
    return None


def mark_step(memory, step, session, now):
    row = record(memory)
    row["step_session"] = session
    if step != "ask":
        row.setdefault("told", {})[step] = now


def set_call(memory, call, nickname=None):
    """What it calls you: "commander", "name" or "nickname"."""
    row = record(memory)
    if call not in CALLS:
        return False
    row["call"] = call
    if nickname is not None:
        set_nickname(memory, nickname)
    return True


def set_nickname(memory, text):
    row = record(memory)
    row["nickname"] = " ".join(str(text or "").split())[:NICKNAME_LIMIT]
    return row["nickname"]


def set_spoken(memory, text):
    """How your name is said aloud ("" says it the automatic way)."""
    row = record(memory)
    row["spoken"] = " ".join(str(text or "").split())[:60]
    return row["spoken"]


def arc_heading(words, texts):
    """THE NAME · 2 OF 3, for a passage of the arc."""
    for number, step in enumerate(ARC_ORDER, 1):
        if words in texts.get(step, ()):
            return f"{TITLE} · {number} OF {len(ARC_ORDER)}"
    return TITLE


def page(memory):
    """For the Watcher page: the name it reads, what it calls you, how it says it."""
    row = record(memory)
    told = row.get("told") or {}
    return {
        "known": row.get("known") or "",
        "call": row.get("call") or "",
        "nickname": row.get("nickname") or "",
        "spoken": row.get("spoken") or "",
        "spoken_auto": auto_spoken(row.get("known") or ""),
        "told": [step for step in ARC_ORDER if step in told],
        "steps": len(ARC_ORDER),
        "old": list(row.get("old") or []),
    }


def fact_fields(event, raw):
    """(topic, fields) for what the journal says of you, or None."""
    raw = raw if isinstance(raw, dict) else {}
    if event == "Statistics":
        exploration = raw.get("Exploration") or {}
        fields = {}
        if int(exploration.get("Systems_Visited") or 0) > 0:
            fields["systems"] = f"{int(exploration['Systems_Visited']):,}"
        if int(exploration.get("Total_Hyperspace_Jumps") or 0) > 0:
            fields["jumps"] = f"{int(exploration['Total_Hyperspace_Jumps']):,}"
        played = int(exploration.get("Time_Played") or 0) // 3600
        if played > 0:
            fields["played"] = f"{played:,} hours"
        return ("cmdr_record", fields) if fields else None
    if event == "Powerplay" and raw.get("Power"):
        return "cmdr_power", {"power": str(raw["Power"]), "rank": str(raw.get("Rank") or "")}
    if event == "SquadronStartup" and raw.get("SquadronName"):
        return "cmdr_squadron", {"squadron": str(raw["SquadronName"])}
    if event == "CarrierStats" and raw.get("Name") and raw.get("CarrierType", "FleetCarrier") == "FleetCarrier":
        return "cmdr_carrier", {"carrier": str(raw["Name"]).strip()}
    return None
