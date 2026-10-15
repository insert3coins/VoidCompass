"""Your constellation (5.5.3.7): your journey drawn as constellations.

Each play session gives one star: the system you lingered in longest (at
least ten minutes; a session that never stopped gives none). Nine stars make
a constellation, joined in the order you flew; then a new one begins, so your
sky fills with them over the years. Each is named, with a short legend, by
the Watcher.

The shape is your own: each line leaves its star on your real bearing,
turned by the star's name, and its length grows with how far you went
(softened, so one long haul doesn't flatten the rest). Now and then, as the
star's name decides, a line branches from an earlier star instead, the way
real constellations hang off one another. The same history always draws the
same sky.
"""
from __future__ import annotations

from datetime import datetime
import math
import zlib

STARS_PER_CONSTELLATION = 9
SESSION_GAP_S = 3 * 3600      # a longer gap between arrivals: a new session
DWELL_CAP_S = 3 * 3600        # a stay counted at most this long
LINGER_S = 10 * 60            # shorter than this isn't lingering
ELITE_YEARS = 1286            # the game's calendar runs this far ahead

ADJECTIVES = (
    "Patient", "Wandering", "Quiet", "Long", "Faithful", "Distant", "Restless", "Silver", "Ember", "Hollow",
    "Second", "Drifting", "Lonely", "Slow", "Bright", "Sleeping", "Unfinished", "Weathered", "Gentle", "Stubborn",
)
NOUNS = (
    "Kite", "Ladder", "Lantern", "Compass", "Heron", "Anchor", "Crown", "Thread", "Harp", "Wake",
    "Spindle", "Bridge", "Key", "Sail", "Bell", "Gate", "Moth", "Oar", "Feather", "Hound",
)
LEGENDS = {
    "normal": (
        "{count} stars, each a place you stayed longer than you had to. {brightest} held you longest.",
        "Drawn between {first} and {last}. Look for it whenever you've stopped to rest.",
        "It began at {first}. Sailors would have steered by {brightest}.",
        "{count} nights, {count} harbours. The brightest is {brightest}.",
        "A shape you made without meaning to, from {first} to {last}.",
        "Every star here is somewhere you chose to stay. {brightest} most of all.",
        "Some say it points the way home. It points to {last}.",
        "Traced over {span}. The old pilots would have named it after you.",
    ),
    "weary": (
        "{count} places you stopped running. {brightest} kept you longest. I noticed.",
        "From {first} to {last}. It took {span}. It felt longer.",
        "{brightest} is the bright one. You stayed there. I waited there.",
        "{count} stars. Nobody else will ever see this shape. That seems right.",
        "It starts at {first}. Where it ends, we were both tired.",
        "Drawn over {span}, one rest at a time. The sky doesn't care. I do, a little.",
        "Look at it. {count} times you stopped. {count} times you went on anyway.",
        "If you squint it looks like something. Most things do, out here.",
    ),
}
LEGEND_NATURE = {"weary": "weary"}


def _epoch(stamp):
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _seed(text):
    return zlib.crc32(str(text).casefold().encode("utf-8"))


SOURCES = ("session", "every")
SHAPES = ("branching", "map")


def constellation_options(config):
    """The Constellation page's choices (5.5.3.7)."""
    config = config or {}

    def whole(key, default, low, high):
        try:
            value = int(float(config.get(key, default)))
        except (TypeError, ValueError):
            value = default
        return max(low, min(high, value))

    source = str(config.get("constellation_source") or "session").casefold()
    shape = str(config.get("constellation_shape") or "branching").casefold()
    return {
        "per": whole("constellation_stars", STARS_PER_CONSTELLATION, 5, 12),
        "linger_min": whole("constellation_linger_min", LINGER_S // 60, 5, 60),
        "source": source if source in SOURCES else "session",
        "shape": shape if shape in SHAPES else "branching",
    }


def session_stars(rows, linger_s=LINGER_S, every=False):
    """One star per play session: the system lingered in longest (or, with
    ``every``, each stay of ``linger_s`` or more). ``rows`` are the travel
    history's, oldest first."""
    stars = []
    session = []

    def close():
        if not session:
            return
        stays = []
        for index, (when, row) in enumerate(session):
            if index + 1 < len(session):
                dwell = min(DWELL_CAP_S, session[index + 1][0] - when)
            else:
                dwell = 0.0  # where the session ended: how long is unknown
            stays.append((dwell, when, row))
        chosen = [stay for stay in stays if stay[0] >= linger_s]
        if not every and chosen:
            chosen = [max(chosen, key=lambda stay: stay[0])]
        for dwell, when, row in chosen:
            stars.append({"system": str(row[1]), "x": float(row[2]), "y": float(row[3]), "z": float(row[4]),
                          "star": str(row[5] or ""), "dwell": round(dwell), "at": when,
                          "session_start": session[0][0], "jumps": len(session) - 1})
        session.clear()

    last = None
    for row in rows or ():
        when = _epoch(row[0]) if row else None
        if when is None:
            continue
        if last is not None and when - last > SESSION_GAP_S:
            close()
        session.append((when, row))
        last = when
    close()
    return stars


def _map_layout(stars):
    """True to the map: each star where it really is, seen from above the
    galaxy, its distance from the middle softened (so a long voyage and a
    cluster of nearby stops both read), joined in the order you flew."""
    points, lines, previous_key = {}, [], None
    distinct = {}
    for star in stars:
        distinct.setdefault(star["system"].casefold(), star)
    cx = sum(star["x"] for star in distinct.values()) / max(1, len(distinct))
    cz = sum(star["z"] for star in distinct.values()) / max(1, len(distinct))
    for key, star in distinct.items():
        dx, dz = star["x"] - cx, star["z"] - cz
        r = math.hypot(dx, dz)
        soft = math.log1p(r / 25.0)
        points[key] = (dx / r * soft, dz / r * soft) if r > 1e-6 else (0.0, 0.0)
    for star in stars:
        key = star["system"].casefold()
        if previous_key and previous_key != key and [previous_key, key] not in lines and [key, previous_key] not in lines:
            lines.append([previous_key, key])
        previous_key = key
    return _fit(points), lines


def _fit(points):
    """Into [-0.9, 0.9] each way, the shape kept whole."""
    xs = [point[0] for point in points.values()] or [0.0]
    ys = [point[1] for point in points.values()] or [0.0]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    middle = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2)
    return {key: (round((x - middle[0]) / span * 1.8, 4), round((y - middle[1]) / span * 1.8, 4))
            for key, (x, y) in points.items()}


def _layout(stars):
    """Where each distinct star sits, in [-1, 1] each way (the sky's middle
    at 0), and the lines between them: the walk described in the module's
    notes, then fitted."""
    points = {}
    lines = []
    heading = math.radians(_seed(stars[0]["system"]) % 360) if stars else 0.0
    position = (0.0, 0.0)
    previous = None
    previous_key = None
    longest = max([math.dist((a["x"], a["z"]), (b["x"], b["z"])) for a, b in zip(stars, stars[1:])] + [1.0])
    for star in stars:
        key = star["system"].casefold()
        if key in points:
            # Back to a star already drawn: a line home, and on from there.
            if previous_key and previous_key != key and [previous_key, key] not in lines and [key, previous_key] not in lines:
                lines.append([previous_key, key])
            position = points[key]
            previous, previous_key = star, key
            continue
        parent = previous_key
        if previous is not None:
            seed = _seed(star["system"])
            if len(points) >= 3 and seed % 4 == 0:
                # A branch: from an earlier star, not the last one.
                parent = list(points)[(seed // 4) % (len(points) - 1)]
                position = points[parent]
                heading += math.radians(90 + (seed // 16) % 140)
            dx, dz = star["x"] - previous["x"], star["z"] - previous["z"]
            distance = math.hypot(dx, dz)
            bearing = math.atan2(dz, dx) if distance > 1 else heading
            turn = math.atan2(math.sin(bearing - heading), math.cos(bearing - heading))
            jitter = math.radians((seed % 1600) / 10.0 - 80.0)
            heading += max(-1.75, min(1.75, turn)) * .5 + jitter
            length = .55 + .45 * math.log1p(distance / 100.0) / math.log1p(longest / 100.0)
            # Never onto (or beside) a star already drawn: turn, then reach
            # further, until there's room.
            for attempt in range(16):
                reach = length * (1 + .25 * (attempt // 8))
                candidate = (position[0] + math.cos(heading) * reach, position[1] + math.sin(heading) * reach)
                if all(math.dist(candidate, other) > .5 for other in points.values()):
                    break
                heading += math.radians(43)
            position = candidate
        points[key] = position
        if parent:
            lines.append([parent, key])
        previous, previous_key = star, key
    return _fit(points), lines


def _span_words(seconds):
    days = max(0.0, seconds) / 86400
    if days < 2:
        return "a day"
    if days < 60:
        return f"{round(days)} days"
    if days < 730:
        return f"{round(days / 30.44)} months"
    return f"{round(days / 365.25)} years"


def _elite_date(epoch):
    moment = datetime.fromtimestamp(epoch)
    return f"{moment.strftime('%b')} {moment.year + ELITE_YEARS}"


def constellations(rows, nature="weary", options=None, sessions=(), postcards=(), capsules=()):
    """The sky: constellations oldest first, the last one still growing.
    ``options`` are the page's (``constellation_options``); ``sessions`` (the
    Captain's Log's), ``postcards`` (the album's rows) and ``capsules`` give
    each star the nights behind it (v2, ``deepen``)."""
    options = options or constellation_options({})
    per = options["per"]
    stars = session_stars(rows, options["linger_min"] * 60, every=options["source"] == "every")
    groups, current, seen = [], [], set()
    for star in stars:
        key = star["system"].casefold()
        if key not in seen and len(seen) >= per:
            groups.append(current)
            current, seen = [], set()
        current.append(star)
        seen.add(key)
    if current:
        groups.append(current)
    legends = LEGENDS[LEGEND_NATURE.get(nature, "normal")]
    taken = set()
    sky = []
    for index, group in enumerate(groups):
        points, lines = _map_layout(group) if options["shape"] == "map" else _layout(group)
        distinct = {}
        for star in group:
            entry = distinct.setdefault(star["system"].casefold(), {**star, "dwell": 0, "visits": 0})
            entry["dwell"] += star["dwell"]
            entry["visits"] += 1
        brightest = max(distinct.values(), key=lambda star: star["dwell"])
        seed = _seed(f"{group[0]['system']}#{index}")
        # No two constellations in one sky share a name (v2).
        for step in range(len(ADJECTIVES) * len(NOUNS)):
            turn = seed + step * 7919
            name = f"The {ADJECTIVES[turn % len(ADJECTIVES)]} {NOUNS[(turn // len(ADJECTIVES)) % len(NOUNS)]}"
            if name not in taken:
                break
        taken.add(name)
        span = _span_words(group[-1]["at"] - group[0]["session_start"])
        legend = legends[(seed // 7) % len(legends)].format(
            count=len(distinct), first=group[0]["system"], last=group[-1]["system"], brightest=brightest["system"], span=span)
        sky.append({
            "index": index + 1,
            "name": name,
            "legend": legend,
            "complete": len(distinct) >= per or index < len(groups) - 1,
            "stars": [{"system": star["system"], "x": points[key][0], "y": points[key][1], "star": star["star"],
                       "dwell": star["dwell"], "visits": star["visits"]} for key, star in distinct.items()],
            "lines": lines,
            "keys": list(distinct),
            "from": _elite_date(group[0]["session_start"]),
            "to": _elite_date(group[-1]["at"]),
            "sessions": len(group),
        })
    return deepen(sky, groups, nature, sessions, postcards, capsules)


# -- v2 (5.5.4): the nights behind the stars, and the whole sky ------------------
GREEK = ("α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ")
GALAXY_RADIUS_LY = 70000.0
# What a constellation's nights were mostly spent on, from the Captain's Log.
CHARACTERS = {
    "pathfinder": "A pathfinder's constellation",
    "gardener": "A gardener's constellation",
    "scholar": "A scholar's constellation",
    "survivor": "A survivor's constellation",
    "wanderer": "A wanderer's constellation",
}
LORE = {
    "normal": {
        "pathfinder": "{firsts} first discoveries are written into it: places nobody had named before you.",
        "gardener": "{bio} living things were catalogued under it. It's a greener sky than most.",
        "scholar": "{codex} new entries in your codex came from its nights.",
        "survivor": "The ship was lost {deaths} times while it was drawn. Every star is somewhere you came back from.",
        "wanderer": "{distance} light years of flying hold it together.",
    },
    "weary": {
        "pathfinder": "{firsts} first discoveries live in it. Nobody else will ever know what they looked like first.",
        "gardener": "{bio} living things, catalogued. They didn't ask to be. Neither did I.",
        "scholar": "{codex} codex entries. You learned things. I remembered them for you.",
        "survivor": "We died {deaths} times making it. I'd rather the next one cost less.",
        "wanderer": "{distance} light years. My circuits remember every one of them.",
    },
}


def _session_spans(sessions):
    """Captain's Log sessions as (start, end, session), oldest first."""
    spans = []
    for session in sessions or ():
        if not isinstance(session, dict):
            continue
        start = _epoch(session.get("started"))
        if start is None:
            continue
        end = _epoch(session.get("ended")) or start + 12 * 3600
        spans.append((start, end, session))
    spans.sort(key=lambda span: span[0])
    return spans


def _session_for(spans, moment):
    for start, end, session in spans:
        if start - 60 <= moment <= end + 60:
            return start, end, session
    return None


def _night(span, star, postcards):
    """The session a star was made in: when, how long, what happened."""
    from voidcompass.exploration.flight_log import flown_text
    if span is None:
        start, end, session = star["session_start"], star["at"] + star["dwell"], {}
    else:
        start, end, session = span
    figures = {
        "jumps": int(session.get("jumps") or star.get("jumps") or 0),
        "distance": round(float(session.get("distance_ly") or 0)),
        "firsts": int(session.get("first_discoveries") or 0),
        "mapped": int(session.get("dss_maps") or 0),
        "bio": int(session.get("bio_analyses") or 0),
        "codex": int(session.get("codex") or 0),
        "rare": int(session.get("rare_worlds") or 0),
        "credits": int(session.get("exploration_sales") or 0) + int(session.get("biology_sales") or 0)
                   + int(session.get("trade_profit") or 0),
        "deaths": int(session.get("deaths") or 0),
    }
    highlights = [str(item.get("title") or "") for item in session.get("highlights") or ()
                  if isinstance(item, dict) and item.get("kind") in ("RARE", "CODEX", "BIO") and item.get("title")]
    cards = [{"id": str(card.get("id")), "title": str(card.get("title") or "")} for card in postcards or ()
             if isinstance(card, dict) and start - 60 <= float(card.get("at") or 0) <= end + 180][:4]
    moment = datetime.fromtimestamp(start)
    return {
        "id": str(session.get("started") or ""),
        "date": f"{moment.day} {moment.strftime('%b').upper()} {moment.year + ELITE_YEARS}",
        "flown": flown_text(end - start),
        "ship": str(session.get("ship") or ""),
        "figures": figures,
        "highlights": highlights[:3],
        "postcards": cards,
    }


def _character(totals):
    scores = {
        "pathfinder": totals["firsts"] + totals["mapped"] * 2,
        "gardener": totals["bio"] * 3,
        "scholar": totals["codex"] * 3,
        "survivor": totals["deaths"] * 12 if totals["deaths"] >= 2 else 0,
        "wanderer": totals["distance"] / 400.0,
    }
    kind = max(scores, key=lambda key: scores[key])
    return kind if scores[kind] > 0 else "wanderer"


def _sky_place(items):
    """Where each constellation sits on the sky chart: its bearing from Sol
    (the core straight up), its distance softened so home and the far side
    both fit, then nudged apart so none sit on another."""
    places = []
    for item in items:
        x, z = item["centre"][0], item["centre"][2]
        distance = math.hypot(x, z)
        radius = .08 + .86 * math.log1p(distance / 100.0) / math.log1p(GALAXY_RADIUS_LY / 100.0)
        angle = math.atan2(x, z)
        places.append([math.sin(angle) * radius, math.cos(angle) * radius])
    for _round in range(60):
        moved = False
        for a in range(len(places)):
            for b in range(a + 1, len(places)):
                dx, dy = places[b][0] - places[a][0], places[b][1] - places[a][1]
                gap = math.hypot(dx, dy)
                if gap < .21:
                    if gap < 1e-6:
                        dx, dy, gap = math.cos(b), math.sin(b), 1.0
                    push = (.21 - gap) / 2
                    places[a][0] -= dx / gap * push
                    places[a][1] -= dy / gap * push
                    places[b][0] += dx / gap * push
                    places[b][1] += dy / gap * push
                    moved = True
        for place in places:
            reach = math.hypot(*place)
            if reach > .94:
                place[0], place[1] = place[0] / reach * .94, place[1] / reach * .94
        if not moved:
            break
    return [[round(x, 4), round(y, 4)] for x, y in places]


def deepen(sky, stars_by_constellation, nature="weary", sessions=(), postcards=(), capsules=()):
    """v2: each star's nights, designations and marks; each constellation's
    character, lore, region and place on the sky chart. ``sky`` is what
    ``constellations`` drew; changed in place and returned."""
    from voidcompass.exploration.flight_log import credits_text
    from voidcompass.exploration.galactic_regions import find_region
    spans = _session_spans(sessions)
    sealed = {}
    for capsule in capsules or ():
        if isinstance(capsule, dict) and capsule.get("system"):
            key = str(capsule["system"]).casefold()
            sealed[key] = sealed.get(key, 0) + 1
    lore_lines = LORE[LEGEND_NATURE.get(nature, "normal")]
    for item, group in zip(sky, stars_by_constellation):
        nights_by_key, seen_sessions, totals = {}, set(), dict.fromkeys(
            ("jumps", "distance", "firsts", "mapped", "bio", "codex", "rare", "credits", "deaths"), 0)
        for star in group:
            span = _session_for(spans, star["at"])
            night = _night(span, star, postcards)
            nights_by_key.setdefault(star["system"].casefold(), []).append(night)
            marker = night["id"] or f"{star['session_start']}"
            if marker not in seen_sessions:
                seen_sessions.add(marker)
                for key in totals:
                    totals[key] += night["figures"][key]
        ranked = sorted(item["stars"], key=lambda star: -star["dwell"])
        for rank, star in enumerate(ranked):
            key = star["system"].casefold()
            nights = list(reversed(nights_by_key.get(key, [])))
            star["designation"] = GREEK[rank] if rank < len(GREEK) else str(rank + 1)
            star["nights"] = nights[:5]
            star["capsules"] = sealed.get(key, 0)
            marks = []
            if any(night["figures"]["firsts"] for night in nights):
                marks.append("first")
            if any(night["figures"]["rare"] for night in nights):
                marks.append("rare")
            if any(night["postcards"] for night in nights):
                marks.append("photo")
            if star["capsules"]:
                marks.append("capsule")
            star["marks"] = marks
        positions = [(star["x"], star["y"], star["z"]) for star in group]
        centre = tuple(sum(axis) / len(positions) for axis in zip(*positions)) if positions else (0.0, 0.0, 0.0)
        region = find_region(*centre) if positions else None
        kind = _character(totals)
        item.update(
            centre=[round(value, 1) for value in centre],
            from_sol=round(math.hypot(*centre)),
            region=region[1] if region else "",
            character=kind, epithet=CHARACTERS[kind],
            lore=lore_lines[kind].format(firsts=f"{totals['firsts']:,}", bio=f"{totals['bio']:,}", codex=f"{totals['codex']:,}",
                                         deaths=totals["deaths"], distance=f"{totals['distance']:,}"),
            totals={**totals, "credits_text": credits_text(totals["credits"]),
                    "hours": round(sum(star["dwell"] for star in item["stars"]) / 3600, 1)},
        )
    for item, place in zip(sky, _sky_place(sky)):
        item["place"] = place
    return sky


def almanac(sky):
    """The sky's own figures, for the top of the page."""
    stars = [(item, star) for item in sky for star in item["stars"]]
    if not stars:
        return {}
    visits = {}
    for item, star in stars:
        entry = visits.setdefault(star["system"].casefold(), {"system": star["system"], "visits": 0, "constellations": 0})
        entry["visits"] += star["visits"]
        entry["constellations"] += 1
    pole = max(visits.values(), key=lambda entry: (entry["visits"], entry["constellations"]))
    brightest_item, brightest = max(stars, key=lambda pair: pair[1]["dwell"])
    farthest_item = max(sky, key=lambda item: item.get("from_sol", 0))
    return {
        "constellations": len(sky),
        "complete": sum(1 for item in sky if item["complete"]),
        "stars": len(stars),
        "hours": round(sum(star["dwell"] for _item, star in stars) / 3600, 1),
        "pole_star": pole if pole["visits"] > 1 else None,
        "brightest": {"system": brightest["system"], "hours": round(brightest["dwell"] / 3600, 1), "in": brightest_item["name"]},
        "farthest": {"name": farthest_item["name"], "ly": farthest_item.get("from_sol", 0), "region": farthest_item.get("region", "")},
    }
