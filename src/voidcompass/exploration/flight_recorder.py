"""The Flight Recorder (5.5.10): any past session, played again on the
Galactic Atlas.

A session's tape is everything that happened in it on one clock, in seconds
from when it began: every arrival (where the ship was, so the trail draws
itself jump by jump), the moments that mattered (first discoveries, rare
worlds, Codex entries, organics, footfalls, sales, losses, postcards, field
finds), and the music that was playing, from the music diary. The Atlas
plays the tape back at any speed; quiet stretches can be skipped.
"""
from __future__ import annotations

import bisect
from datetime import datetime, timezone
import time

from voidcompass.exploration.flight_log import ELITE_YEARS, flown_text, watcher_words, credits_text

MAX_ARRIVALS = 4000
MAX_MOMENTS = 900
# The highlights worth a moment on the tape (jumps are the trail itself).
MOMENT_KINDS = {
    "RARE": "rare", "VALUABLE": "valuable", "CODEX": "codex", "BIO": "bio", "FSS": "survey",
    "SALE": "sale", "LOSS": "loss", "PHOTO": "photo", "NOTE": "note", "DEBRIEF": "debrief",
}
FIND_KINDS = {"MaterialDiscovered": "material", "DataScanned": "data", "DatalinkScan": "data", "DatalinkVoucher": "data"}
# A stretch longer than this with nothing happening is "quiet" (skippable).
QUIET_GAP_S = 150


def epoch(stamp):
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def session_id(session):
    return str((session or {}).get("started") or "")


def recorder_sessions(sessions, now=None, rows=()):
    """The sessions the recorder can play, newest first. ``rows`` (the
    travel history's) say where a session began when its log doesn't."""
    now = now if now is not None else time.time()
    timed = sorted(when for when in (epoch(row[0]) for row in rows or () if row) if when is not None)
    names = {epoch(row[0]): str(row[1]) for row in rows or () if row}
    out = []
    for session in sessions or ():
        start = epoch((session or {}).get("started"))
        if start is None:
            continue
        end = epoch(session.get("ended")) or now
        local = datetime.fromtimestamp(start)
        highlights = [item for item in session.get("highlights") or () if isinstance(item, dict)]
        out.append({
            "id": session_id(session),
            "date": local.strftime("%a %d %b %Y").replace(" 0", " "),
            "elite_date": f"{local.day} {local.strftime('%b').upper()} {local.year + ELITE_YEARS}",
            "time": local.strftime("%H:%M"),
            "flown": flown_text(end - start),
            "seconds": round(end - start),
            "open": not session.get("ended"),
            "jumps": int(session.get("jumps") or 0),
            "distance": round(float(session.get("distance_ly") or 0), 1),
            "firsts": int(session.get("first_discoveries") or 0),
            "start_system": str(session.get("start_system") or _where_before(timed, names, start)),
            "end_system": str(session.get("end_system") or session.get("start_system") or ""),
            "moments": sum(1 for item in highlights if str(item.get("kind")) in MOMENT_KINDS),
        })
    return out


def _where_before(timed, names, moment):
    index = bisect.bisect_left(timed, moment) - 1
    return names.get(timed[index], "") if index >= 0 else ""


def _thin(rows, limit):
    if len(rows) <= limit:
        return rows
    step = (len(rows) - 1) / float(limit - 1)
    return [rows[round(index * step)] for index in range(limit)]


def tape(session, rows=(), finds=(), postcards=(), music=(), bodies=(), nature="weary", now=None):
    """One session's tape. ``rows`` are the travel history's (oldest first),
    ``finds`` the deep survey's field discoveries, ``postcards`` the album's
    rows, ``music`` the diary's plays, ``bodies`` the first discoveries and
    footfalls scanned in it ({name, system, when, value, kind})."""
    session = session or {}
    start = epoch(session.get("started"))
    if start is None:
        return None
    now = now if now is not None else time.time()
    end = epoch(session.get("ended")) or now
    timed = [(epoch(row[0]), row) for row in rows or () if row]
    timed = [(when, row) for when, row in timed if when is not None]
    timed.sort(key=lambda item: item[0])
    times = [when for when, _row in timed]
    first, last = bisect.bisect_left(times, start), bisect.bisect_right(times, end)
    # Where the session began: the arrival before it.
    if first > 0:
        first -= 1
    arrivals = []
    for when, row in _thin(timed[first:last], MAX_ARRIVALS):
        arrivals.append({"t": round(max(0.0, when - start), 1), "system": str(row[1]),
                         "pos": [round(float(row[2]), 3), round(float(row[3]), 3), round(float(row[4]), 3)],
                         "star": str(row[5] or ""), "jump": round(float(row[6] or 0), 2),
                         "carrier": len(row) > 7 and row[7] == "C"})
    arrival_times = [arrival["t"] for arrival in arrivals]

    def where(seconds):
        index = bisect.bisect_right(arrival_times, seconds) - 1
        return max(0, index)

    moments = []

    def add(seconds, kind, title, detail="", **extra):
        if seconds is None or not -60 <= seconds <= end - start + 120:
            return
        seconds = max(0.0, seconds)
        moments.append({"t": round(seconds, 1), "kind": kind, "title": str(title or "")[:160],
                        "detail": str(detail or "")[:200], "at": where(seconds), **extra})

    for item in session.get("highlights") or ():
        if not isinstance(item, dict):
            continue
        kind = MOMENT_KINDS.get(str(item.get("kind") or ""))
        when = epoch(item.get("timestamp"))
        if kind and when is not None:
            add(when - start, kind, item.get("title"), item.get("detail"))
    for body in bodies or ():
        when = float(body.get("when") or 0)
        if when:
            title = "First footfall" if body.get("kind") == "footfall" else "First discovery"
            add(when - start, "first" if body.get("kind") != "footfall" else "footfall", title,
                body.get("name") or "", value=int(body.get("value") or 0))
    for find in finds or ():
        if not isinstance(find, dict):
            continue
        when = epoch(find.get("timestamp"))
        if when is not None and start <= when <= end:
            add(when - start, FIND_KINDS.get(str(find.get("event") or ""), "find"), find.get("title") or "Field find",
                " · ".join(part for part in (str(find.get("system") or ""), str(find.get("body") or "")) if part))
    for card in postcards or ():
        when = float(card.get("at") or 0)
        if start <= when <= end + 120:
            add(when - start, "postcard", card.get("title") or "Postcard", "", postcard=str(card.get("id") or ""))
    moments.sort(key=lambda moment: moment["t"])
    moments = moments[:MAX_MOMENTS]

    tracks = []
    for row in music or ():
        when = float(row[0])
        if when <= end:
            tracks.append({"t": round(max(0.0, when - start), 1), "track_id": str(row[1]), "title": str(row[2] or ""),
                           "artist": str(row[3] or "")})

    # Quiet stretches: long gaps with no arrival and no moment, which the
    # player can skip over.
    beats = sorted({0.0, round(end - start, 1), *arrival_times, *(moment["t"] for moment in moments)})
    quiet = [[a + 30, b - 30] for a, b in zip(beats, beats[1:]) if b - a > QUIET_GAP_S]

    local = datetime.fromtimestamp(start)
    credits = int(session.get("exploration_sales") or 0) + int(session.get("biology_sales") or 0) + int(
        session.get("trade_profit") or 0)
    facts = {"id": session_id(session), "flown": flown_text(end - start),
             "start": str(session.get("start_system") or (arrivals[0]["system"] if arrivals else "") or "somewhere"),
             "end": str(session.get("end_system") or session.get("start_system") or "somewhere"),
             "firsts": f"{int(session.get('first_discoveries') or 0):,}",
             "firsts_count": int(session.get("first_discoveries") or 0),
             "distance": f"{float(session.get('distance_ly') or 0):,.0f}",
             "distance_value": float(session.get("distance_ly") or 0),
             "credits": credits_text(credits), "credits_value": credits,
             "deaths": int(session.get("deaths") or 0), "rare_text": "", "rare": "", "star": ""}
    return {
        "id": session_id(session),
        "date": local.strftime("%A %d %B %Y").replace(" 0", " "),
        "elite_date": f"{local.day} {local.strftime('%b').upper()} {local.year + ELITE_YEARS}",
        "began": local.strftime("%H:%M"),
        "start_epoch": start,
        "length": round(end - start, 1),
        "open": not session.get("ended"),
        "ship": str(session.get("ship") or ""),
        "arrivals": arrivals,
        "moments": moments,
        "music": tracks,
        "quiet": quiet,
        "figures": {"jumps": int(session.get("jumps") or 0), "distance": round(float(session.get("distance_ly") or 0), 1),
                    "firsts": facts["firsts_count"], "codex": int(session.get("codex") or 0),
                    "bio": int(session.get("bio_analyses") or 0), "credits": credits,
                    "deaths": facts["deaths"]},
        "words": watcher_words(facts, nature),
    }
