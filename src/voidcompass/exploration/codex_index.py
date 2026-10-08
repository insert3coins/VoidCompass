"""The commander's biological Codex record, for Survey Operations' flags (5.5.1.6).

Like SrvSurvey's bio panel, Survey Operations can mark the species worth
logging for the Codex: never logged anywhere, or never logged in the current
galactic region. That needs every Codex entry the commander has made, so this
keeps one compact row per biological CodexEntry, imported once from every
journal file (only new or changed files are read again) and extended live.

A row is ``[timestamp, entry, region, system address, body id]``. ``entry`` is
the game's own identifier, such as ``$Codex_Ent_Bacterial_01_G_Name;`` (one
colour variant of Bacterium Aurasus), which reads the same in every game
language. A variant's identifier starts with its species' identifier
(``$Codex_Ent_Bacterial_01``), which is how species-level flags are found.
"""

from __future__ import annotations

import json
import os
import re
import threading

from voidcompass.core.journal_files import journal_sort_key
from voidcompass.core.persistence_queue import persistence_queue
from voidcompass.exploration.travel_history import commander_matches

SCHEMA = 1
MARKERS = tuple(
    marker
    for event in ("CodexEntry", "Commander", "LoadGame")
    for marker in (f'"event":"{event}"', f'"event": "{event}"')
)
_REGION = re.compile(r"_(\d+);?$")
NEW, REGION = "new", "region"


def region_id(value):
    """``$Codex_RegionName_18;`` (or 18) as 18; None when unknown."""
    if isinstance(value, int):
        return value
    match = _REGION.search(str(value or "").strip())
    return int(match.group(1)) if match else None


def species_prefix(species_key):
    """``$Codex_Ent_Bacterial_01_Name;`` -> ``$Codex_Ent_Bacterial_01``."""
    key = str(species_key or "").strip()
    return key[:-len("_Name;")] if key.endswith("_Name;") else ""


class CodexIndex:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.rows = []
        self.files = {}
        self.revision = 0
        self._by_entry = {}
        self.load()

    # -- storage -------------------------------------------------------------
    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self.lock:
            self.rows = [row for row in data.get("rows") or [] if isinstance(row, list) and len(row) >= 5]
            self.files = {str(key): str(value) for key, value in (data.get("files") or {}).items()}
            self._reindex()

    def _reindex(self):
        self._by_entry = {}
        for row in self.rows:
            self._by_entry.setdefault(str(row[1]), []).append(row)
        self.revision += 1

    def _payload(self):
        with self.lock:
            return {"schema": SCHEMA, "rows": list(self.rows), "files": dict(self.files)}

    def save(self, immediate=False):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None,
                                            delay_s=0.25 if immediate else 3.0, immediate=immediate)

    def flush(self, wait=False):
        self.save(immediate=True)
        if wait and self.path:
            persistence_queue().flush(self.path, timeout=1.0)

    # -- recording -----------------------------------------------------------
    def _record(self, raw):
        """Add one biological CodexEntry; True when it was new to the index."""
        if raw.get("event") != "CodexEntry" or "biology" not in str(raw.get("Category") or "").casefold():
            return False
        entry = str(raw.get("Name") or "").strip()
        timestamp = str(raw.get("timestamp") or "")
        if not entry.startswith("$Codex_Ent_") or not timestamp:
            return False
        row = [timestamp, entry, region_id(raw.get("Region")), raw.get("SystemAddress"), raw.get("BodyID")]
        known = self._by_entry.setdefault(entry, [])
        if any(existing[0] == timestamp for existing in known):
            return False
        self.rows.append(row)
        known.append(row)
        return True

    def observe(self, raw):
        """A live journal event."""
        if not isinstance(raw, dict):
            return False
        with self.lock:
            added = self._record(raw)
            if added:
                self.revision += 1
        if added:
            self.save()
        return added

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
            except OSError:
                continue
            if self.files.get(name) == signature:
                continue
            active = not bool(commander or fid)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    lines = [line for line in handle if any(marker in line for marker in MARKERS)]
            except OSError:
                continue
            with self.lock:
                for line in lines:
                    try:
                        raw = json.loads(line)
                    except ValueError:
                        continue
                    if raw.get("event") in ("Commander", "LoadGame"):
                        active = commander_matches(raw, commander, fid)
                        continue
                    if active and self._record(raw):
                        added += 1
                self.files[name] = signature
        with self.lock:
            if added:
                self.revision += 1
        self.save(immediate=bool(added))
        return added

    # -- reading -------------------------------------------------------------
    def _species_rows(self, species_key):
        prefix = species_prefix(species_key)
        if not prefix:
            return []
        rows = list(self._by_entry.get(str(species_key), ()))
        for entry, entry_rows in self._by_entry.items():
            if entry.startswith(prefix + "_") and entry != species_key:
                rows.extend(entry_rows)
        return rows

    def species_flag(self, species_key, region):
        """For a species still to find: never logged (NEW), never in this
        region (REGION), or "" when the Codex already has it here."""
        if not species_prefix(species_key):
            return ""
        with self.lock:
            rows = self._species_rows(species_key)
        if not rows:
            return NEW
        if region is not None and not any(row[2] == region for row in rows):
            return REGION
        return ""

    def entries_on(self, address, body_id):
        """Codex entries the commander logged on one body, oldest first."""
        with self.lock:
            rows = [row for row in self.rows
                    if str(row[3]) == str(address) and str(row[4]) == str(body_id)]
        seen, entries = set(), []
        for row in sorted(rows, key=lambda row: row[0]):
            if row[1] not in seen:
                seen.add(row[1])
                entries.append(row[1])
        return entries

    def entry_flag(self, entry, region):
        """For a predicted colour variant: never logged (NEW), never in this
        region (REGION), or "" when the Codex already has it here."""
        entry = str(entry or "").strip()
        if not entry.startswith("$Codex_Ent_"):
            return ""
        with self.lock:
            rows = list(self._by_entry.get(entry, ()))
        if not rows:
            return NEW
        if region is not None and not any(row[2] == region for row in rows):
            return REGION
        return ""

    def variant_flag(self, variant_key, region, address=None, body_id=None):
        """For a variant being sampled. Logging it writes its Codex entry, so
        it stays flagged on the body where it was first logged (anywhere, or
        in this region) rather than losing the flag with the first sample."""
        variant_key = str(variant_key or "").strip()
        if not variant_key.startswith("$Codex_Ent_"):
            return ""
        with self.lock:
            rows = list(self._by_entry.get(variant_key, ()))

        def here(row):
            return (address is not None and str(row[3]) == str(address)
                    and body_id is not None and str(row[4]) == str(body_id))

        if not rows:
            return NEW
        if here(min(rows, key=lambda row: row[0])):
            return NEW
        in_region = [row for row in rows if region is None or row[2] == region]
        if not in_region:
            return REGION
        if region is not None and here(min(in_region, key=lambda row: row[0])):
            return REGION
        return ""
