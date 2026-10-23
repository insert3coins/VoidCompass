"""Dev-only (never released): what a commander has heard of the Watcher's story
at a point in time, and what comes next.

    python tools/watcher_timeline.py --hours 1200 --days 400 --sessions 90 --echoes all --road open

Days are real days since the first passage; passages are assumed told as soon
as they unlock (the fastest a commander could hear them).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voidcompass.overlays import watcher_lore  # noqa: E402


def simulate(hours, days, sessions, echoes, road, places):
    start = 1_700_000_000.0
    memory = {"lore": [], "echoes": {name: [1, start] for name in echoes}, "places": {name: [1, start] for name in places},
              "road": road}
    now = start
    told = []
    while True:
        row = watcher_lore.due(memory, sessions, hours, now)
        if row is None:
            if watcher_lore.book_one_complete(memory) and not memory.get("afterword"):
                memory["afterword"] = now
                continue
            # Wait out a real-days gap, if the next passage is only waiting on days.
            waiting = next((r for r in watcher_lore.FRAGMENTS if r[0] not in watcher_lore.told(memory)
                            and (r[8] is None or r[8] == road)), None)
            if waiting is None:
                break
            gap = watcher_lore.days_to_wait(waiting, memory, now)
            if gap > 0 and (now + gap * 86400 - start) / 86400 <= days:
                now += gap * 86400 + 1
                continue
            break
        memory["lore"].append([row[0], now])
        told.append((row, now))
    return memory, told, now


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hours", type=float, default=100)
    parser.add_argument("--days", type=float, default=30)
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--echoes", default="", help="comma-separated echo topics, or 'all'")
    parser.add_argument("--places", default="", help="comma-separated pilgrimage kinds reached, or 'all'")
    parser.add_argument("--road", choices=("shut", "open"), default=None)
    args = parser.parse_args()
    echoes = list(watcher_lore.ECHOES) if args.echoes == "all" else [name for name in args.echoes.split(",") if name]
    from voidcompass.overlays.watcher_places import PLACES
    places = list(PLACES) if args.places == "all" else [name for name in args.places.split(",") if name]
    memory, told, now = simulate(args.hours, args.days, args.sessions, echoes, args.road, places)
    chapters = {}
    for row, _at in told:
        chapters.setdefault((row[5], row[1]), 0)
        chapters[(row[5], row[1])] += 1
    print(f"{len(told)} passages told by {args.hours:g} h, {args.sessions} sessions, {args.days:g} days:")
    for (index, title), count in sorted(chapters.items()):
        chapter = watcher_lore.ALL_CHAPTERS[index]
        print(f"  Book {watcher_lore.book_of(index)} · {chapter[0]:>6} {title:<22} {count}/{len(chapter[5])}")
    page = watcher_lore.page(memory, args.sessions, args.hours, now=now)
    upcoming = page.get("next")
    if upcoming:
        print(f"Next: chapter {upcoming.get('chapter')} · {upcoming.get('hours')} h, {upcoming.get('sessions')} sessions,"
              f" {upcoming.get('days', 0)} days to go{' · waits for ' + upcoming['waits_for'] if upcoming.get('waits_for') else ''}")
    if watcher_lore.road_question_due(memory):
        print("Book Four asks about the shutter now (no --road given).")
    wanted = watcher_lore.waiting_place(memory, args.sessions, args.hours, now)
    if wanted:
        print(f"It asks to be taken to: {wanted}")
    print(f"Progress: {watcher_lore.progress(memory)}")


if __name__ == "__main__":
    main()
