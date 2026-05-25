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
                self.conn.execute("BEGIN TRANSACTION")
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
                    self.conn.execute("BEGIN TRANSACTION")
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
                self.conn.execute("BEGIN TRANSACTION")
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

    def load_system_from_db(self, sys_name):
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                row = cursor.fetchone()
                if row:
                    self.total = row[0] or 0
                    cursor.execute("SELECT body_id FROM bodies WHERE system_name=?", (sys_name,))
                    self.scanned_bodies = set(r[0] for r in cursor.fetchall())
                    self.scanned = len(self.scanned_bodies)
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
