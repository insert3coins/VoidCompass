"""The BGS record, one SQLite file per commander profile (bgs.db).

* ``snapshots``: a system's factions, influence, states and conflicts each
  time you arrived (``source`` "journal") or looked it up on EDSM ("edsm").
* ``systems`` / ``presence``: the latest of each system, and of each faction
  in each system, for quick lists.
* ``edsm_points``: EDSM's influence and state history, for charts.
* ``activity``: your BGS work, one row per journal event (ids make reading
  history again, or live and history both, count each once).
* ``ticks``: galaxy ticks seen; ``tracked``: factions and systems you follow;
  ``missions``: missions open, for failed missions; ``files``: journals read.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    system_address INTEGER NOT NULL, ts REAL NOT NULL, source TEXT NOT NULL, system TEXT,
    data TEXT NOT NULL, PRIMARY KEY (system_address, ts, source));
CREATE TABLE IF NOT EXISTS systems (
    system_address INTEGER PRIMARY KEY, system TEXT, ts REAL, source TEXT, controlling TEXT,
    population INTEGER, allegiance TEXT, government TEXT, economy TEXT, security TEXT,
    factions INTEGER, conflicts INTEGER, star_pos TEXT, visits INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS systems_name ON systems(system COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS presence (
    faction TEXT NOT NULL, system_address INTEGER NOT NULL, system TEXT, ts REAL, source TEXT,
    influence REAL, state TEXT, data TEXT, controlling INTEGER DEFAULT 0,
    PRIMARY KEY (faction, system_address));
CREATE INDEX IF NOT EXISTS presence_system ON presence(system_address);
CREATE TABLE IF NOT EXISTS edsm_points (
    system_address INTEGER NOT NULL, faction TEXT NOT NULL, ts REAL NOT NULL, influence REAL, state TEXT,
    PRIMARY KEY (system_address, faction, ts));
CREATE TABLE IF NOT EXISTS activity (
    uid TEXT PRIMARY KEY, ts REAL, kind TEXT, faction TEXT, system_address INTEGER, system TEXT,
    amount REAL, count INTEGER, detail TEXT);
CREATE INDEX IF NOT EXISTS activity_ts ON activity(ts);
CREATE TABLE IF NOT EXISTS ticks (ts REAL PRIMARY KEY);
CREATE TABLE IF NOT EXISTS tracked (kind TEXT NOT NULL, name TEXT NOT NULL, ts REAL, PRIMARY KEY (kind, name));
CREATE TABLE IF NOT EXISTS missions (mission_id INTEGER PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS files (name TEXT PRIMARY KEY, size INTEGER, mtime REAL);
"""


class BgsStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.revision = 0
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    def close(self):
        with self.lock:
            try:
                self.conn.commit()
                self.conn.close()
            except sqlite3.Error:
                pass

    def commit(self):
        with self.lock:
            self.conn.commit()

    # -- writes ----------------------------------------------------------
    def apply(self, records, commit=True):
        """Store what BgsJournal.observe returned; True when anything changed."""
        changed = False
        with self.lock:
            for record in records or ():
                kind, value = record
                if kind == "snapshot":
                    changed = self.add_snapshot(value, commit=False) or changed
                elif kind == "activity":
                    cursor = self.conn.execute(
                        "INSERT OR IGNORE INTO activity VALUES (?,?,?,?,?,?,?,?,?)",
                        (value["uid"], value["ts"], value["kind"], value["faction"], value["system_address"],
                         value["system"], value["amount"], value["count"], value["detail"]))
                    changed = changed or cursor.rowcount > 0
                elif kind == "activity_upsert":
                    self.conn.execute(
                        "INSERT OR REPLACE INTO activity VALUES (?,?,?,?,?,?,?,?,?)",
                        (value["uid"], value["ts"], value["kind"], value["faction"], value["system_address"],
                         value["system"], value["amount"], value["count"], value["detail"]))
                    changed = True
                elif kind == "mission":
                    self.conn.execute("INSERT OR REPLACE INTO missions VALUES (?,?)", (value["mission_id"], json.dumps(value)))
                elif kind == "mission_done":
                    self.conn.execute("DELETE FROM missions WHERE mission_id = ?", (value,))
            if changed:
                self.revision += 1
            if commit:
                self.conn.commit()
        return changed

    def add_snapshot(self, snap, commit=True):
        if not snap or snap.get("ts") is None:
            return False
        with self.lock:
            cursor = self.conn.execute("INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?)",
                                       (snap["system_address"], snap["ts"], snap["source"], snap["system"], json.dumps(snap)))
            if cursor.rowcount <= 0:
                return False
            row = self.conn.execute("SELECT ts, visits FROM systems WHERE system_address = ?", (snap["system_address"],)).fetchone()
            visits = (row["visits"] if row else 0) + (1 if snap["source"] == "journal" else 0)
            if row is None or snap["ts"] >= (row["ts"] or 0):
                self.conn.execute(
                    "INSERT OR REPLACE INTO systems VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (snap["system_address"], snap["system"], snap["ts"], snap["source"], snap.get("controlling") or "",
                     snap.get("population") or 0, snap.get("allegiance") or "", snap.get("government") or "",
                     snap.get("economy") or "", snap.get("security") or "", len(snap.get("factions") or ()),
                     len([c for c in snap.get("conflicts") or () if c.get("status") in ("active", "pending")]),
                     json.dumps(snap.get("star_pos")), visits))
                # The faction list is the system's now: drop ones that left.
                names = [row["name"] for row in snap.get("factions") or ()]
                self.conn.execute(
                    f"DELETE FROM presence WHERE system_address = ? AND faction NOT IN ({','.join('?' * len(names)) or 'NULL'})",
                    (snap["system_address"], *names))
                for faction in snap.get("factions") or ():
                    self.conn.execute(
                        "INSERT OR REPLACE INTO presence VALUES (?,?,?,?,?,?,?,?,?)",
                        (faction["name"], snap["system_address"], snap["system"], snap["ts"], snap["source"],
                         faction.get("influence"), faction.get("state") or "None", json.dumps(faction),
                         1 if faction["name"] == snap.get("controlling") else 0))
            elif row is not None:
                self.conn.execute("UPDATE systems SET visits = ? WHERE system_address = ?", (visits, snap["system_address"]))
            self.revision += 1
            if commit:
                self.conn.commit()
        return True

    def add_edsm_points(self, system_address, points):
        with self.lock:
            self.conn.executemany("INSERT OR REPLACE INTO edsm_points VALUES (?,?,?,?,?)",
                                  [(system_address, faction, ts, influence, state) for faction, ts, influence, state in points])
            self.conn.commit()
            self.revision += 1

    def add_tick(self, ts):
        with self.lock:
            cursor = self.conn.execute("INSERT OR IGNORE INTO ticks VALUES (?)", (float(ts),))
            self.conn.commit()
            if cursor.rowcount > 0:
                self.revision += 1
            return cursor.rowcount > 0

    def set_tracked(self, kind, name, tracked):
        with self.lock:
            if tracked:
                self.conn.execute("INSERT OR REPLACE INTO tracked VALUES (?,?,?)", (kind, name, time.time()))
            else:
                self.conn.execute("DELETE FROM tracked WHERE kind = ? AND name = ?", (kind, name))
            self.conn.commit()
            self.revision += 1

    def file_done(self, name, size, mtime):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)", (name, size, mtime))

    # -- reads -----------------------------------------------------------
    def query(self, sql, params=()):
        with self.lock:
            return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def file_signature(self, name):
        rows = self.query("SELECT size, mtime FROM files WHERE name = ?", (name,))
        return (rows[0]["size"], rows[0]["mtime"]) if rows else None

    def missions(self):
        return {row["mission_id"]: json.loads(row["data"]) for row in self.query("SELECT * FROM missions")}

    def tracked(self, kind):
        return [row["name"] for row in self.query("SELECT name FROM tracked WHERE kind = ? ORDER BY name COLLATE NOCASE", (kind,))]

    def ticks(self):
        return [row["ts"] for row in self.query("SELECT ts FROM ticks ORDER BY ts")]

    def latest_snapshot(self, system_address):
        rows = self.query("SELECT data FROM snapshots WHERE system_address = ? ORDER BY ts DESC LIMIT 1", (system_address,))
        return json.loads(rows[0]["data"]) if rows else None

    def snapshots(self, system_address, limit=400):
        rows = self.query("SELECT data FROM snapshots WHERE system_address = ? ORDER BY ts DESC LIMIT ?", (system_address, limit))
        return [json.loads(row["data"]) for row in reversed(rows)]

    def find_system(self, name):
        rows = self.query("SELECT * FROM systems WHERE system = ? COLLATE NOCASE LIMIT 1", (name,))
        return rows[0] if rows else None

    def edsm_points(self, system_address):
        return self.query("SELECT faction, ts, influence, state FROM edsm_points WHERE system_address = ? ORDER BY ts", (system_address,))
