"""Local market database (SQLite): seeded from the Spansh galaxy dump, kept
fresh by the EDDN listener, queried by the local route planner.

Keying: stations by in-game MarketID (the Spansh dump's station "id" is the
MarketID), commodities by lowercase symbol (matches EDDN commodity names)."""

import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def _default_data_dir():
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: keep the database next to the exe, not in the
        # temp extraction dir that vanishes on exit.
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parent.parent / "data"


DATA_DIR = Path(os.environ.get("ET_DATA_DIR") or _default_data_dir())
DB_PATH = DATA_DIR / "market.db"

CARRIER_TYPES = {"Drake-Class Carrier", "Fleet Carrier"}
CARRIER_NAME_RE = re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS systems(
    id64 INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_systems_x ON systems(x);
CREATE INDEX IF NOT EXISTS idx_systems_xyz ON systems(x, y, z);
CREATE TABLE IF NOT EXISTS stations(
    market_id INTEGER PRIMARY KEY,
    system_id64 INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    dist_ls REAL,
    large_pad INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER);
CREATE INDEX IF NOT EXISTS idx_stations_system ON stations(system_id64);
CREATE INDEX IF NOT EXISTS idx_stations_system_updated ON stations(system_id64, updated_at);
CREATE INDEX IF NOT EXISTS idx_stations_updated ON stations(updated_at);
CREATE INDEX IF NOT EXISTS idx_stations_pad_updated ON stations(large_pad, updated_at);
CREATE TABLE IF NOT EXISTS commodities(
    market_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    buy_price INTEGER NOT NULL DEFAULT 0,
    sell_price INTEGER NOT NULL DEFAULT 0,
    supply INTEGER NOT NULL DEFAULT 0,
    demand INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(market_id, symbol)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_commodities_symbol_market ON commodities(symbol, market_id);
CREATE INDEX IF NOT EXISTS idx_commodities_symbol_supply ON commodities(symbol, supply, buy_price);
CREATE INDEX IF NOT EXISTS idx_commodities_symbol_demand ON commodities(symbol, demand, sell_price);
CREATE TABLE IF NOT EXISTS commodity_names(
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT);
CREATE INDEX IF NOT EXISTS idx_commodity_names_name ON commodity_names(name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS trade_log(
    ts INTEGER NOT NULL,
    event TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    count INTEGER NOT NULL DEFAULT 0,
    price INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    profit INTEGER,
    PRIMARY KEY(ts, event, symbol, total)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS balance_log(
    ts INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS watches(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    payload TEXT NOT NULL);
"""

_init_lock = threading.Lock()
_initialized = False
_status_lock = threading.Lock()
_status_cache = None
_status_cache_at = 0.0
STATUS_CACHE_TTL_S = 30.0


def connect(db_path=None):
    """New connection (SQLite connections are not shared across threads here)."""
    global _initialized
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(db_path) if db_path is not None else DB_PATH
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    if db_path is None:
        with _init_lock:
            if not _initialized:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executescript(SCHEMA)
                conn.commit()
                _initialized = True
    else:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    return conn


def is_carrier(station_type, station_name):
    if station_type in CARRIER_TYPES:
        return True
    return station_type is None and bool(CARRIER_NAME_RE.match(station_name or ""))


def parse_update_time(value):
    """Spansh '2026-01-21 03:55:54+00' or EDDN '2026-07-05T20:50:21Z' -> epoch."""
    if not value:
        return None
    text = str(value).strip().replace(" ", "T").replace("Z", "+00:00")
    if text.endswith("+00"):
        text += ":00"
    try:
        return int(datetime.fromisoformat(text).timestamp())
    except ValueError:
        return None


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, str(value)))


def log_trade(ts, event, symbol, name, count, price, total, profit=None):
    if not ts or not symbol:
        return
    conn = connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO trade_log(ts, event, symbol, name, count, price, total, profit)"
            " VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (int(ts), event, symbol, name, int(count or 0), int(price or 0), int(total or 0), profit),
        )
        conn.commit()
    finally:
        conn.close()


def log_balance(ts, balance):
    if not ts or balance is None:
        return
    conn = connect()
    try:
        conn.execute("INSERT OR REPLACE INTO balance_log(ts, balance) VALUES(?, ?)", (int(ts), int(balance)))
        conn.commit()
    finally:
        conn.close()


def trade_analytics(days=30):
    days = max(1, min(365, int(days or 30)))
    now = now_epoch()
    since = now - days * 86400
    conn = connect()
    try:
        balance = conn.execute(
            "SELECT ts, balance FROM balance_log WHERE ts >= ? ORDER BY ts", (since,)
        ).fetchall()
        if len(balance) > 400:
            step = len(balance) // 400 + 1
            balance = balance[::step] + [balance[-1]]
        daily = conn.execute(
            """SELECT date(ts, 'unixepoch') AS d,
                      SUM(CASE WHEN event = 'sell' THEN COALESCE(profit, 0) ELSE 0 END),
                      SUM(CASE WHEN event = 'sell' THEN count ELSE 0 END)
               FROM trade_log WHERE ts >= ? GROUP BY d ORDER BY d""",
            (since,),
        ).fetchall()

        def profit_since(cutoff):
            row = conn.execute(
                "SELECT SUM(COALESCE(profit, 0)), SUM(count), COUNT(*) FROM trade_log"
                " WHERE event = 'sell' AND ts >= ?", (cutoff,)
            ).fetchone()
            return {"profit": row[0] or 0, "tons": row[1] or 0, "sales": row[2] or 0}

        top = conn.execute(
            """SELECT symbol, name, SUM(COALESCE(profit, 0)) AS p, SUM(count) AS c
               FROM trade_log WHERE event = 'sell' AND ts >= ?
               GROUP BY symbol, name ORDER BY p DESC LIMIT 12""",
            (since,),
        ).fetchall()
        day_start = now - (now % 86400)
        return {
            "balance": [{"ts": t, "balance": b} for t, b in balance],
            "daily": [{"date": d, "profit": p or 0, "tons": t or 0} for d, p, t in daily],
            "today": profit_since(day_start),
            "week": profit_since(now - 7 * 86400),
            "period": profit_since(since),
            "top": [{"symbol": s, "name": n, "profit": p or 0, "tons": c or 0} for s, n, p, c in top],
        }
    finally:
        conn.close()


def keep_commodity(buy, sell, supply, demand):
    """Only rows usable for trading: buyable somewhere or sellable with demand."""
    return (supply > 0 and buy > 0) or (demand > 0 and sell > 0)


def clean_commodity_symbol(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1]
    lower = text.lower()
    for suffix in ("_name", "_name_localised"):
        if lower.endswith(suffix):
            lower = lower[: -len(suffix)]
            break
    return lower.replace(" ", "_")


def replace_market(conn, market_id, rows):
    """rows: iterable of (symbol, buy, sell, supply, demand)."""
    conn.execute("DELETE FROM commodities WHERE market_id = ?", (market_id,))
    conn.executemany(
        "INSERT OR REPLACE INTO commodities(market_id, symbol, buy_price, sell_price, supply, demand)"
        " VALUES(?, ?, ?, ?, ?, ?)",
        [(market_id, s, b, sl, sp, d) for (s, b, sl, sp, d) in rows],
    )


def import_market_json(conn, data, context=None):
    """Import Elite Dangerous Market.json into the local trade database.

    Market.json is written by the game when the commodity market screen opens.
    It does not always include coordinates, so context can provide the current
    SystemAddress/StarPos captured from live journal location events.
    """
    context = context or {}
    market_id = data.get("MarketID")
    system_name = data.get("StarSystem") or context.get("system_name")
    station_name = data.get("StationName") or context.get("station_name") or "?"
    if market_id is None or not system_name:
        return {"updated": False, "reason": "missing market id or system"}

    updated = parse_update_time(data.get("timestamp")) or now_epoch()
    rows = []
    names = []
    for item in data.get("Items") or []:
        symbol = clean_commodity_symbol(item.get("Name"))
        if not symbol:
            symbol = clean_commodity_symbol(item.get("Name_Localised"))
        if not symbol:
            continue
        buy = int(item.get("BuyPrice") or 0)
        sell = int(item.get("SellPrice") or 0)
        supply = int(item.get("Stock") or 0)
        demand = int(item.get("Demand") or 0)
        if not keep_commodity(buy, sell, supply, demand):
            continue
        rows.append((symbol, buy, sell, supply, demand))
        display = item.get("Name_Localised") or symbol.replace("_", " ").title()
        category = item.get("Category_Localised") or item.get("Category") or ""
        names.append((symbol, display, category))
    if not rows:
        return {"updated": False, "reason": "no tradeable commodities"}

    existing_station = conn.execute(
        "SELECT system_id64, name, type, dist_ls, large_pad FROM stations WHERE market_id = ?",
        (market_id,),
    ).fetchone()
    system = find_system(conn, system_name)
    coords = context.get("star_pos")
    system_id64 = context.get("system_address")
    if system:
        system_id64 = system[0]
    elif existing_station:
        system_id64 = existing_station[0]
    elif system_id64 is not None and isinstance(coords, (list, tuple)) and len(coords) >= 3:
        conn.execute(
            "INSERT OR REPLACE INTO systems(id64, name, x, y, z) VALUES(?, ?, ?, ?, ?)",
            (int(system_id64), system_name, float(coords[0]), float(coords[1]), float(coords[2])),
        )
    else:
        return {"updated": False, "reason": "system coordinates unavailable"}

    station_type = context.get("station_type")
    dist_ls = context.get("dist_ls")
    large_pad = context.get("large_pad")
    if existing_station:
        station_type = station_type if station_type is not None else existing_station[2]
        dist_ls = dist_ls if dist_ls is not None else existing_station[3]
        large_pad = large_pad if large_pad is not None else existing_station[4]
    conn.execute(
        "INSERT OR REPLACE INTO stations(market_id, system_id64, name, type, dist_ls, large_pad, updated_at)"
        " VALUES(?, ?, ?, ?, ?, ?, ?)",
        (market_id, int(system_id64), station_name, station_type, dist_ls, int(bool(large_pad)), updated),
    )
    conn.executemany(
        "INSERT OR REPLACE INTO commodity_names(symbol, name, category) VALUES(?, ?, ?)",
        names,
    )
    replace_market(conn, market_id, rows)
    set_meta(conn, "journal_market_updated_at", utc_now_iso())
    conn.commit()
    return {
        "updated": True,
        "market_id": market_id,
        "station": station_name,
        "system": system_name,
        "commodities": len(rows),
    }


def find_system(conn, name):
    return conn.execute(
        "SELECT id64, name, x, y, z FROM systems WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()


def stations_near(conn, x, y, z, radius, min_updated=0, require_large_pad=False, max_dist_ls=None):
    """Stations with markets within `radius` ly of (x,y,z), with exact-sphere
    filtering done in Python after a bounding-box query."""
    rows = conn.execute(
        """SELECT st.market_id, st.name, st.type, st.dist_ls, st.large_pad, st.updated_at,
                  sy.id64, sy.name, sy.x, sy.y, sy.z
           FROM stations st JOIN systems sy ON sy.id64 = st.system_id64
           WHERE sy.x BETWEEN ? AND ? AND sy.y BETWEEN ? AND ? AND sy.z BETWEEN ?  AND ?
             AND st.updated_at >= ?""",
        (x - radius, x + radius, y - radius, y + radius, z - radius, z + radius, min_updated),
    ).fetchall()
    r2 = radius * radius
    out = []
    for m in rows:
        dx, dy, dz = m[8] - x, m[9] - y, m[10] - z
        if dx * dx + dy * dy + dz * dz > r2:
            continue
        if require_large_pad and not m[4]:
            continue
        if max_dist_ls is not None and m[3] is not None and m[3] > max_dist_ls:
            continue
        out.append(
            {
                "market_id": m[0], "station": m[1], "type": m[2], "dist_ls": m[3],
                "large_pad": bool(m[4]), "updated_at": m[5],
                "system_id64": m[6], "system": m[7], "x": m[8], "y": m[9], "z": m[10],
            }
        )
    return out


def commodity_display_names(conn, symbols):
    if not symbols:
        return {}
    marks = ",".join("?" for _ in symbols)
    rows = conn.execute(
        f"SELECT symbol, name FROM commodity_names WHERE symbol IN ({marks})", list(symbols)
    ).fetchall()
    return dict(rows)


def is_ready(conn):
    return conn.execute("SELECT 1 FROM stations LIMIT 1").fetchone() is not None


def status(conn, force=False):
    global _status_cache, _status_cache_at
    now = time.monotonic()
    with _status_lock:
        if not force and _status_cache is not None and now - _status_cache_at < STATUS_CACHE_TTL_S:
            return dict(_status_cache)

    counts = {}
    for table in ("systems", "stations", "commodities"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    result = {
        "db_path": str(DB_PATH),
        "db_size_mb": round(DB_PATH.stat().st_size / 1e6, 1) if DB_PATH.exists() else 0,
        "systems": counts["systems"],
        "stations": counts["stations"],
        "commodity_rows": counts["commodities"],
        "seeded_at": get_meta(conn, "seeded_at"),
        "journal_market_updated_at": get_meta(conn, "journal_market_updated_at"),
        "ready": counts["stations"] > 0,
    }
    with _status_lock:
        _status_cache = dict(result)
        _status_cache_at = now
    return result


def now_epoch():
    return int(time.time())


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
