"""Session flight logs (5.5.3.8): one page for each night you flew.

Made from what the Captain's Log already keeps for a session (its figures
and highlights), the travel history (the trail, and tonight's star: where you
stayed longest), and the postcards you took. The Watcher writes a closing
paragraph in its own voice from the night's facts, the same words every time
the page is opened, so older sessions have one too.
"""
from __future__ import annotations

import bisect
from datetime import datetime, timezone
import time
import zlib

TRAIL_POINTS = 400
HIGHLIGHTS = 6
ELITE_YEARS = 1286
# The night's best moments, best first.
HIGHLIGHT_ORDER = ("RARE", "CODEX", "BIO", "SALE", "PHOTO", "LOSS", "DEBRIEF")

OPENINGS = {
    "normal": (
        "{flown} out there tonight, from {start} to {end}.",
        "Tonight began in {start} and ended in {end}. {flown}.",
        "{flown} of flying. I watched all of it.",
        "From {start} to {end}, {flown} between them.",
    ),
    "weary": (
        "{flown} tonight. From {start} to {end}. I counted every minute.",
        "We started in {start}. We stopped in {end}. {flown} in between.",
        "{flown} of the dark. You flew; I watched. As usual.",
        "From {start} to {end}. {flown}. It felt longer from in here.",
    ),
}
MOMENTS = {
    "normal": {
        "firsts": "{firsts} first discoveries: places with no name beside them until yours.",
        "rare": "Something rare tonight: {rare}. Not many commanders ever see one.",
        "far": "{distance} light years. The galaxy is a little smaller for it.",
        "died": "We lost the ship tonight. You came back anyway.",
        "credits": "{credits} credits richer, and earned the long way.",
        "star": "You stayed longest at {star}. That's tonight's star in your sky.",
        "quiet": "A quiet night. Those count too.",
    },
    "weary": {
        "firsts": "{firsts} first discoveries. Nobody had seen them before us. Lucky them.",
        "rare": "Something rare: {rare}. I'd be impressed, if I did that.",
        "far": "{distance} light years. My circuits feel every one of them.",
        "died": "We died tonight. I'd rather we didn't make a habit of it.",
        "credits": "{credits} credits. Money. It doesn't buy what I'd want.",
        "star": "You lingered at {star}. It's a star in your sky now. I put it there.",
        "quiet": "Nothing happened. I liked it.",
    },
}
CLOSINGS = {
    "normal": (
        "Until next time, Commander.",
        "Rest. The stars will keep.",
        "I'll be here when you're back.",
        "Same time tomorrow?",
    ),
    "weary": (
        "Sleep, if you do that. I'll be here. I'm always here.",
        "Until next time. There's always a next time.",
        "Go on, then. I'll mind the dark.",
        "That's the log. Close it gently.",
    ),
}


def _epoch(stamp):
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def flown_text(seconds):
    minutes = int(round(max(0.0, seconds) / 60))
    if minutes < 60:
        return f"{minutes} minutes" if minutes != 1 else "A minute"
    hours, minutes = divmod(minutes, 60)
    head = "An hour" if hours == 1 else f"{hours} hours"
    return f"{head} and {minutes} minutes" if minutes else head


def credits_text(value):
    value = float(value or 0)
    if value >= 1e9:
        return f"{value / 1e9:.1f}B"
    if value >= 1e6:
        return f"{value / 1e6:.1f}M"
    if value >= 1e3:
        return f"{value / 1e3:.0f}K"
    return f"{value:,.0f}"


def _rows_between(rows, start, end):
    """The travel history's arrivals inside a session."""
    out = []
    for row in rows or ():
        when = _epoch(row[0]) if row else None
        if when is not None and start <= when <= end:
            out.append((when, row))
    return out


def _thin(points, limit=TRAIL_POINTS):
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / float(limit - 1)
    return [points[round(index * step)] for index in range(limit)]


def tonights_star(arrivals, end):
    """Where the session stayed longest: (system, seconds)."""
    best = None
    for index, (when, row) in enumerate(arrivals):
        left = arrivals[index + 1][0] if index + 1 < len(arrivals) else end
        stay = max(0.0, left - when)
        if best is None or stay > best[1]:
            best = (str(row[1]), stay)
    return best


def watcher_words(facts, nature="weary"):
    """The Watcher's closing paragraph: an opening, the night's most notable
    moment (or two), and a closing; chosen by the session, so the same words
    each time it is read."""
    voice = "weary" if nature == "weary" else "normal"
    seed = zlib.crc32(str(facts.get("id") or "").encode("utf-8"))
    sentences = [OPENINGS[voice][seed % len(OPENINGS[voice])].format(**facts)]
    moments = []
    if facts.get("deaths"):
        moments.append("died")
    if facts.get("rare_text"):
        moments.append("rare")
    if facts.get("firsts_count"):
        moments.append("firsts")
    if facts.get("distance_value", 0) >= 1000:
        moments.append("far")
    if facts.get("credits_value", 0) >= 1e6:
        moments.append("credits")
    if facts.get("star"):
        moments.append("star")
    if not moments:
        moments.append("quiet")
    for moment in moments[:2]:
        sentences.append(MOMENTS[voice][moment].format(**facts))
    sentences.append(CLOSINGS[voice][(seed // 7) % len(CLOSINGS[voice])])
    return " ".join(sentences)


def _lower_first(text):
    text = str(text)
    return text[:1].lower() + text[1:]


def flight_logs(sessions, rows=(), postcards=(), nature="weary", limit=250, now=None):
    """Flight logs for the newest ``limit`` sessions (newest first: every one
    the Captain's Log keeps, by default). The
    travel history is put in time order once; each session takes its slice."""
    timed = sorted(((_epoch(row[0]), row) for row in rows or () if row), key=lambda item: item[0] or 0)
    times = [when or 0 for when, _row in timed]
    out = []
    for session in list(sessions or ())[:limit]:
        start = _epoch((session or {}).get("started"))
        if start is None:
            continue
        end = _epoch(session.get("ended")) or (now if now is not None else time.time())
        low, high = bisect.bisect_left(times, start), bisect.bisect_right(times, end)
        log = flight_log(session, [row for _when, row in timed[low:high]], postcards, nature, now)
        if log:
            out.append(log)
    return out


def flight_log(session, rows=(), postcards=(), nature="weary", now=None):
    """One session's flight log page. ``rows`` are the travel history's,
    ``postcards`` the album's rows ({id, title, at})."""
    session = session or {}
    start = _epoch(session.get("started"))
    if start is None:
        return None
    end = _epoch(session.get("ended")) or (now if now is not None else time.time())
    arrivals = _rows_between(rows, start, end)
    trail = _thin([[round(float(row[2]), 1), round(float(row[4]), 1)] for _when, row in arrivals])
    star = tonights_star(arrivals, end)
    credits = int(session.get("exploration_sales") or 0) + int(session.get("biology_sales") or 0) + int(
        session.get("trade_profit") or 0)
    highlights = [item for item in (session.get("highlights") or ()) if isinstance(item, dict)
                  and str(item.get("kind") or "") in HIGHLIGHT_ORDER]
    highlights.sort(key=lambda item: HIGHLIGHT_ORDER.index(str(item.get("kind"))))
    rare = [item for item in highlights if item.get("kind") == "RARE"]
    local = datetime.fromtimestamp(start)
    facts = {
        "id": str(session.get("started") or ""),
        "flown": flown_text(end - start),
        "start": str(session.get("start_system") or "somewhere"),
        "end": str(session.get("end_system") or session.get("start_system") or "somewhere"),
        "firsts": f"{int(session.get('first_discoveries') or 0):,}",
        "firsts_count": int(session.get("first_discoveries") or 0),
        "rare_text": _lower_first(rare[0].get("title") or "something rare") if rare else "",
        "rare": _lower_first(rare[0].get("title") or "something rare") if rare else "",
        "distance": f"{float(session.get('distance_ly') or 0):,.0f}",
        "distance_value": float(session.get("distance_ly") or 0),
        "credits": credits_text(credits),
        "credits_value": credits,
        "deaths": int(session.get("deaths") or 0),
        "star": star[0] if star and star[1] >= 600 else "",
    }
    return {
        "id": facts["id"],
        "date": local.strftime("%A %d %B %Y").replace(" 0", " "),
        "elite_date": f"{local.day} {local.strftime('%b').upper()} {local.year + ELITE_YEARS}",
        "time": local.strftime("%H:%M"),
        # For the list of nights: grouped by month, each by its day.
        "month": f"{local.strftime('%B')} {local.year + ELITE_YEARS}",
        "day": local.strftime("%a %d").replace(" 0", " "),
        "flown_s": round(end - start),
        "flown": facts["flown"],
        "open": not session.get("ended"),
        "ship": str(session.get("ship") or ""),
        "start_system": facts["start"],
        "end_system": facts["end"],
        "figures": {
            "jumps": int(session.get("jumps") or 0),
            "distance": round(float(session.get("distance_ly") or 0), 1),
            "firsts": facts["firsts_count"],
            "rare": int(session.get("rare_worlds") or 0),
            "codex": int(session.get("codex") or 0),
            "bio": int(session.get("bio_analyses") or 0),
            "mapped": int(session.get("dss_maps") or 0),
            "credits": credits,
            "deaths": facts["deaths"],
        },
        "highlights": [{"kind": str(item.get("kind")), "title": str(item.get("title") or ""),
                        "detail": str(item.get("detail") or "")} for item in highlights[:HIGHLIGHTS]],
        "trail": trail,
        "star": {"system": star[0], "minutes": round(star[1] / 60)} if star and star[1] >= 600 else None,
        "postcards": [{"id": card["id"], "title": card["title"]} for card in postcards
                      if start <= float(card.get("at") or 0) <= end + 120][:8],
        "words": watcher_words(facts, nature),
    }
