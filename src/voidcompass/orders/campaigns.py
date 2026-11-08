"""Campaigns (5.7.7): orders in several stages, handed between officers.

Each is written by hand, and its targets come from your own data, so no two
commanders get the same one. A stage is built when it starts (``build``),
from the facts at that moment: First Light's later stages happen in the
system where its first one was done. A stage that can't find a target yet
waits, and its officer says so. The Fork asks you to pick between two
officers who disagree.
"""

from __future__ import annotations

import time

from voidcompass.orders import objectives as obj
from voidcompass.orders import places
from voidcompass.orders.generators import _ly, _why

CAMPAIGN_GAP_S = 3 * 3600.0


def _static(*rows):
    return lambda facts, order: list(rows)


def _nearest_new_variant(facts, species, skip=()):
    flag, keyof = facts.get("codex_flag"), facts.get("codex_key")
    if not callable(flag) or not callable(keyof):
        return None
    for row in sorted(facts.get("bio_nearby") or (), key=lambda item: item.get("distance") or 9e9):
        for name, variant in row.get("variants") or ():
            if name != species or not variant:
                continue
            entry = keyof(f"{name} - {variant}")
            if entry and entry not in skip and flag(entry, None) == "new":
                return entry, f"{name} - {variant}", row
    return None


# -- Every Colour (Lyra) -------------------------------------------------------
def _colour_eligible(facts):
    flag, keyof = facts.get("codex_flag"), facts.get("codex_key")
    if not callable(flag) or not callable(keyof):
        return None
    counts = {}
    for row in facts.get("bio_nearby") or ():
        for name, variant in row.get("variants") or ():
            entry = keyof(f"{name} - {variant}") if variant else None
            if entry and flag(entry, None) == "new":
                counts.setdefault(name, set()).add(entry)
    good = {name: len(entries) for name, entries in counts.items() if len(entries) >= 2}
    if not good:
        return None
    species = max(good, key=good.get)
    return {"species": species, "count": min(3, good[species])}


def _colour_stage(index):
    def build(facts, order):
        done = [row.get("entry") for stage in order.get("stages") or () for row in stage.get("objectives") or ()]
        found = _nearest_new_variant(facts, order["fields"]["species"], skip=set(done))
        if not found:
            return None
        entry, name, row = found
        return [obj.make("bio", label=f"{name} on {row.get('body')} ({_ly(row.get('distance'))})", entry=entry)]
    return build


def _colour_stages(fields):
    officers = ("lyra", "axiom", "lyra")
    titles = ("The first colour", "The second colour", "The third colour")
    return [{"key": f"colour{index}", "title": titles[index], "officer": officers[index], "build": _colour_stage(index)}
            for index in range(int(fields.get("count") or 2))]


# -- The Long Haul (Meridian, then the crew) -------------------------------------
def _haul_eligible(facts):
    here, visited = facts.get("coords"), facts.get("visited")
    if not here or not callable(visited):
        return None
    options = []
    for place_id in ("colonia", "sag_a"):
        system, coords, _words = places.PLACES[place_id]
        gap = places.distance(here, coords)
        if gap and gap >= 3000 and not visited(system):
            options.append((gap, system, coords))
    if not options:
        return None
    gap, system, coords = min(options)
    return {"destination": system, "distance": _ly(gap), "ly": round(gap), "coords": list(coords)}


def _haul_stages(fields):
    coords, ly, destination = fields["coords"], float(fields["ly"]), fields["destination"]
    return [
        {"key": "out", "title": "Out of sight of home", "officer": "meridian",
         "build": _static(obj.make("approach", label=f"A quarter of the way to {destination}", coords=coords,
                                   within=round(ly * .75)))},
        {"key": "charts", "title": "Charts on the way", "officer": "axiom",
         "build": _static(obj.make("map", 3, label="Map 3 worlds on the way"))},
        {"key": "samples", "title": "Samples on the way", "officer": "lyra",
         "build": _static(obj.make("bio", 3, label="Analyse 3 species on the way"))},
        {"key": "half", "title": "The halfway mark", "officer": "meridian",
         "build": _static(obj.make("approach", label=f"Halfway to {destination}", coords=coords, within=round(ly * .5)))},
        {"key": "arrive", "title": f"Landfall at {destination}", "officer": "meridian",
         "build": _static(obj.make("visit", label=f"Reach {destination}", system=destination))},
        {"key": "file", "title": "The paperwork", "officer": "aster",
         "build": _static(obj.make("sell_carto", 5_000_000, label="File the charts from the voyage"))},
    ]


# -- A Clean Sheet (Axiom) ----------------------------------------------------------
def _sheet_eligible(facts):
    if facts.get("region_id") is None or not facts.get("region"):
        return None
    return {"region": facts["region"], "region_id": facts["region_id"]}


def _sheet_stages(fields):
    region, region_id = fields["region"], fields["region_id"]
    return [
        {"key": "three", "title": "Three systems, whole", "officer": "axiom",
         "build": _static(obj.make("fss_all", 3, label=f"Complete 3 systems in {region}", region_id=region_id))},
        {"key": "seven", "title": "Seven more", "officer": "axiom",
         "build": _static(obj.make("fss_all", 7, label=f"Complete 7 more in {region}", region_id=region_id))},
        {"key": "maps", "title": "Surface maps", "officer": "axiom",
         "build": _static(obj.make("map", 5, label=f"Map 5 worlds in {region}", region_id=region_id))},
        {"key": "firsts", "title": "Names on the chart", "officer": "meridian",
         "build": _static(obj.make("discover", 10, label=f"10 first discoveries in {region}", region_id=region_id))},
    ]


# -- The Ledger (Aster) ------------------------------------------------------------
def _ledger_eligible(facts):
    capacity = int(facts.get("cargo_capacity") or 0)
    if capacity < 32 or int(facts.get("trades") or 0) < 3:
        return None
    unit = max(2_000_000, capacity * 20_000)
    return {"unit": unit, "first": obj.short_credits(unit * 2)}


def _ledger_stages(fields):
    unit = int(fields["unit"])
    return [
        {"key": "open", "title": "Opening the account", "officer": "aster",
         "build": _static(obj.make("trade_profit", unit * 2, label="Trade profit"))},
        {"key": "route", "title": "A proper route", "officer": "meridian",
         "build": _static(obj.make("trade_profit", unit * 5, label="Trade profit"))},
        {"key": "close", "title": "The books balanced", "officer": "aster",
         "build": _static(obj.make("trade_profit", unit * 10, label="Trade profit"))},
    ]


# -- First Light (Axiom and Lyra) -----------------------------------------------------
def _light_eligible(facts):
    if float(facts.get("home_ly") or 0) < 500:
        return None
    return {}


def _light_here(facts, order):
    if not facts.get("address"):
        return None
    order["fields"]["system"] = facts.get("system")
    order["target"] = {"system": facts.get("system"), "address": facts["address"]}
    return [obj.make("map", label=f"Be first to map a world in {facts.get('system')}", address=facts["address"], first=True)]


def _light_ground(facts, order):
    address = (order.get("target") or {}).get("address") or facts.get("address")
    if not address:
        return None
    system = order["fields"].get("system") or facts.get("system")
    rows = [obj.make("footfall", label=f"A first footfall in {system}", address=address)]
    if int(facts.get("bio_signals_here") or 0) > 0 and str(address) == str(facts.get("address")):
        rows.append(obj.make("bio", label=f"Analyse a species in {system}", address=address))
    return rows


def _light_stages(fields):
    return [
        {"key": "star", "title": "An undiscovered star", "officer": "axiom",
         "build": _static(obj.make("discover", label="Be the first to scan a star", stars=True))},
        {"key": "map", "title": "Its first map", "officer": "axiom", "build": _light_here},
        {"key": "ground", "title": "Its first footprints", "officer": "lyra", "build": _light_ground},
    ]


# -- Home (the Watcher) ----------------------------------------------------------------
def _home_eligible(facts):
    home, ly = facts.get("home") or {}, facts.get("home_ly")
    if not home.get("pos") or not home.get("name") or ly is None or float(ly) < 2000:
        return None
    return {"home": home["name"], "coords": list(home["pos"]), "ly": round(float(ly)), "distance": _ly(ly)}


def _home_stages(fields):
    home = fields["home"]
    return [
        {"key": "turn", "title": "Turning for home", "officer": "watcher",
         "build": _static(obj.make("approach", label=f"Halfway home to {home}", coords=fields["coords"],
                                   within=round(float(fields["ly"]) / 2)))},
        {"key": "arrive", "title": f"{home}", "officer": "watcher",
         "build": _static(obj.make("visit", label=f"Reach {home}", system=home))},
        {"key": "stay", "title": "Staying a while", "officer": "watcher",
         "build": _static(obj.make("stay", label=f"Ten minutes at {home}", minutes=10, system=home))},
    ]


# -- The Fork (Meridian or Axiom) ----------------------------------------------------------
def _fork_eligible(facts):
    if float(facts.get("home_ly") or 0) < 300 or facts.get("docked"):
        return None
    return {}


FORK_CHOICES = {
    "meridian": ("Make distance (Meridian)", lambda: [obj.make("jumps", 25, label="25 jumps")]),
    "axiom": ("Survey properly (Axiom)", lambda: [obj.make("fss_all", 5, label="Complete 5 systems")]),
}


def _fork_amends(facts, order):
    if order.get("choice") == "meridian":
        return [obj.make("map", 2, label="Map 2 worlds, for Axiom")]
    return [obj.make("jumps", 10, label="10 jumps, for Meridian")]


def _fork_stages(fields):
    return [
        {"key": "choose", "title": "The fork in the road", "officer": "meridian", "choice": list(FORK_CHOICES)},
        {"key": "amends", "title": "Making it up", "officer": "axiom", "build": _fork_amends},
    ]


CAMPAIGNS = {
    "every_colour": {"title": "Every Colour", "officer": "lyra", "category": "exobiology", "eligible": _colour_eligible,
                     "stages": _colour_stages, "ribbon": "every_colour",
                     "brief": "Every colour of {species} you've never logged, one at a time, nearest first."},
    "long_haul": {"title": "The Long Haul", "officer": "meridian", "category": "travel", "eligible": _haul_eligible,
                  "stages": _haul_stages, "ribbon": "long_haul",
                  "brief": "{destination}, {distance} away, in legs: out of sight of home, charts and samples on the way, "
                           "the halfway mark, landfall, and the paperwork."},
    "clean_sheet": {"title": "A Clean Sheet", "officer": "axiom", "category": "exploration", "eligible": _sheet_eligible,
                    "stages": _sheet_stages, "ribbon": "clean_sheet",
                    "brief": "Ten whole systems in {region}, five surface maps, and ten first discoveries."},
    "the_ledger": {"title": "The Ledger", "officer": "aster", "category": "trade", "eligible": _ledger_eligible,
                   "stages": _ledger_stages, "ribbon": "the_ledger",
                   "brief": "Trade profit in three stages, starting with {first} CR."},
    "first_light": {"title": "First Light", "officer": "axiom", "category": "exploration", "eligible": _light_eligible,
                    "stages": _light_stages, "ribbon": "first_light",
                    "brief": "An undiscovered star, its first map and its first footprints, all in one system."},
    "home": {"title": "Home", "officer": "watcher", "category": "watcher", "eligible": _home_eligible,
             "stages": _home_stages, "ribbon": "home",
             "brief": "Back to {home}, {distance} away, in the Watcher's own time."},
    "the_fork": {"title": "The Fork", "officer": "meridian", "category": "travel", "eligible": _fork_eligible,
                 "stages": _fork_stages, "ribbon": "the_fork",
                 "brief": "Meridian and Axiom disagree about what to do next. You decide."},
}


def draft(campaign_id, facts):
    """A campaign as an order draft, or None if it doesn't fit right now."""
    spec = CAMPAIGNS[campaign_id]
    fields = spec["eligible"](facts)
    if fields is None:
        return None
    fields = dict(fields, campaign=spec["title"])
    stages = []
    for stage in spec["stages"](fields):
        row = {"key": stage["key"], "title": stage["title"], "officer": stage["officer"], "objectives": [], "built": False}
        if stage.get("choice"):
            row["choice"] = [{"id": option, "label": FORK_CHOICES[option][0]} for option in stage["choice"]]
        stages.append(row)
    try:
        brief = spec["brief"].format(**fields)
    except (KeyError, ValueError):
        brief = spec["brief"]
    return {
        "kind": f"campaign_{campaign_id}", "campaign": campaign_id, "officer": spec["officer"], "category": spec["category"],
        "size": "campaign", "title": spec["title"], "brief": brief, "stages": stages, "key": f"campaign:{campaign_id}",
        "score": 50.0, "fields": dict(fields, title=spec["title"]),
        "why": [_why(_reason(campaign_id, fields), "Your journal")], "target": {},
        "reward": {"standing": 3, "ribbon": spec["ribbon"], "file": True},
    }


def _reason(campaign_id, fields):
    return {
        "every_colour": "{count} colours of {species} near you, none in your Codex",
        "long_haul": "{destination} is {distance} away and you've never been",
        "clean_sheet": "You're in {region}",
        "the_ledger": "Your hold and your trading record",
        "first_light": "You're far enough out for undiscovered stars",
        "home": "{home} is {distance} away",
        "the_fork": "Two officers with opinions",
    }[campaign_id].format(**fields)


def build_stage(order, facts):
    """Objectives for the campaign's current stage, or None to wait."""
    spec = CAMPAIGNS.get(order.get("campaign"))
    stages = order.get("stages") or []
    index = int(order.get("stage") or 0)
    if spec is None or not (0 <= index < len(stages)):
        return None
    stage = stages[index]
    if stage.get("choice"):
        return None
    builder = next((row.get("build") for row in spec["stages"](order.get("fields") or {}) if row["key"] == stage["key"]), None)
    if builder is None:
        return None
    return builder(facts, order)


def choose(order, option):
    """The Fork: your pick. Returns the stage's objectives."""
    if option not in FORK_CHOICES:
        return None
    order["choice"] = option
    return FORK_CHOICES[option][1]()


def candidates(facts, *, categories, watcher=True, fresh=lambda key: True, last_ended=0.0, now=None):
    now = time.time() if now is None else now
    if now - float(last_ended or 0) < CAMPAIGN_GAP_S:
        return []
    out = []
    for campaign_id, spec in CAMPAIGNS.items():
        if spec["category"] == "watcher" and not watcher:
            continue
        if spec["category"] != "watcher" and spec["category"] not in categories:
            continue
        if not fresh(f"campaign:{campaign_id}"):
            continue
        try:
            row = draft(campaign_id, facts)
        except Exception:
            row = None
        if row:
            out.append(row)
    return out
