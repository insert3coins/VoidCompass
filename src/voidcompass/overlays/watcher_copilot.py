"""The Watcher as co-pilot (5.7.1, experimental): what the ship's systems
show when you ask it something, and the few small things it will do when
asked.

Only the app's own numbers go in: the route, the survey, the ship, the
colony needs, Powerplay, the expedition, Galnet, the music. Each line is
plain fact for its own words to draw on (and is checked against, like the
rest). The actions are the harmless ones: the music, the overlays, the
clipboard and its own voice. Nothing here touches the game.
"""
from __future__ import annotations

import re

# What a question is about: the systems asked, by the words in it.
TOPICS = {
    "route": re.compile(r"\b(route|jumps?|next system|destination|how far|plotted|waypoints?|hops?|headed|heading|going)\b", re.I),
    "survey": re.compile(r"\b(survey|scan(ned|s)?|bod(y|ies)|fss|honk|bio(logy|logicals?)?|signals?|planets?|worth|value|"
                         r"undiscovered|this system)\b", re.I),
    "ship": re.compile(r"\b(ship|fuel|tank|hull|cargo|hold|jump range|range|credits|money|balance|rich)\b", re.I),
    "colony": re.compile(r"\b(colon\w*|construction|build(ing)?|haul\w*|commodit\w*|needs?|site)\b", re.I),
    "powerplay": re.compile(r"\b(power ?play|merits?|pledged?|powers?|rank)\b", re.I),
    "expedition": re.compile(r"\b(expeditions?|trip|journey)\b", re.I),
    "galnet": re.compile(r"\b(galnet|news|headlines?|happening out there|in the galaxy)\b", re.I),
    "music": re.compile(r"\b(music|song|track|tune|playing|listening)\b", re.I),
    # What could live on a world: Survey's own predictions, from your scans.
    "life": re.compile(r"\b(life|living|alive|live|bio\w*|organics?|species|genus|genera|grow\w*|flora|exobio\w*|"
                       r"bacteri\w*|fungoid\w*|tussocks?|stratum|osseus|frutex\w*|fonticulua|concha|tubus|aleoida|"
                       r"clypeus|cactoida|electricae|recepta)\b", re.I),
}
LOOKUP_LIMIT = 12
SCALE = {"B": "billion", "M": "million", "K": "thousand"}


def topics_for(question):
    """The systems a question asks about, in a fixed order."""
    text = str(question or "")
    return [name for name, pattern in TOPICS.items() if pattern.search(text)]


# -- the lines --------------------------------------------------------------------
def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _whole(value):
    number = _number(value)
    return None if number is None else int(round(number))


def route_lines(nav):
    nav = nav or {}
    next_name = str(nav.get("next") or "")
    if not next_name or next_name == "---":
        return ["No route is plotted."]
    lines = [f"Next system on the route: {next_name}"]
    distance = str(nav.get("next_distance") or "")
    if distance and distance != "--":
        lines[0] += f", {distance.replace(' LY', ' light years')} away"
    remaining = _whole(nav.get("route_remaining"))
    if remaining is not None:
        lines.append(f"Jumps left on the route: {remaining}")
    total = str(nav.get("total_distance_text") or "")
    if total and any(ch.isdigit() for ch in total):
        lines.append(f"Distance left on the route: {total.replace(' LY', ' light years')}")
    hops = [hop for hop in nav.get("hops") or () if isinstance(hop, dict)]
    known = [hop for hop in hops if hop.get("scoopable") is not None]
    if known:
        lines.append(f"Scoopable stars in the next {len(known)} jumps: {sum(1 for hop in known if hop.get('scoopable'))}")
    return lines


def survey_lines(system, scanned=0, total=0, bio_signals=0, bio_done=0, valuable=0, undiscovered=False, mapped=0):
    where = f" in {system}" if system and system != "---" else ""
    scanned, total = _whole(scanned) or 0, _whole(total) or 0
    lines = [f"Bodies scanned{where} so far: {scanned}"]
    if total:
        lines[0] = f"Bodies in the system{where}: {total}, of which {scanned} scanned"
        lines.append("Every body in the system has been found" if scanned >= total
                     else f"Bodies still to find: {total - scanned}")
    if bio_signals:
        lines.append(f"Biological signals here: {int(bio_signals)}, {int(bio_done or 0)} logged so far")
    if valuable:
        lines.append(f"Valuable worlds found here: {int(valuable)}")
    if mapped:
        lines.append(f"Bodies mapped with probes here: {int(mapped)}")
    if undiscovered:
        lines.append("Nobody had discovered this system before the commander")
    return lines


def ship_lines(kind="", name="", jump_range=0, fuel_percent=None, cargo_tons=0, cargo_capacity=0, credits="",
               hull_percent=None):
    lines = []
    if kind:
        lines.append(f"Ship: {kind}" + (f", named {name}" if name else ""))
    jump = _number(jump_range)
    if jump:
        lines.append(f"Jump range: {jump:.1f} light years")
    fuel = _whole(fuel_percent)
    if fuel is not None:
        lines.append(f"Fuel: {fuel}%")
    hull = _whole(hull_percent)
    if hull is not None:
        lines.append(f"Hull: {hull}%")
    capacity = _whole(cargo_capacity) or 0
    tons = _whole(cargo_tons) or 0
    if capacity:
        lines.append(f"Cargo: {tons} of {capacity} tonnes")
    elif tons:
        lines.append(f"Cargo: {tons} tonnes")
    if credits and credits != "---":
        # "1.2B CR" as words: the model says "billion" whatever it's given.
        spoken = re.sub(r"(\d)([BMK]) CR$", lambda m: f"{m.group(1)} {SCALE[m.group(2)]} credits", credits)
        lines.append(f"Credits: {spoken.replace(' CR', ' credits')}")
    return lines


def colony_lines(projects, needs):
    """projects: [(name, system)]; needs: {commodity name: tonnes still wanted}."""
    if not projects:
        return ["No colony construction is being tracked."]
    names = ", ".join(f"{name} in {system}" if system else name for name, system in projects[:3])
    lines = [f"Construction projects tracked: {len(projects)} ({names})"]
    wanted = sorted(((name, int(count)) for name, count in (needs or {}).items() if int(count or 0) > 0),
                    key=lambda row: -row[1])
    if wanted:
        lines.append(f"Still needed, in all: {sum(count for _name, count in wanted):,} tonnes")
        lines.append("Most needed: " + ", ".join(f"{name} {count:,} tonnes" for name, count in wanted[:5]))
    else:
        lines.append("Nothing more is needed for them")
    return lines


def powerplay_lines(state):
    state = state or {}
    if not state.get("pledged") or not state.get("power"):
        return ["The commander isn't pledged to a power."]
    line = f"Pledged to {state['power']}"
    rank = _whole(state.get("rank"))
    merits = _whole(state.get("merits"))
    if rank is not None:
        line += f", rank {rank}"
    if merits is not None:
        line += f", {merits:,} merits"
    return [line]


def expedition_lines(expedition):
    if not expedition:
        return ["No expedition is under way."]
    stats = expedition.get("stats") or {}
    line = f"Expedition under way: {expedition.get('name') or 'unnamed'}"
    jumps = _whole(stats.get("jumps")) or 0
    distance = _number(stats.get("distance_ly")) or 0.0
    if jumps:
        line += f", {jumps:,} jumps and {distance:,.0f} light years so far"
    lines = [line]
    if expedition.get("destination"):
        lines.append(f"Expedition destination: {expedition['destination']}")
    firsts = _whole(stats.get("first_discoveries")) or 0
    if firsts:
        lines.append(f"First discoveries on the expedition: {firsts:,}")
    return lines


def life_lines(bodies, limit=3):
    """What could live on these worlds, from Survey's own predictions:
    bodies = [{"name", "signals", "known" (genera found), "genera"
    (bio_values.predict_genera), "colours" ({species casefolded: colour})}]."""
    if not bodies:
        return ["No world scanned here has any sign of life yet."]
    lines = []
    for body in bodies[:limit]:
        name = body.get("name") or "this world"
        signals = int(body.get("signals") or 0)
        head = f"{name}: {signals} biological signal{'s' if signals != 1 else ''}" if signals else f"{name}: no signals read yet"
        if body.get("known"):
            head += f", found so far: {', '.join(body['known'])}"
        lines.append(head)
        genera = sorted(body.get("genera") or (), key=lambda row: -(row.get("max_value") or 0))
        if not genera:
            lines.append(f"Nothing in the species data fits {name} as scanned")
            continue
        lines.append(f"Could grow on {name}: " + ", ".join(
            f"{row['name']} ({_value_range(row.get('min_value'), row.get('max_value'))})" for row in genera[:4]))
        species = sorted((row for genus in genera for row in genus.get("species") or () if row.get("value")),
                         key=lambda row: -row["value"])
        for row in species[:2]:
            colour = (body.get("colours") or {}).get(str(row["name"]).casefold())
            lines.append(f"On {name}, {row['name']} would fetch {int(row['value']):,} credits"
                         + (f", in {colour}" if colour else ""))
    return lines


def _value_range(low, high):
    if low and high and low != high:
        return f"{int(low):,} to {int(high):,} credits"
    return f"{int(high or low):,} credits" if (high or low) else "value unknown"


def galnet_lines(titles, limit=3):
    titles = [" ".join(str(title or "").split()) for title in titles or ()]
    titles = [title for title in titles if title][:limit]
    return [f"Galnet headline: {title}" for title in titles] or ["No Galnet news has come in."]


def music_lines(status, title="", artist=""):
    status = status or {}
    if not status.get("track_id"):
        return ["No music is playing."]
    what = f"{title} by {artist}" if title and artist else title or "a track"
    return [f"Music: {'playing' if status.get('playing') else 'paused on'} {what}"]


# -- the small things it will do ----------------------------------------------------
_PLEASE = r"^(?:(?:please|could you|can you|would you|will you|go on|ok|okay|hey|watcher)[\s,]+)*"


def _asks(pattern):
    """Asked at the start of what you said: "pause the music", not "the
    music I'd pause for"."""
    return re.compile(_PLEASE + r"(?:" + pattern + r")\b", re.I)


INTENTS = (
    ("music_pause", _asks(r"(?:pause|stop|mute)\b.*\b(?:music|song|track|tune)|pause(?: it| that)?$")),
    ("music_next", _asks(r"(?:next|skip)\s+(?:the\s+|this\s+)?(?:song|track|tune)|skip(?: it| this| this one| that)?$"
                         r"|play the next (?:song|track|tune)")),
    ("music_previous", _asks(r"previous\s+(?:song|track|tune)|(?:the\s+)?last\s+(?:song|track|tune)(?:\s+again)?$"
                             r"|go back\b.*\b(?:song|track|tune)|play the last (?:song|track|tune)")),
    ("music_play", _asks(r"(?:play|resume|unpause|start)\b.*\b(?:music|song|track|tune|something)|(?:play|resume)$")),
    ("overlays_hide", _asks(r"hide\b.*\b(?:overlays?|hud|everything)")),
    ("overlays_show", _asks(r"(?:show|bring back|restore|unhide)\b.*\b(?:overlays?|hud)")),
    ("copy_next", _asks(r"copy\b.*\b(?:next|system|waypoint|destination)")),
    ("unhush", _asks(r"unhush|unmute|you can (?:speak|talk)|(?:speak|talk) (?:again|aloud)")),
    ("hush", _asks(r"hush|shush|be quiet|quiet down|stop talking|mute yourself|silence")),
)


def intent(text):
    """The small thing asked of it, or None (most talk asks nothing)."""
    words = " ".join(str(text or "").split()).strip(" .!?")
    if not words or len(words) > 80:
        return None
    for name, pattern in INTENTS:
        if pattern.search(words):
            return name
    return None


# What it says when it has done it (or couldn't). Its own few words, never the model's.
REPLIES = {
    "music_pause": ("Paused. The quiet comes back.", "The music stops. I'll listen to the hull instead.", "Paused."),
    "music_play": ("Music, then.", "Playing. The dark could use it.", "There. Something to fly to."),
    "music_next": ("The next one.", "Skipped.", "On to the next."),
    "music_previous": ("Back one.", "That one again.", "The last one, again."),
    "music_not_playing": ("Nothing is playing.", "There's no music to stop."),
    "music_already": ("It's already playing.",),
    "overlays_hide": ("Hidden. I'm still here.", "Gone from the glass.", "Hidden. Say the word and they're back."),
    "overlays_show": ("Back on the glass.", "There they are.", "Shown again."),
    "overlays_already_hidden": ("They're already hidden.",),
    "overlays_already_shown": ("They're already showing.",),
    "copy_next": ("{system} is on your clipboard.", "Copied: {system}.", "{system}. It's on the clipboard."),
    "copy_none": ("There's no next system to copy.", "Nothing is plotted to copy."),
    "hush": ("I'll keep quiet for a while.", "Quiet, then.", "I'll keep my voice down."),
    "unhush": ("I can speak again.", "My voice is back.", "Aloud again, then."),
    "unavailable": ("I can't reach that from here.",),
}


def reply(outcome, rng, **fields):
    lines = REPLIES.get(outcome) or REPLIES["unavailable"]
    line = rng.choice(lines) if rng is not None else lines[0]
    try:
        return line.format(**fields)
    except (KeyError, IndexError, ValueError):
        return REPLIES["unavailable"][0]
