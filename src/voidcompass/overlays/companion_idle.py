"""Quiet-watch subjects shared by the officer-style companions.

Only recorded facts: learned habits, kept postcards, saved service moments
and story chapters the commander has actually heard.
"""
from datetime import datetime
import zlib

from voidcompass.overlays import watcher_habits, watcher_postcards


RECALL_REST_S = 30 * 86400
FACT_TOPICS = {"cmdr_record", "cmdr_power", "cmdr_squadron", "cmdr_carrier"}
RESTS = {"idle_postcard": watcher_postcards.RECALL_REST_S, "idle_moment": 6 * 3600,
         "aster_recall": 6 * 3600, "aster_lore_recall": 6 * 3600,
         "idle_aster_lore": 3 * 3600, "long_session": 3600}
ACTIVITIES = {"an explorer": "exploration", "a trader": "trade", "a miner": "mining",
              "a fighter": "combat", "a courier": "courier work"}


def casual(topic):
    return (topic.startswith("idle_")
            or topic in {"quiet", "aster_after", "aster_recall", "aster_lore_recall", "long_session"}
            or topic.startswith("habit_") and topic != "habit_milestone")


def _key(kind, *values):
    value = repr((kind, *values)).encode("utf-8")
    return f"{kind}:{zlib.crc32(value):08x}"


def _fields(memory, key, at, now):
    from voidcompass.overlays.watcher_mind import when_text

    previous = memory.get("aster_idle_recalled", {}).get(key)
    if previous is not None and now - previous < RECALL_REST_S:
        return None
    try:
        when = when_text(datetime.fromtimestamp(float(at)).astimezone().isoformat(), now)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    return {"_recall": key, "when": when, "When": when[:1].upper() + when[1:]} if when else None


def choices(memory, rng, now, story):
    """Only use recorded facts. Recall identities rest across wording/restarts."""
    out = watcher_habits.choices(memory, 0, rng)
    for topic, fields in out:
        if topic == "habit_style":
            fields["style"] = ACTIVITIES.get(fields["style"], fields["style"])
    heard = story.told(memory)
    if story.begun(memory):
        out.append(("idle_aster_lore", {}))
    for index in story.complete_chapters(memory):
        at = max(heard[key] for key in story.chapter_ids(index))
        if now - at >= 86400:
            fields = _fields(memory, _key("chapter", index), at, now)
            if fields:
                out.append(("aster_lore_recall", {**fields, **story.recall_fields(index)}))
    for row in memory.get("postcards") or ():
        if not isinstance(row, (list, tuple)) or len(row) < 2 or not row[1]:
            continue
        try:
            old = now - float(row[0]) >= watcher_postcards.RECALL_AFTER_S
        except (TypeError, ValueError):
            continue
        fields = _fields(memory, _key("postcard", *row[:2]), row[0], now) if old else None
        if fields:
            out.append(("idle_postcard", {**fields, "place": str(row[1])}))
    for row in memory.get("aster_moments") or ():
        if not isinstance(row, dict) or not row.get("system"):
            continue
        try:
            old = now - float(row.get("at", now)) >= 2 * 86400
        except (TypeError, ValueError):
            continue
        event, system, station = row.get("event"), row["system"], row.get("station")
        # Several visits to one place form one memory, not a bank of repeatable announcements.
        fields = _fields(memory, _key("service", event, system, station), row.get("at"), now) if old else None
        if not fields:
            continue
        if event == "FSDJump":
            out.append(("aster_recall", {**fields, "system": system}))
            continue
        about = {"Docked": f"our docking at {station} in {system}" if station else "",
                 "MissionCompleted": f"a completed mission in {system}",
                 "SellExplorationData": f"the survey data we sold in {system}",
                 "MultiSellExplorationData": f"the survey data we sold in {system}",
                 "SellOrganicData": f"the biological data we sold in {system}"}.get(event)
        if about:
            out.append(("idle_moment", {**fields, "about": about, "About": about[:1].upper() + about[1:]}))
    rng.shuffle(out)
    return out
