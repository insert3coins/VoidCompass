import json
import os
import sqlite3
import time

SCAN_HISTORY_FILE = "scan_history.json"
DB_FILE = "exploration_data.db"
SCAN_CACHE_FILE = "scan_cache.json"


class DashboardDBMixin:
    def init_db(self):
        """Initialize SQLite database and migrate JSON if needed."""
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self._db_last_commit_ts = time.time()
        self._db_commit_interval_s = max(0.05, float(self.config.get("db_commit_interval_ms", 250)) / 1000.0)
        with self.db_lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            # NORMAL+WAL significantly reduces fsync spikes while preserving good durability.
            self.conn.execute("PRAGMA synchronous = NORMAL")
            self.conn.execute("CREATE TABLE IF NOT EXISTS systems (name TEXT PRIMARY KEY, total INTEGER, scanned_count INTEGER)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS bodies (system_name TEXT, body_id INTEGER, PRIMARY KEY (system_name, body_id))")
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS scan_hud_items (system_name TEXT, body_id INTEGER, data_json TEXT, ts INTEGER, PRIMARY KEY (system_name, body_id))"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS edsm_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, queued_ts REAL NOT NULL, event_json TEXT NOT NULL)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS edsm_backfill (journal_file TEXT PRIMARY KEY, backfilled_ts REAL NOT NULL)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS colonisation_projects "
                "(market_id INTEGER PRIMARY KEY, system_name TEXT, body_name TEXT, "
                " progress REAL, complete INTEGER, failed INTEGER, "
                " resources_json TEXT, last_updated INTEGER)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS bgs_snapshots ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " system_name TEXT NOT NULL,"
                " system_address INTEGER,"
                " faction_name TEXT NOT NULL,"
                " influence REAL NOT NULL,"
                " government TEXT,"
                " allegiance TEXT,"
                " happiness TEXT,"
                " active_states TEXT,"
                " pending_states TEXT,"
                " recovering_states TEXT,"
                " event_timestamp TEXT,"
                " recorded_at REAL NOT NULL,"
                " UNIQUE(system_name, faction_name, event_timestamp)"
                ")"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_bgs_sys_ts "
                "ON bgs_snapshots(system_name, recorded_at DESC)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS visited_systems ("
                " system_name TEXT PRIMARY KEY,"
                " system_address INTEGER,"
                " last_visited_at REAL NOT NULL"
                ")"
            )
            # Seed visited_systems from existing bgs_snapshots so previously
            # tracked inhabited systems aren't lost after the migration.
            self.conn.execute(
                "INSERT OR IGNORE INTO visited_systems (system_name, last_visited_at) "
                "SELECT system_name, MAX(recorded_at) FROM bgs_snapshots GROUP BY system_name"
            )
            self.conn.commit()

        if os.path.exists(SCAN_HISTORY_FILE):
            self.migrate_json_history()

    def _db_commit(self, reason=""):
        t0 = time.perf_counter()
        self.conn.commit()
        self._db_last_commit_ts = time.time()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if hasattr(self, "_trace_record_ms"):
            try:
                self._trace_record_ms(f"db_commit:{reason or 'general'}", elapsed_ms)
            except Exception:
                pass
        if elapsed_ms >= 25.0:
            self.log(f"PERF SPIKE [db_commit:{reason or 'general'}] {elapsed_ms:.1f} ms")

    def _db_maybe_commit(self, reason=""):
        if self.batch_mode:
            return
        now = time.time()
        if (now - self._db_last_commit_ts) >= self._db_commit_interval_s:
            self._db_commit(reason=reason)

    def import_scan_cache_json(self):
        if not os.path.exists(SCAN_CACHE_FILE):
            return
        try:
            with open(SCAN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        now = int(time.time())
        with self.db_lock:
            try:
                bodies_per_system = {}
                for system_name, items in data.items():
                    if not isinstance(items, list):
                        continue
                    for idx, item in enumerate(items):
                        if not isinstance(item, dict):
                            continue
                        body_id = item.get("body_id")
                        if body_id is None:
                            continue
                        ts = item.get("_ts")
                        if not isinstance(ts, int):
                            ts = now - idx
                            item["_ts"] = ts
                        payload = json.dumps(item)
                        self.conn.execute(
                            "INSERT OR REPLACE INTO scan_hud_items (system_name, body_id, data_json, ts) VALUES (?, ?, ?, ?)",
                            (system_name, int(body_id), payload, int(ts)),
                        )
                        bodies_per_system.setdefault(system_name, set()).add(int(body_id))
                # Populate bodies and systems tables so scan_stat loads correctly
                # on the next startup without requiring a full cache rebuild.
                cur = self.conn.cursor()
                for system_name, body_ids in bodies_per_system.items():
                    for bid in body_ids:
                        self.conn.execute(
                            "INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)",
                            (system_name, bid),
                        )
                    scanned_count = len(body_ids)
                    cur.execute("SELECT total, scanned_count FROM systems WHERE name=?", (system_name,))
                    row = cur.fetchone()
                    if row:
                        new_total = max(int(row[0] or 0), scanned_count)
                        new_sc = max(int(row[1] or 0), scanned_count)
                    else:
                        new_total = scanned_count
                        new_sc = scanned_count
                    self.conn.execute(
                        "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                        (system_name, new_total, new_sc),
                    )
                self.conn.commit()
            except sqlite3.Error:
                self.conn.rollback()
                return

        try:
            os.rename(SCAN_CACHE_FILE, SCAN_CACHE_FILE + ".bak")
        except Exception:
            pass

    def load_scan_items_from_db(self, system_name):
        items = []
        with self.db_lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT data_json FROM scan_hud_items WHERE system_name=? ORDER BY ts DESC LIMIT 60",
                    (system_name,),
                )
                rows = cur.fetchall()
                for (data_json,) in rows:
                    try:
                        item = json.loads(data_json)
                        if isinstance(item, dict):
                            items.append(item)
                    except Exception:
                        pass
            except sqlite3.Error:
                return []
        return items

    def save_scan_item_to_db(self, system_name, item):
        try:
            body_id = item.get("body_id")
            ts = item.get("_ts")
            if body_id is None or ts is None:
                return
            payload = json.dumps(item)
            with self.db_lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO scan_hud_items (system_name, body_id, data_json, ts) VALUES (?, ?, ?, ?)",
                    (system_name, int(body_id), payload, int(ts)),
                )
                self._db_maybe_commit(reason="scan_item")
        except sqlite3.Error:
            return

    def migrate_json_history(self):
        self.log("📦 MIGRATING HISTORY TO DATABASE...")
        try:
            with open(SCAN_HISTORY_FILE, "r") as f:
                data = json.load(f)

            with self.db_lock:
                try:
                    for sys_name, info in data.items():
                        total = info.get("total", 0)
                        bodies = info.get("bodies", [])
                        scanned_count = info.get("scanned_count", len(bodies))

                        self.conn.execute(
                            "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                            (sys_name, total, scanned_count),
                        )
                        for bid in bodies:
                            self.conn.execute("INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)", (sys_name, bid))
                    self.conn.commit()
                except sqlite3.Error:
                    self.conn.rollback()
                    raise

            os.rename(SCAN_HISTORY_FILE, SCAN_HISTORY_FILE + ".bak")
            self.log("✅ MIGRATION COMPLETE.")
        except Exception as e:
            self.log(f"❌ MIGRATION FAILED: {e}")

    def scan_all_logs_threaded(self):
        import threading

        threading.Thread(target=self.scan_all_logs, daemon=True).start()

    def scan_all_logs(self):
        self.log("📚 STARTING HISTORY REBUILD...")

        new_history = self.watcher.scan_history(lambda p, t: self.log(f"⏳ Scanning... {int((p/t)*100)}%"))

        if not new_history:
            self.log("⚠️ No history found or scan failed.")
            return

        self.log("💾 Saving to database...")
        with self.db_lock:
            try:
                for sys_name, data in new_history.items():
                    bodies = set(data.get("bodies", []))
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                    row = cursor.fetchone()
                    existing_total = row[0] if row else 0
                    existing_scanned = row[1] if row else 0
                    cursor.execute("SELECT COUNT(*) FROM bodies WHERE system_name=?", (sys_name,))
                    existing_body_count = cursor.fetchone()[0] or 0

                    scanned_count = max(
                        int(data.get("scanned_count", 0) or 0),
                        len(bodies),
                        int(existing_scanned or 0),
                        int(existing_body_count or 0),
                    )
                    total = max(
                        int(data.get("total", 0) or 0),
                        scanned_count,
                        int(existing_total or 0),
                    )
                    if total <= 0 and scanned_count <= 0 and not bodies:
                        continue

                    for body_id in bodies:
                        self.conn.execute("INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)", (sys_name, body_id))
                    self.conn.execute(
                        "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                        (sys_name, total, scanned_count),
                    )
                self.conn.commit()
            except sqlite3.Error as e:
                self.conn.rollback()
                self.log(f"❌ DB ERROR (Rebuild): {e}")

        self.log("✅ CACHE REBUILD COMPLETE.")
        self.load_system_from_db(self.current_sys)
        self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
        self.update_hud()

        if self.config.get("edsm_upload_enabled"):
            self.edsm.run_backfill(self.config.get("journal_path", ""))

    def load_system_from_db(self, sys_name):
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                row = cursor.fetchone()
                if row:
                    self.total = row[0] or 0
                    # scanned_count may have been set by FSSAllBodiesFound or history
                    # builder without individual body IDs being written; use it as a floor.
                    db_scanned_count = row[1] or 0
                    cursor.execute("SELECT body_id FROM bodies WHERE system_name=?", (sys_name,))
                    self.scanned_bodies = set(r[0] for r in cursor.fetchall())
                    bodies_count = len(self.scanned_bodies)
                    # Clamp stored count to total so we never present scanned > total here.
                    self.scanned = max(bodies_count, min(db_scanned_count, self.total or db_scanned_count))
                    if self.scanned > self.total:
                        self.total = self.scanned
                        self.conn.execute(
                            "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                            (sys_name, self.total, self.scanned),
                        )
                        self._db_maybe_commit(reason="system_reconcile")
                else:
                    cursor.execute("SELECT body_id FROM bodies WHERE system_name=?", (sys_name,))
                    self.scanned_bodies = set(r[0] for r in cursor.fetchall())
                    self.scanned = len(self.scanned_bodies)
                    self.total = self.scanned
                    if self.scanned:
                        self.conn.execute(
                            "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                            (sys_name, self.total, self.scanned),
                        )
                        self._db_maybe_commit(reason="system_reconcile")
            except sqlite3.Error as e:
                self.log(f"❌ DB READ ERROR: {e}")
                self.total = 0
                self.scanned = 0
                self.scanned_bodies = set()

    def db_update_system(self, sys_name, total, scanned):
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                row = cursor.fetchone()
                if row:
                    total = max(int(total or 0), int(row[0] or 0))
                    scanned = int(scanned or 0)
                self.conn.execute(
                    "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                    (sys_name, total, scanned),
                )
                self._db_maybe_commit(reason="system")
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (System): {e}")

    def db_add_body(self, sys_name, body_id):
        with self.db_lock:
            try:
                self.conn.execute("INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)", (sys_name, body_id))
                self._db_maybe_commit(reason="body")
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (Body): {e}")

    # ── Colonization ──────────────────────────────────────────────────────────

    def db_save_colonisation_project(self, proj: dict):
        mid = proj.get("market_id")
        if mid is None:
            return
        with self.db_lock:
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO colonisation_projects "
                    "(market_id, system_name, body_name, progress, complete, failed, resources_json, last_updated) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(mid),
                        proj.get("system_name", ""),
                        proj.get("body_name", ""),
                        float(proj.get("progress", 0)),
                        1 if proj.get("complete") else 0,
                        1 if proj.get("failed") else 0,
                        json.dumps(proj.get("resources") or []),
                        int(proj.get("last_updated") or 0),
                    ),
                )
                self._db_maybe_commit(reason="colonisation")
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (Colonisation): {e}")

    # ── BGS ───────────────────────────────────────────────────────────────────

    def db_save_bgs_snapshot(
        self,
        system_name: str,
        system_address,
        factions: list,
        event_timestamp: str | None = None,
    ):
        """Persist a BGS faction snapshot.  Duplicate (system, faction, timestamp) rows
        are silently ignored so startup journal replay never inflates the history."""
        now = time.time()
        with self.db_lock:
            try:
                for f in factions:
                    fname = f.get("Name") or f.get("faction_name")
                    if not fname:
                        continue
                    inf = float(f.get("Influence") or f.get("influence") or 0)
                    gov = f.get("Government") or f.get("government") or ""
                    ally = f.get("Allegiance") or f.get("allegiance") or ""
                    hap = f.get("Happiness_Localised") or f.get("happiness") or ""
                    active = json.dumps([
                        {"State": (s.get("State") or s) if isinstance(s, dict) else s}
                        for s in (f.get("ActiveStates") or [])
                    ])
                    pending = json.dumps([
                        {"State": (s.get("State") or s) if isinstance(s, dict) else s}
                        for s in (f.get("PendingStates") or [])
                    ])
                    recovering = json.dumps([
                        {"State": (s.get("State") or s) if isinstance(s, dict) else s}
                        for s in (f.get("RecoveringStates") or [])
                    ])
                    self.conn.execute(
                        "INSERT OR IGNORE INTO bgs_snapshots "
                        "(system_name, system_address, faction_name, influence, "
                        " government, allegiance, happiness, active_states, "
                        " pending_states, recovering_states, event_timestamp, recorded_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (system_name, system_address, fname, inf, gov, ally, hap,
                         active, pending, recovering, event_timestamp, now),
                    )
                self._db_maybe_commit(reason="bgs")
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (BGS): {e}")

    def db_record_visit(self, system_name: str, system_address, ts: float = None):
        """Record that the commander visited system_name. Called on every jump."""
        if not system_name or system_name in ("---", "Unknown"):
            return
        now = ts or time.time()
        with self.db_lock:
            try:
                self.conn.execute(
                    "INSERT INTO visited_systems (system_name, system_address, last_visited_at) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(system_name) DO UPDATE SET "
                    "last_visited_at=excluded.last_visited_at, "
                    "system_address=excluded.system_address",
                    (system_name, system_address, now),
                )
                self._db_maybe_commit(reason="visit")
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (visit): {e}")

    def db_load_bgs_systems(self) -> list:
        """Return [(system_name, last_visited_at, has_factions)] for all visited systems."""
        results = []
        try:
            with self.db_lock:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT v.system_name, v.last_visited_at, "
                    "       CASE WHEN COUNT(b.id) > 0 THEN 1 ELSE 0 END "
                    "FROM visited_systems v "
                    "LEFT JOIN bgs_snapshots b ON b.system_name = v.system_name "
                    "GROUP BY v.system_name "
                    "ORDER BY v.last_visited_at DESC"
                )
                results = [(row[0], row[1], bool(row[2])) for row in cur.fetchall()]
        except sqlite3.Error:
            pass
        return results

    def db_load_bgs_factions(self, system_name: str) -> list:
        """Return all snapshots for system_name, newest first (up to 500 rows)."""
        results = []
        try:
            with self.db_lock:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT faction_name, influence, government, allegiance, happiness, "
                    "active_states, pending_states, recovering_states, recorded_at "
                    "FROM bgs_snapshots "
                    "WHERE system_name=? "
                    "ORDER BY recorded_at DESC "
                    "LIMIT 500",
                    (system_name,),
                )
                for row in cur.fetchall():
                    results.append({
                        "faction_name":      row[0],
                        "influence":         row[1],
                        "government":        row[2],
                        "allegiance":        row[3],
                        "happiness":         row[4],
                        "active_states":     row[5],
                        "pending_states":    row[6],
                        "recovering_states": row[7],
                        "recorded_at":       row[8],
                    })
        except sqlite3.Error:
            pass
        return results

    def db_load_colonisation_projects(self) -> dict:
        projects = {}
        try:
            with self.db_lock:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT market_id, system_name, body_name, progress, complete, failed, "
                    "resources_json, last_updated FROM colonisation_projects ORDER BY last_updated DESC"
                )
                for row in cur.fetchall():
                    mid = row[0]
                    try:
                        resources = json.loads(row[6] or "[]")
                    except Exception:
                        resources = []
                    projects[mid] = {
                        "market_id":    mid,
                        "system_name":  row[1],
                        "body_name":    row[2],
                        "progress":     float(row[3] or 0),
                        "complete":     bool(row[4]),
                        "failed":       bool(row[5]),
                        "resources":    resources,
                        "last_updated": int(row[7] or 0),
                    }
        except sqlite3.Error:
            pass
        return projects
