"""Profile-local reminders derived only from the commander's journal evidence.

The board is deliberately a list of unfinished observations, not a catalogue
of predicted discoveries.  Existing rows are retained when a later journal
snapshot is sparse; they are cleared only when that body is observed complete.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from voidcompass.exploration.deep_survey import HIGH_VALUE_WORLDS, item_value


MAX_ENTRIES = 500
MAX_DISMISSED = 1500


def _integer(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _stamp(value):
    return str(value or datetime.now(timezone.utc).isoformat(timespec="seconds"))[:40]


def _coords(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return [float(axis) for axis in value]
    except (TypeError, ValueError):
        return None


def _body_key(item):
    body_id = item.get("body_id")
    if body_id is not None:
        return f"body:{body_id}"
    return "name:" + str(item.get("name") or item.get("full_name") or "").casefold()


def _analysed_count(item):
    scans = item.get("organic_scans") or {}
    rows = scans.values() if isinstance(scans, dict) else scans
    analysed = sum(
        1 for row in rows if isinstance(row, dict) and (
            row.get("is_complete")
            or str(row.get("scan_type") or "").casefold() == "analyse"
        )
    )
    return max(_integer(item.get("organic_complete_count")), analysed)


def _scanned_count(scan_items, scanned):
    known = {
        _body_key(item) for item in scan_items or ()
        if isinstance(item, dict) and (item.get("body_id") is not None or item.get("name") or item.get("full_name"))
    }
    return max(_integer(scanned), len(known))


def _pin_active(item, pinned):
    if not pinned:
        return False
    if not isinstance(item, dict):
        return True
    bio_total = _integer(item.get("bio_count"))
    return not bool(
        (item.get("dss_complete") or item.get("was_mapped"))
        and _analysed_count(item) >= bio_total
        and not _integer(item.get("geo_count"))
    )


def unfinished_entries(
    system, scan_items, survey_state=None, *, scanned=0, total=0,
    total_confirmed=False, fss_all_bodies=False, visited_at=None, coords=None,
    body_signals=None,
):
    """Describe unfinished work supported by the current journal snapshot."""
    system = str(system or "").strip()[:140]
    if not system or system in {"---", "Unknown"}:
        return []
    state = survey_state if isinstance(survey_state, dict) else {}
    pinned = {str(value) for value in state.get("pinned") or ()}
    skipped = {str(value) for value in state.get("skipped") or ()}
    completed = {str(value) for value in state.get("completed") or ()}
    system_key = system.casefold()
    stamp = _stamp(visited_at)
    position = _coords(coords)
    if position == [0.0, 0.0, 0.0] and system.casefold() != "sol":
        # The runtime uses the origin as an unknown-coordinate fallback.  Sol
        # is the only legitimate zero vector in this coordinate system.
        position = None
    rows = []
    known_scanned = _scanned_count(scan_items, scanned)
    if total_confirmed and not fss_all_bodies and _integer(total) > known_scanned:
        missing = _integer(total) - known_scanned
        rows.append({
            "id": f"{system_key}|fss", "system": system, "body": "",
            "body_key": "fss", "reasons": [
                f"{missing} FSS {'bodies' if missing != 1 else 'body'} unresolved"
            ], "last_visited": stamp, "source": "journal", "coords": position,
        })
    scanned_items = [item for item in scan_items or () if isinstance(item, dict)]
    scanned_keys = {_body_key(item) for item in scanned_items}
    signal_only = []
    for body_id, signals in (body_signals if isinstance(body_signals, dict) else {}).items():
        if not isinstance(signals, dict) or not _integer(signals.get("bio")):
            continue
        body_name = str(signals.get("body_name") or "").strip()
        if not body_name or f"body:{body_id}" in scanned_keys:
            continue
        signal_only.append({
            "body_id": body_id, "name": body_name, "bio_count": signals.get("bio"),
            "dss_complete": bool(signals.get("dss_complete")), "_signal_only": True,
        })
    for item in [*scanned_items, *signal_only]:
        if not isinstance(item, dict) or item.get("is_star") or item.get("star_type"):
            continue
        body = str(item.get("name") or item.get("full_name") or "").strip()[:180]
        if not body:
            continue
        key = _body_key(item)
        if key in skipped or key in completed:
            continue
        reasons = []
        pin_active = _pin_active(item, key in pinned)
        if pin_active:
            reasons.append("Pinned survey target")
        bio_total = _integer(item.get("bio_count"))
        bio_done = min(bio_total, _analysed_count(item))
        if bio_total > bio_done:
            reasons.append(f"Biology {bio_done}/{bio_total} analysed")
        valuable = bool(
            item.get("terraformable")
            or str(item.get("planet_class") or item.get("class") or "") in HIGH_VALUE_WORLDS
            or item_value(item) >= 250_000
        )
        if valuable and not (item.get("dss_complete") or item.get("was_mapped")):
            reasons.append("Valuable world not DSS mapped")
        if not reasons:
            continue
        rows.append({
            "id": f"{system_key}|{key}", "system": system, "body": body,
            "body_key": key, "reasons": reasons, "last_visited": stamp,
            "source": "journal + pin" if pin_active else "journal signals" if item.get("_signal_only") else "journal",
            "coords": position,
            "work": {
                "pinned": pin_active,
                "bio_total": bio_total if bio_total > bio_done else 0,
                "bio_done": bio_done,
                "dss": bool(valuable and not (item.get("dss_complete") or item.get("was_mapped"))),
            },
        })
    return rows


def empty_state():
    return {"version": 1, "entries": [], "dismissed": []}


def read_state(path):
    """Read a profile board; a damaged file cannot block the cockpit."""
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError, TypeError):
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()
    entries = [row for row in data.get("entries") or () if isinstance(row, dict) and row.get("id") and row.get("system")]
    entries.sort(key=lambda row: (str(row.get("last_visited") or ""), str(row.get("system") or "")), reverse=True)
    dismissed = [str(value) for value in data.get("dismissed") or () if value]
    return {
        "version": 1, "entries": entries[:MAX_ENTRIES],
        "dismissed": dismissed[-MAX_DISMISSED:],
    }


def write_state(path, state):
    """Atomically persist the bounded board in the commander's profile."""
    temp_path = str(path) + ".tmp"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)
        return True
    except OSError:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return False


def reconcile_state(
    state, system, scan_items, survey_state=None, *, scanned=0, total=0,
    total_confirmed=False, fss_all_bodies=False, visited_at=None, coords=None,
    departure=False, body_signals=None,
):
    """Merge fresh evidence without treating absent replay data as completion."""
    old = state if isinstance(state, dict) else empty_state()
    system = str(system or "").strip()[:140]
    if not system or system in {"---", "Unknown"}:
        return old
    candidates = unfinished_entries(
        system, scan_items, survey_state, scanned=scanned, total=total,
        total_confirmed=total_confirmed, fss_all_bodies=fss_all_bodies,
        visited_at=visited_at, coords=coords, body_signals=body_signals,
    )
    candidate_by_id = {row["id"]: row for row in candidates}
    dismissed = set(old.get("dismissed") or ())
    scanned_by_key = {
        _body_key(item): item for item in scan_items or ()
        if isinstance(item, dict) and (item.get("body_id") is not None or item.get("name") or item.get("full_name"))
    }
    signals_by_key = {
        f"body:{body_id}": signals for body_id, signals in
        (body_signals if isinstance(body_signals, dict) else {}).items()
        if isinstance(signals, dict)
    }
    queue_state = survey_state if isinstance(survey_state, dict) else {}
    pinned = {str(value) for value in queue_state.get("pinned") or ()}
    skipped = {str(value) for value in queue_state.get("skipped") or ()}
    completed = {str(value) for value in queue_state.get("completed") or ()}
    system_key = system.casefold()
    existing = {}
    old_ids = set()
    for row in old.get("entries") or ():
        if not isinstance(row, dict) or not row.get("id") or not row.get("system"):
            continue
        row_id = str(row["id"])
        old_ids.add(row_id)
        if row_id in dismissed:
            continue
        if str(row["system"]).casefold() != system_key:
            existing[row_id] = row
            continue
        body_key = str(row.get("body_key") or "")
        candidate = candidate_by_id.get(row_id)
        if body_key == "fss":
            if fss_all_bodies or (
                total_confirmed and _integer(total)
                and _scanned_count(scan_items, scanned) >= _integer(total)
            ):
                continue
            updated = dict(candidate or row)
        else:
            if body_key in skipped or body_key in completed:
                continue
            item = scanned_by_key.get(body_key)
            signals = signals_by_key.get(body_key) or {}
            prior_work = row.get("work") if isinstance(row.get("work"), dict) else {}
            current_work = candidate.get("work") if isinstance(candidate, dict) else {}
            bio_total = max(
                _integer(prior_work.get("bio_total")),
                _integer(current_work.get("bio_total")),
                _integer(item.get("bio_count")) if item else 0,
                _integer(signals.get("bio")),
            )
            bio_done = max(
                _integer(prior_work.get("bio_done")),
                _integer(current_work.get("bio_done")),
                _analysed_count(item) if item else 0,
            )
            dss_required = bool(prior_work.get("dss") or current_work.get("dss"))
            if (item and (item.get("dss_complete") or item.get("was_mapped"))) or signals.get("dss_complete"):
                dss_required = False
            pin_active = bool(body_key in pinned and not (
                item and (item.get("dss_complete") or item.get("was_mapped"))
                and bio_done >= bio_total and not _integer(item.get("geo_count"))
            ))
            reasons = []
            if pin_active:
                reasons.append("Pinned survey target")
            if bio_total > bio_done:
                reasons.append(f"Biology {bio_done}/{bio_total} analysed")
            if dss_required:
                reasons.append("Valuable world not DSS mapped")
            if not reasons:
                # Old v1 rows without structured work may still be useful on a
                # sparse replay; do not infer completion merely from absence.
                if not prior_work and not candidate and not item:
                    updated = dict(row)
                else:
                    continue
            else:
                updated = dict(candidate or row)
                updated["reasons"] = reasons
                updated["work"] = {
                    "pinned": pin_active, "bio_total": bio_total if bio_total > bio_done else 0,
                    "bio_done": bio_done, "dss": dss_required,
                }
                if item and (item.get("name") or item.get("full_name")):
                    updated["body"] = str(item.get("name") or item.get("full_name"))[:180]
                updated["source"] = (
                    "journal + pin" if pin_active else
                    "journal signals" if not item and (signals or row.get("source") == "journal signals")
                    else "journal"
                )
        if departure:
            updated["last_visited"] = _stamp(visited_at)
            updated["coords"] = candidate.get("coords") if candidate and candidate.get("coords") is not None else row.get("coords")
        else:
            updated["last_visited"] = row.get("last_visited") or updated.get("last_visited")
            updated["coords"] = row.get("coords") or updated.get("coords")
        existing[row_id] = updated
    for row_id, row in candidate_by_id.items():
        if row_id in dismissed or row_id in old_ids or not departure:
            continue
        existing[row_id] = row
    entries = list(existing.values())
    entries.sort(key=lambda row: (str(row.get("last_visited") or ""), str(row.get("system") or "")), reverse=True)
    return {"version": 1, "entries": entries[:MAX_ENTRIES], "dismissed": list(old.get("dismissed") or ())[-MAX_DISMISSED:]}


def dismiss_entry(state, entry_id):
    """Dismiss a saved target without allowing the next refresh to revive it."""
    entry_id = str(entry_id or "")
    if not entry_id or not any(row.get("id") == entry_id for row in state.get("entries") or ()):
        return state
    dismissed = [value for value in state.get("dismissed") or () if value != entry_id]
    dismissed.append(entry_id)
    return {
        "version": 1,
        "entries": [row for row in state.get("entries") or () if row.get("id") != entry_id],
        "dismissed": dismissed[-MAX_DISMISSED:],
    }
