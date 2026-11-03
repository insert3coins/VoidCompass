"""The Watcher as co-pilot: what the ship's systems
show when you ask it something, and the few small things it will do when
asked.

Only the app's own numbers go in: the route, the survey, the ship, the
hold, the station you're docked at, the system's factions, the planet's
materials and your mining sites, your materials, your Codex, your missions,
ranks, carrier, unsold data, the world you're at and your lifetime record,
the colony needs, Powerplay, the expedition, Galnet, the music. Each line is
plain fact to answer from. The actions here handle the music, the overlays,
the clipboard and its voice; ship controls have their own command catalogue.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

# What a question is about: the systems asked, by the words in it. Narrow on
# purpose (5.7.2): "how's it going" brought the route, "are you alive" the
# exobiology readout and "what do you need" the colony, and it recited them.
TOPICS = {
    "route": re.compile(r"\b(route|next (system|jump|stop|star)|destination|how far|plotted|waypoints?|hops?|neutron|"
                        r"jumps? (left|to go|remaining)|where are we (going|headed|heading)|heading (to|for))\b",
                        re.I),
    "survey": re.compile(r"\b(survey|scan(ned|s)?|bod(y|ies)|fss|honk|bio(logy|logicals?)?|signals?|planets?|worlds?|"
                         r"undiscovered|first discover\w*|valuable)\b", re.I),
    "ship": re.compile(r"\b((our|my|the|this) ship|ship'?s (state|condition|health)|fuel|tank|hull|jump range|credits|"
                       r"money|balance|rebuy|insurance|wanted|legal|clean)\b", re.I),
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
    # The planet's materials, its ground and your saved mining sites (the
    # journal logs no ground sites: these are the ones you saved, and rigs).
    "planet": re.compile(r"\b(mining sites?|saved sites?|deposits?|rigs?|rhino|drill\w*|ground mining|surface mining|"
                         r"ores?|minerals?|planet(ary)? materials?|in the ground|ground (here|holds?|tends))\b", re.I),
    # Your missions: where each goes, what it pays and when it runs out.
    "missions": re.compile(r"\b(missions?|contracts?|deliver(y|ies)?|passengers?|massacre|courier)\b", re.I),
    # Your ranks and their progress, the navies and the superpowers.
    "ranks": re.compile(r"\b(ranks?|rating|promot\w*|navy|imperial|federal|empire|federation|alliance|superpowers?)\b",
                        re.I),
    # Your fleet carrier.
    "carrier": re.compile(r"\b((fleet |our |my |the )?carrier'?s?|callsign)\b", re.I),
    # The exploration and exobiology data you haven't sold yet.
    "data": re.compile(r"\b(unsold|cartographic|(exploration|exobiology|biology|bio|organic|scan) data|data (we|to sell|worth|"
                       r"value)|sell (the |our )?(data|samples)|universal cartographics)\b", re.I),
    # The world you're at (or name): what it is, its gravity, heat and air.
    "world": re.compile(r"\b(gravity|temperature|how (hot|cold)|atmosphere|landable|can (we|i) land|terraform\w*|volcanism|"
                        r"radius|how big|day (length|lasts?)|rotation|tidally locked|(planet|world|moon|star) like|"
                        r"what kind of (planet|world|moon|body|star)|tell me about (this|the|that) (planet|world|moon|body|star))\b",
                        re.I),
    # Your lifetime record, from the game's own Statistics.
    "record": re.compile(r"\b(statistics|stats|career|lifetime|all time|in total|total (jumps|distance)|"
                         r"how many jumps (have|did|in total)|"
                         r"how far have (we|i)|time played|how long have (we|i)|systems (we('ve| have)|i('ve| have)) visited|"
                         r"how many systems)\b", re.I),
    # Commodity prices: the market you're at (or last opened), the galactic
    # averages and the best prices anywhere.
    "market": re.compile(r"\b(prices?|market|commodit\w*|cheapest|most expensive|good to (sell|buy)|best (to sell|to buy|price)|"
                         r"where (can|do|should) (i|we) (sell|buy)|sells? for|buy (it )?for|costs?)\b", re.I),
    # Your Codex (biology): what you've logged, here and for a species you name.
    "codex": re.compile(r"\b(codex|colou?r variants?|variants?|missing colou?rs?|colou?rs? (we|i) (have|need|haven'?t)|"
                        r"logged)\b", re.I),
    # Your engineering materials: raw, manufactured, encoded.
    "materials": re.compile(r"\b(materials?|mats|raw|manufactured|encoded)\b", re.I),
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
# Materials somewhere ("on this planet", "here") are the planet's, not your stock.
_SOMEWHERE = re.compile(r"\b(planet\w*|worlds?|moons?|bod(y|ies)|here|ground|surface|sites?|rhino|crust)\b", re.I)
# A species named in a Codex question is about the Codex, unless it's about here.
_HERE_LIFE = re.compile(r"\b(here|could live|this (planet|world|moon|body)|on (it|this))\b", re.I)
# What still makes a planet question a survey question too.
_SURVEYING = re.compile(r"\b(survey|scan(ned|s)?|fss|honk|signals?|undiscovered|first discover\w*|valuable|bio\w*)\b", re.I)
SCALE = {"B": "billion", "M": "million", "K": "thousand"}


def topics_for(question):
    """The systems a question asks about, in a fixed order."""
    text = str(question or "")
    found = {name for name, pattern in TOPICS.items() if pattern.search(text)}
    if "cargo" in found and "ship" in found and not _SHIP_ITSELF.search(text):
        found.discard("ship")
    if "materials" in found and _SOMEWHERE.search(text):
        found.discard("materials")
        found.add("planet")
    if "planet" in found and "survey" in found and not _SURVEYING.search(text):
        found.discard("survey")
    if "world" in found and "survey" in found and not _SURVEYING.search(text):
        found.discard("survey")
    # "Reputation with the Federation" is the superpower, not a faction.
    if "ranks" in found and "factions" in found and re.search(r"\b(empire|federation|alliance|navy|superpowers?)\b", text, re.I):
        found.discard("factions")
    # "Sell our data" is the data; "the value of my cargo" the hold.
    if "market" in found and "data" in found:
        found.discard("market")
    if "codex" in found:
        if not _HERE_LIFE.search(text):
            found.discard("life")
        if not re.search(r"\b(scan(ned|s)?|fss|honk|signals?|undiscovered)\b", text, re.I):
            found.discard("survey")
    return [name for name in TOPICS if name in found]


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
               hull_percent=None, rebuy=None, legal=""):
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
        # Expand the deck's abbreviated credits for speech.
        spoken = re.sub(r"(\d)([BMK]) CR$", lambda m: f"{m.group(1)} {SCALE[m.group(2)]} credits", credits)
        lines.append(f"Credits: {spoken.replace(' CR', ' credits')}")
    if _whole(rebuy):
        lines.append(f"Rebuy (the insurance to replace the ship): {_whole(rebuy):,} credits")
    if legal:
        lines.append(f"Legal status: {LEGAL_STATES.get(str(legal), re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(legal)).lower())}")
    return lines


LEGAL_STATES = {
    "Clean": "clean", "IllegalCargo": "carrying illegal cargo", "Speeding": "speeding", "Wanted": "wanted",
    "Hostile": "hostile (wanted, with a large bounty)", "PassengerWanted": "carrying a wanted passenger",
    "Warrant": "a warrant out for the commander", "Allied": "allied", "Thargoid": "flagged by Thargoid hostility",
}


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


# Asked what the cargo is worth: its value comes with it.
VALUE_ASKED = re.compile(r"\b(worth|value|valued|prices?|sell\w*|profit\w*|how much (is|are|will|would|can|could|do))\b",
                         re.I)


def cargo_value_lines(held, station="", here=None, averages=None, best=None, paid=None, limit=6):
    """What the cargo is worth (5.7.2): at the station you're docked at (its
    own market file), else at the galactic average prices the game lists;
    with the best price anywhere (when the Trading page has asked Spansh) and
    what you paid (from your trades)."""
    rows = [row for row in held or () if isinstance(row, dict) and (_whole(row.get("count")) or 0) > 0]
    if not rows:
        return []
    here, averages, best, paid = here or {}, averages or {}, best or {}, paid or {}
    docked = bool(station and here)
    prices = here if docked else averages
    total = sum(_whole(row["count"]) * prices[row["symbol"]] for row in rows if prices.get(row["symbol"]))
    if docked:
        lines = [f"The cargo would sell for {total:,} credits in all at {station}" if total
                 else f"{station} buys none of the cargo"]
    elif total:
        lines = [f"At the galactic average prices, the cargo is worth about {total:,} credits in all"]
    else:
        lines = ["No prices known for the cargo yet (open a commodity market to learn them)"]
    for row in rows[:limit]:
        key, count = row["symbol"], _whole(row["count"])
        parts = []
        if prices.get(key):
            parts.append(f"{count * prices[key]:,} credits {'here' if docked else 'at the galactic average'}, "
                         f"{prices[key]:,} a tonne")
        elif docked:
            parts.append(f"not bought at {station}")
        if docked and averages.get(key):
            parts.append(f"galactic average {averages[key]:,} a tonne")
        if best.get(key):
            parts.append(f"best price anywhere right now {_whole(best[key]):,} a tonne")
        if paid.get(key):
            parts.append(f"bought for about {_whole(paid[key]):,} a tonne")
        if _whole(row.get("stolen")):
            parts.append("stolen, so only a black market buys it")
        unit = "tonne" if count == 1 else "tonnes"
        lines.append(f"{row['name']}, {count} {unit}: " + (", ".join(parts) if parts else "no price known yet"))
    return lines


def market_lines(station, items, asked=(), docked=False, age_s=None, best=None, fetching=False, limit=4):
    """Commodity prices (5.7.2): the market you're docked at, or the last one
    you opened (the game's Market.json), with the galactic average it lists
    and the best prices anywhere (Spansh, when fetched). ``asked`` is the
    commodities you named, as (symbol, name); naming none, what sells well
    and what's cheap there."""
    items = [row for row in items or () if isinstance(row, dict) and row.get("name")]
    best = best or {}
    by_symbol = {row["symbol"]: row for row in items}
    lines = []
    if station and items:
        lines.append(f"Prices at {station}" + ("" if docked else ", the last market the commander opened"
                                                + (f" ({_ago(age_s)})" if age_s is not None else "")))
    elif not asked:
        lines.append("No market prices known yet: open a commodity market to learn them")
    for key, name in asked:
        row = by_symbol.get(key)
        if row:
            parts = []
            if row.get("sell") and (row.get("demand") or not row.get("buy")):
                parts.append(f"{station} buys it for {row['sell']:,} a tonne")
            if row.get("buy") and row.get("stock"):
                parts.append(f"{station} sells it for {row['buy']:,} a tonne ({row['stock']:,} in stock)")
            if row.get("mean"):
                parts.append(f"galactic average {row['mean']:,} a tonne")
            lines.append(f"{name}: " + (", ".join(parts) if parts else f"listed at {station}, but not traded right now"))
        elif station:
            lines.append(f"{name}: not traded at {station}")
        low, high = (best.get(name) or (None, None))
        if low or high:
            lines.append(f"{name}, best prices anywhere right now: " + ", ".join(part for part in (
                high and f"sells for up to {_whole(high):,} a tonne", low and f"can be bought from {_whole(low):,} a tonne")
                if part))
    if not asked and items:
        selling = sorted((row for row in items if row.get("sell") and row.get("demand") and row.get("mean")
                          and row["sell"] > row["mean"]), key=lambda row: -row["sell"] / row["mean"])[:limit]
        if selling:
            lines.append("Best to sell there (above the galactic average): " + ", ".join(
                f"{row['name']} {row['sell']:,} (average {row['mean']:,})" for row in selling))
        buying = sorted((row for row in items if row.get("buy") and row.get("stock") and row.get("mean")
                         and row["buy"] < row["mean"]), key=lambda row: row["buy"] / row["mean"])[:limit]
        if buying:
            lines.append("Cheapest to buy there (below the galactic average): " + ", ".join(
                f"{row['name']} {row['buy']:,} (average {row['mean']:,})" for row in buying))
    if fetching and asked:
        lines.append("Best prices anywhere are being fetched from Spansh: ask again in a moment")
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


def _percent(value):
    share = _number(value) or 0
    return f"{round(share)}%" if share >= 1 else "under 1%"


def _metres(value):
    distance = _number(value)
    if distance is None:
        return ""
    # In words: "300 m" came back as "30 meters".
    return f"{distance / 1000:.1f} kilometres" if distance >= 1000 else f"{round(distance)} metres"


def planet_lines(body, materials=(), forecast=(), ground="", sites=(), mining_locations=0, rigs=(), elsewhere=(),
                 system="", site_limit=5, focus="materials"):
    """A planet's materials, its ground and your mining sites on it (5.7.2).
    The journal logs no ground sites: these are the ones you saved, and the
    rigs you marked; what the ground tends to hold is the Rhino forecast."""
    if not body:
        lines = ["Not at or near a planet right now"]
        if elsewhere:
            lines.append(f"Saved mining sites in {system or 'this system'}: "
                         + ", ".join(f"{count} on {name}" for name, count in elsewhere))
        return lines
    lines = []
    # Asked where the sites are: the sites first, without the crust's makeup.
    shown = [] if focus == "sites" else [row for row in materials or () if isinstance(row, dict) and row.get("name")][:6]
    if shown:
        lines.append(f"Raw materials on {body}, from its scan: "
                     + ", ".join(f"{row['name']} {_percent(row.get('percent'))}" + (" (rare)" if row.get("rare") else "")
                                 for row in shown))
    if _whole(mining_locations) and focus != "sites":
        lines.append(f"Mining locations its scan found on {body}: {_whole(mining_locations)}")
    best = [row for row in forecast or () if isinstance(row, dict) and row.get("material")]
    if best:
        kind = f"{ground} ground" if ground else "Ground like this"
        lines.append(f"{kind} tends to hold: " + ", ".join(
            f"{row['material']} (at {round(_number(row.get('pct')) or 0)}% of sites like it"
            + (f", about {_whole(row.get('median')):,} credits a tonne" if _whole(row.get("median")) else "") + ")"
            for row in best))
    ordered = sorted(sites or (), key=lambda row: (_number(row.get("distance_m")) is None, _number(row.get("distance_m")) or 0))
    if ordered:
        lines.append(f"Your saved mining sites on {body}: {len(ordered)}")
        for row in ordered[:site_limit]:
            what = str(row.get("materials") or "").strip() or ("a drill marker" if row.get("site_type") == "drill" else "")
            # Name and distance first: it answered "where are the sites?" without either.
            where = f", {_metres(row.get('distance_m'))} from here" if _metres(row.get("distance_m")) else ""
            notes = []
            if row.get("density"):
                notes.append(f"{str(row['density']).lower()} density")
            if row.get("depleted") or row.get("amount") == "Depleted":
                notes.append("depleted")
            elif row.get("amount"):
                notes.append(f"{str(row['amount']).lower()} amount left")
            tons = str(row.get("tons_left") or "")
            if tons and tons != "Depleted":
                notes.append(tons.replace("Estimated ", "about ").replace(" t left", " tonnes left").replace("–", " to "))
            lines.append(f"Saved site {row.get('name') or 'without a name'}{where}: {what}"
                         + (f" ({', '.join(notes)})" if notes else ""))
        if len(ordered) > site_limit:
            lines.append(f"And {len(ordered) - site_limit} more saved sites on {body}")
    else:
        lines.append(f"No saved mining sites on {body}")
    marked = sorted(int(slot) for slot in rigs or ())
    if marked:
        # Not sites: "we have saved two rigs here".
        # "rigs 1, 3" was read as three rigs.
        numbered = " and ".join(f"rig {slot}" for slot in marked)
        lines.append(f"Rigs you marked as deployed here (not sites): {len(marked)} rig{'' if len(marked) == 1 else 's'}, "
                     f"{numbered}")
    if elsewhere:
        lines.append("Saved mining sites elsewhere in the system: " + ", ".join(f"{count} on {name}" for name, count in elsewhere))
    return lines


def _when(value):
    """A journal time ("2026-01-31T00:34:48Z") or a number, as seconds; 0 if neither."""
    number = _number(value)
    if number is not None:
        return number
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _ago(seconds):
    days = int(max(0, seconds) // 86400)
    if days < 1:
        return "today"
    if days < 2:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


def codex_lines(rows, reference, region=None, region_name="", question="", here=(), now=None, latest=4):
    """Your Codex (5.7.2): the biology you've logged (the index the Survey
    flags use), named from Canonn's reference; for a species you name, the
    colours logged and still to log; what you logged on this body."""
    reference = reference or {}
    logged = {}
    for row in rows or ():
        if len(row) < 3 or not str(row[1]).startswith("$Codex_Ent_"):
            continue
        name, category = reference.get(row[1], ("", ""))
        if category and category != "Biology":
            continue
        info = logged.setdefault(row[1], {"first": _when(row[0]), "regions": set(), "name": name})
        info["first"] = min(info["first"], _when(row[0]))
        info["regions"].add(row[2])
    if not logged:
        return ["No biology logged in the Codex yet"]

    def species(entry):
        return logged[entry]["name"].partition(" - ")[0] or entry

    named = {entry: info for entry, info in logged.items() if info["name"]}
    kinds = {species(entry) for entry in named}
    regions = {region_id for info in logged.values() for region_id in info["regions"] if region_id is not None}
    # "in 26 regions" became "26 regions of the Inner Orion Spur": galactic regions, said so.
    lines = [f"Biology logged in the commander's Codex: {len(kinds)} species ({len(logged)} colours in all), "
             f"across {len(regions)} different galactic region{'' if len(regions) == 1 else 's'}"]
    if region is not None:
        count = sum(1 for info in logged.values() if region in info["regions"])
        lines.append(f"Logged in {region_name or 'this region'}: {count} colour{'' if count == 1 else 's'}")
    words = f" {str(question or '').casefold()} "
    every = {}
    for entry, (name, category) in reference.items():
        if category == "Biology" and " - " in name:
            kind, _separator, colour = name.partition(" - ")
            every.setdefault(kind, {})[colour] = entry
    asked = sorted((kind for kind in every if f" {kind.casefold()}" in words), key=len, reverse=True)[:2]
    for kind in asked:
        colours = every[kind]
        have = sorted(colour for colour, entry in colours.items() if entry in logged)
        missing = sorted(colour for colour, entry in colours.items() if entry not in logged)
        lines.append(f"{kind}: {len(have)} of {len(colours)} colours logged" + (f" ({', '.join(have)})" if have else ""))
        if missing:
            # With their count: it said "ten remain", a number it wasn't given.
            lines.append(f"{kind} colours not logged yet ({len(missing)}): {', '.join(missing)}")
        if region is not None and have:
            in_region = any(region in logged[colours[colour]]["regions"] for colour in have)
            lines.append(f"{kind} {'is' if in_region else 'is not yet'} logged in {region_name or 'this region'}")
    if here:
        lines.append("Logged on this body: " + ", ".join(reference.get(entry, (entry, ""))[0] or entry for entry in here))
    if now is not None and not asked:
        newest = sorted(named.items(), key=lambda item: -item[1]["first"])[:latest]
        if newest:
            lines.append("Most recently logged: " + ", ".join(f"{info['name']} ({_ago(now - info['first'])})"
                                                              for _entry, info in newest))
    return lines


def _hours_left(expiry, now):
    left = _when(expiry) - now if expiry else None
    if left is None or not _when(expiry):
        return ""
    if left <= 0:
        return "expired"
    hours = left / 3600
    if hours < 1:
        return f"{max(1, round(left / 60))} minutes left"
    if hours < 48:
        return f"{round(hours)} hours left"
    return f"{round(hours / 24)} days left"


def missions_lines(missions, now, limit=6):
    """Your active missions (5.7.2): where each goes, what it pays and the time
    left, the soonest to run out first."""
    rows = [row for row in missions or () if isinstance(row, dict)]
    if not rows:
        return ["No active missions"]
    total = sum(_whole(row.get("reward")) or 0 for row in rows)
    lines = [f"Active missions: {len(rows)}" + (f", paying {total:,} credits in all" if total else "")]
    rows.sort(key=lambda row: _when(row.get("expiry")) or float("inf"))
    for row in rows[:limit]:
        where = ", ".join(str(part) for part in (row.get("destination_station") or row.get("destination_settlement"),
                                                 row.get("destination_system")) if part)
        parts = [f"to {where}" if where else ""]
        if row.get("commodity") and _whole(row.get("count")):
            parts.append(f"{_whole(row['count'])} tonnes of {row['commodity']}")
        if row.get("target") and _whole(row.get("kill_count")):
            parts.append(f"{_whole(row['kill_count'])} kills of {row['target']}")
        if _whole(row.get("reward")):
            parts.append(f"pays {_whole(row['reward']):,} credits")
        left = _hours_left(row.get("expiry"), now)
        if left:
            parts.append(left)
        if row.get("illegal"):
            parts.append("illegal")
        name = str(row.get("name") or "A mission").strip()
        lines.append(f"{name}: " + ", ".join(part for part in parts if part))
    if len(rows) > limit:
        lines.append(f"And {len(rows) - limit} more missions")
    return lines


RANK_KINDS = (("Combat", "Combat"), ("Trade", "Trade"), ("Explore", "Exploration"), ("Exobiologist", "Exobiology"),
              ("Soldier", "Mercenary"), ("CQC", "CQC"), ("Empire", "Imperial Navy"), ("Federation", "Federal Navy"))


def ranks_lines(ranks, progress=None, reputation=None, names=None):
    """Your ranks with their progress to the next, and how the superpowers see
    you (5.7.2). ``names(kind, number)`` is the rank's name (core.ranks.name)."""
    ranks, progress, reputation = ranks or {}, progress or {}, reputation or {}
    lines = []
    for key, label in RANK_KINDS:
        number = _whole(ranks.get(key))
        title = names(key, number) if callable(names) and number is not None else ""
        if not title or title == "None":
            continue
        share = _whole(progress.get(key))
        lines.append(f"{label}: {title}" + (f", {share}% of the way to the next rank" if share else ""))
    standing = [f"{power} {reputation_word(reputation.get(power))}" for power in ("Federation", "Empire", "Alliance", "Independent")
                if reputation_word(reputation.get(power))]
    if standing:
        lines.append("Superpower reputation: " + ", ".join(standing))
    return lines or ["No ranks on record yet (the journal lists them when the game starts)"]


def carrier_lines(carrier, now=None):
    """Your fleet carrier (5.7.2), as its tracker has it."""
    carrier = carrier or {}
    if not carrier.get("carrier_id") and not carrier.get("name") and not carrier.get("callsign"):
        return ["No fleet carrier on record"]
    name = str(carrier.get("name") or "").strip()
    callsign = str(carrier.get("callsign") or "").strip()
    title = f"{name} ({callsign})" if name and callsign else name or callsign
    lines = [f"The carrier {title}" + (f" is in {carrier['system']}" if carrier.get("system") else "")]
    status = str(carrier.get("status") or "")
    if status == "jumping" and carrier.get("jump_destination"):
        when = _hours_left(carrier.get("jump_departure_time"), now) if now is not None else ""
        lines.append(f"Jumping to {carrier['jump_destination']}" + (f", departing with {when}" if when and when != "expired" else ""))
    elif status.startswith("cooldown"):
        lines.append("Its frame shift drive is cooling down after a jump")
    fuel = _whole(carrier.get("fuel_level"))
    if fuel is not None:
        lines.append(f"Tritium in its tank: {fuel} of {_whole(carrier.get('fuel_capacity')) or 1000} tonnes"
                     + (" (estimated)" if carrier.get("fuel_level_estimated") else ""))
    balance = _whole(carrier.get("balance"))
    if balance is not None:
        available = _whole(carrier.get("available_balance"))
        lines.append(f"Its balance: {balance:,} credits" + (f", {available:,} available" if available is not None else ""))
    if carrier.get("docking_access"):
        access = {"all": "everyone", "none": "no one", "friends": "friends only", "squadron": "the squadron only",
                  "squadronfriends": "the squadron and friends"}.get(str(carrier["docking_access"]).casefold(),
                                                                     str(carrier["docking_access"]))
        lines.append(f"Docking open to {access}" + (", notorious commanders too" if carrier.get("allow_notorious") else ""))
    free = _whole(carrier.get("space_free"))
    if free is not None:
        lines.append(f"Free space: {free:,} tonnes")
    if carrier.get("pending_decom"):
        lines.append("It is set to be decommissioned")
    return lines


def data_lines(exploration=0, biology=0):
    """The data you're carrying and haven't sold (5.7.2): lost if the ship is."""
    exploration, biology = _whole(exploration) or 0, _whole(biology) or 0
    if not exploration and not biology:
        return ["No unsold exploration or exobiology data"]
    lines = []
    if exploration:
        lines.append(f"Unsold exploration data: about {exploration:,} credits (sold at Universal Cartographics)")
    if biology:
        lines.append(f"Unsold exobiology samples: about {biology:,} credits (sold at Vista Genomics)")
    if exploration and biology:
        lines.append(f"Together about {exploration + biology:,} credits, lost if the ship is destroyed")
    return lines


WORLD_DETAIL = re.compile(r"\b(big|size|radius|day|rotation|spin|tidal\w*|ring\w*)\b", re.I)


def world_lines(item, question=""):
    """The world you're at or name (5.7.2), from its scan."""
    if not item:
        return ["No scanned world here to describe"]
    name = str(item.get("full_name") or item.get("name") or "This world")
    if item.get("is_star") or item.get("star_type"):
        star = str(item.get("star_type") or "")
        kind = ("a neutron star" if star == "N" else "a black hole" if star in ("H", "SupermassiveBlackHole")
                else "a white dwarf" if star.startswith("D") else f"a star of class {star}" if star else "a star")
        lines = [f"{name}: {kind}"]
    else:
        kind = str(item.get("planet_class") or item.get("class") or "world")
        if item.get("terraformable"):
            kind = f"terraformable {kind}"
        lines = [f"{name}: {'an' if kind[:1].casefold() in 'aeiou' else 'a'} {kind}"
                 + (", landable" if item.get("landable") else ", not landable" if item.get("landable") is False else "")]
        gravity = _number(item.get("gravity_g"))
        if gravity:
            lines.append(f"Gravity: {gravity:.2f} g" + (" (heavy)" if gravity > 2 else ""))
        temperature = _number(item.get("surface_temp"))
        if temperature:
            lines.append(f"Surface temperature: {round(temperature - 273.15)} degrees Celsius")
        air = str(item.get("atmosphere_type") or item.get("atmosphere") or "").strip()
        lines.append(f"Atmosphere: {air}" if air and air.casefold() not in {"none", "no atmosphere"} else "No atmosphere")
        volcanism = str(item.get("volcanism") or "").strip()
        if volcanism and volcanism.casefold() != "no volcanism":
            lines.append(f"Volcanism: {volcanism}")
    distance = _number(item.get("distance_to_arrival"))
    if distance:
        lines.append(f"Distance from the arrival star: {distance:,.0f} light seconds")
    if WORLD_DETAIL.search(str(question or "")):
        radius = _number(item.get("radius"))
        if radius:
            lines.append(f"Radius: {radius / 1000:,.0f} kilometres")
        rotation = _number(item.get("rotation_period"))
        if rotation:
            lines.append(f"One rotation takes {abs(rotation) / 86400:.1f} days"
                         + (" (tidally locked)" if item.get("tidal_lock") else ""))
        if item.get("rings"):
            lines.append("It has rings")
    scanned, mapped = _whole(item.get("reward")), _whole(item.get("dss_reward"))
    if scanned or mapped:
        lines.append("Worth about " + " and ".join(part for part in (
            scanned and f"{scanned:,} credits scanned", mapped and f"{mapped:,} credits mapped") if part))
    firsts = [label for label, first in (("discover it", item.get("was_discovered") is False),
                                         ("map it", item.get("was_mapped") is False and not item.get("is_star")),
                                         ("set foot on it", item.get("first_footfall"))) if first]
    if firsts:
        lines.append("The commander was the first to " + " and ".join(firsts))
    return lines


# The parts of your record, by what you ask; asked nothing in particular, a little of each.
RECORD = (
    (re.compile(r"\b(jumps?|distance|travel\w*|far|visited|systems|explor\w*|scan\w*|time|played|hours|long)\b", re.I),
     "Exploration", (("Time_Played", "time played", "hours"), ("Systems_Visited", "systems visited", ""),
                     ("Total_Hyperspace_Jumps", "hyperspace jumps", ""),
                     ("Total_Hyperspace_Distance", "light years jumped", ""),
                     ("Greatest_Distance_From_Start", "farthest from the starting system, in light years", ""),
                     ("Planets_Scanned_To_Level_3", "bodies scanned in detail", ""),
                     ("Exploration_Profits", "earned from exploration", "credits"))),
    (re.compile(r"\b(bio\w*|organic\w*|species|genus|genera|exobio\w*)\b", re.I),
     "Exobiology", (("Organic_Species_Encountered", "species encountered", ""),
                    ("Organic_Genus_Encountered", "genera encountered", ""), ("First_Logged", "first logged", ""),
                    ("Organic_Data_Profits", "earned from exobiology", "credits"))),
    (re.compile(r"\b(combat|bount\w*|kills?|fight\w*|bonds?)\b", re.I),
     "Combat", (("Bounties_Claimed", "bounties claimed", ""), ("Bounty_Hunting_Profit", "earned from bounties", "credits"),
                ("Combat_Bonds", "combat bonds", ""), ("Combat_Bond_Profits", "earned from combat bonds", "credits"))),
    (re.compile(r"\b(trad\w*|market\w*)\b", re.I),
     "Trading", (("Markets_Traded_With", "markets traded with", ""), ("Market_Profits", "earned from trade", "credits"),
                 ("Resources_Traded", "tonnes traded", ""))),
    (re.compile(r"\b(min(ing|ed)|ores?)\b", re.I),
     "Mining", (("Mining_Profits", "earned from mining", "credits"), ("Quantity_Mined", "tonnes mined", ""))),
    (re.compile(r"\b(wealth|worth|rich|insurance|died|deaths?|destroyed|lost)\b", re.I),
     "Bank_Account", (("Current_Wealth", "current wealth", "credits"), ("Insurance_Claims", "insurance claims (ships lost)", ""),
                      ("Spent_On_Insurance", "spent on insurance", "credits"))),
)
RECORD_EVERYDAY = (("Exploration", "Time_Played", "time played", "hours"), ("Exploration", "Systems_Visited", "systems visited", ""),
                   ("Exploration", "Total_Hyperspace_Jumps", "hyperspace jumps", ""),
                   ("Exploration", "Total_Hyperspace_Distance", "light years jumped", ""),
                   ("Bank_Account", "Current_Wealth", "current wealth", "credits"))


def record_lines(statistics, question=""):
    """Your lifetime record (5.7.2), from the game's own Statistics."""
    statistics = statistics or {}
    if not isinstance(statistics, dict) or not statistics:
        return ["No lifetime record yet (the game sends it when it starts)"]

    def line(section, key, label, unit):
        value = _number((statistics.get(section) or {}).get(key))
        if value is None:
            return None
        if unit == "hours":
            return f"Lifetime {label}: {round(value / 3600):,} hours"
        return f"Lifetime {label}: {round(value):,}" + (" credits" if unit == "credits" else "")

    text = str(question or "")
    chosen = [(section, key, label, unit) for pattern, section, rows in RECORD if pattern.search(text)
              for key, label, unit in rows]
    lines = [found for found in (line(*row) for row in chosen or RECORD_EVERYDAY) if found]
    return lines[:10] or ["No lifetime record yet (the game sends it when it starts)"]


def materials_lines(inventory, question="", top=5):
    """Your engineering materials (5.7.2): the ones you named, else each kind's
    total and the most plentiful raw ones."""
    inventory = inventory or {}
    kinds = (("raw", "Raw"), ("manufactured", "Manufactured"), ("encoded", "Encoded"))
    rows = {key: [entry for entry in (inventory.get(key) or {}).values()
                  if isinstance(entry, dict) and entry.get("name") and (_whole(entry.get("count")) or 0) > 0]
            for key, _label in kinds}
    if not any(rows.values()):
        return ["No engineering materials on record yet (the journal lists them when the game starts)"]
    words = f" {str(question or '').casefold()} "
    named = [(label, entry) for key, label in kinds for entry in rows[key] if f" {str(entry['name']).casefold()}" in words]
    if named:
        return [f"{entry['name']}: {_whole(entry['count'])} ({label.lower()})" for label, entry in named[:10]]
    asked = [key for key, label in kinds if label.casefold() in words]
    lines = [f"{label} materials: {sum(_whole(entry['count']) for entry in rows[key]):,} in all, "
             f"{len(rows[key])} kind{'' if len(rows[key]) == 1 else 's'}"
             for key, label in kinds if rows[key] and (not asked or key in asked)]
    for key, label in kinds:
        if asked and key not in asked or not asked and key != "raw":
            continue
        most = sorted(rows[key], key=lambda entry: (-_whole(entry["count"]), str(entry["name"])))[:top]
        if most:
            lines.append(f"Most plentiful {label.lower()}: " + ", ".join(f"{entry['name']} {_whole(entry['count'])}" for entry in most))
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


# The uplink (5.7.3): asked where to sell or buy a commodity, or to look it up
# online, it asks Spansh's market data (the Trading page's own search) and
# answers when the reply comes. Nothing else of yours goes online.
_UPLINK = re.compile(r"\b(look\s*(it|that|them)?\s*up|online|internet|uplink|spansh|"
                     r"where (can|do|should|could|would) (i|we) (sell|buy|get|find|offload)|"
                     r"best (place|station|market|price)s? (to|for) (sell|buy)|who (buys|sells|pays)|"
                     r"search (spansh|online|the uplink|for (the )?(best|cheapest|nearest)))\b", re.I)
# Asked to look something up, with nothing to look up: what the uplink reaches.
_ONLINE = re.compile(r"\b(look\s*(it|that|them)?\s*up|online|internet|uplink|spansh)\b", re.I)
_TO_BUY = re.compile(r"\b(who sells|(i|we) (buy|get|find|purchase)|to buy|cheapest|buy (it|some|more|from))\b", re.I)


def uplink_request(text, commodities):
    """{"kind": "sell" | "buy", "commodity"} for a question the uplink answers;
    {"kind": None} asked online for nothing it can look up; else None."""
    words = " ".join(str(text or "").split())
    if not _UPLINK.search(words):
        return None
    if not commodities:
        return {"kind": None, "commodity": ""} if _ONLINE.search(words) else None
    return {"kind": "buy" if _TO_BUY.search(words) else "sell", "commodity": str(commodities[0][1])}


PADS = {"L": "large", "M": "medium", "S": "small"}


def uplink_sell_results(rows, now=None):
    """Two distinct buyers: reports within a day first, then the best price."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    unique = {}
    def report_time(row):
        updated = _number(row.get("updated")) or 0
        return updated if 0 < updated <= now else 0
    for row in rows or ():
        if not row:
            continue
        key = row.get("market_id") or (str(row.get("station") or "").casefold(), str(row.get("system") or "").casefold())
        updated = report_time(row)
        if key not in unique or updated > report_time(unique[key]):
            unique[key] = row
    def rank(row):
        updated = report_time(row)
        freshness = 0 if updated and now - updated <= 86400 else 1 if updated else 2
        return freshness, -(_number(row.get("price")) or 0), _number(row.get("distance")) or 0
    return sorted(unique.values(), key=rank)[:2]


def uplink_lines(kind, commodity, best=(), nearest=(), system="", radius=0, now=None, error=""):
    """Selling: two buyers, day-old-or-newer reports first. Buying: the best
    prices and nearest market. Each includes the station and its details."""
    if error:
        return [f"The uplink to Spansh failed: {error}"]
    best, nearest = [row for row in best or () if row], [row for row in nearest or () if row]
    if kind == "sell":
        now = datetime.now(timezone.utc).timestamp() if now is None else now
        best = uplink_sell_results([*best, *nearest], now)
        nearest = []
    station_does = "buys" if kind == "sell" else "sells"
    if not best and not nearest:
        return [f"Through the uplink: Spansh knows no station near {system or 'here'} that {station_does} {commodity}"]

    def describe(row):
        parts = [f"{_whole(row.get('price')) or 0:,} credits a tonne",
                 f"{'demand' if kind == 'sell' else 'stock'} {_whole(row.get('stock')) or 0:,}"]
        distance = _number(row.get("distance"))
        if distance:
            parts.append(f"{distance:,.1f} light years away")
        elif system and str(row.get("system") or "").casefold() == system.casefold():
            parts.append("in this system")
        if PADS.get(row.get("pad")):
            parts.append(f"{PADS[row['pad']]} pads")
        if row.get("carrier"):
            parts.append("a fleet carrier")
        elif row.get("planetary"):
            parts.append("on a planet")
        updated = _number(row.get("updated"))
        if now is not None and updated and now - updated >= 86400:
            days = int((now - updated) // 86400)
            parts.append(f"prices {days} {'day' if days == 1 else 'days'} old")
        elif kind == "sell":
            if not updated or updated > now:
                parts.append("price age unknown")
            elif now - updated < 3600:
                parts.append("prices less than an hour old")
            else:
                hours = int((now - updated) // 3600)
                parts.append(f"prices {hours} {'hour' if hours == 1 else 'hours'} old")
        return f"{row.get('station') or 'A station'} in {row.get('system') or 'an unknown system'}: " + ", ".join(parts)

    verb = "sell" if kind == "sell" else "buy"
    lines = []
    if best:
        if kind == "sell":
            lines.append(f"Through the uplink, places to sell {commodity} within {radius} light years, prices from the last 24 hours first: {describe(best[0])}")
        else:
            lines.append(f"Through the uplink, the best place to {verb} {commodity} within {radius} light years: {describe(best[0])}")
        if len(best) > 1:
            lines.append(f"{'Second result' if kind == 'sell' else 'Next best'}: {describe(best[1])}")
    def same(one, other):
        def key(row):
            return row.get("market_id") or (row.get("station"), row.get("system"))
        return key(one) == key(other)

    if nearest and (not best or not same(nearest[0], best[0])):
        lines.append(f"The nearest station that {station_does} {commodity}: {describe(nearest[0])}")
    return lines


# One overlay by name (5.7.3): hide or show it (as its hotkey does), or turn it
# off or on (as Overlay Studio does). What each is called aloud, longest
# first; "the HUD" alone stays all of them, as before.
OVERLAY_NAMES = {
    "navigation": ("navigation hud", "nav hud", "navigation overlay", "navigation"),
    "cargo": ("cargo manifest", "cargo overlay", "cargo"),
    "carrier": ("carrier hud", "carrier overlay", "fleet carrier hud", "carrier"),
    "prospector": ("prospector analysis", "prospector overlay", "prospector"),
    "planet-materials": ("planet materials overlay", "planet materials"),
    "powerplay": ("powerplay overlay", "power play", "powerplay"),
    "gravity": ("gravity warning", "gravity overlay", "gravity"),
    "station": ("station information", "station info", "station overlay"),
    "survey": ("survey operations", "survey overlay", "survey"),
    "toast": ("cockpit notifications", "notifications", "toasts"),
    "achievements": ("achievements overlay", "achievements"),
    "galnet-ticker": ("galnet ticker", "news ticker", "ticker", "galnet"),
    "music-player": ("music player", "music overlay", "player"),
    "heartbeat": ("journal heartbeat", "your orb", "the orb", "orb", "yourself", "heartbeat"),
    "contact-scope": ("deep space contact scope", "contact scope", "contacts"),
    "jump-info": ("jump information", "jump info"),
    "colony-needs": ("construction needs", "colony needs"),
    "expedition": ("expedition guide", "expedition overlay", "expedition"),
    "hatchling": ("hatchling", "pet"),
    "trade-route": ("trade route overlay", "trade route"),
    "galaxy-minimap": ("galaxy minimap", "minimap", "mini map"),
    "rhino-map": ("rhino map",),
    "postcards": ("postcards", "postcard"),
    "rig-tracker": ("rig tracker", "rigs"),
    "ground-target": ("planet waypoint navigation", "planet waypoint", "waypoint navigation"),
}
# How each is said in a reply.
OVERLAY_SPOKEN = {"heartbeat": "my orb", "carrier": "the carrier HUD", "toast": "notifications",
                  "ground-target": "planet waypoint navigation", "navigation": "the Navigation HUD"}
_OVERLAY_VERBS = (
    ("off", r"(?:turn|switch|shut)\s+off|disable"),
    ("on", r"(?:turn|switch)\s+on|enable"),
    ("hide", r"hide|close|put away|get rid of|lose"),
    ("show", r"show|bring back|unhide|restore|display|open"),
)
_OVERLAY_ANY = "|".join(re.escape(name) for name in
                        sorted({name for names in OVERLAY_NAMES.values() for name in names}, key=len, reverse=True))


def overlay_request(text):
    """{"op": "hide" | "show" | "off" | "on", "overlay": id} for one overlay
    named; None when none is (the whole lot stays the overlays intents)."""
    words = " ".join(str(text or "").split()).strip(" .!?").casefold()
    if not words or len(words) > 80:
        return None
    for op, verb in _OVERLAY_VERBS:
        # "hide the survey overlay", or "turn the minimap off".
        ahead = re.match(_PLEASE + rf"(?:{verb})\s+(?:the\s+|my\s+|your\s+)?({_OVERLAY_ANY})"
                                   rf"(?:\s+(?:overlay|hud|window|panel))?(?:\s+(?:for me|please|now))*$", words, re.I)
        split = None
        if op in ("off", "on"):
            split = re.match(_PLEASE + rf"(?:turn|switch|shut)\s+(?:the\s+|my\s+|your\s+)?({_OVERLAY_ANY})"
                                       rf"(?:\s+(?:overlay|hud|window|panel))?\s+{op}(?:\s+(?:for me|please|now))*$",
                             words, re.I)
        found = ahead or split
        if found:
            name = found.group(1)
            overlay = next(key for key, names in OVERLAY_NAMES.items() if name in names)
            return {"op": op, "overlay": overlay}
    return None


def intent(text):
    """The small thing asked of it, or None (most talk asks nothing)."""
    words = " ".join(str(text or "").split()).strip(" .!?")
    if not words or len(words) > 80:
        return None
    for name, pattern in INTENTS:
        if pattern.search(words):
            return name
    return None


# Written replies to commands.
REPLIES = {
    "music_pause": ("Paused. The quiet comes back.", "The music stops. I'll listen to the hull instead.", "Paused."),
    "music_play": ("Music, then.", "Playing. The dark could use it.", "There. Something to fly to."),
    "music_next": ("The next one.", "Skipped.", "On to the next."),
    "music_previous": ("Back one.", "That one again.", "The last one, again."),
    "music_not_playing": ("Nothing is playing.", "There's no music to stop."),
    "music_already": ("It's already playing.",),
    # WebView2 won't start sound by itself until the deck has had one click.
    "music_blocked": ("The deck wants one click in its window before it can play. Click it once, and ask again.",),
    "overlays_hide": ("Hidden. I'm still here.", "Gone from the glass.", "Hidden. Say the word and they're back."),
    "overlays_show": ("Back on the glass.", "There they are.", "Shown again."),
    "overlays_already_hidden": ("They're already hidden.",),
    "overlays_already_shown": ("They're already showing.",),
    # One overlay (5.7.3).
    "overlay_hidden": ("{label} hidden.", "{label}: off the glass.", "Hidden: {label_l}."),
    "overlay_shown": ("{label} is back.", "There. {label}.", "{label}, shown again."),
    "overlay_on": ("{label} switched on.", "{label} is on now."),
    "overlay_off": ("{label} switched off.", "{label} is off now."),
    "overlay_already_hidden": ("{label} is already hidden.",),
    "overlay_already_shown": ("{label} is already showing.",),
    "overlay_already_on": ("{label} is already on.",),
    "overlay_already_off": ("{label} is already off.",),
    "overlay_waiting": ("{label} is on. It shows itself when there's something to show.",),
    "overlay_curtain": ("All the overlays are hidden. Ask me to show the overlays first.",),
    "overlay_self": ("I'll keep out of sight. You'll still hear me, if my voice is on.",),
    "copy_next": ("{system} is on your clipboard.", "Copied: {system}.", "{system}. It's on the clipboard."),
    "copy_none": ("There's no next system to copy.", "Nothing is plotted to copy."),
    "hush": ("I'll keep quiet for a while.", "Quiet, then.", "I'll keep my voice down."),
    "unhush": ("I can speak again.", "My voice is back.", "Aloud again, then."),
    "unavailable": ("I can't reach that from here.",),
    "uplink_opening": ("Opening the uplink. Where to {verb} {commodity}: a moment.",
                       "Asking the uplink where to {verb} {commodity}.",
                       "The uplink's open. Looking for {commodity}."),
    "uplink_off": ("The uplink is off. Turn on trading searches in Settings, under Integrations.",),
    "uplink_what": ("The uplink reaches Spansh's markets. Name a commodity, and ask where to sell or buy it.",),
    "plain": ("I can work the ship's controls, show or hide overlays, and play the music. "
              "Or ask what's in the hold, where we are, or where we're headed.",
              "Try a ship command, or ask me what the ship's systems show. I can also look up commodity "
              "prices through the uplink."),
}


# Answer a question from the ship's readings, a few lines at most.
PLAIN_QUESTION = re.compile(r"\?\s*$|^(?:(?:please|hey|watcher|ok|okay)[\s,]+)*(?:what|what's|whats|where|where's|"
                            r"how|how's|which|who|when|is|are|do|does|did|can|could|tell me|show me|list|any)\b", re.I)
PLAIN_LINES = 4


def plain_answer(lines, limit=PLAIN_LINES):
    said = [str(line).strip().rstrip(".") for line in lines or () if str(line).strip()][:limit]
    return ". ".join(said) + "." if said else ""


def reply(outcome, rng, **fields):
    if getattr(rng, "companion_identity", "") == "aster":
        from voidcompass.overlays.aster_lines import command_reply
        own = command_reply(outcome, rng, fields)
        if own:
            return own
    lines = REPLIES.get(outcome) or REPLIES["unavailable"]
    line = rng.choice(lines) if rng is not None else lines[0]
    try:
        return line.format(**fields)
    except (KeyError, IndexError, ValueError):
        return REPLIES["unavailable"][0]
