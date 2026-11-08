"""Every body the commander has stepped out on, and when first.

The game's WasFootfalled stays false after you've walked there, so nothing in
a Scan can say a return trip isn't a first footfall. Built once from every
journal, then kept up as you step out.
"""

from __future__ import annotations

import json
import os
import threading

from voidcompass.core.journal_files import journal_sort_key
from voidcompass.core.persistence_queue import persistence_queue
from voidcompass.exploration.travel_history import commander_matches

SCHEMA = 1
MARKERS = tuple(
    marker
    for event in ("Disembark", "Commander", "LoadGame")
    for marker in (f'"event":"{event}"', f'"event": "{event}"')
)


class WalkedBodies:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.bodies = {}
        self.files = {}
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            with self.lock:
                self.bodies = {str(key): str(value) for key, value in (data.get("bodies") or {}).items()}
                self.files = {str(key): str(value) for key, value in (data.get("files") or {}).items()}

    def _payload(self):
        with self.lock:
            return {"schema": SCHEMA, "bodies": dict(self.bodies), "files": dict(self.files)}

    def save(self, immediate=False):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None,
                                            delay_s=0.25 if immediate else 3.0, immediate=immediate)

    def flush(self, wait=False):
        self.save(immediate=True)
        if wait and self.path:
            persistence_queue().flush(self.path, timeout=1.0)

    def _record(self, raw):
        """Keep the earliest time for this body. True if that changed."""
        body = str(raw.get("Body") or "").strip().casefold()
        stamp = str(raw.get("timestamp") or "")
        if not body or not raw.get("OnPlanet") or raw.get("OnStation"):
            return False
        with self.lock:
            first = self.bodies.get(body)
            if first is None or (stamp and stamp < first):
                self.bodies[body] = stamp
                return True
        return False

    def before(self, raw):
        """Whether this Disembark is a return to the body. By time rather than
        by call, so every part of the app asking about one event gets one answer."""
        if self._record(raw):
            self.save()
        with self.lock:
            first = self.bodies.get(str(raw.get("Body") or "").strip().casefold())
        return bool(first) and first < str(raw.get("timestamp") or "")

    def import_journals(self, journal_path, commander=None, fid=None):
        """Read every journal file not read before (or changed since)."""
        if not journal_path or not os.path.isdir(journal_path):
            return 0
        names = sorted((name for name in os.listdir(journal_path)
                        if name.startswith("Journal.") and name.endswith(".log")), key=journal_sort_key)
        added = 0
        for name in names:
            path = os.path.join(journal_path, name)
            try:
                signature = f"{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
                if self.files.get(name) == signature:
                    continue
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    lines = [line for line in handle if any(marker in line for marker in MARKERS)]
            except OSError:
                continue
            active = not bool(commander or fid)
            with self.lock:
                for line in lines:
                    try:
                        raw = json.loads(line)
                    except ValueError:
                        continue
                    if raw.get("event") in ("Commander", "LoadGame"):
                        active = commander_matches(raw, commander, fid)
                    elif active and self._record(raw):
                        added += 1
                self.files[name] = signature
        if added:
            self.save(immediate=True)
        return added
