"""The Watcher as co-pilot (5.7.1, experimental): what the ship's systems
show when you ask it something, and the few small things it will do when
asked.

Only the app's own numbers go in: the route, the survey, the ship, the
hold, the station you're docked at, the system's factions, the colony
needs, Powerplay, the expedition, Galnet, the music. Each line is
plain fact for its own words to draw on (and is checked against, like the
rest). The actions are the harmless ones: the music, the overlays, the
clipboard and its own voice. Nothing here touches the game.
"""
from __future__ import annotations

import re

# What a question is about: the systems asked, by the words in it. Narrow on
# purpose (5.7.2): "how's it going" brought the route, "are you alive" the
# exobiology readout and "what do you need" the colony, and it recited them.
TOPICS = {
    "route": re.compile(r"\b(route|next (system|jump|stop|star)|destination|how far|plotted|waypoints?|hops?|neutron|"
                        r"jumps? (left|to go|remaining)|how many jumps|where are we (going|headed|heading)|heading (to|for))\b",
                        re.I),
    "survey": re.compile(r"\b(survey|scan(ned|s)?|bod(y|ies)|fss|honk|bio(logy|logicals?)?|signals?|planets?|worlds?|"
                         r"undiscovered|first discover\w*|valuable)\b", re.I),
    "ship": re.compile(r"\b((our|my|the|this) ship|ship'?s (state|condition|health)|fuel|tank|hull|jump range|credits|"
                       r"money|balance)\b", re.I),
    # What's in the hold, by name: its own topic, not the whole ship readout.
    "cargo": re.compile(r"\b(cargo|carrying|inventory|limpets?|((the|our|my|cargo|ship'?s|srv'?s) )hold|in the hold)\b",
                        re.I),
    # The station you're docked at, as the game describes it on docking.
    "station": re.compile(r"\b(station|starport|outpost|docked|services|shipyard|outfitting|black market|"
                          r"material trader|tech(nology)? broker|interstellar factors|landing pads?)\b", re.I),
    # The system's factions, from the BGS readings the journal gives on arrival.
    "factions": re.compile(r"\b(factions?|bgs|influence|who (runs|controls|owns)|controll?ing|governments?|allegiance|"
                           r"conflicts?|wars?|elections?|civil (war|unrest|liberty)|boom|expansion|lockdown|outbreak|"
                           r"famine|retreat|reputation|population|security)\b", re.I),
    "colony": re.compile(r"\b(colon(y|ies|is\w*)|construction|build(ing)? site|still needs?|what('s| is) (still )?needed)\b",
                         re.I),
    "powerplay": re.compile(r"\b(power ?play|merits?|pledged?|powers?)\b", re.I),
    "expedition": re.compile(r"\b(expeditions?|trip|journey)\b", re.I),
    "galnet": re.compile(r"\b(galnet|news|headlines?|happening out there)\b", re.I),
    "music": re.compile(r"\b(music|song|track|tune|what('s| is) playing|now playing)\b", re.I),
    # What could live on a world: Survey's own predictions, from your scans.
    "life": re.compile(r"\b(could live|lives? (here|there|on)|life (here|there|on)|living (here|there|on)|bio(logy|logicals?)|"
                       r"organics?|species|genus|genera|flora|exobio\w*|"
                       r"bacteri\w*|fungoid\w*|tussocks?|stratum|osseus|frutex\w*|fonticulua|concha|tubus|aleoida|"
                       r"clypeus|cactoida|electricae|recepta)\b", re.I),
}
LOOKUP_LIMIT = 14
CARGO_KINDS = 8
# "What's in the ship's hold?" is about the hold, not the ship.
_SHIP_ITSELF = re.compile(r"\b(fuel|tank|hull|jump range|credits|money|balance)\b", re.I)
SCALE = {"B": "billion", "M": "million", "K": "thousand"}


def topics_for(question):
    """The systems a question asks about, in a fixed order."""
    text = str(question or "")
    found = [name for name, pattern in TOPICS.items() if pattern.search(text)]
    if "cargo" in found and "ship" in found and not _SHIP_ITSELF.search(text):
        found.remove("ship")
    return found


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


def _journal_name(row):
    """A journal name as the game shows it: its localised name, or the symbol
    made readable ("$Gold_Name;" is Gold)."""
    name = str(row.get("Name_Localised") or row.get("Name") or "").strip()
    if name.startswith("$"):
        name = name[1:]
    if name.casefold().endswith("_name;"):
        name = name[:-len("_name;")]
    name = name.strip(";").replace("_", " ").strip()
    return name.title() if name == name.lower() else name


def cargo_lines(rows, capacity=0, hold="Ship", limit=CARGO_KINDS):
    """What's in the hold (5.7.2): each kind by name with its tonnes, most first."""
    kinds = {}
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        name = _journal_name(row)
        count = _whole(row.get("Count", row.get("count"))) or 0
        if not name or count <= 0:
            continue
        kind = kinds.setdefault(name, {"count": 0, "stolen": 0, "mission": 0})
        kind["count"] += count
        kind["stolen"] += _whole(row.get("Stolen")) or 0
        kind["mission"] += count if row.get("MissionID") else 0
    capacity = _whole(capacity) or 0
    where = "The SRV's hold" if str(hold).casefold() == "srv" else "The ship's hold"
    if not kinds:
        return [f"{where} is empty" + (f", {capacity} tonnes free" if capacity else "")]
    tons = sum(kind["count"] for kind in kinds.values())
    # "60 of 64 tonnes" came back as "60 tonnes of space": carried and free, said apart.
    free = max(0, capacity - tons)
    lines = [f"{where} carries {tons} tonne{'' if tons == 1 else 's'}"
             + (f", with {free} tonne{'' if free == 1 else 's'} free" if capacity else "")]
    ordered = sorted(kinds.items(), key=lambda item: (-item[1]["count"], item[0]))
    for name, kind in ordered[:limit]:
        notes = [note for note, on in (("stolen", kind["stolen"]), ("for a mission", kind["mission"])) if on]
        lines.append(f"{name}: {kind['count']} tonne{'' if kind['count'] == 1 else 's'}"
                     + (f" ({', '.join(notes)})" if notes else ""))
    if len(ordered) > limit:
        lines.append(f"And {len(ordered) - limit} other kinds of cargo")
    return lines


STATION_KINDS = {
    "coriolis": "Coriolis starport", "orbis": "Orbis starport", "ocellus": "Ocellus starport",
    "bernal": "Ocellus starport", "dodec": "Dodec starport", "outpost": "outpost", "asteroidbase": "asteroid base",
    "megaship": "megaship", "fleetcarrier": "fleet carrier", "craterport": "planetary port",
    "crateroutpost": "planetary outpost", "surfacestation": "planetary port", "onfootsettlement": "settlement",
    "planetaryconstructiondepot": "planetary construction site", "spaceconstructiondepot": "orbital construction site",
}
# The services worth saying, by the game's own names for them.
STATION_SERVICES = (
    ("shipyard", "shipyard"), ("outfitting", "outfitting"), ("commodities", "market"), ("blackmarket", "black market"),
    ("materialtrader", "material trader"), ("techbroker", "technology broker"), ("facilitator", "interstellar factors"),
    ("exploration", "Universal Cartographics"), ("vistagenomics", "Vista Genomics"), ("refuel", "refuel"),
    ("repair", "repair"), ("rearm", "rearm"), ("engineer", "an engineer"), ("pioneersupplies", "Pioneer Supplies"),
    ("frontlinesolutions", "Frontline Solutions"), ("bartender", "a bar"),
)


def _game_word(value):
    """"$economy_HighTech;" as High Tech; already readable text as it is."""
    text = str(value or "").strip()
    match = re.match(r"^\$\w+?_(\w+);$", text)
    if match:
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", match.group(1))
    return "" if text.casefold() in {"none", "$none;"} else text


def station_lines(name, kind="", system="", faction="", faction_state="", government="", allegiance="", economy="",
                  services=(), pads=None, distance_ls=None):
    """The station you're docked at (5.7.2), as the game describes it on docking."""
    if not name:
        return ["Not docked at a station right now"]
    readable = STATION_KINDS.get(re.sub(r"[\s_]", "", str(kind or "")).casefold(), "")
    if not readable and kind:
        readable = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(kind)).lower()
    article = "an" if readable[:1].casefold() in ("a", "e", "i", "o", "u") else "a"
    lines = [f"Docked at {name}" + (f", {article} {readable}" if readable else "") + (f" in {system}" if system else "")]
    if faction:
        # "Run by Jaques (state: Boom)" came back as "Boom runs the shipyard".
        state = _game_word(faction_state)
        lines.append(f"The station belongs to the faction {faction}"
                     + (f", which is in the {state} state" if state else ""))
    about = [part for part in (_game_word(government) and f"{_game_word(government)} government",
                               _game_word(allegiance) and f"{_game_word(allegiance)} allegiance",
                               _game_word(economy) and f"{_game_word(economy)} economy") if part]
    if about:
        lines.append("Station: " + ", ".join(about))
    offered = {str(service).casefold() for service in services or ()}
    shown = [label for key, label in STATION_SERVICES if key in offered]
    if shown:
        lines.append("Services: " + ", ".join(shown))
    if isinstance(pads, dict):
        counts = [(size.lower(), _whole(pads.get(size)) or 0) for size in ("Large", "Medium", "Small")]
        sizes = [f"{count} {size}" for size, count in counts if count]
        if sizes:
            # With their total: it added 8, 4 and 4 up to twelve.
            lines.append(f"Landing pads: {sum(count for _size, count in counts)} in all ({', '.join(sizes)})")
    distance = _number(distance_ls)
    if distance:
        lines.append(f"Distance from the main star: {distance:,.0f} light seconds")
    return lines


def reputation_word(value):
    """The game's reputation bands, from the journal's -100 to 100."""
    number = _number(value)
    if number is None:
        return ""
    for limit, word in ((90, "allied"), (35, "friendly"), (4, "cordial"), (-35, "neutral"), (-90, "unfriendly")):
        if number >= limit:
            return word
    return "hostile"


def faction_lines(snap, system="", now=None, limit=7):
    """The system's factions (5.7.2), from the BGS reading taken on arrival."""
    if not snap:
        return [f"No faction readings for {system or 'this system'}: nobody lives here, or the journal hasn't said yet"]
    lines = []
    if snap.get("controlling"):
        lines.append(f"Controlling faction: {snap['controlling']}")
    about = [part for part in (snap.get("government") and f"{snap['government']} government",
                               snap.get("allegiance") and f"{snap['allegiance']} allegiance",
                               snap.get("economy") and f"{snap['economy']} economy",
                               snap.get("security") and f"{snap['security']} security") if part]
    population = _whole(snap.get("population"))
    if population:
        about.append(f"population {population:,}")
    if about:
        lines.append(f"{snap.get('system') or system}: " + ", ".join(about))
    factions = sorted((row for row in snap.get("factions") or () if isinstance(row, dict) and row.get("name")),
                      key=lambda row: -(_number(row.get("influence")) or 0))
    for row in factions[:limit]:
        # Whole percents: the model turned "55.3%" into "5.53 percent".
        share = (_number(row.get("influence")) or 0) * 100
        parts = [f"{round(share)}% influence" if share >= 1 else "under 1% influence"]
        state = _game_word(row.get("state"))
        if state:
            parts.append(f"state {state}")
        if row.get("government"):
            parts.append(str(row["government"]))
        standing = reputation_word(row.get("reputation"))
        if standing:
            parts.append(f"the commander is {standing} with them")
        if row.get("squadron"):
            parts.append("the commander's squadron faction")
        lines.append(f"{row['name']}: {', '.join(parts)}")
    if len(factions) > limit:
        lines.append(f"And {len(factions) - limit} smaller factions")
    for conflict in snap.get("conflicts") or ():
        sides = [side for side in conflict.get("sides") or () if side.get("name")]
        if len(sides) == 2:
            # "has won 2 days" was read as "2 days left": who leads, and by how much.
            first, second = sorted(sides, key=lambda side: -int(side.get("won_days") or 0))
            won = (int(first.get("won_days") or 0), int(second.get("won_days") or 0))
            score = (f"{first['name']} leads {second['name']} {won[0]} to {won[1]} in days won" if won[0] != won[1]
                     else f"{first['name']} and {second['name']} are level at {won[0]} days won each")
            lines.append(f"{(conflict.get('type') or 'conflict').title()} ({conflict.get('status') or 'active'}): {score}")
    taken = _number(snap.get("ts"))
    if taken and now is not None and now - taken > 36 * 3600:
        lines.append(f"These readings are {int((now - taken) // 86400)} days old")
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


# "Remember that my carrier is the Black Rose" (5.7.2): kept as you said it,
# like TEACH IT. "Remember when we…?" is a question, not a request.
_REMEMBER = re.compile(_PLEASE + r"(?:remember|don'?t forget|make a note|note down|keep in mind)"
                                 r"(?:\s+(?:that|this))?[\s:,]+(.+)$", re.I)
_RECALLING = re.compile(r"^(when|what|where|who|how|the time|us|me)\b", re.I)


def remember_request(text):
    """What you asked it to remember, or None."""
    words = " ".join(str(text or "").split()).strip()
    if not words or words.endswith("?"):
        return None
    match = _REMEMBER.match(words)
    fact = match.group(1).strip(" .!") if match else ""
    if not fact or _RECALLING.match(fact):
        return None
    return fact[:1].upper() + fact[1:] + "."


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
    "remember": ("I'll remember that.", "Kept. It's in my library now.", "Noted. I won't forget."),
    "remember_known": ("I know that already.", "You told me. I kept it."),
    "remember_refused": ("Not that. Some things I don't keep.",),
    "remember_long": ("That's too much to keep in one go. Say it shorter.",),
}


def reply(outcome, rng, **fields):
    lines = REPLIES.get(outcome) or REPLIES["unavailable"]
    line = rng.choice(lines) if rng is not None else lines[0]
    try:
        return line.format(**fields)
    except (KeyError, IndexError, ValueError):
        return REPLIES["unavailable"][0]
