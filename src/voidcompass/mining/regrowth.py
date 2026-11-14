"""Worked-out deposits, and when to look at them again.

How fast a Rhino deposit grows back isn't published, and it differs from
ground to ground, so nothing here guesses. Each deposit keeps two dates:

- ``depleted_at``: when it was first worked out (UTC, ISO);
- ``rechecks``: each time you went back, found it still empty and said so.

And a few rules over them:

- worked out, it stays depleted for HOLD_DAYS;
- after that a look is due ("recheck due");
- looked at and still empty: the first date stays, the look is kept, and the
  mark comes off RECHECK_DAYS after that look;
- its own commodity refined there again: it has grown back, and the next time
  it's worked out is a new first date.

Plain functions of a deposit row and a clock, so the whole timeline can be
checked day by day."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

HOLD_DAYS = 14
RECHECK_DAYS = 7
DAY = 86400.0
# This close to a deposit due a look, you're told.
DUE_NEAR_M = 100.0


def stamp(epoch):
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def when_of(text):
    """A stored date as epoch seconds, or None."""
    text = str(text or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def depleted(row):
    return bool((row or {}).get("depleted")) or str((row or {}).get("amount") or "") == "Depleted"


def looks(row):
    """Each look that found it still empty, oldest first, as epoch seconds."""
    return sorted(at for at in (when_of(part) for part in str((row or {}).get("rechecks") or "").split(";")) if at)


def standing(row, now=None):
    """Where a deposit is in its timeline:

    ``state`` intact, unknown (worked out, no date), fresh (under HOLD_DAYS),
    due (a look is due), waiting (looked at; the mark comes off later) or
    expired (the mark is due off); ``age_days``, ``off_in_days`` and ``text``,
    the line to show."""
    now = time.time() if now is None else now
    out = {"state": "intact", "age_days": None, "off_in_days": None, "looks": 0, "due": False, "text": ""}
    if not depleted(row):
        return out
    first = when_of((row or {}).get("depleted_at"))
    if first is None:
        out.update(state="unknown", text="worked out · since when isn't known")
        return out
    age = max(0, int((now - first) // DAY))
    seen = [at for at in looks(row) if at >= first]
    out.update(age_days=age, looks=len(seen))
    if seen:
        left = seen[-1] + RECHECK_DAYS * DAY - now
        if left <= 0:
            out.update(state="expired", text=f"still empty at {int((seen[-1] - first) // DAY)} days · mark due off")
        else:
            days = int(math.ceil(left / DAY))
            out.update(state="waiting", off_in_days=days,
                       text=f"worked out {age} days ago · checked · mark off in {days} day{'s' if days != 1 else ''}")
        return out
    if age >= HOLD_DAYS:
        out.update(state="due", due=True, text=f"worked out {age} days ago · recheck due")
        return out
    out.update(state="fresh", text="worked out today" if age == 0 else
               f"worked out {age} day{'s' if age != 1 else ''} ago · look again in {HOLD_DAYS - age}")
    return out


def mined_out_changes(row, now=None):
    """What marking a deposit worked out writes, and what that was:

    "new" (first time, or since it grew back: a new first date), "recheck" (it
    was due a look and is still empty: the look is kept) or "same" (marked
    again before a look was due: nothing moves)."""
    now = time.time() if now is None else now
    first = when_of((row or {}).get("depleted_at")) if depleted(row) else None
    if first is None:
        return {"amount": "Depleted", "depleted": 1, "depleted_at": stamp(now), "rechecks": ""}, "new"
    seen = [at for at in looks(row) if at >= first]
    due = (seen[-1] + RECHECK_DAYS * DAY <= now) if seen else (now - first) >= HOLD_DAYS * DAY
    if due:
        seen.append(now)
    return ({"amount": "Depleted", "depleted": 1, "depleted_at": stamp(first),
             "rechecks": ";".join(stamp(at) for at in seen)}, "recheck" if due else "same")


def regrown_changes(row, now=None):
    """It has grown back: the mark off, the amount unread until it's read
    again, the dates cleared; the note keeps what it was."""
    info = standing(row, now)
    was = f" after {info['age_days']} days" if info["age_days"] is not None else ""
    note = str((row or {}).get("notes") or "").strip()
    line = f"Grown back{was} ({datetime.now().strftime('%d %b %Y')})"
    return {"amount": "", "depleted": 0, "depleted_at": "", "rechecks": "",
            "notes": f"{note}\n{line}".strip()[:4000]}


def expiry_changes(row, now=None):
    """The mark coming off a deposit looked at RECHECK_DAYS ago, or None."""
    info = standing(row, now)
    if info["state"] != "expired":
        return None
    return regrown_changes(row, now) | {"notes": (f"{str(row.get('notes') or '').strip()}\n"
                                                    f"Depleted mark came off a week after the last look").strip()[:4000]}
