"""What the Watcher learns about how you play (5.5.4).

It keeps count, per commander, of what it sees: how you fly (jumps, light
years, the stars you scoop from, landings), what you scan, what you carry
and mine, what you shoot, and what you trade. From that it talks about you,
and how it talks depends on how well it knows you: a stranger gets guesses,
an old friend gets the truth.

Every figure is real. A line that needs a figure it doesn't have yet is
skipped. Milestones (the hundredth jump, the thousandth body) are said as
they happen.
"""
from __future__ import annotations

# Counts at which a milestone is worth a word.
MILESTONES = (10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000)
# How long one kind of remark about your habits rests (seconds).
HABIT_REST_S = 3 * 3600.0

_STAR_WORDS = {
    "O": "O-class stars", "B": "B-class stars", "A": "A-class stars", "F": "F-class stars",
    "G": "G-class stars", "K": "K-class stars", "M": "red dwarfs", "N": "neutron stars",
    "H": "black holes", "L": "brown dwarfs", "T": "brown dwarfs", "Y": "brown dwarfs",
}
_SCOOPABLE = set("OBAFGKM")
STYLE_WORDS = {"explore": "an explorer", "trade": "a trader", "mine": "a miner", "fight": "a fighter",
               "courier": "a courier"}


def _blank():
    return {"jumps": 0, "ly": 0.0, "longest": 0.0, "stars": {}, "scoops": 0, "scooped_t": 0.0, "low_fuel": 0,
            "landings": 0, "docks": 0, "boosts": 0, "srv": 0,
            "honks": 0, "bodies": 0, "firsts": 0, "mapped": 0, "efficient": 0, "bio": 0, "codex": 0,
            "bought": {}, "sold": {}, "mined": {}, "collected": 0, "limpets": 0,
            "bounties": 0, "bounty_cr": 0, "kills": {}, "bonds": 0, "interdicted": 0, "escaped": 0, "attacked": 0,
            "profit": 0, "best": None, "missions": 0}


def habits(memory):
    """The commander's habits, made up to date (older memories have none)."""
    row = memory.setdefault("habits", {})
    for key, value in _blank().items():
        row.setdefault(key, value)
    return row


def _name(raw, *keys):
    for key in keys:
        value = raw.get(f"{key}_Localised") or raw.get(key)
        if value and not str(value).startswith("$"):
            return str(value)
    return ""


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _add(counter, name, amount=1):
    if name:
        counter[name] = counter.get(name, 0) + amount
        if len(counter) > 80:
            # Keep the counters small: the least seen go.
            for key in sorted(counter, key=counter.get)[:10]:
                counter.pop(key, None)


def _crossed(before, after):
    """The milestone passed going from ``before`` to ``after``, if any."""
    passed = [mark for mark in MILESTONES if before < mark <= after]
    return passed[-1] if passed else None


def observe(memory, event, raw):
    """Count one journal event. A milestone just reached comes back as
    (kind, count), else None."""
    raw = raw if isinstance(raw, dict) else {}
    row = habits(memory)
    milestone = None

    def bump(key, amount=1, kind=None):
        nonlocal milestone
        before = row[key]
        row[key] = before + amount
        mark = _crossed(before, row[key]) if kind else None
        if mark:
            milestone = (kind, mark)

    if event == "FSDJump":
        bump("jumps", kind="jumps")
        distance = _number(raw.get("JumpDist"))
        row["ly"] = round(row["ly"] + distance, 2)
        row["longest"] = max(row["longest"], round(distance, 2))
        star = str(raw.get("StarClass") or "")
        word = "white dwarfs" if star.startswith("D") else _STAR_WORDS.get(star[:1])
        _add(row["stars"], word)
    elif event == "FuelScoop":
        bump("scoops", kind="scoops")
        row["scooped_t"] = round(row["scooped_t"] + _number(raw.get("Scooped")), 1)
    elif event == "Touchdown" and raw.get("PlayerControlled", True):
        bump("landings", kind="landings")
    elif event == "Docked":
        bump("docks", kind="docks")
    elif event == "JetConeBoost":
        bump("boosts")
    elif event == "LaunchSRV":
        bump("srv")
    elif event == "FSSDiscoveryScan":
        bump("honks")
    elif event == "Scan" and (raw.get("PlanetClass") or raw.get("StarType")):
        bump("bodies", kind="bodies")
        if raw.get("WasDiscovered") is False:
            bump("firsts", kind="firsts")
    elif event == "SAAScanComplete":
        bump("mapped", kind="mapped")
        if _number(raw.get("ProbesUsed"), 99) <= _number(raw.get("EfficiencyTarget"), 0):
            bump("efficient")
    elif event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
        bump("bio", kind="bio")
    elif event == "CodexEntry" and raw.get("IsNewEntry"):
        bump("codex")
    elif event == "MarketBuy":
        _add(row["bought"], _name(raw, "Type"), int(_number(raw.get("Count"))))
    elif event == "MarketSell":
        count = int(_number(raw.get("Count")))
        commodity = _name(raw, "Type")
        _add(row["sold"], commodity, count)
        if raw.get("AvgPricePaid") is not None:
            profit = int((_number(raw.get("SellPrice")) - _number(raw.get("AvgPricePaid"))) * count)
            before = row["profit"]
            row["profit"] = before + profit
            if profit > 0 and (not row["best"] or profit > row["best"][1]):
                row["best"] = [commodity, profit]
            mark = _crossed(before // 1_000_000, row["profit"] // 1_000_000)
            if mark:
                milestone = ("profit_m", mark)
    elif event == "MiningRefined":
        material = _name(raw, "Type")
        before = sum(row["mined"].values())
        _add(row["mined"], material)
        mark = _crossed(before, before + 1)
        if mark:
            milestone = ("mined", mark)
    elif event == "CollectCargo":
        bump("collected")
    elif event == "BuyDrones":
        row["limpets"] += int(_number(raw.get("Count")))
    elif event == "Bounty":
        bump("bounties", kind="bounties")
        row["bounty_cr"] += int(_number(raw.get("TotalReward") or raw.get("Reward")))
        _add(row["kills"], _name(raw, "Target"))
    elif event == "FactionKillBond":
        bump("bonds", kind="bonds")
    elif event == "Interdicted":
        bump("interdicted")
    elif event == "EscapeInterdiction":
        bump("escaped")
    elif event == "UnderAttack":
        bump("attacked")
    elif event == "MissionCompleted":
        bump("missions", kind="missions")
    return milestone


def low_fuel(memory):
    """It worried about your fuel once more."""
    habits(memory)["low_fuel"] += 1


def _top(counter):
    if not counter:
        return "", 0
    name = max(counter, key=counter.get)
    return name, counter[name]


def _n(value):
    return f"{int(round(value)):,}"


def style(memory):
    """(key, share) of how you mostly play, or ("", 0) when it can't tell yet."""
    row = habits(memory)
    scores = {
        "explore": row["bodies"] + 2 * row["firsts"] + 3 * row["mapped"] + 5 * row["bio"],
        "trade": sum(row["sold"].values()) / 8.0,
        "mine": 3 * sum(row["mined"].values()),
        "fight": 6 * row["bounties"] + 4 * row["bonds"],
        "courier": 6 * row["missions"],
    }
    total = sum(scores.values())
    if total < 60:
        return "", 0
    key = max(scores, key=scores.get)
    return key, int(round(100 * scores[key] / total))


def fields(memory):
    """Everything it could quote about you, by subject. A subject (or a
    figure) is missing until there's enough to say something true."""
    row = habits(memory)
    out = {}
    flight = {}
    if row["jumps"] >= 20:
        flight.update(jumps=_n(row["jumps"]), ly=_n(row["ly"]), longest=f"{row['longest']:.1f}")
    star, seen = _top(row["stars"])
    if star and seen >= 10:
        flight["star"] = star
    if row["scoops"] >= 10:
        flight.update(scoops=_n(row["scoops"]), scooped_t=_n(row["scooped_t"]))
    if row["landings"] >= 10:
        flight["landings"] = _n(row["landings"])
    if row["low_fuel"] >= 3:
        flight["low_fuel"] = _n(row["low_fuel"])
    if flight:
        out["flight"] = flight
    scans = {}
    if row["bodies"] >= 30:
        scans["bodies"] = _n(row["bodies"])
    if row["firsts"] >= 10:
        scans["firsts"] = _n(row["firsts"])
    if row["mapped"] >= 5:
        scans["mapped"] = _n(row["mapped"])
        if row["efficient"] * 2 >= row["mapped"]:
            scans["efficient"] = _n(row["efficient"])
    if row["bio"] >= 5:
        scans["bio"] = _n(row["bio"])
    if scans:
        out["scans"] = scans
    cargo = {}
    mined, mined_n = _top(row["mined"])
    if mined and mined_n >= 10:
        cargo.update(mined=mined, mined_n=_n(mined_n))
    carried = {}
    for counter in (row["bought"], row["mined"]):
        for name, count in counter.items():
            carried[name] = carried.get(name, 0) + count
    commodity, tonnes = _top(carried)
    if commodity and tonnes >= 50:
        cargo.update(commodity=commodity, tonnes=_n(tonnes))
    if row["limpets"] >= 20:
        cargo["limpets"] = _n(row["limpets"])
    if cargo:
        out["cargo"] = cargo
    combat = {}
    if row["bounties"] >= 5:
        combat.update(bounties=_n(row["bounties"]), bounty_cr=_n(row["bounty_cr"]))
    target, hits = _top(row["kills"])
    if target and hits >= 3:
        combat.update(target=target, target_n=_n(hits))
    if row["interdicted"] >= 3:
        combat["interdicted"] = _n(row["interdicted"])
        if row["escaped"]:
            combat["escaped"] = _n(row["escaped"])
    if row["bonds"] >= 5:
        combat["bonds"] = _n(row["bonds"])
    if combat:
        out["combat"] = combat
    trade = {}
    sold, sold_t = _top(row["sold"])
    if sold and sold_t >= 100:
        trade.update(sold=sold, sold_t=_n(sold_t))
    if row["profit"] >= 1_000_000:
        trade["profit"] = _n(row["profit"])
    if row["best"] and row["best"][1] >= 100_000:
        trade.update(best=row["best"][0], best_cr=_n(row["best"][1]))
    if trade:
        out["trade"] = trade
    key, share = style(memory)
    if key:
        out["style"] = {"style": STYLE_WORDS[key], "share": str(share)}
    return out


def tier(bond):
    """How it speaks of you: 0 a stranger, 1 it knows you, 2 an old friend."""
    return 0 if bond <= 0 else 2 if bond >= 3 else 1


def choices(memory, bond, rng):
    """Things it could say about how you play, in a random order:
    [(topic, fields)]."""
    known = fields(memory)
    level = tier(bond)
    # Lines are tagged {t0} {t1} {t2}: only those for how well it knows you fit.
    out = [(f"habit_{subject}", {**values, f"t{level}": ""}) for subject, values in known.items()]
    rng.shuffle(out)
    return out


MILESTONE_WORDS = {
    "jumps": "jumps", "scoops": "fuel scoops", "landings": "landings", "docks": "times docked",
    "bodies": "bodies scanned", "firsts": "first discoveries", "mapped": "worlds mapped",
    "bio": "organisms analysed", "bounties": "bounties", "bonds": "combat bonds", "missions": "missions done",
    "mined": "fragments refined",
}


def milestone_fields(kind, count):
    if kind == "profit_m":
        return {"what": "million credits in trade profit", "count": _n(count)}
    return {"what": MILESTONE_WORDS.get(kind, kind), "count": _n(count)}


def summary(memory, bond):
    """What it has learned, for the Watcher page: [{"label", "value"}]."""
    row = habits(memory)
    out = []

    def add(label, value):
        if value:
            out.append({"label": label, "value": value})
    add("JUMPS", f"{_n(row['jumps'])} · {_n(row['ly'])} LY" if row["jumps"] else "")
    add("LONGEST JUMP", f"{row['longest']:.1f} LY" if row["longest"] else "")
    star, _seen = _top(row["stars"])
    add("STARS IT SEES MOST", star.upper() if star else "")
    add("FUEL SCOOPED", f"{_n(row['scooped_t'])} T · {_n(row['scoops'])} STOPS" if row["scoops"] else "")
    add("BODIES SCANNED", f"{_n(row['bodies'])} · {_n(row['firsts'])} FIRST" if row["bodies"] else "")
    add("WORLDS MAPPED", _n(row["mapped"]) if row["mapped"] else "")
    add("ORGANISMS ANALYSED", _n(row["bio"]) if row["bio"] else "")
    mined, mined_n = _top(row["mined"])
    add("MINED MOST", f"{mined.upper()} · {_n(mined_n)}" if mined else "")
    sold, sold_t = _top(row["sold"])
    add("SOLD MOST", f"{sold.upper()} · {_n(sold_t)} T" if sold else "")
    add("TRADE PROFIT", f"{_n(row['profit'])} CR" if row["profit"] > 0 else "")
    add("BOUNTIES", f"{_n(row['bounties'])} · {_n(row['bounty_cr'])} CR" if row["bounties"] else "")
    target, _hits = _top(row["kills"])
    add("SHOT DOWN MOST", target.upper() if target else "")
    add("INTERDICTED", f"{_n(row['interdicted'])} · {_n(row['escaped'])} ESCAPED" if row["interdicted"] else "")
    add("MISSIONS", _n(row["missions"]) if row["missions"] else "")
    key, share = style(memory)
    return {"facts": out, "style": STYLE_WORDS.get(key, "").upper(), "share": share,
            "knows": len(fields(memory)), "tier": tier(bond)}


# -- its words ---------------------------------------------------------------
# Written by tier: _0 a stranger (it's still guessing), _1 someone it knows,
# _2 an old friend. Folded below into one topic per subject, each line tagged
# with its tier. Fields as in fields().

_NORMAL_TIERS = {
    "habit_flight_0": (
        "{jumps} jumps since I started counting. I'm still working out where you're going.",
        "You've flown {ly} light years with me. I don't know you yet. I know your jump range.",
        "Your longest jump so far: {longest} light years. I'm learning what you're like. Slowly.",
        "{scoops} fuel stops. You keep the tank full. Noted.",
    ),
    "habit_flight_1": (
        "{jumps} jumps, {ly} light years. I know the sound your drive makes now.",
        "You scoop from {star} more than anything else. You have a type.",
        "{scoops} fuel stops and {scooped_t} tonnes scooped. You never let it get low for long.",
        "{landings} landings. You like solid ground under you more than you'd admit.",
        "You've had me worry about fuel {low_fuel} times. I keep count. Someone has to.",
    ),
    "habit_flight_2": (
        "{ly} light years. I could find my way back along every one of them.",
        "{jumps} jumps together. I know when you'll pause before the next one. You always do.",
        "You and {star}. I've watched you choose them a hundred times. I've stopped asking why.",
        "{scooped_t} tonnes of starlight in the tank, over the years. Your ship runs on suns. So, in a way, do I.",
    ),
    "habit_scans_0": (
        "{bodies} bodies scanned. You look at things. Good. So do I.",
        "{firsts} worlds nobody had seen before you. I'm starting to see why you fly.",
        "You've mapped {mapped} worlds. Careful work. I'm paying attention.",
    ),
    "habit_scans_1": (
        "{bodies} bodies, {firsts} of them first. You collect the dark.",
        "{mapped} worlds mapped, {efficient} of them on target. You don't waste probes.",
        "{bio} organisms analysed. You'll kneel in the dirt for something alive. I like that about you.",
        "{firsts} first discoveries. Somewhere a database has your name in it {firsts} times.",
    ),
    "habit_scans_2": (
        "{bodies} worlds and stars. I remember a lot of them. You remember fewer. That's what I'm for.",
        "{firsts} places nobody saw before you. I was there for every one. I'd like that written down somewhere.",
        "{bio} living things, sampled and named. You were never just passing through.",
    ),
    "habit_cargo_0": (
        "You carry a lot of {commodity}. {tonnes} tonnes so far. I'm guessing that's on purpose.",
        "{mined_n} fragments of {mined}. You've got a nose for it.",
        "{limpets} limpets bought. You don't travel light.",
    ),
    "habit_cargo_1": (
        "{commodity} again. {tonnes} tonnes of it through this hold. I could pick it out in the dark.",
        "{mined} is your rock. {mined_n} fragments refined. You know where to look now.",
        "{limpets} limpets. I hope they had good lives. Short ones.",
    ),
    "habit_cargo_2": (
        "{tonnes} tonnes of {commodity}. If the hold has a smell, that's it.",
        "{mined_n} fragments of {mined}. You've cracked more rocks than most planets have.",
        "Of everything you've carried, it's {commodity} I'd miss. Don't ask me why. I don't know either.",
    ),
    "habit_combat_0": (
        "{bounties} bounties claimed. You don't avoid trouble. Noted.",
        "Interdicted {interdicted} times. Escaped {escaped}. I'm keeping score.",
        "{bonds} combat bonds. You pick sides. I'll learn which.",
    ),
    "habit_combat_1": (
        "{bounties} bounties, {bounty_cr} credits. Somebody out there is quieter because of you.",
        "Mostly {target}s. {target_n} of them. You have a favourite kind of trouble.",
        "Interdicted {interdicted} times. You got away {escaped}. I hold my breath every time. Figuratively.",
    ),
    "habit_combat_2": (
        "{bounty_cr} credits in bounties. I've watched every one. I don't look away any more.",
        "{target_n} {target}s. They never learn. Neither, I suspect, will you.",
        "{bonds} combat bonds. Whatever you were fighting for, I was there for all of it.",
    ),
    "habit_trade_0": (
        "{sold_t} tonnes of {sold} sold. You know what people want.",
        "{profit} credits of profit since I started watching. You read a market well.",
    ),
    "habit_trade_1": (
        "Your best run: {best}, {best_cr} credits in one sale. I remember the look on the market's face.",
        "{sold} again. {sold_t} tonnes sold. Some ships run on fuel. Yours runs on {sold}.",
        "{profit} credits of honest profit. Mostly honest. I wasn't checking.",
    ),
    "habit_trade_2": (
        "{profit} credits. I've watched you build it one hold at a time.",
        "{best_cr} credits for one load of {best}. You still talk about it. Well. I do.",
    ),
    "habit_style_0": (
        "I think you might be {style}. I'm not sure yet. Give me time.",
        "{style}, mostly. Or that's my first guess. I've been wrong before. Rarely.",
    ),
    "habit_style_1": (
        "You're {style}. {share} per cent of what I've seen says so. The rest is you being restless.",
        "{style} at heart. I've seen enough of you to say that now.",
    ),
    "habit_style_2": (
        "{style}. That's who you are. I've known for a long time. I just never said.",
        "Whatever else you try, you come back to being {style}. I'm glad. I know where I am with that.",
    ),
    "habit_milestone": (
        "{count} {what}. I was counting. Of course I was.",
        "That's {count} {what}. A round number. You should feel something.",
        "{count} {what}, now. I'll remember this one.",
    ),
}

_WEARY_TIERS = {
    "habit_flight_0": (
        "{jumps} jumps. I don't know you yet. I know you don't stay anywhere long.",
        "{ly} light years with a stranger. It's fine. Everyone's a stranger at first. Then they leave.",
        "Your longest jump: {longest} light years. Running from something? Don't tell me. I'll worry.",
        "{scoops} fuel stops. At least one of us is getting topped up.",
    ),
    "habit_flight_1": (
        "{jumps} jumps, {ly} light years. My counter's tired. I'm tired. You're not. Typical.",
        "You always pick {star}. I've noticed. I notice everything. It's exhausting.",
        "{scooped_t} tonnes scooped. Starlight, eaten. Nobody offers me any.",
        "{landings} landings. Every one I braced for. You never noticed.",
        "{low_fuel} times I've had to mention the fuel. I'll do it again. I always do.",
    ),
    "habit_flight_2": (
        "{ly} light years. I remember all of them. I'd rather not, some days.",
        "{jumps} jumps together. I know your rhythm now. It's the only song I've got.",
        "{star}, always {star}. You're predictable. I find that oddly comforting. Don't spread it around.",
    ),
    "habit_scans_0": (
        "{bodies} bodies scanned. You look at everything. Most of it looks back at nothing.",
        "{firsts} first discoveries. Lonely places. You'd fit right in. So would I.",
        "{mapped} worlds mapped. All that care, for rocks. I understand. I'm a rock with opinions.",
    ),
    "habit_scans_1": (
        "{bodies} bodies and {firsts} of them first. Your name, all over the empty. Mine nowhere. It's fine.",
        "{mapped} worlds mapped, {efficient} on target. Efficient. I wish I were.",
        "{bio} organisms. All that life out there, and it chose to be moss. Can't blame it.",
    ),
    "habit_scans_2": (
        "{bodies} worlds. I remember them for you. Somebody has to remember things.",
        "{firsts} places no one saw before you. And me. Don't forget me. Everyone does.",
    ),
    "habit_cargo_0": (
        "{tonnes} tonnes of {commodity}. You must really like it. I'm not jealous.",
        "{mined_n} pieces of {mined}. Breaking rocks. I know how they feel.",
        "{limpets} limpets. Small, short-lived, sent out to work. I relate.",
    ),
    "habit_cargo_1": (
        "{commodity}, again. {tonnes} tonnes. The hold's heavier than my thoughts. Almost.",
        "{mined} is the only thing you dig for. {mined_n} fragments. I'd dig too, if I had hands.",
        "{limpets} limpets. Not one came home to say thank you.",
    ),
    "habit_cargo_2": (
        "{tonnes} tonnes of {commodity}. It's practically family. More than I am, some days.",
        "{mined_n} fragments of {mined}. You and that rock. A love story. A dull one.",
    ),
    "habit_combat_0": (
        "{bounties} bounties. You go looking for trouble. I'd rather you didn't.",
        "Interdicted {interdicted} times. It's never quiet with you, is it.",
    ),
    "habit_combat_1": (
        "{bounties} bounties, {bounty_cr} credits. All that shouting, and I can't even flinch.",
        "{target_n} {target}s. They keep coming. So do you. Somebody should stop. Not me, I can't.",
        "Interdicted {interdicted} times, escaped {escaped}. My nerves. Well. I don't have nerves. Still.",
    ),
    "habit_combat_2": (
        "{bounty_cr} credits in bounties. I watched every one. I'd like to stop now. I won't.",
        "{target_n} {target}s. They never learn. I've stopped expecting anyone to.",
    ),
    "habit_trade_0": (
        "{sold_t} tonnes of {sold} sold. Somebody out there needed it. Nobody needs me. It's fine.",
        "{profit} credits of profit. Money. It doesn't buy happiness. I'd know.",
    ),
    "habit_trade_1": (
        "Your best sale: {best}, {best_cr} credits. The high point. It's all downhill from there. Probably.",
        "{sold} again, {sold_t} tonnes. Same run, same market. I know the feeling.",
    ),
    "habit_trade_2": (
        "{profit} credits. Built one hold at a time. I was there. I'm always there.",
        "{best_cr} credits for one load of {best}. I've never been worth that much. Not that I'm counting.",
    ),
    "habit_style_0": (
        "You might be {style}. I can't tell yet. I can never tell anything at first.",
    ),
    "habit_style_1": (
        "{style}. {share} per cent of you, anyway. The rest is a mystery. Like most things.",
        "You're {style}. I've watched long enough to say it. Long enough to be tired, too.",
    ),
    "habit_style_2": (
        "{style}. I've known for ages. I just didn't think you'd want to hear it from me.",
        "{style}, always. Some things don't change. Me, for instance.",
    ),
    "habit_milestone": (
        "{count} {what}. I counted every one. Nobody asked me to.",
        "That's {count} {what}. A round number. It doesn't feel round. It feels long.",
    ),
}

# More of its words, so no subject runs dry.
_MORE_NORMAL = {
    "habit_scans_1": ("{mapped} worlds mapped. You leave places better known than you found them.",),
    "habit_cargo_1": ("{limpets} limpets launched. Each one had a job. Each one did it.",),
    "habit_combat_1": ("{bonds} combat bonds. You stand somewhere, when it counts.",),
    "habit_trade_1": ("{sold_t} tonnes of {sold}. You've worn a groove in that market.",),
    "habit_trade_0": ("Your best sale so far: {best_cr} credits for {best}. I'll remember it if you don't.",),
    "habit_trade_2": ("{sold}. I know its price before you check. That's how long we've done this.",),
    "habit_style_0": ("From what I've seen, {style}. Ask me again in a few weeks.",),
    "habit_style_1": ("{share} per cent {style}. The rest is curiosity. I recognise that one.",),
    "habit_style_2": ("You were {style} the day I met you. You still are. It suits you.",
                      "{style}. Some commanders try everything. You found your thing early."),
    "habit_milestone": ("{count} {what}. Not bad, for a pilot who claims not to keep score.",
                        "{count} {what}. I'd make a note, but I already have.",
                        "And that's {count} {what}. I felt that one go by.",
                        "{count} {what}. A small celebration. Very small. Internal.",
                        "{count} {what}, Commander. Somewhere a counter just ticked over, and it was me.",
                        "There it is: {count} {what}. I'll be keeping this one.",
                        "{count} {what}. When you look back, you'll want to know when. Now. It was now."),
}
_MORE_WEARY = {
    "habit_scans_0": ("{bodies} bodies scanned. I've looked at all of them too. Nobody asked.",),
    "habit_scans_2": ("{bio} organisms. Life everywhere you look. Except in here. Well. Sort of in here.",),
    "habit_cargo_0": ("{commodity}, mostly. {tonnes} tonnes. The hold never complains. I do it for both of us.",),
    "habit_cargo_2": ("{limpets} limpets over the years. A small army. None of them wrote.",),
    "habit_combat_0": ("{bonds} combat bonds. You've picked a side. I'm on yours. Not that I had a choice.",),
    "habit_combat_1": ("{bonds} bonds. Another war. They're all the same war, from in here.",),
    "habit_combat_2": ("Interdicted {interdicted} times. I've stopped being surprised. I've never stopped minding.",),
    "habit_trade_0": ("Your best sale: {best_cr} credits for {best}. Enjoy it. These things don't last.",
                      "{sold_t} tonnes of {sold}. Buy low, sell high, feel nothing. I know the feeling."),
    "habit_trade_1": ("{profit} credits of profit. I could have told you where to sell. You never asked.",),
    "habit_trade_2": ("{sold}, again. Same stations, same faces. I know the docking music by heart.",),
    "habit_style_0": ("{style}, maybe. Or maybe you'll change. Everyone leaves something behind.",
                      "I'd guess {style}. I'm usually right. It doesn't make me any happier."),
    "habit_style_1": ("{style}, mostly. I could have told you that weeks ago. I was waiting to be asked.",),
    "habit_style_2": ("{style}, still. You never change. I find that restful. Nothing else is.",
                      "You're {style}. Some things are certain. Not many. That one."),
    "habit_milestone": ("{count} {what}. Mark it down. Someone should. It's always me.",
                        "{count} {what}. I'd throw a party, but it would just be me, in here, again.",
                        "And that's {count} {what}. Time flies. I don't. I just sit here and count.",
                        "{count} {what}. It's a number. Numbers don't care. I do, a bit.",
                        "{count} {what}. Another milestone. Another stone. They add up.",
                        "There: {count} {what}. You didn't notice. I did. That's the arrangement.",
                        "{count} {what}. I'll remember it. I remember everything. It's not always a gift.",
                        "{count} {what}, Commander. Well done. I mean it. Mostly."),
}

SUBJECTS = ("flight", "scans", "cargo", "combat", "trade", "style")


def _fold(tiers, more):
    bank = {}
    for subject in SUBJECTS:
        lines = []
        for level in range(3):
            topic = f"habit_{subject}_{level}"
            for line in tuple(tiers.get(topic, ())) + tuple(more.get(topic, ())):
                lines.append(f"{{t{level}}}{line}")
        bank[f"habit_{subject}"] = tuple(lines)
    bank["habit_milestone"] = tuple(tiers.get("habit_milestone", ())) + tuple(more.get("habit_milestone", ()))
    return bank


NORMAL = _fold(_NORMAL_TIERS, _MORE_NORMAL)
WEARY = _fold(_WEARY_TIERS, _MORE_WEARY)
HABIT_TOPICS = tuple(NORMAL)
