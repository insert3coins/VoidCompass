"""What each officer can offer you (5.7.7), from what the app already knows.

Every generator is pure: it takes the deck's facts (and any search results
the deck has fetched) and returns drafts. A draft always says what it rests
on (``why``: the fact, its source, and when it was true), and never claims
something exists that nobody has recorded.

Facts (all optional): now, system, address, coords, region_id, region,
home {name, pos}, home_ly, record_far_ly, jump_range, docked, unsold_bio,
unsold_carto, codex_flag(entry, region_id), codex_key(english name),
bio_nearby [Spansh rows], route {destination, jumps, coords},
neutron {total_jumps}, system_bodies [...], undiscovered_here, star_class,
body_count, bodies_found, sale {...}, colony {...}, power, visited(name),
visited_regions {ids}.
"""

from __future__ import annotations

import time

from voidcompass.orders import objectives as obj
from voidcompass.orders import places

CATEGORIES = {
    "exobiology": "Exobiology",
    "exploration": "Exploration",
    "travel": "Travel and routes",
    "trade": "Trade",
    "colonisation": "Colonisation",
    "powerplay": "Powerplay",
}
DEFAULT_CATEGORIES = tuple(CATEGORIES)

# kind: (officer, category, how the officer names it when they stop offering it)
KINDS = {
    "bio_hunt": ("lyra", "exobiology", "species hunts"),
    "cash_bio": ("lyra", "exobiology", "reminders to cash in samples"),
    "map_worlds": ("axiom", "exploration", "mapping orders"),
    "first_discoveries": ("axiom", "exploration", "discovery counts"),
    "finish_system": ("axiom", "exploration", "full system surveys"),
    "neutron": ("meridian", "travel", "neutron routes"),
    "new_region": ("meridian", "travel", "new regions"),
    "record_far": ("meridian", "travel", "distance records"),
    "sell_price": ("aster", "trade", "price tips"),
    "cash_carto": ("aster", "exploration", "reminders to sell cartographic data"),
    "colony": ("aster", "colonisation", "construction deliveries"),
    "merits": ("aster", "powerplay", "merit targets"),
    "place": ("watcher", "watcher", "long journeys"),
    "errand": ("watcher", "watcher", "errands"),
}

WORTHY = ("earthlike", "earth-like", "water world", "ammonia world")
BIO_RADIUS_LY = 500
MAX_BIO_TARGETS = 3
CASH_BIO_MIN = 25_000_000
CASH_CARTO_MIN = 20_000_000


def _ly(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if value >= 1000:
        return f"{value:,.0f} ly"
    if value >= 10:
        return f"{value:.0f} ly"
    return f"{value:.1f} ly"


def spoken_credits(value):
    """Credits as they're said aloud: "45 million", "1.2 billion"."""
    value = float(value or 0)
    if value >= 1e9:
        return f"{value / 1e9:.1f}".rstrip("0").rstrip(".") + " billion"
    if value >= 1e6:
        return f"{value / 1e6:.0f} million"
    if value >= 1e3:
        return f"{value / 1e3:.0f} thousand"
    return f"{value:.0f}"


def _why(text, source, at=None):
    return {"text": str(text), "source": str(source), "at": float(at or time.time())}


def draft(kind, title, brief, objectives, *, key, score, fields=None, why=(), target=None, size="field",
          reward=None, officer=None):
    owner, category, _ = KINDS[kind]
    return {
        "kind": kind, "officer": officer or owner, "category": category, "size": size,
        "title": title, "brief": brief, "objectives": list(objectives), "key": key, "score": float(score),
        "fields": dict(fields or {}, title=title), "why": list(why), "target": dict(target or {}),
        "reward": dict(reward or {"standing": 1}),
    }


# -- Lyra: exobiology and getting the samples home ---------------------------
def lyra_bio_hunt(facts):
    rows = facts.get("bio_nearby")
    flag, keyof = facts.get("codex_flag"), facts.get("codex_key")
    if not rows or not callable(flag) or not callable(keyof):
        return []
    found = {}
    for row in rows:
        coords = row.get("coords")
        region_id, region = places.region_of(coords)
        for species, variant in row.get("variants") or ():
            name = f"{species} - {variant}" if variant else species
            entry = keyof(name)
            if not entry or entry in found:
                continue
            state = flag(entry, region_id)
            if state not in {"new", "region"}:
                continue
            found[entry] = {"entry": entry, "name": name, "species": species, "variant": variant, "state": state,
                            "system": row.get("system"), "body": row.get("body"), "distance": row.get("distance"),
                            "coords": coords, "region": region, "region_id": region_id, "address": row.get("system_id64")}
    if not found:
        return []
    # The genus with the most unlogged colours close by makes the hunt.
    by_genus = {}
    for item in sorted(found.values(), key=lambda item: item["distance"] or 9e9):
        by_genus.setdefault(item["species"].split(" ")[0], []).append(item)
    genus, items = max(by_genus.items(), key=lambda pair: (len(pair[1][:MAX_BIO_TARGETS]), -(pair[1][0]["distance"] or 9e9)))
    items = items[:MAX_BIO_TARGETS]
    first = items[0]
    new_count = sum(1 for item in items if item["state"] == "new")
    objectives = [obj.make("bio", label=f"{item['name']} on {item['body']}", entry=item["entry"],
                           place={key: item[key] for key in ("system", "body", "coords", "address")}) for item in items]
    count = len(items)
    title = f"The {first['variant'].lower()} {first['species'].split(' ', 1)[-1]}" if count == 1 and first["variant"] else (
        f"{count} {genus} you've never logged" if new_count == count else f"{count} {genus} colours for your Codex")
    brief = (f"{first['name']} is on {first['body']}, {_ly(first['distance'])} away"
             + (f", and {count - 1} more {genus} close by." if count > 1 else ".")
             + " Logged by others; never by you" + ("" if new_count == count else " (or not in this region)") + ".")
    return [draft(
        "bio_hunt", title, brief, objectives, key=f"bio:{first['entry']}",
        score=60 + 15 * new_count + 8 * (count - new_count) - min(40, (first["distance"] or 0) / 15),
        fields={"species": first["name"], "genus": genus, "count": count, "body": first["body"], "system": first["system"],
                "distance": _ly(first["distance"])},
        why=[_why(f"{item['name']} recorded on {item['body']}", "Spansh body catalogue", facts.get("bio_at")) for item in items]
            + [_why("Never analysed by you" + ("" if new_count == count else ", or not in this region"), "Your Codex (journal)")],
        target={"system": first["system"], "body": first["body"], "coords": first["coords"], "address": first["address"]},
    )]


def lyra_cash_bio(facts):
    value = int(facts.get("unsold_bio") or 0)
    if value < CASH_BIO_MIN or facts.get("docked"):
        return []
    rebuy = int(facts.get("rebuy") or 0)
    need = int(value * .9)
    bucket = value // 25_000_000
    return [draft(
        "cash_bio", "Cash in the samples",
        f"You're carrying about {obj.short_credits(value)} CR of exobiology data. Sell it at a Vista Genomics before anything goes wrong.",
        [obj.make("sell_bio", need, label="Sell exobiology data")], key=f"cashbio:{bucket}", score=45 + min(40, value / 10_000_000),
        fields={"value": spoken_credits(value), "rebuy": spoken_credits(rebuy) if rebuy else ""},
        why=[_why(f"{obj.short_credits(value)} CR of unsold samples aboard", "Your journal")]
            + ([_why(f"Rebuy {obj.short_credits(rebuy)} CR", "Your journal")] if rebuy else []),
    )]


# -- Axiom: the survey ----------------------------------------------------------
def axiom_map_worlds(facts):
    bodies = []
    for row in facts.get("system_bodies") or ():
        kind = str(row.get("type") or "").casefold()
        if row.get("mapped"):
            continue
        if row.get("terraformable") or any(word in kind for word in WORTHY):
            bodies.append(row)
    if not bodies or not facts.get("address"):
        return []
    bodies = sorted(bodies, key=lambda row: -(row.get("value") or 0))[:4]
    names = [row["name"] for row in bodies if row.get("name")]
    if not names:
        return []
    count = len(names)
    title = f"Map {names[0]}" if count == 1 else f"Map {count} worlds here"
    return [draft(
        "map_worlds", title, f"{', '.join(names)} in {facts.get('system')}: worth a probe each, and not mapped yet.",
        [obj.make("map", count, label=f"Map {', '.join(names)}", bodies=names, address=facts["address"], first=True)],
        key=f"map:{facts['address']}", score=55 + 10 * count,
        fields={"count": count, "body": names[0], "system": facts.get("system"),
                "value": spoken_credits(sum(row.get("value") or 0 for row in bodies))},
        why=[_why(f"{row['name']}: {row.get('type') or 'world'}{', terraformable' if row.get('terraformable') else ''}, unmapped",
                  "Your scans (journal)") for row in bodies],
        target={"system": facts.get("system"), "address": facts["address"]},
    )]


def axiom_first_discoveries(facts):
    if not facts.get("undiscovered_here") or float(facts.get("home_ly") or 0) < 300:
        return []
    day = int(float(facts.get("now") or time.time()) // 86400)
    return [draft(
        "first_discoveries", "Ten first discoveries", "Out here most of what we scan has never been scanned. Let's make it ten.",
        [obj.make("discover", 10, label="First discoveries")], key=f"disc:{day}", score=40,
        fields={"count": 10, "system": facts.get("system")},
        why=[_why(f"{facts.get('system')} was undiscovered when we arrived", "Your scans (journal)")],
    )]


def axiom_finish_system(facts):
    total, found = int(facts.get("body_count") or 0), int(facts.get("bodies_found") or 0)
    if total < 15 or found >= total or not facts.get("address"):
        return []
    if facts.get("system_quiet") is False:
        # More than five visits a year: someone else has surveyed it, or will.
        return []
    return [draft(
        "finish_system", f"Every body in {facts.get('system')}", f"{total} bodies here and we've found {found}. Finish the FSS.",
        [obj.make("fss_all", label=f"Find all {total} bodies", address=facts["address"])], key=f"fss:{facts['address']}",
        score=45 + min(25, total - found),
        fields={"count": total, "left": total - found, "system": facts.get("system")},
        why=[_why(f"{total} bodies reported, {found} found", "Discovery scan (journal)")],
        target={"system": facts.get("system"), "address": facts["address"]},
    )]


# -- Meridian: routes and reach ---------------------------------------------------
def meridian_neutron(facts):
    route, neutron = facts.get("route") or {}, facts.get("neutron") or {}
    jumps, faster = int(route.get("jumps") or 0), int(neutron.get("total_jumps") or 0)
    destination = route.get("destination")
    if not destination or jumps < 15 or not faster or faster > jumps * .7:
        return []
    saved = jumps - faster
    hours = saved * 50 / 3600
    return [draft(
        "neutron", f"The neutron road to {destination}",
        f"Your route is {jumps} jumps. Riding neutron stars it's {faster}: {saved} fewer, about {hours:.1f} hours saved.",
        [obj.make("visit", label=f"Reach {destination}", system=destination)], key=f"neutron:{str(destination).casefold()}",
        score=70 + min(20, saved / 5),
        fields={"system": destination, "jumps": jumps, "faster": faster, "saved": saved, "hours": f"{hours:.1f}",
                "percent": round(saved * 100 / jumps)},
        why=[_why(f"Plotted route: {jumps} jumps", "Your NavRoute (journal)"),
             _why(f"Neutron route: {faster} jumps", "Spansh neutron plotter", facts.get("neutron_at"))],
        target={"system": destination, "coords": route.get("coords"), "plot": (neutron.get("first") or destination)},
    )]


def meridian_new_region(facts):
    region = facts.get("nearest_region")
    if not region:
        return []
    reach = max(600.0, float(facts.get("jump_range") or 30) * 40)
    if region["ly"] > reach:
        return []
    return [draft(
        "new_region", f"Into {region['name']}", f"You've never been in {region['name']}. Its nearest edge is about {_ly(region['ly'])} away.",
        [obj.make("region", label=f"Enter {region['name']}", region_id=region["id"])], key=f"region:{region['id']}",
        score=50 - region["ly"] / 60,
        fields={"region": region["name"], "distance": f"about {_ly(region['ly'])}"},
        why=[_why(f"No jump of yours has ended in {region['name']}", "Your travel history (journal)"),
             _why("Region borders", "Universal Cartographics region map")],
        target={"coords": region["coords"], "region": region["name"]},
    )]


def meridian_record(facts):
    home, here_ly, record = facts.get("home") or {}, facts.get("home_ly"), float(facts.get("record_far_ly") or 0)
    if not home.get("pos") or here_ly is None:
        return []
    here_ly = float(here_ly)
    step = 1000 if record < 10000 else 5000
    milestone = (int(max(record, here_ly) // step) + 1) * step
    if milestone - here_ly > 600:
        return []
    return [draft(
        "record_far", f"{milestone:,} ly from home", f"We're {_ly(here_ly)} from {home.get('name') or 'home'}. "
        f"Your furthest is {_ly(record)}. {milestone:,} ly is close.",
        [obj.make("far", label=f"Get {milestone:,} ly from home", coords=list(home["pos"]), ly=milestone)],
        key=f"far:{milestone}", score=45,
        fields={"distance": f"{milestone:,} ly", "home": home.get("name") or "home", "record": _ly(record)},
        why=[_why(f"Furthest from home so far: {_ly(record)}", "Your travel history (journal)")],
    )]


# -- Aster: the ledger, the markets and the paperwork ------------------------------
def aster_sell_price(facts):
    sale = facts.get("sale") or {}
    price, last = int(sale.get("price") or 0), int(sale.get("last_price") or 0)
    if not sale.get("station") or not price or not last or price < last * 1.2 or int(sale.get("count") or 0) <= 0:
        return []
    percent = round((price - last) * 100 / last)
    name = sale.get("name") or sale.get("commodity")
    return [draft(
        "sell_price", f"{name} at {sale['station']}",
        f"{sale['station']} in {sale.get('system')} pays {price:,} CR for {name}: {percent}% above what you last sold it for.",
        [obj.make("market_sell", int(sale["count"]), label=f"Sell {name} at {sale['station']}", commodity=sale.get("commodity"),
                  market_id=sale.get("market_id"))],
        key=f"sell:{sale.get('commodity')}:{sale.get('market_id')}", score=65 + min(25, percent / 4),
        fields={"commodity": name, "station": sale["station"], "system": sale.get("system"), "price": f"{price:,}",
                "percent": percent, "distance": _ly(sale.get("distance")), "count": int(sale["count"])},
        why=[_why(f"{sale['station']} buys at {price:,} CR", "Spansh market data", sale.get("updated")),
             _why(f"Your last sale: {last:,} CR", "Your trades (journal)")],
        target={"system": sale.get("system"), "station": sale["station"], "market_id": sale.get("market_id")},
    )]


def aster_cash_carto(facts):
    value = int(facts.get("unsold_carto") or 0)
    if value < CASH_CARTO_MIN or facts.get("docked"):
        return []
    return [draft(
        "cash_carto", "File the charts", f"About {obj.short_credits(value)} CR of cartographic data "
        "is unsold. Any Universal Cartographics will take it.",
        [obj.make("sell_carto", int(value * .9), label="Sell cartographic data")], key=f"cashcarto:{value // 20_000_000}",
        score=40 + min(30, value / 10_000_000), fields={"value": spoken_credits(value)},
        why=[_why(f"{obj.short_credits(value)} CR unsold", "Your journal")],
    )]


def aster_colony(facts):
    colony = facts.get("colony") or {}
    needs = [row for row in colony.get("needs") or () if int(row.get("left") or 0) > 0]
    if not needs or colony.get("market_id") is None:
        return []
    row = max(needs, key=lambda item: int(item.get("left") or 0))
    amount = min(int(row["left"]), max(50, int(facts.get("cargo_capacity") or 0) or 200))
    return [draft(
        "colony", f"{row.get('name')} for {colony.get('site') or 'the site'}",
        f"{colony.get('site') or 'The construction site'} still needs {int(row['left']):,} t of {row.get('name')}. Deliver {amount:,} t.",
        [obj.make("deliver", amount, label=f"Deliver {row.get('name')}", commodity=row.get("symbol"), market_id=colony["market_id"])],
        key=f"colony:{colony['market_id']}:{row.get('symbol')}", score=55,
        fields={"commodity": row.get("name"), "count": amount, "station": colony.get("site"), "system": colony.get("system")},
        why=[_why(f"{int(row['left']):,} t of {row.get('name')} still needed", "Construction depot (journal)")],
        target={"system": colony.get("system"), "station": colony.get("site"), "market_id": colony["market_id"]},
    )]


def aster_merits(facts):
    power = facts.get("power")
    if not power:
        return []
    week = int(float(facts.get("now") or time.time()) // (7 * 86400))
    return [draft(
        "merits", f"1,500 merits for {power}", f"You're pledged to {power}. A steady week's work: 1,500 merits.",
        [obj.make("merits", 1500, label="Earn merits")], key=f"merits:{week}", score=30,
        fields={"power": power, "count": 1500}, why=[_why(f"Pledged to {power}", "Your journal")],
    )]


# -- The Watcher: long orders and errands --------------------------------------------
ERRANDS = {
    "unseen": ("A system nobody has seen", "Go somewhere no one has been. Stay ten minutes. Tell me what it felt like.",
               lambda: [obj.make("stay", label="Ten minutes in an undiscovered system", minutes=10, undiscovered=True)]),
    "picture": ("A picture for me", "Take a picture of something you think I'd like.",
                lambda: [obj.make("screenshot", label="Take a picture")]),
    "footfall": ("Ground nobody has walked on", "Walk on a world nobody has walked on. That's all.",
                 lambda: [obj.make("footfall", label="A first footfall")]),
    "black_hole": ("Sit with a black hole", "Find a black hole. Sit near it for five minutes. Don't talk.",
                   lambda: [obj.make("stay", label="Five minutes by a black hole", minutes=5, star_class="H")]),
    "hutton": ("Hutton", "Go to Hutton Orbital. Dock. I'm told it's a long way in. I want to see if that's true.",
               lambda: [obj.make("dock", label="Dock at Hutton Orbital", station="Hutton Orbital")]),
}


def watcher_place(facts):
    here, visited = facts.get("coords"), facts.get("visited")
    if not here or not callable(visited):
        return []
    drafts = []
    for place_id, (system, coords, words) in places.PLACES.items():
        if visited(system):
            continue
        gap = places.distance(here, coords)
        if gap is None or gap < 500:
            continue
        drafts.append(draft(
            "place", system, f"Take me to {system}. {words[0].upper() + words[1:]}. {_ly(gap)} from here. There's no hurry.",
            [obj.make("visit", label=f"Reach {system}", system=system)], key=f"place:{place_id}", size="long",
            score=30 - gap / 5000, fields={"place": system, "words": words, "distance": _ly(gap), "system": system},
            why=[_why(f"You've never been to {system}", "Your travel history (journal)")],
            target={"system": system, "coords": list(coords)}, reward={"standing": 2, "file": True}))
    return sorted(drafts, key=lambda row: -row["score"])[:1]


def watcher_errand(facts):
    choices = []
    for errand_id, (title, brief, make) in ERRANDS.items():
        if errand_id == "unseen" and float(facts.get("home_ly") or 0) < 300:
            continue
        if errand_id == "hutton" and callable(facts.get("visited")) and facts["visited"]("Alpha Centauri"):
            continue
        if errand_id == "black_hole" and float(facts.get("home_ly") or 0) < 200:
            continue
        choices.append(draft("errand", title, brief, make(), key=f"errand:{errand_id}", score=35,
                             fields={"errand": errand_id}, why=[_why("Its own reasons", "The Watcher")],
                             reward={"standing": 1, "file": True}))
    day = int(float(facts.get("now") or time.time()) // 86400)
    return [choices[day % len(choices)]] if choices else []


GENERATORS = (lyra_bio_hunt, lyra_cash_bio, axiom_map_worlds, axiom_first_discoveries, axiom_finish_system,
              meridian_neutron, meridian_new_region, meridian_record, aster_sell_price, aster_cash_carto,
              aster_colony, aster_merits, watcher_place, watcher_errand)


def candidates(facts, *, categories=DEFAULT_CATEGORIES, watcher=True, muted=lambda officer, kind: False,
               fresh=lambda key: True, on_watch=None, duty=None):
    """Every draft worth offering now, best first. The officer on watch, and
    the one whose duty this is, get a lift."""
    out = []
    for generator in GENERATORS:
        try:
            drafts = generator(facts)
        except Exception:
            continue
        for row in drafts:
            if row["category"] == "watcher":
                if not watcher:
                    continue
            elif row["category"] not in categories:
                continue
            if muted(row["officer"], row["kind"]) or not fresh(row["key"]):
                continue
            if row["officer"] == on_watch:
                row["score"] += 25
            if duty and DUTY_KINDS.get(duty) and row["kind"] in DUTY_KINDS[duty]:
                row["score"] += 15
            out.append(row)
    return sorted(out, key=lambda row: -row["score"])


# What fits each watch duty (core.crew_rota duties).
DUTY_KINDS = {
    "docked": {"sell_price", "colony", "merits", "neutron", "new_region"},
    "scanning": {"map_worlds", "finish_system", "first_discoveries"},
    "surface": {"bio_hunt", "cash_bio"},
    "route": {"neutron", "record_far", "new_region"},
    "deep": {"place", "errand", "first_discoveries", "bio_hunt"},
    "flight": {"cash_bio", "cash_carto", "bio_hunt", "record_far"},
}
