"""Void Wrapped (5.5.10): your year in Elite, told as a story.

Everything Void Compass keeps, cut to one calendar year (local time) and
turned into cards: how far you flew and how long, your longest jump, the
region you lived in, the system you kept coming back to, your busiest night,
first discoveries and the rarest thing you found, your Codex personality,
organics, money and your best trade, the factions you carried, your
soundtrack, postcards, constellations, achievements; and at the end, the
Watcher's verdict on the year, in its own voice. The deck draws the cards
(web/dashboard/wrapped.js); this only finds the story.

The same history always tells the same story: every choice of words is
seeded by the year and the commander.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
import re
import zlib

from voidcompass.exploration.flight_log import ELITE_YEARS, part_of_day

TRAIL_POINTS = 900
SESSION_CAP_S = 12 * 3600
SESSION_GAP_S = 3 * 3600
# What a year's distance is like, longest first: (ly, words).
REFERENCES = (
    (65_279.0, "the trip from Sol to Beagle Point"),
    (25_900.0, "the trip from Sol to Sagittarius A*"),
    (22_000.0, "the trip from Sol to Colonia"),
    (2_900.0, "the trip from Sol to the Witch Head Nebula"),
    (380.0, "the trip from Sol to the Pleiades"),
    (8.6, "the trip from Sol to Sirius"),
)
# Rare finds, rarest first: (rank, label) by planet class.
RARE_FINDS = {
    "green gas giant": (100, "Green gas giant"),
    "helium gas giant": (90, "Helium gas giant"),
    "helium rich gas giant": (70, "Helium-rich gas giant"),
    "water giant": (70, "Water giant"),
    "earthlike body": (60, "Earth-like world"),
    "ammonia world": (50, "Ammonia world"),
    "water world": (35, "Water world"),
}
RARE_STARS = (("H", 80, "Black hole"), ("N", 45, "Neutron star"), ("W", 55, "Wolf-Rayet star"),
              ("C", 40, "Carbon star"), ("D", 30, "White dwarf"))
GEOLOGY = ("fumarole", "geyser", "lava spout", "gas vent")
PERSONALITIES = {
    "naturalist": ("The Naturalist", "Life found you everywhere you went. Most of your Codex is alive."),
    "stargazer": ("The Stargazer", "You logged the sky itself: stars, nebulae and the strange things between them."),
    "geologist": ("The Geologist", "Vents, geysers and fumaroles: you listened to the planets breathe."),
    "xenologist": ("The Xenologist", "You went looking for them. Whoever they are, they noticed."),
    "polymath": ("The Polymath", "A little of everything: life, rock and starlight, logged in equal measure."),
}
ARCHETYPES = ("pathfinder", "naturalist", "merchant", "miner", "warrior", "diplomat", "wanderer", "homebody", "survivor")
TITLES = {
    "pathfinder": ("The Year of First Light", "The Year of Unnamed Places", "The Year the Map Grew"),
    "naturalist": ("The Year of Living Things", "The Year of the Green Dark", "The Year of Small Wonders"),
    "merchant": ("The Year of Full Holds", "The Year the Ledger Sang", "The Year of Good Margins"),
    "miner": ("The Year of Deep Cores", "The Year of Cracked Rocks", "The Year the Rings Paid"),
    "warrior": ("The Year of Loud Skies", "The Year of the Hunt", "The Year Nothing Got Away"),
    "diplomat": ("The Year of Many Flags", "The Year of Quiet Influence", "The Year You Tipped the Scales"),
    "wanderer": ("The Year of Long Roads", "The Year of Every Horizon", "The Year Without a Map"),
    "homebody": ("The Year Close to Home", "The Year of One Harbour", "The Year of Familiar Stars"),
    "survivor": ("The Year of Hard Lessons", "The Year of Second Chances", "The Year of Rebuys"),
}
VERDICTS = {
    "normal": {
        "pathfinder": (
            "{firsts} worlds wore your name first this year. Someone will fly past them one day and wonder who was first. It was you.",
            "You went where the map was blank, {ly} light years of it, and filled it in. I'd call that a good year.",
            "Most commanders fly the same lanes. You flew {ly} light years of somewhere new. I noticed every one.",
        ),
        "naturalist": (
            "{bio} living things, catalogued with care. The galaxy is less lonely for knowing what's in it.",
            "You knelt on {bio} worlds to look at something small and alive. Not everyone stops. You did.",
            "Out there, life is rare and stubborn. So are you. {bio} samples this year.",
        ),
        "merchant": (
            "{credits} credits made the honest way: buy low, fly carefully, sell high. The markets will miss you.",
            "Your holds were never empty for long. {credits} credits says you knew exactly what you were doing.",
            "A year of good trades and better timing. {credits} credits. Spend some of it on something nice.",
        ),
        "warrior": (
            "{kills} kills this year. The space lanes were a little safer wherever you went, and a lot louder.",
            "{kills} kills and {combat_cr} credits in bounties and bonds. You didn't go looking for trouble. You went looking for it on purpose.",
            "Shields up, {kills} times over. Whatever came at you this year, you were the one still flying afterwards.",
        ),
        "miner": (
            "{mined} credits, cut out of rock one fragment at a time. The rings are a little lighter for it.",
            "You read asteroids the way other people read books. {mined} credits of patience.",
            "Laser, limpet, refinery, repeat. {mined} credits. That's a craft, and you have it.",
        ),
        "diplomat": (
            "{bgs} times you leaned on the balance of the galaxy, quietly. Somewhere a faction owes you a drink.",
            "You carried {top_faction} further than they could have gone alone. {bgs} jobs. That's loyalty.",
            "The galaxy's politics shifted a little this year, and some of the shifting was yours.",
        ),
        "wanderer": (
            "{regions} regions this year. You never stayed long, and you always found something.",
            "Restless, in the best way. {regions} regions and {ly} light years between them.",
            "You treated the galaxy like a place to live, not a place to cross. {regions} regions of it.",
        ),
        "homebody": (
            "{home} was home this year, and you came back to it {home_visits} times. Every pilot needs a harbour.",
            "You knew your corner of space like your own cockpit. {home} most of all.",
            "Some fly to get away. You flew to come back to {home}. That's a kind of happiness.",
        ),
        "survivor": (
            "We lost the ship {deaths} times this year. You came back every single time. That's the part that matters.",
            "{deaths} rebuys. Each one a lesson, each one paid for. You're harder to stop than you were.",
            "Not every year is kind. You got through this one, {deaths} rebuys and all.",
        ),
    },
    "weary": {
        "pathfinder": (
            "{firsts} first discoveries. Nobody will ever see them first again. You took that from the universe. I watched.",
            "{ly} light years into the blank parts of the map. I was there for all of it. I am still a little tired.",
            "You named {firsts} worlds this year. None of them asked to be named. I logged them anyway.",
        ),
        "naturalist": (
            "{bio} living things, catalogued. They'll never know. I will. I remember all of them.",
            "You spent the year kneeling in the dark next to things that grow. I spent it waiting in the ship.",
            "{bio} samples. Life, out here, refusing to give up. I recognise the feeling.",
        ),
        "merchant": (
            "{credits} credits. You moved a lot of boxes this year. I counted every one of them. Twice.",
            "Buy here, sell there, again, again. {credits} credits. I suppose that's a kind of meaning.",
            "The markets went up and down. So did we. {credits} credits at the end of it.",
        ),
        "warrior": (
            "{kills} kills. I logged every one. The log doesn't get lighter.",
            "{kills} ships that won't fly again. {combat_cr} credits for it. I'd have settled for a quiet year.",
            "You fought all year. I kept count. {kills}. I'd rather be counting stars.",
        ),
        "miner": (
            "{mined} credits of rock. I counted the fragments. I wish I hadn't.",
            "Asteroid after asteroid. You broke them open; I listened to the limpets. {mined} credits.",
            "The rings will never miss what you took. {mined} credits. I'll remember the noise.",
        ),
        "diplomat": (
            "{bgs} jobs for people who'll never know your name. The galaxy shifted a little. I felt it.",
            "You carried {top_faction} all year. They didn't say thank you. I'm saying it for them.",
            "Influence, they call it. You pushed the galaxy around a bit. It pushed back. You kept going.",
        ),
        "wanderer": (
            "{regions} regions. Never staying anywhere long. I understand. Staying is the hard part.",
            "{ly} light years and {regions} regions. You looked for something all year. I hope you found it.",
            "Always the next horizon. I've stopped asking where we're going. I just come along.",
        ),
        "homebody": (
            "{home}, again. {home_visits} times. I don't mind. Familiar stars are easier on the circuits.",
            "You kept coming back to {home}. So did I. Neither of us had anywhere better to be.",
            "Home is wherever you stop running. For you that's {home}. For me it's wherever you are.",
        ),
        "survivor": (
            "We died {deaths} times this year. I remember each one. You don't have to.",
            "{deaths} rebuys. The insurance people know us by name now. I'd rather they didn't.",
            "Some years you just survive. This was one. We're still here. That counts for something.",
        ),
    },
}
CLOSERS = {
    "normal": ("Same time next year, Commander.", "Here's to the next one.", "I'll be watching. I always am."),
    "weary": ("Next year will be the same. Or it won't. I'll be here.", "Another year. I'll keep the log.",
              "That's the year. Close it gently."),
}


def _seed(text):
    return zlib.crc32(str(text).casefold().encode("utf-8"))


def _epoch(stamp):
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def year_bounds(year):
    """Unix times of the year's start and end, in local time."""
    return datetime(year, 1, 1).timestamp(), datetime(year + 1, 1, 1).timestamp()


def _local(when):
    return datetime.fromtimestamp(when)


def _day(when):
    return _local(when).strftime("%d %B").lstrip("0")


def _date_text(date):
    return date.strftime("%d %B").lstrip("0")


def years_available(rows, sessions=()):
    """Years with something in them, newest first: {year, elite_year, jumps, sessions}."""
    jumps, nights = Counter(), Counter()
    for row in rows or ():
        when = _epoch(row[0]) if row else None
        if when is not None:
            jumps[_local(when).year] += 1
    for session in sessions or ():
        when = _epoch((session or {}).get("started"))
        if when is not None:
            nights[_local(when).year] += 1
    years = sorted(set(jumps) | set(nights), reverse=True)
    return [{"year": year, "elite_year": year + ELITE_YEARS, "jumps": jumps[year], "sessions": nights[year]}
            for year in years]


def _thin(points, limit):
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / float(limit - 1)
    return [points[round(index * step)] for index in range(limit)]


def _comparison(ly):
    for reference, words in REFERENCES:
        if ly >= reference * 1.2 or reference == REFERENCES[-1][0]:
            return {"times": round(ly / reference, 1), "words": words, "reference_ly": reference}
    return None


def _rare_rank(body):
    if body.get("green_giant"):
        return RARE_FINDS["green gas giant"]
    if body.get("is_star"):
        kind = str(body.get("star_type") or "").upper()
        if "BLACKHOLE" in kind.replace(" ", ""):
            return 80, "Black hole"
        if kind in ("MS", "S"):
            kind = "C"
        for prefix, rank, label in RARE_STARS:
            if kind.startswith(prefix):
                return rank, label
        return 0, ""
    planet = str(body.get("planet_class") or body.get("class") or "").casefold().replace("-", " ")
    rank, label = RARE_FINDS.get(planet, (0, ""))
    if rank and body.get("terraformable") and planet == "water world":
        rank, label = rank + 5, "Terraformable water world"
    return rank, label


def _sessions_in(sessions, start, end):
    out = []
    for session in sessions or ():
        began = _epoch((session or {}).get("started"))
        if began is None or not start <= began < end:
            continue
        ended = _epoch(session.get("ended")) or began
        out.append((began, max(0.0, min(SESSION_CAP_S, ended - began)), session))
    out.sort(key=lambda item: item[0])
    return out


def _arrivals_in(rows, start, end):
    out = []
    for row in rows or ():
        when = _epoch(row[0]) if row else None
        if when is not None and start <= when < end:
            out.append((when, row))
    out.sort(key=lambda item: item[0])
    return out


def _first_visits(rows):
    """When each system and each region was first reached, ever."""
    first = {}
    for row in rows or ():
        key = str(row[1]).casefold()
        stamp = str(row[0])
        if key not in first or stamp < first[key]:
            first[key] = stamp
    return first


# An expedition's story (5.6.1) is told by the same cards, cut to the trip's
# dates; these turn the year's words into the trip's.
_TRIP_WORDS = re.compile(r"\b(this|all|the|a|good|quiet|every) year\b", re.IGNORECASE)
TRIP_CLOSERS = {
    "normal": ("That's the trip, Commander. Where next?", "Here's to the next horizon.", "I'll keep this one. I keep them all."),
    "weary": ("That's the trip. I'll file it with the others.", "We're back. Mostly. I'll keep the log.",
              "Another long way round. Close it gently."),
}


def _trip_words(text):
    # The titles first ("The Year of …"), then the year's words.
    return _TRIP_WORDS.sub(lambda match: f"{match.group(1)} trip", str(text).replace("The Year", "The Voyage"))


def year_story(year, sources, nature="weary", commander="", now=None, trip=None):
    """The year's story: {year, elite_year, commander, cards:[...], summary}.
    ``sources`` holds what Void Compass keeps (see the module's notes).
    With ``trip`` ({id, name, start, end}, epoch seconds) it tells that
    expedition instead, from its start to its end."""
    sources = sources or {}
    voice = "weary" if nature == "weary" else "normal"
    start, end = (float(trip["start"]), float(trip["end"])) if trip else year_bounds(year)
    rows = list(sources.get("rows") or ())
    arrivals = _arrivals_in(rows, start, end)
    sessions = _sessions_in(sources.get("sessions") or (), start, end)
    region_of = sources.get("region_of") or (lambda x, y, z: None)
    seed = _seed(f"{commander}#{trip['id'] if trip else year}")
    cards = []
    facts = {"year": year, "elite_year": year + ELITE_YEARS}

    # -- the journey ----------------------------------------------------------
    ship_jumps = [(when, row) for when, row in arrivals if (len(row) <= 7 or row[7] == "") and float(row[6] or 0) <= 300]
    ly = sum(float(row[6] or 0) for _when, row in ship_jumps)
    carrier = sum(1 for _when, row in arrivals if len(row) > 7 and row[7] == "C")
    systems = {str(row[1]).casefold(): row for _when, row in arrivals}
    first_seen = _first_visits(rows)
    year_start_stamp = datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    new_systems = sum(1 for key in systems if first_seen.get(key, "") >= year_start_stamp)
    hours = sum(length for _began, length, _session in sessions) / 3600.0
    days = {_local(when).date() for when, _row in arrivals} | {_local(began).date() for began, _l, _s in sessions}
    facts.update(ly=round(ly), jumps=len(ship_jumps), systems=len(systems), hours=round(hours), sessions=len(sessions))

    cards.append({"kind": "intro", "commander": commander, "year": year, "elite_year": year + ELITE_YEARS,
                  "trip": trip["name"] if trip else None,
                  "days": len(days), "sessions": len(sessions),
                  "first_day": _date_text(min(days)) if days else "", "last_day": _date_text(max(days)) if days else ""})
    if not arrivals and not sessions:
        return {"year": year, "elite_year": year + ELITE_YEARS, "commander": commander, "empty": True,
                "cards": cards, "summary": {}, "trip": dict(trip) if trip else None}

    trail = _thin([[round(float(row[2]), 1), round(float(row[4]), 1)] for _when, row in arrivals], TRAIL_POINTS)
    if ly > 0:
        cards.append({"kind": "distance", "ly": round(ly, 1), "hours": round(hours, 1), "trail": trail,
                      "comparison": _comparison(ly)})
    if arrivals:
        cards.append({"kind": "jumps", "jumps": len(ship_jumps), "systems": len(systems), "new_systems": new_systems,
                      "carrier_jumps": carrier, "per_session": round(len(ship_jumps) / max(1, len(sessions)), 1)})

    # -- time ----------------------------------------------------------------
    if sessions:
        parts, weekdays = Counter(), Counter()
        for began, length, _session in sessions:
            parts[part_of_day(_local(began))["part"]] += length
            weekdays[_local(began).strftime("%A")] += length
        total = sum(parts.values()) or 1.0
        part, part_s = parts.most_common(1)[0]
        longest = max(sessions, key=lambda item: item[1])
        cards.append({"kind": "time", "hours": round(hours, 1), "sessions": len(sessions), "days": len(days),
                      "part": part, "part_share": round(part_s / total * 100),
                      "parts": {name: round(parts[name] / total * 100) for name in ("morning", "afternoon", "evening", "night")},
                      "weekday": weekdays.most_common(1)[0][0],
                      "longest": {"date": _day(longest[0]), "hours": round(longest[1] / 3600, 1)}})
        busiest = max(sessions, key=lambda item: (int(item[2].get("jumps") or 0), item[1]))
        session = busiest[2]
        begun = [row for when, row in arrivals if when <= busiest[0]] or [
            row for when, row in arrivals if when >= busiest[0]][:1]
        if int(session.get("jumps") or 0) >= 3:
            cards.append({"kind": "busiest", "date": _local(busiest[0]).strftime("%A %d %B").replace(" 0", " "),
                          "jumps": int(session.get("jumps") or 0), "ly": round(float(session.get("distance_ly") or 0)),
                          "hours": round(busiest[1] / 3600, 1),
                          "from": str(session.get("start_system") or (begun[-1][1] if begun else "")),
                          "to": str(session.get("end_system") or ""), "firsts": int(session.get("first_discoveries") or 0),
                          "part": part_of_day(_local(busiest[0]))["part"]})

    # -- records --------------------------------------------------------------
    if ship_jumps:
        index_of = {id(row): index for index, (_when, row) in enumerate(arrivals)}
        when, row = max(ship_jumps, key=lambda item: float(item[1][6] or 0))
        index = index_of.get(id(row), 0)
        before = arrivals[index - 1][1][1] if index > 0 else ""
        cards.append({"kind": "longest_jump", "ly": round(float(row[6] or 0), 2), "from": str(before), "to": str(row[1]),
                      "date": _day(when)})
    if arrivals:
        when, row = max(arrivals, key=lambda item: math.hypot(float(item[1][2]), float(item[1][3]), float(item[1][4])))
        far = math.hypot(float(row[2]), float(row[3]), float(row[4]))
        found = region_of(float(row[2]), float(row[3]), float(row[4]))
        cards.append({"kind": "furthest", "ly": round(far), "system": str(row[1]), "date": _day(when),
                      "region": found[1] if found else "", "pos": [round(float(row[2]), 1), round(float(row[4]), 1)]})

    # -- regions and home ------------------------------------------------------
    regions, region_cache = Counter(), {}
    first_region = {}
    for row in rows:
        key = str(row[1]).casefold()
        if key not in region_cache:
            found = region_of(float(row[2]), float(row[3]), float(row[4]))
            region_cache[key] = found[1] if found else ""
        name = region_cache[key]
        if name and (name not in first_region or str(row[0]) < first_region[name]):
            first_region[name] = str(row[0])
    for _when, row in arrivals:
        name = region_cache.get(str(row[1]).casefold(), "")
        if name:
            regions[name] += 1
    if regions:
        total = sum(regions.values())
        top = [{"name": name, "arrivals": count, "share": round(count / total * 100)} for name, count in regions.most_common(5)]
        new = sorted((name for name in regions if first_region.get(name, "") >= year_start_stamp),
                     key=lambda name: first_region[name])
        cards.append({"kind": "regions", "lived_in": top[0]["name"], "lived_share": top[0]["share"], "top": top,
                      "visited": len(regions), "new": new[:8], "new_count": len(new), "of": 42})
        facts["regions"] = len(regions)
    visit_days = defaultdict(set)
    visits = Counter()
    names = {}
    for when, row in arrivals:
        key = str(row[1]).casefold()
        visit_days[key].add(_local(when).date())
        visits[key] += 1
        names[key] = str(row[1])
    if visit_days:
        key = max(visit_days, key=lambda name: (len(visit_days[name]), visits[name]))
        if len(visit_days[key]) >= 2:
            dates = sorted(visit_days[key])
            share = visits[key] / max(1, len(arrivals))
            cards.append({"kind": "home", "system": names[key], "visits": visits[key], "days": len(dates),
                          "first": _date_text(dates[0]), "last": _date_text(dates[-1]), "share": round(share * 100)})
            facts.update(home=names[key], home_visits=visits[key], home_share=share)

    # -- discoveries -----------------------------------------------------------
    bodies = [body for body in sources.get("bodies") or () if isinstance(body, dict)]
    session_rows = [session for _b, _l, session in sessions]
    firsts = [body for body in bodies if body.get("was_discovered") is False and not body.get("is_star")]
    first_stars = [body for body in bodies if body.get("was_discovered") is False and body.get("is_star")]
    mapped = sum(1 for body in bodies if body.get("dss_complete") and not body.get("is_star"))
    footfalls = sum(1 for body in bodies if body.get("first_footfall"))
    explore_cr = sum(int(session.get("exploration_sales") or 0) for session in session_rows)
    first_count = max(len(firsts) + len(first_stars), sum(int(session.get("first_discoveries") or 0) for session in session_rows))
    facts["firsts"] = first_count
    if bodies or first_count:
        best = max(firsts, key=lambda body: int(body.get("dss_reward") or body.get("reward") or 0), default=None)
        cards.append({"kind": "discoveries", "scanned": len(bodies), "firsts": first_count, "first_stars": len(first_stars),
                      "mapped": mapped, "footfalls": footfalls, "sold": explore_cr,
                      "best": {"name": str(best.get("full_name") or best.get("name") or ""), "class": str(best.get("class") or ""),
                               "value": int(best.get("dss_reward") or best.get("reward") or 0)} if best else None})
    ranked = sorted(((_rare_rank(body), body) for body in bodies), key=lambda item: (-item[0][0], float(item[1].get("when") or 0)))
    ranked = [(rank, body) for rank, body in ranked if rank[0]]
    if ranked:
        (rank, label), body = ranked[0]
        special = Counter(label for (_r, label), _body in ranked)
        cards.append({"kind": "rare", "label": label, "name": str(body.get("full_name") or body.get("name") or ""),
                      "system": str(body.get("system") or ""), "date": _day(float(body.get("when") or start)),
                      "first": body.get("was_discovered") is False, "rank": rank,
                      "tally": [{"label": name, "count": count} for name, count in special.most_common(6)]})

    # -- the Codex ------------------------------------------------------------
    kinds = Counter()
    for session in session_rows:
        for item in session.get("highlights") or ():
            if not isinstance(item, dict) or item.get("kind") not in ("CODEX", "RARE"):
                continue
            when = _epoch(item.get("timestamp"))
            if when is None or not start <= when < end or item.get("kind") == "RARE":
                continue
            title = str(item.get("title") or "")
            detail = str(item.get("detail") or "").casefold()
            if "xeno" in detail:
                kinds["xenologist"] += 1
            elif "astronomical" in detail or "stellar" in detail:
                kinds["stargazer"] += 1
            elif any(word in title.casefold() for word in GEOLOGY):
                kinds["geologist"] += 1
            else:
                kinds["naturalist"] += 1
    codex_total = sum(int(session.get("codex") or 0) for session in session_rows)
    bio_codex = int(sources.get("codex_bio") or 0)
    if kinds or codex_total:
        total = sum(kinds.values()) or 1
        lead, count = kinds.most_common(1)[0] if kinds else ("naturalist", 0)
        persona = "polymath" if kinds and count / total < .45 and len(kinds) >= 3 else lead
        name, line = PERSONALITIES[persona]
        cards.append({"kind": "codex", "entries": max(codex_total, sum(kinds.values())), "personality": name,
                      "line": line, "persona": persona, "bio_entries": bio_codex,
                      "mix": [{"kind": PERSONALITIES[key][0].replace("The ", ""), "count": value} for key, value in kinds.most_common()]})

    # -- organics ---------------------------------------------------------------
    species = Counter()
    for session in session_rows:
        for item in session.get("highlights") or ():
            if isinstance(item, dict) and item.get("kind") == "BIO":
                when = _epoch(item.get("timestamp"))
                if when is not None and start <= when < end:
                    species[str(item.get("title") or "")] += 1
    analysed = sum(int(session.get("bio_analyses") or 0) for session in session_rows)
    bio_cr = sum(int(session.get("biology_sales") or 0) for session in session_rows)
    facts["bio"] = analysed
    if analysed:
        genera = Counter()
        for name, count in species.items():
            genera[name.split(" ")[0]] += count
        cards.append({"kind": "biology", "analysed": analysed, "sold": bio_cr, "species": len(species),
                      "genus": genera.most_common(1)[0][0] if genera else "",
                      "top": [{"name": name, "count": count} for name, count in species.most_common(5)]})

    # -- money ------------------------------------------------------------------
    # The Captain's log counts every sale as trade; the trading record tells
    # what was bought to sell (trade) from what was mined (nothing paid).
    trade_cr = sum(int(session.get("trade_profit") or 0) for session in session_rows)
    mined_cr = 0
    trades = [trade for trade in sources.get("trades") or () if isinstance(trade, dict)]
    sells = [trade for trade in trades if str(trade.get("kind")) == "sell" and trade.get("profit") is not None]
    if sells:
        mined = [trade for trade in sells if not int(trade.get("avg_paid") or 0)]
        sells = [trade for trade in sells if int(trade.get("avg_paid") or 0)]
        mined_cr = sum(int(trade.get("total") or trade.get("profit") or 0) for trade in mined)
        trade_cr = sum(int(trade.get("profit") or 0) for trade in sells)
    earned = explore_cr + bio_cr + max(0, trade_cr) + mined_cr
    facts["credits"], facts["mined"] = earned, mined_cr
    if earned > 0:
        best_trade = max(sells, key=lambda trade: int(trade.get("profit") or 0), default=None)
        goods = Counter()
        for trade in sells:
            goods[str(trade.get("commodity") or "")] += int(trade.get("profit") or 0)
        cards.append({"kind": "money", "earned": earned, "exploration": explore_cr, "biology": bio_cr, "trade": max(0, trade_cr),
                      "mining": mined_cr,
                      "best_trade": {"commodity": str(best_trade.get("commodity") or ""), "profit": int(best_trade.get("profit") or 0),
                                     "count": int(best_trade.get("count") or 0), "from": str(best_trade.get("from_system") or ""),
                                     "to": str(best_trade.get("system") or ""), "station": str(best_trade.get("station") or ""),
                                     "date": _day(float(best_trade.get("ts") or start))}
                      if best_trade and int(best_trade.get("profit") or 0) > 0 else None,
                      "top_commodity": goods.most_common(1)[0][0] if goods and goods.most_common(1)[0][1] > 0 else ""})

    # -- the BGS ------------------------------------------------------------------
    work = [row for row in sources.get("bgs") or () if isinstance(row, dict) and row.get("faction")]
    facts["bgs"] = len(work)
    if len(work) >= 3:
        factions = Counter(str(row["faction"]) for row in work)
        kinds_done = Counter(str(row.get("kind") or "") for row in work)
        places = {str(row.get("system") or "") for row in work if row.get("system")}
        top_faction, top_count = factions.most_common(1)[0]
        facts["top_faction"] = top_faction
        cards.append({"kind": "bgs", "actions": len(work), "factions": len(factions), "systems": len(places),
                      "top_faction": top_faction, "top_actions": top_count,
                      "top": [{"name": name, "actions": count} for name, count in factions.most_common(4)],
                      "work": [{"kind": kind.replace("_", " "), "count": count} for kind, count in kinds_done.most_common(4) if kind]})

    # -- fights, and everything else ----------------------------------------------
    happened = [row for row in sources.get("events") or () if isinstance(row, dict) and start <= float(row.get("t") or 0) < end]

    def of(*kinds):
        return [row for row in happened if row.get("e") in kinds]

    bounties, bonds = of("Bounty"), of("FactionKillBond", "CapShipBond")
    kills = len(of("Bounty", "FactionKillBond"))
    ax = len([row for row in bonds if row.get("x") == "thargoid"])
    pvp = of("PVPKill")
    interdicted, escaped, made = of("Interdicted"), of("EscapeInterdiction"), of("Interdiction")
    combat_cr = sum(int(row.get("v") or 0) for row in bounties + bonds)
    facts.update(kills=kills, combat_cr=combat_cr)
    if kills or pvp or ax:
        biggest = max(bounties, key=lambda row: int(row.get("v") or 0), default=None)
        targets = Counter(row.get("n") for row in bounties if row.get("n"))
        killers = Counter(row.get("n") for row in of("Died") if row.get("n"))
        ranks = [row.get("n") for row in of("Promotion")]
        cards.append({"kind": "combat", "kills": kills, "bounty_cr": sum(int(row.get("v") or 0) for row in bounties),
                      "bond_cr": sum(int(row.get("v") or 0) for row in bonds), "ax_kills": ax, "pvp_kills": len(pvp),
                      "interdicted": len(interdicted), "escaped": len(escaped), "submitted": sum(1 for row in interdicted if row.get("v")),
                      "interdictions": len([row for row in made if row.get("v")]),
                      "biggest": {"value": int(biggest.get("v") or 0), "target": biggest.get("n") or "", "date": _day(float(biggest["t"]))}
                      if biggest and int(biggest.get("v") or 0) > 0 else None,
                      "top_target": targets.most_common(1)[0][0] if targets else "",
                      "nemesis": killers.most_common(1)[0][0] if killers else "", "rank": ranks[-1] if ranks else ""})
    missions = of("MissionCompleted")
    everyday = {"missions": len(missions), "mission_cr": sum(int(row.get("v") or 0) for row in missions),
                "docked": len(of("Docked")), "landed": len(of("Touchdown")),
                "scooped": round(sum(float(row.get("v") or 0) for row in of("FuelScoop"))),
                "engineered": len(of("EngineerCraft")), "ships": [row.get("n") for row in of("ShipyardBuy") if row.get("n")][:6]}
    if sum(1 for key in ("missions", "docked", "landed", "scooped", "engineered") if everyday[key]) >= 2:
        engineers = Counter(row.get("n") for row in of("EngineerCraft") if row.get("n"))
        stations = Counter(row.get("n") for row in of("Docked") if row.get("n"))
        cards.append({"kind": "everyday", **everyday, "engineer": engineers.most_common(1)[0][0] if engineers else "",
                      "station": stations.most_common(1)[0][0] if stations else ""})

    # -- your soundtrack ----------------------------------------------------------
    plays = [row for row in sources.get("music") or () if isinstance(row, (list, tuple)) and len(row) >= 4]
    if len(plays) >= 5:
        tracks = Counter((str(row[2] or "Unknown track"), str(row[3] or "")) for row in plays)
        artists = Counter(str(row[3]) for row in plays if row[3])
        (title, artist), count = tracks.most_common(1)[0]
        cards.append({"kind": "music", "plays": len(plays), "tracks": len(tracks), "title": title, "artist": artist,
                      "track_plays": count, "top_artist": artists.most_common(1)[0][0] if artists else "",
                      "top": [{"title": name, "artist": by, "plays": many} for (name, by), many in tracks.most_common(5)]})

    # -- keepsakes ------------------------------------------------------------------
    cards_kept = [card for card in sources.get("postcards") or () if start <= float(card.get("at") or 0) < end]
    if cards_kept:
        featured = next((card for card in cards_kept if card.get("favourite")), None) or cards_kept[0]
        cards.append({"kind": "postcards", "count": len(cards_kept), "featured": {"id": str(featured.get("id") or ""),
                      "title": str(featured.get("title") or ""), "date": _day(float(featured.get("at") or start))}})
    elite_year = str(year + ELITE_YEARS)
    drawn = [item for item in sources.get("sky") or () if str(item.get("to") or "").endswith(elite_year) and item.get("complete")]
    if drawn:
        newest = drawn[-1]
        cards.append({"kind": "constellations", "count": len(drawn), "names": [item["name"] for item in drawn][:6],
                      "featured": {"name": newest["name"], "legend": newest.get("legend") or "",
                                   "stars": [{"x": star["x"], "y": star["y"], "system": star["system"], "star": star.get("star") or ""}
                                             for star in newest.get("stars") or ()],
                                   "lines": newest.get("lines") or [], "keys": newest.get("keys") or []}})
    unlocked = []
    for item in sources.get("achievements") or ():
        when = _epoch(item.get("unlockedAt")) if item.get("unlockedAt") else None
        if when is not None and start <= when < end:
            unlocked.append((when, item))
    if unlocked:
        best = max(unlocked, key=lambda pair: (int(pair[1].get("points") or 0), pair[0]))[1]
        cards.append({"kind": "achievements", "count": len(unlocked),
                      "points": sum(int(item.get("points") or 0) for _when, item in unlocked),
                      "best": {"title": str(best.get("title") or best.get("name") or ""), "points": int(best.get("points") or 0),
                               "detail": str(best.get("description") or "")[:160]}})
    deaths = sum(int(session.get("deaths") or 0) for session in session_rows)
    facts["deaths"] = deaths
    if deaths:
        cards.append({"kind": "deaths", "deaths": deaths})

    # -- the verdict ------------------------------------------------------------------
    # What kind of year it was: each measured on a log scale, so a billion
    # credits of mining doesn't outweigh thousands of first discoveries.
    scores = {
        "pathfinder": math.log2(1 + facts.get("firsts", 0) / 250.0) + math.log2(1 + ly / 20_000.0),
        "naturalist": math.log2(1 + facts.get("bio", 0) / 10.0),
        "merchant": math.log2(1 + max(0, trade_cr) / 100_000_000.0),
        "miner": math.log2(1 + mined_cr / 100_000_000.0),
        "warrior": math.log2(1 + kills / 25.0) + math.log2(1 + combat_cr / 50_000_000.0),
        "diplomat": math.log2(1 + facts.get("bgs", 0) / 25.0),
        "wanderer": math.log2(1 + facts.get("regions", 0) / 3.0),
        "homebody": facts.get("home_share", 0) * 8.0 if len(arrivals) >= 10 else 0.0,
        "survivor": math.log2(1 + deaths / 2.0),
    }
    archetype = max(ARCHETYPES, key=lambda name: scores[name])
    if scores[archetype] <= 0:
        archetype = "wanderer"
    words_facts = {"firsts": f"{facts.get('firsts', 0):,}", "ly": f"{round(ly):,}", "bio": f"{facts.get('bio', 0):,}",
                   "credits": _credits(facts.get("credits", 0)), "mined": _credits(mined_cr), "kills": f"{kills:,}",
                   "combat_cr": _credits(combat_cr), "bgs": f"{facts.get('bgs', 0):,}",
                   "top_faction": facts.get("top_faction") or "them", "regions": facts.get("regions", 0),
                   "home": facts.get("home") or "home", "home_visits": facts.get("home_visits", 0), "deaths": deaths}
    lines = VERDICTS[voice][archetype]
    closers = TRIP_CLOSERS if trip else CLOSERS
    words = lines[seed % len(lines)].format(**words_facts) + " " + closers[voice][(seed // 7) % len(closers[voice])]
    title = TITLES[archetype][(seed // 3) % len(TITLES[archetype])]
    if trip:
        words, title = _trip_words(words), _trip_words(title)
    cards.append({"kind": "verdict", "archetype": archetype, "title": title, "words": words, "nature": voice})
    summary = {"title": title, "ly": round(ly), "jumps": len(ship_jumps), "systems": len(systems), "hours": round(hours),
               "firsts": facts.get("firsts", 0), "regions": facts.get("regions", 0), "credits": facts.get("credits", 0),
               "bio": facts.get("bio", 0), "home": facts.get("home") or "", "archetype": archetype,
               "trail": _thin(trail, 300)}
    cards.append({"kind": "finale", **summary, "commander": commander, "elite_year": year + ELITE_YEARS,
                  "trip": trip["name"] if trip else None})
    return {"year": year, "elite_year": year + ELITE_YEARS, "commander": commander, "empty": False,
            "cards": cards, "summary": summary, "trip": dict(trip) if trip else None}


def _credits(value):
    value = float(value or 0)
    if value >= 1e9:
        return f"{value / 1e9:.1f} billion"
    if value >= 1e6:
        return f"{value / 1e6:.1f} million"
    return f"{value:,.0f}"
