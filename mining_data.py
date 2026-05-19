import math
import os
import sqlite3
from datetime import datetime

import requests


MINING_DB_FILE = "mining_data.db"
SPANSH_BODIES_SEARCH_URL = "https://spansh.co.uk/api/bodies/search"
SPANSH_STATIONS_SEARCH_URL = "https://spansh.co.uk/api/stations/search"

SPANSH_COMMODITY_MAP = {
    "Void Opals": "Void Opal",
    "Low Temperature Diamonds": "Low Temperature Diamond",
    "Painite": "Painite",
    "Platinum": "Platinum",
    "Bromellite": "Bromellite",
    "Alexandrite": "Alexandrite",
    "Benitoite": "Benitoite",
    "Grandidierite": "Grandidierite",
    "Monazite": "Monazite",
    "Musgravite": "Musgravite",
    "Rhodplumsite": "Rhodplumsite",
    "Serendibite": "Serendibite",
    "Tritium": "Tritium",
    "Osmium": "Osmium",
    "Palladium": "Palladium",
}


class MiningDataStore:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.abspath(MINING_DB_FILE)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hotspots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_name TEXT NOT NULL,
                    body_name TEXT NOT NULL,
                    material_name TEXT NOT NULL,
                    hotspot_count INTEGER DEFAULT 0,
                    ring_type TEXT,
                    ls_distance REAL,
                    x_coord REAL,
                    y_coord REAL,
                    z_coord REAL,
                    overlap_tag TEXT,
                    res_tag TEXT,
                    data_source TEXT,
                    scan_date TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(system_name, body_name, material_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mining_bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_name TEXT NOT NULL,
                    body_name TEXT NOT NULL,
                    material_name TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(system_name, body_name, material_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mining_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    system_name TEXT,
                    body_name TEXT,
                    prospected_count INTEGER DEFAULT 0,
                    core_count INTEGER DEFAULT 0,
                    mined_tons INTEGER DEFAULT 0,
                    cargo_json TEXT,
                    material_json TEXT,
                    report_path TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hotspots_material ON hotspots(material_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hotspots_system ON hotspots(system_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hotspots_ring ON hotspots(ring_type)")
            conn.commit()

    @staticmethod
    def distance_ly(a, b):
        if not a or not b:
            return None
        try:
            return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))
        except Exception:
            return None

    def upsert_hotspot(self, hotspot):
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hotspots (
                    system_name, body_name, material_name, hotspot_count, ring_type,
                    ls_distance, x_coord, y_coord, z_coord, overlap_tag, res_tag,
                    data_source, scan_date, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(system_name, body_name, material_name) DO UPDATE SET
                    hotspot_count=excluded.hotspot_count,
                    ring_type=COALESCE(excluded.ring_type, hotspots.ring_type),
                    ls_distance=COALESCE(excluded.ls_distance, hotspots.ls_distance),
                    x_coord=COALESCE(excluded.x_coord, hotspots.x_coord),
                    y_coord=COALESCE(excluded.y_coord, hotspots.y_coord),
                    z_coord=COALESCE(excluded.z_coord, hotspots.z_coord),
                    overlap_tag=COALESCE(excluded.overlap_tag, hotspots.overlap_tag),
                    res_tag=COALESCE(excluded.res_tag, hotspots.res_tag),
                    data_source=COALESCE(excluded.data_source, hotspots.data_source),
                    scan_date=COALESCE(excluded.scan_date, hotspots.scan_date),
                    updated_at=excluded.updated_at
                """,
                (
                    hotspot.get("system_name") or hotspot.get("system") or "",
                    hotspot.get("body_name") or hotspot.get("body") or "",
                    hotspot.get("material_name") or hotspot.get("material") or "",
                    int(hotspot.get("hotspot_count") or hotspot.get("count") or 0),
                    hotspot.get("ring_type"),
                    hotspot.get("ls_distance") or hotspot.get("distance"),
                    hotspot.get("x_coord"),
                    hotspot.get("y_coord"),
                    hotspot.get("z_coord"),
                    hotspot.get("overlap_tag"),
                    hotspot.get("res_tag"),
                    hotspot.get("data_source"),
                    hotspot.get("scan_date"),
                    now,
                ),
            )
            conn.commit()

    def search_hotspots(self, material=None, ring_type=None, reference_coords=None, max_distance=None, limit=250):
        clauses = []
        params = []
        if material and material != "All":
            clauses.append("lower(material_name) = lower(?)")
            params.append(material)
        if ring_type and ring_type != "All":
            clauses.append("lower(ring_type) = lower(?)")
            params.append(ring_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit or 250), 1000))
        rows = []
        with self._connect() as conn:
            for row in conn.execute(
                f"""
                SELECT * FROM hotspots
                {where}
                ORDER BY hotspot_count DESC, system_name COLLATE NOCASE, body_name COLLATE NOCASE
                LIMIT ?
                """,
                (*params, limit * 3 if reference_coords and max_distance else limit),
            ):
                item = dict(row)
                coords = self._coords_from_row(item)
                item["distance_ly"] = self.distance_ly(reference_coords, coords)
                if reference_coords and max_distance is not None:
                    if item["distance_ly"] is None or item["distance_ly"] > float(max_distance):
                        continue
                rows.append(item)
                if len(rows) >= limit:
                    break
        rows.sort(key=lambda r: (r["distance_ly"] is None, r["distance_ly"] or 0, -int(r.get("hotspot_count") or 0)))
        return rows

    @staticmethod
    def _coords_from_row(row):
        if row.get("x_coord") is None or row.get("y_coord") is None or row.get("z_coord") is None:
            return None
        return (row.get("x_coord"), row.get("y_coord"), row.get("z_coord"))

    def add_bookmark(self, system_name, body_name, material_name=None, notes=None):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO mining_bookmarks
                (system_name, body_name, material_name, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    system_name,
                    body_name,
                    material_name,
                    notes,
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                ),
            )
            conn.commit()

    def list_bookmarks(self):
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM mining_bookmarks
                    ORDER BY created_at DESC
                    """
                )
            ]

    def create_session(self, started_at, system_name=None, body_name=None):
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO mining_sessions (started_at, system_name, body_name)
                VALUES (?, ?, ?)
                """,
                (started_at, system_name, body_name),
            )
            conn.commit()
            return cur.lastrowid

    def finish_session(self, session_id, summary):
        if not session_id:
            return
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE mining_sessions
                SET ended_at = ?, system_name = ?, body_name = ?, prospected_count = ?,
                    core_count = ?, mined_tons = ?, cargo_json = ?, material_json = ?,
                    report_path = ?
                WHERE id = ?
                """,
                (
                    summary.get("ended_at"),
                    summary.get("system_name"),
                    summary.get("body_name"),
                    int(summary.get("prospected_count") or 0),
                    int(summary.get("core_count") or 0),
                    int(summary.get("mined_tons") or 0),
                    summary.get("cargo_json"),
                    summary.get("material_json"),
                    summary.get("report_path"),
                    session_id,
                ),
            )
            conn.commit()

    def list_sessions(self, limit=100):
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM mining_sessions
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (int(limit or 100),),
                )
            ]

    def import_elitemining_user_db(self, source_db_path):
        if not source_db_path or not os.path.exists(source_db_path):
            raise FileNotFoundError(source_db_path)
        imported = 0
        source = sqlite3.connect(f"file:{source_db_path}?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            cursor = source.execute(
                """
                SELECT system_name, body_name, material_name, hotspot_count, scan_date,
                       x_coord, y_coord, z_coord, ring_type, ls_distance,
                       overlap_tag, res_tag, data_source
                FROM hotspot_data
                """
            )
            rows = [dict(row) for row in cursor]
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO hotspots (
                        system_name, body_name, material_name, hotspot_count, ring_type,
                        ls_distance, x_coord, y_coord, z_coord, overlap_tag, res_tag,
                        data_source, scan_date, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(system_name, body_name, material_name) DO UPDATE SET
                        hotspot_count=excluded.hotspot_count,
                        ring_type=COALESCE(excluded.ring_type, hotspots.ring_type),
                        ls_distance=COALESCE(excluded.ls_distance, hotspots.ls_distance),
                        x_coord=COALESCE(excluded.x_coord, hotspots.x_coord),
                        y_coord=COALESCE(excluded.y_coord, hotspots.y_coord),
                        z_coord=COALESCE(excluded.z_coord, hotspots.z_coord),
                        overlap_tag=COALESCE(excluded.overlap_tag, hotspots.overlap_tag),
                        res_tag=COALESCE(excluded.res_tag, hotspots.res_tag),
                        data_source=COALESCE(excluded.data_source, hotspots.data_source),
                        scan_date=COALESCE(excluded.scan_date, hotspots.scan_date),
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            row.get("system_name") or "",
                            row.get("body_name") or "",
                            row.get("material_name") or "",
                            int(row.get("hotspot_count") or 0),
                            row.get("ring_type"),
                            row.get("ls_distance"),
                            row.get("x_coord"),
                            row.get("y_coord"),
                            row.get("z_coord"),
                            row.get("overlap_tag"),
                            row.get("res_tag"),
                            row.get("data_source") or "EliteMining Import",
                            row.get("scan_date"),
                            now,
                        )
                        for row in rows
                    ],
                )
                conn.commit()
            imported = len(rows)
        finally:
            source.close()
        return imported


def search_spansh_rings(system_name, material=None, ring_type=None, max_results=100):
    filters = {
        "rings": {"value": [True]},
    }
    if system_name:
        filters["reference_system"] = {"value": system_name}
        filters["distance"] = {"value": [0, 300]}
    if ring_type and ring_type != "All":
        filters["rings.type"] = {"value": [ring_type]}

    payload = {
        "filters": filters,
        "sort": [{"distance": {"order": "asc"}}],
        "size": max(1, min(int(max_results or 100), 250)),
    }
    response = requests.post(SPANSH_BODIES_SEARCH_URL, json=payload, timeout=18)
    response.raise_for_status()
    data = response.json()

    rows = []
    for item in data.get("results", []):
        system = item.get("system_name") or item.get("systemName") or ""
        distance_ly = item.get("distance")
        body_name = item.get("name") or item.get("body_name") or ""
        reserve = item.get("reserve_level") or item.get("reserve") or ""
        for ring in item.get("rings", []) or []:
            rtype = ring.get("type") or ring.get("ring_type") or ""
            ring_name = ring.get("name") or body_name
            hotspots = ring.get("hotspots") or ring.get("signals") or []
            if hotspots:
                for hotspot in hotspots:
                    hmat = hotspot.get("name") or hotspot.get("type") or hotspot.get("material") or ""
                    if material and material != "All" and hmat.lower() != material.lower():
                        continue
                    rows.append(
                        {
                            "system_name": system,
                            "body_name": ring_name,
                            "material_name": hmat or material or "",
                            "hotspot_count": int(hotspot.get("count") or 1),
                            "ring_type": rtype,
                            "ls_distance": item.get("distance_to_arrival") or item.get("distanceToArrival"),
                            "distance_ly": distance_ly,
                            "reserve_level": reserve,
                            "data_source": "Spansh",
                        }
                    )
            elif not material or material == "All":
                rows.append(
                    {
                        "system_name": system,
                        "body_name": ring_name,
                        "material_name": "",
                        "hotspot_count": 0,
                        "ring_type": rtype,
                        "ls_distance": item.get("distance_to_arrival") or item.get("distanceToArrival"),
                        "distance_ly": distance_ly,
                        "reserve_level": reserve,
                        "data_source": "Spansh",
                    }
                )
    return rows


def search_spansh_buyers(commodity, reference_system=None, max_distance=500, max_results=100, exclude_carriers=True):
    spansh_name = SPANSH_COMMODITY_MAP.get(commodity, commodity)
    payload = {
        "filters": {"buying_commodities": {"value": [spansh_name]}},
        "sort": [{"market_updated_at": {"direction": "desc"}}],
        "size": max(1, min(int(max_results or 100), 250)),
    }
    if reference_system:
        payload["reference_system"] = reference_system
    response = requests.post(SPANSH_STATIONS_SEARCH_URL, json=payload, timeout=18)
    response.raise_for_status()
    rows = []
    for station in response.json().get("results", []):
        distance = station.get("distance")
        if max_distance and distance is not None and float(distance) > float(max_distance):
            continue
        station_type = station.get("type") or ""
        if exclude_carriers and ("carrier" in station_type.lower() or station_type == "Drake-Class Carrier"):
            continue
        market = station.get("market") or []
        entry = next(
            (item for item in market if str(item.get("commodity", "")).lower() == spansh_name.lower()),
            None,
        )
        if not entry:
            continue
        price = entry.get("sell_price") or 0
        demand = entry.get("demand") or 0
        if not price:
            continue
        rows.append(
            {
                "system_name": station.get("system_name") or "",
                "station_name": station.get("name") or "",
                "station_type": station_type,
                "distance_ly": distance,
                "ls_distance": station.get("distance_to_arrival") or 0,
                "price": int(price or 0),
                "demand": int(demand or 0),
                "updated_at": station.get("market_updated_at") or "",
            }
        )
    rows.sort(key=lambda r: (-r["price"], r["distance_ly"] is None, r["distance_ly"] or 0))
    return rows[: int(max_results or 100)]
