"""Spot what Elite starts writing to its journals after an update: an event
by a new name, or a new field on one already known. A developer tool, run on
its own; it's no part of Void Compass and never ships.

    python tools/journal_watch.py learn    # before an update: learn what's normal
    python tools/journal_watch.py check    # after it: what's new since then
    python tools/journal_watch.py watch    # check, then keep watching the live journal

What it has learnt, and what it found (each with an example), are kept in
tools/journal_watch/ (git-ignored): seen.json and report.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent / "journal_watch"
SEEN = HERE / "seen.json"
REPORT = HERE / "report.jsonl"
DEFAULT_JOURNALS = Path.home() / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
IGNORED_KEYS = {"timestamp", "event"}
SAMPLE_TEXT = 200


def _journals(folder):
    return sorted(Path(folder).glob("Journal.*.log"), key=lambda path: path.stat().st_mtime)


def _sample(value):
    """An example of an event, long text cut short."""
    if isinstance(value, str):
        return value[:SAMPLE_TEXT]
    if isinstance(value, list):
        return [_sample(item) for item in value[:10]]
    if isinstance(value, dict):
        return {key: _sample(item) for key, item in list(value.items())[:40]}
    return value


def _read(path, offset=0):
    """(events from ``offset`` on, the offset reached)."""
    events = []
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read()
    # Only whole lines: the game may be part-way through writing the last.
    end = data.rfind(b"\n") + 1
    for line in data[:end].decode("utf-8", errors="ignore").splitlines():
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if isinstance(raw, dict) and raw.get("event"):
            events.append(raw)
    return events, offset + end


class Watch:
    def __init__(self, seen_path=SEEN, report_path=REPORT):
        self.seen_path, self.report_path = Path(seen_path), Path(report_path)
        self.known, self.read_to, self.journals = {}, {}, ""
        if self.seen_path.exists():
            stored = json.loads(self.seen_path.read_text(encoding="utf-8"))
            self.known = {name: set(keys) for name, keys in stored.get("events", {}).items()}
            self.read_to = dict(stored.get("read_to") or {})
            self.journals = stored.get("journals", "")

    @property
    def learnt(self):
        return bool(self.known)

    def save(self):
        self.seen_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": time.strftime("%Y-%m-%d %H:%M:%S"), "journals": self.journals, "read_to": self.read_to,
                   "events": {name: sorted(keys) for name, keys in sorted(self.known.items())}}
        self.seen_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    def learn(self, folder):
        """Everything in every journal now is normal."""
        self.known, self.read_to, self.journals = {}, {}, str(folder)
        for path in _journals(folder):
            events, reached = _read(path)
            for raw in events:
                self.known.setdefault(str(raw["event"]), set()).update(str(key) for key in raw if key not in IGNORED_KEYS)
            self.read_to[path.name] = reached
        self.save()
        return len(self.known)

    def look(self, raw):
        """Something new in one event: {"event", "new_event", "new_keys"}, or None."""
        event = str(raw["event"])
        keys = {str(key) for key in raw if key not in IGNORED_KEYS}
        held = self.known.get(event)
        new_keys = sorted(keys - (held or set()))
        if held is not None and not new_keys:
            return None
        self.known.setdefault(event, set()).update(keys)
        finding = {"event": event, "new_event": held is None, "new_keys": [] if held is None else new_keys,
                   "journal_time": raw.get("timestamp")}
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.report_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({**finding, "example": _sample(raw)}, ensure_ascii=False) + "\n")
        return finding

    def check(self, folder):
        """What's new in the journals since they were last read."""
        found, moved = [], False
        for path in _journals(folder):
            start = self.read_to.get(path.name, 0)
            if path.stat().st_size <= start:
                continue
            events, reached = _read(path, start)
            for raw in events:
                finding = self.look(raw)
                if finding:
                    found.append(finding)
            moved = moved or reached != start
            self.read_to[path.name] = reached
        if moved:
            self.save()
        return found


def describe(finding):
    if finding["new_event"]:
        return f"NEW EVENT   {finding['event']}   ({finding['journal_time']})"
    return f"NEW FIELDS  {finding['event']}: {', '.join(finding['new_keys'])}   ({finding['journal_time']})"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="check", choices=("learn", "check", "watch"))
    parser.add_argument("--journals", default=str(DEFAULT_JOURNALS), help="the journal folder")
    args = parser.parse_args(argv)
    folder = Path(args.journals)
    if not folder.is_dir():
        print(f"No journal folder at {folder}")
        return 1
    watch = Watch()
    if args.command == "learn" or not watch.learnt:
        started = time.time()
        count = watch.learn(folder)
        print(f"Learnt {count} event types from {len(watch.read_to)} journals in {time.time() - started:.1f} s.")
        print("After the game updates and you've played a session, run:  python tools/journal_watch.py check")
        if args.command == "learn":
            return 0
    found = watch.check(folder)
    for finding in found:
        print(describe(finding))
    print(f"{len(found)} new since last time." + (f" Examples in {REPORT}" if found else ""))
    if args.command != "watch":
        return 0
    print("Watching the journal as you play. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
            for finding in watch.check(folder):
                print(describe(finding))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
