"""The commander's trading record, one SQLite file per profile (trading.db).
Their own trades only: never a price database (prices come from Spansh).

* ``trades``: every MarketBuy and MarketSell, by journal-line id. A sale is
  linked to the last purchase of the same commodity before it, which is where
  that cargo came from (the route it was flown on).
* ``markets``: station and system names by market id, from docking.
* ``names``: commodity names the journal has shown.
* ``sessions``: game sessions (LoadGame to Shutdown), for profit per hour.
* ``kv``: the route being followed; ``files``: journals already read.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    uid TEXT PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL, market_id INTEGER, station TEXT, system TEXT,
    commodity TEXT NOT NULL, count INTEGER, price INTEGER, total INTEGER, avg_paid INTEGER, profit INTEGER,
    stolen INTEGER DEFAULT 0, black_market INTEGER DEFAULT 0, illegal INTEGER DEFAULT 0,
    from_market_id INTEGER, from_station TEXT, from_system TEXT);
CREATE INDEX IF NOT EXISTS trades_ts ON trades(ts);
CREATE INDEX IF NOT EXISTS trades_commodity ON trades(commodity, kind, ts);
CREATE TABLE IF NOT EXISTS markets (market_id INTEGER PRIMARY KEY, station TEXT, system TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS names (symbol TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS sessions (start REAL PRIMARY KEY, end REAL);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files (name TEXT PRIMARY KEY, size INTEGER, mtime REAL);
"""
_SESSION_CAP = 12 * 3600   # a session with no Shutdown is counted up to this long


class TradeStore:
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
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    def close(self):
        with self.lock:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass

    def commit(self):
        with self.lock:
            self.conn.commit()

    def query(self, sql, params=()):
        with self.lock:
            return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    # -- writes ------------------------------------------------------------
    def apply(self, records, commit=True):
        """Store what TradeJournal.observe returned; True when anything changed."""
        changed = False
        with self.lock:
            for kind, value in records or ():
                if kind == "market":
                    self.conn.execute("INSERT OR REPLACE INTO markets VALUES (?,?,?,?)",
                                      (value["market_id"], value["station"], value["system"], value["ts"]))
                elif kind == "name":
                    cursor = self.conn.execute("INSERT OR REPLACE INTO names VALUES (?,?)", value)
                    changed = changed or cursor.rowcount > 0
                elif kind == "session":
                    self.conn.execute("INSERT OR IGNORE INTO sessions VALUES (?, NULL)", (value,))
                elif kind == "session_end":
                    self.conn.execute("UPDATE sessions SET end = ? WHERE start = (SELECT MAX(start) FROM sessions WHERE start <= ?) "
                                      "AND end IS NULL", (value, value))
                elif kind == "trade":
                    changed = self._add_trade(value) or changed
            if changed:
                self.revision += 1
            if commit:
                self.conn.commit()
        return changed

    def _add_trade(self, trade):
        if self.conn.execute("SELECT 1 FROM trades WHERE uid = ?", (trade["uid"],)).fetchone():
            return False
        if not trade.get("station") and trade.get("market_id"):
            row = self.conn.execute("SELECT station, system FROM markets WHERE market_id = ?", (trade["market_id"],)).fetchone()
            if row:
                trade = {**trade, "station": row["station"], "system": row["system"]}
        origin = (None, None, None)
        if trade["kind"] == "sell" and trade.get("profit") is not None:
            row = self.conn.execute(
                "SELECT market_id, station, system FROM trades WHERE kind = 'buy' AND commodity = ? AND ts <= ? "
                "ORDER BY ts DESC LIMIT 1", (trade["commodity"], trade["ts"])).fetchone()
            if row:
                origin = (row["market_id"], row["station"], row["system"])
        self.conn.execute(
            "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (trade["uid"], trade["ts"], trade["kind"], trade.get("market_id"), trade.get("station") or "",
             trade.get("system") or "", trade["commodity"], trade["count"], trade.get("price"), trade.get("total"),
             trade.get("avg_paid"), trade.get("profit"), trade.get("stolen", 0), trade.get("black_market", 0),
             trade.get("illegal", 0), *origin))
        return True

    def file_signature(self, name):
        rows = self.query("SELECT size, mtime FROM files WHERE name = ?", (name,))
        return (rows[0]["size"], rows[0]["mtime"]) if rows else None

    def file_done(self, name, size, mtime):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)", (name, size, mtime))

    def set_value(self, key, value):
        with self.lock:
            if value is None:
                self.conn.execute("DELETE FROM kv WHERE key = ?", (key,))
            else:
                self.conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))
            self.conn.commit()
            self.revision += 1

    def value(self, key, default=None):
        rows = self.query("SELECT value FROM kv WHERE key = ?", (key,))
        try:
            return json.loads(rows[0]["value"]) if rows else default
        except ValueError:
            return default

    # -- reads ---------------------------------------------------------------
    def names(self):
        return {row["symbol"]: row["name"] for row in self.query("SELECT symbol, name FROM names")}

    def sessions(self, since=0):
        """``(start, end)`` of each session; an open one ends at its last
        trade or the cap, whichever is sooner."""
        out = []
        rows = self.query("SELECT start, end FROM sessions WHERE start >= ? ORDER BY start", (since,))
        for index, row in enumerate(rows):
            end = row["end"]
            if end is None:
                following = rows[index + 1]["start"] if index + 1 < len(rows) else None
                last = self.query("SELECT MAX(ts) ts FROM trades WHERE ts >= ? AND ts < ?",
                                  (row["start"], following or row["start"] + _SESSION_CAP))[0]["ts"]
                end = min(x for x in (following, last, row["start"] + _SESSION_CAP, time.time()) if x)
            out.append((row["start"], max(row["start"], end)))
        return out
