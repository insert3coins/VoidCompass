"""What an order asks for, and how the journal says it's done (5.7.7).

An objective is a small dict: ``type``, how many are needed (``need``), how
many are done (``have``), and its own parameters. ``advance`` reads one
journal event and moves it on; ``settle`` handles the ones that need time
(staying somewhere), from the deck's own clock. Event names and fields follow
the journal schema (schemas.edomh.nl).
"""

from __future__ import annotations

import math

from voidcompass.exploration import galactic_regions

ARRIVALS = frozenset({"FSDJump", "CarrierJump", "Location"})
SEEN_LIMIT = 400

# type: (what it counts, short label used on cards when no label was given)
TYPES = {
    "visit": "Reach a system",
    "approach": "Get within range of a place",
    "region": "Enter a region",
    "far": "Get far enough from a point",
    "bio": "Analyse a species",
    "codex": "Log a Codex entry",
    "sell_bio": "Sell exobiology data",
    "sell_carto": "Sell cartographic data",
    "map": "Map worlds with probes",
    "fss_all": "Find every body in a system",
    "discover": "First discoveries",
    "land": "Touch down",
    "footfall": "First footfall",
    "jumps": "Jumps",
    "trade_profit": "Trade profit",
    "market_sell": "Sell a commodity",
    "deliver": "Deliver to a construction site",
    "merits": "Powerplay merits",
    "screenshot": "Take a picture",
    "stay": "Stay a while",
    "dock": "Dock",
}
# Counted in credits or tonnes rather than one by one.
AMOUNTS = frozenset({"sell_bio", "sell_carto", "trade_profit", "market_sell", "deliver", "merits"})


def make(kind, need=1, label="", **params):
    """A new objective."""
    if kind not in TYPES:
        raise ValueError(f"unknown objective {kind}")
    row = {"type": kind, "need": max(1, int(need or 1)), "have": 0, "label": str(label or TYPES[kind])}
    row.update({key: value for key, value in params.items() if value is not None})
    return row


def done(objective):
    return int(objective.get("have") or 0) >= int(objective.get("need") or 1)


def fraction(objective):
    need = max(1, int(objective.get("need") or 1))
    return min(1.0, max(0, int(objective.get("have") or 0)) / need)


def _same(a, b):
    return bool(a) and bool(b) and str(a).strip().casefold() == str(b).strip().casefold()


def _coords(raw):
    pos = raw.get("StarPos")
    try:
        return [float(pos[0]), float(pos[1]), float(pos[2])]
    except (TypeError, ValueError, IndexError):
        return None


def distance(a, b):
    try:
        return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))
    except (TypeError, ValueError):
        return None


def _seen(objective, key):
    """True the first time ``key`` counts for this objective."""
    seen = objective.setdefault("seen", [])
    key = str(key).casefold()
    if key in seen:
        return False
    seen.append(key)
    del seen[:-SEEN_LIMIT]
    return True


def _in_place(objective, raw, ctx):
    """An objective tied to one system (by address or name) or region."""
    address = objective.get("address")
    if address is not None:
        here = raw.get("SystemAddress", ctx.get("address"))
        if here is not None and str(here) != str(address):
            return False
    system = objective.get("system")
    if system and not address:
        here = raw.get("StarSystem") or raw.get("SystemName") or raw.get("System") or ctx.get("system")
        if here and not _same(here, system):
            return False
    region = objective.get("region_id")
    if region is not None and ctx.get("region_id") is not None and int(ctx["region_id"]) != int(region):
        return False
    return True


def _credits(value):
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _gain(kind, objective, event, raw, ctx):
    """How far this event moves the objective on (0: not at all)."""
    if kind == "visit":
        if event not in ARRIVALS:
            return 0
        if objective.get("address") is not None and raw.get("SystemAddress") is not None:
            return 1 if str(raw["SystemAddress"]) == str(objective["address"]) else 0
        return 1 if _same(raw.get("StarSystem"), objective.get("system")) else 0
    if kind == "approach" or kind == "far":
        if event not in ARRIVALS:
            return 0
        here = _coords(raw)
        gap = distance(here, objective.get("coords")) if here else None
        if gap is None:
            return 0
        if kind == "approach":
            return 1 if gap <= float(objective.get("within") or 0) else 0
        return 1 if gap >= float(objective.get("ly") or 0) else 0
    if kind == "region":
        if event not in ARRIVALS:
            return 0
        here = _coords(raw)
        found = galactic_regions.find_region(*here) if here else None
        return 1 if found and int(found[0]) == int(objective.get("region_id") or -1) else 0
    if kind == "bio":
        if event != "ScanOrganic" or str(raw.get("ScanType") or "") != objective.get("stage", "Analyse"):
            return 0
        if objective.get("entry") and not _same(raw.get("Variant"), objective["entry"]):
            return 0
        if objective.get("species") and not str(raw.get("Species") or "").startswith(str(objective["species"])):
            return 0
        if objective.get("genus") and not str(raw.get("Genus") or "").startswith(str(objective["genus"])):
            return 0
        if not _in_place(objective, raw, ctx):
            return 0
        return 1 if _seen(objective, f"{raw.get('SystemAddress')}:{raw.get('Body')}:{raw.get('Variant') or raw.get('Species')}") else 0
    if kind == "codex":
        if event != "CodexEntry":
            return 0
        name = str(raw.get("Name") or "")
        if objective.get("entry") and not _same(name, objective["entry"]):
            return 0
        if objective.get("prefix") and not name.startswith(str(objective["prefix"])):
            return 0
        if objective.get("category") and not _same(raw.get("Category"), objective["category"]):
            return 0
        if objective.get("new_only") and not raw.get("IsNewEntry"):
            return 0
        return 1 if _seen(objective, name) else 0
    if kind == "sell_bio":
        if event != "SellOrganicData":
            return 0
        return sum(_credits(row.get("Value")) + _credits(row.get("Bonus")) for row in raw.get("BioData") or () if isinstance(row, dict))
    if kind == "sell_carto":
        if event == "MultiSellExplorationData":
            return _credits(raw.get("TotalEarnings"))
        if event == "SellExplorationData":
            return _credits(raw.get("TotalEarnings")) or _credits(raw.get("BaseValue")) + _credits(raw.get("Bonus"))
        return 0
    if kind == "map":
        if event != "SAAScanComplete" or not _in_place(objective, raw, ctx):
            return 0
        bodies = objective.get("bodies")
        name = str(raw.get("BodyName") or "")
        if objective.get("first") and ((ctx.get("bodies") or {}).get(name.casefold()) or {}).get("mapped_before"):
            return 0
        if bodies and not any(_same(name, body) for body in bodies):
            return 0
        if objective.get("worthy") and name.casefold() not in {str(b).casefold() for b in ctx.get("worthy_bodies") or ()}:
            return 0
        return 1 if _seen(objective, f"{raw.get('SystemAddress')}:{name}") else 0
    if kind == "fss_all":
        if event != "FSSAllBodiesFound" or not _in_place(objective, raw, ctx):
            return 0
        return 1 if _seen(objective, raw.get("SystemAddress") or raw.get("SystemName")) else 0
    if kind == "discover":
        if event != "Scan" or raw.get("WasDiscovered") is not False or raw.get("ScanType") == "NavBeaconDetail":
            return 0
        if objective.get("stars") and not raw.get("StarType"):
            return 0
        if not _in_place(objective, raw, ctx):
            return 0
        return 1 if _seen(objective, f"{raw.get('SystemAddress')}:{raw.get('BodyName')}") else 0
    if kind == "land":
        if event != "Touchdown" or raw.get("PlayerControlled") is False or not _in_place(objective, raw, ctx):
            return 0
        if objective.get("body") and not _same(raw.get("Body"), objective["body"]):
            return 0
        return 1 if _seen(objective, f"{raw.get('SystemAddress')}:{raw.get('Body')}") else 0
    if kind == "footfall":
        if event != "Disembark" or not raw.get("OnPlanet") or not _in_place(objective, raw, ctx):
            return 0
        body = str(raw.get("Body") or "")
        facts = (ctx.get("bodies") or {}).get(body.casefold()) or {}
        if facts.get("footfalled") is not False:
            return 0
        return 1 if _seen(objective, f"{raw.get('SystemAddress')}:{body}") else 0
    if kind == "jumps":
        return 1 if event == "FSDJump" and _in_place(objective, raw, ctx) else 0
    if kind == "trade_profit":
        if event != "MarketSell" or raw.get("StolenGoods") or raw.get("BlackMarket"):
            return 0
        paid = _credits(raw.get("AvgPricePaid"))
        if not paid:
            return 0
        return max(0, (_credits(raw.get("SellPrice")) - paid) * _credits(raw.get("Count")))
    if kind == "market_sell":
        if event != "MarketSell":
            return 0
        if objective.get("commodity") and not _same(str(raw.get("Type") or "").replace("$", "").replace("_name;", ""),
                                                    objective["commodity"]):
            return 0
        if objective.get("market_id") is not None and str(raw.get("MarketID")) != str(objective["market_id"]):
            return 0
        if objective.get("min_price") and _credits(raw.get("SellPrice")) < int(objective["min_price"]):
            return 0
        return _credits(raw.get("Count"))
    if kind == "deliver":
        if event != "ColonisationContribution":
            return 0
        if objective.get("market_id") is not None and str(raw.get("MarketID")) != str(objective["market_id"]):
            return 0
        total = 0
        for row in raw.get("Contributions") or ():
            if not isinstance(row, dict):
                continue
            name = str(row.get("Name") or "").replace("$", "").replace("_name;", "")
            if objective.get("commodity") and not _same(name, objective["commodity"]):
                continue
            total += _credits(row.get("Amount"))
        return total
    if kind == "merits":
        return _credits(raw.get("MeritsGained")) if event == "PowerplayMerits" else 0
    if kind == "screenshot":
        if event != "Screenshot" or not _in_place(objective, raw, ctx):
            return 0
        return 1 if _seen(objective, raw.get("Filename") or raw.get("timestamp")) else 0
    if kind == "dock":
        if event != "Docked":
            return 0
        if objective.get("market_id") is not None and str(raw.get("MarketID")) != str(objective["market_id"]):
            return 0
        if objective.get("station") and not _same(raw.get("StationName"), objective["station"]):
            return 0
        return 1 if _seen(objective, raw.get("MarketID") or raw.get("StationName")) else 0
    return 0


def taken(objective, event, raw):
    """5.7.7: a first someone else got to, as the journal shows it. A body an
    order wants to be first to map, whose fresh Scan says it's already mapped,
    leaves the objective. True when that leaves nothing to do: overtaken."""
    if objective.get("type") != "map" or not objective.get("first") or event != "Scan" or done(objective):
        return False
    if raw.get("WasMapped") is not True:
        return False
    name = str(raw.get("BodyName") or "")
    # The Scan the game writes after your own map says "mapped" too: that one's yours.
    if any(str(key).endswith(":" + name.casefold()) for key in objective.get("seen") or ()):
        return False
    bodies = list(objective.get("bodies") or ())
    keep = [body for body in bodies if not _same(body, name)]
    if len(keep) == len(bodies):
        return False
    objective["bodies"] = keep
    objective.setdefault("taken", []).append(name)
    have = int(objective.get("have") or 0)
    objective["need"] = max(1, have, int(objective.get("need") or 1) - 1)
    return not keep and have == 0


def advance(objective, event, raw, ctx=None):
    """Read one journal event. Returns how much it added (0: nothing)."""
    if done(objective):
        return 0
    kind = objective.get("type")
    if kind == "stay":
        # Leaving the system resets the clock.
        if event in ARRIVALS:
            objective.pop("since", None)
        return 0
    gain = _gain(kind, objective, str(event or ""), raw or {}, ctx or {})
    if gain <= 0:
        return 0
    need = int(objective.get("need") or 1)
    before = int(objective.get("have") or 0)
    objective["have"] = min(need, before + int(gain))
    return objective["have"] - before


def settle(objective, ctx, now):
    """The objectives that need time: staying in the right kind of system.
    ctx: address, star_class, undiscovered, arrived_at. Returns the gain."""
    if objective.get("type") != "stay" or done(objective):
        return 0
    address = ctx.get("address")
    fits = address is not None and not ctx.get("in_danger")
    if objective.get("undiscovered") and not ctx.get("undiscovered"):
        fits = False
    star = str(objective.get("star_class") or "")
    if star and not str(ctx.get("star_class") or "").upper().startswith(star.upper()):
        fits = False
    if objective.get("system") and not _same(ctx.get("system"), objective["system"]):
        fits = False
    if not fits:
        objective.pop("since", None)
        objective.pop("since_address", None)
        return 0
    if objective.get("since_address") != str(address):
        objective["since_address"] = str(address)
        objective["since"] = float(ctx.get("arrived_at") or now)
    if now - float(objective["since"]) >= float(objective.get("minutes") or 10) * 60:
        objective["have"] = int(objective.get("need") or 1)
        return 1
    return 0


def describe(objective):
    """The objective as one line for a card: label and progress."""
    label = str(objective.get("label") or TYPES.get(objective.get("type"), "Objective"))
    need, have = int(objective.get("need") or 1), int(objective.get("have") or 0)
    if objective.get("type") in {"sell_bio", "sell_carto", "trade_profit"}:
        return f"{label}: {short_credits(have)} of {short_credits(need)} CR"
    if objective.get("type") in {"market_sell", "deliver"}:
        return f"{label}: {have:,} of {need:,} t"
    if need > 1:
        return f"{label}: {have} of {need}"
    return label


def short_credits(value):
    value = float(value or 0)
    if value >= 1e9:
        return f"{value / 1e9:.1f}B"
    if value >= 1e6:
        return f"{value / 1e6:.1f}M"
    if value >= 1e3:
        return f"{value / 1e3:.0f}K"
    return f"{value:.0f}"
