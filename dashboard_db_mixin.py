import json
import logging
import os
import shutil
import sqlite3
import threading
import time

from config import get_active_profile, get_profile_file

SCAN_HISTORY_FILE = "scan_history.json"
DB_FILE = "exploration_data.db"
SCAN_CACHE_FILE = "scan_cache.json"

_SCAN_HISTORY_EVENTS = (
    "Commander", "LoadGame", "Location", "FSDJump", "CarrierJump",
    "FSSDiscoveryScan", "FSSAllBodiesFound", "NavBeaconScan", "Scan",
)


def _journal_commander_matches(raw, commander=None, fid=None):
    expected_name = str(commander or "").strip().casefold()
    expected_fid = str(fid or "").strip().casefold()
    actual_name = str(raw.get("Commander") or raw.get("Name") or "").strip().casefold()
    actual_fid = str(raw.get("FID") or "").strip().casefold()
    if expected_fid and actual_fid:
        return expected_fid == actual_fid
    if expected_name and actual_name:
        return expected_name == actual_name
    return not bool(expected_name or expected_fid)


def import_scan_journal_history(db_path, journal_path, commander=None, fid=None):
    """Incrementally restore authoritative scan totals from profile journals.

    A dedicated SQLite connection keeps this background repair tied to the
    profile that started it, even if the live UI changes commander mid-scan.
    File signatures make the history pass a one-time cost; later starts only
    revisit journals that have grown or changed.
    """
    result = {"files": 0, "systems": set(), "completed": 0}
    if not db_path or not journal_path or not os.path.isdir(journal_path):
        return result
    try:
        files = sorted(
            os.path.join(journal_path, name)
            for name in os.listdir(journal_path)
            if name.startswith("Journal.") and name.endswith(".log")
        )
    except OSError:
        return result

    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS scan_journal_imports ("
            "journal_file TEXT PRIMARY KEY, signature TEXT NOT NULL, imported_at REAL NOT NULL)"
        )
        imported = dict(conn.execute(
            "SELECT journal_file, signature FROM scan_journal_imports"
        ).fetchall())
        aggregate = {}
        signatures = {}
        wanted = tuple(f'"{event}"' for event in _SCAN_HISTORY_EVENTS)

        for path in files:
            try:
                signature = f"{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
            except OSError:
                continue
            name = os.path.basename(path)
            if imported.get(name) == signature:
                continue
            active = not bool(commander or fid)
            context = None
            parsed = False
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        if not any(marker in line for marker in wanted):
                            continue
                        try:
                            raw = json.loads(line)
                        except (ValueError, TypeError):
                            continue
                        event = raw.get("event")
                        if event in ("Commander", "LoadGame"):
                            active = _journal_commander_matches(raw, commander, fid)
                            context = None
                            continue
                        if not active:
                            continue
                        if event in ("Location", "FSDJump") or (
                                event == "CarrierJump" and raw.get("Docked")):
                            context = raw.get("StarSystem") or context
                            continue

                        system = raw.get("SystemName") or raw.get("StarSystem") or context
                        if not system:
                            continue
                        row = aggregate.setdefault(system, {
                            "total": 0, "scanned": 0, "bodies": set(), "complete": False,
                        })
                        if event == "FSSDiscoveryScan":
                            count = int(raw.get("BodyCount") or 0)
                            row["total"] = max(row["total"], count)
                            try:
                                complete = float(raw.get("Progress")) >= 1.0
                            except (TypeError, ValueError):
                                complete = False
                            if complete:
                                row["complete"] = True
                                row["scanned"] = max(row["scanned"], count)
                        elif event == "FSSAllBodiesFound":
                            count = int(raw.get("Count") or raw.get("BodyCount") or 0)
                            row["total"] = max(row["total"], count)
                            row["scanned"] = max(row["scanned"], count)
                            row["complete"] = True
                        elif event == "NavBeaconScan":
                            count = int(raw.get("NumBodies") or 0)
                            row["total"] = max(row["total"], count)
                            row["scanned"] = max(row["scanned"], count)
                            row["complete"] = True
                        elif event == "Scan" and (
                                "StarType" in raw or "PlanetClass" in raw):
                            body_id = raw.get("BodyID")
                            if body_id is not None:
                                try:
                                    row["bodies"].add(int(body_id))
                                except (TypeError, ValueError):
                                    pass
                        parsed = True
            except OSError:
                continue
            if parsed or os.path.exists(path):
                signatures[name] = signature

        if not signatures:
            return result

        now = time.time()
        conn.execute("BEGIN")
        try:
            for system, evidence in aggregate.items():
                old = conn.execute(
                    "SELECT total, scanned_count FROM systems WHERE name=?", (system,),
                ).fetchone() or (0, 0)
                body_count = len(evidence["bodies"])
                total = max(int(old[0] or 0), int(evidence["total"] or 0), body_count)
                scanned = max(int(old[1] or 0), int(evidence["scanned"] or 0), body_count)
                if evidence["complete"] and total > 0:
                    scanned = max(scanned, total)
                total = max(total, scanned)
                for body_id in evidence["bodies"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)",
                        (system, body_id),
                    )
                if (total, scanned) != (int(old[0] or 0), int(old[1] or 0)):
                    conn.execute(
                        "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                        (system, total, scanned),
                    )
                    result["systems"].add(system)
                    if evidence["complete"]:
                        result["completed"] += 1
            for name, signature in signatures.items():
                conn.execute(
                    "INSERT OR REPLACE INTO scan_journal_imports "
                    "(journal_file, signature, imported_at) VALUES (?, ?, ?)",
                    (name, signature, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        result["files"] = len(signatures)
        return result
    finally:
        conn.close()


class DashboardDBMixin:
    def _profile_file(self, filename):
        return get_profile_file(get_active_profile(self.config), filename)

    def _copy_legacy_profile_file(self, filename):
        src = os.path.abspath(filename)
        dst = self._profile_file(filename)
        if os.path.exists(dst) or not os.path.exists(src):
            return dst
        if len(self.config.get("commander_profiles", {})) > 1:
            return dst
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass
        return dst

    def import_scan_journal_history(self, journal_path, commander=None, fid=None,
                                    db_path=None):
        return import_scan_journal_history(
            db_path or getattr(self, "db_path", None),
            journal_path, commander, fid,
        )

    def init_db(self):
        """Initialize SQLite database and migrate JSON if needed."""
        db_path = self._copy_legacy_profile_file(DB_FILE)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._db_last_commit_ts = time.time()
        self._db_commit_interval_s = max(0.05, float(self.config.get("db_commit_interval_ms", 250)) / 1000.0)
        with self.db_lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            # NORMAL+WAL significantly reduces fsync spikes while preserving good durability.
            self.conn.execute("PRAGMA synchronous = NORMAL")
            self.conn.execute("CREATE TABLE IF NOT EXISTS systems (name TEXT PRIMARY KEY, total INTEGER, scanned_count INTEGER)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS bodies (system_name TEXT, body_id INTEGER, PRIMARY KEY (system_name, body_id))")
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS scan_journal_imports ("
                "journal_file TEXT PRIMARY KEY, signature TEXT NOT NULL, imported_at REAL NOT NULL)"
            )
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
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS bgs_hidden_systems ("
                " system_name TEXT PRIMARY KEY,"
                " hidden_at REAL NOT NULL"
                ")"
            )
            # Seed visited_systems from existing bgs_snapshots so previously
            # tracked inhabited systems aren't lost after the migration.
            self.conn.execute(
                "INSERT OR IGNORE INTO visited_systems (system_name, last_visited_at) "
                "SELECT system_name, MAX(recorded_at) FROM bgs_snapshots GROUP BY system_name"
            )
            self.conn.commit()

        if os.path.exists(self._profile_file(SCAN_HISTORY_FILE)) or os.path.exists(SCAN_HISTORY_FILE):
            self.migrate_json_history()
        self._start_db_commit_worker()

    def _start_db_commit_worker(self):
        """Commit routine journal writes away from Tk's event thread."""
        conn = self.conn
        db_lock = self.db_lock
        event = threading.Event()
        stopping = threading.Event()
        reasons_lock = threading.Lock()
        reasons = set()
        state = {
            "conn": conn,
            "event": event,
            "stopping": stopping,
            "reasons_lock": reasons_lock,
            "reasons": reasons,
            "close": False,
        }

        def _worker():
            while True:
                event.wait()
                if not stopping.is_set():
                    stopping.wait(self._db_commit_interval_s)
                event.clear()
                with reasons_lock:
                    reason = "+".join(sorted(reasons)) or "background"
                    reasons.clear()
                try:
                    with db_lock:
                        self._commit_connection(conn, reason=reason, background=True)
                except Exception as exc:
                    logging.warning("Background exploration DB commit failed: %s", exc)
                if stopping.is_set():
                    if state.get("close"):
                        try:
                            with db_lock:
                                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                                conn.close()
                        except Exception as exc:
                            logging.warning("Exploration DB background close failed: %s", exc)
                    return

        thread = threading.Thread(
            target=_worker, name="exploration-db-commit", daemon=True,
        )
        state["thread"] = thread
        self._db_commit_worker_state = state
        thread.start()

    def _request_db_commit(self, reason=""):
        state = getattr(self, "_db_commit_worker_state", None)
        if not state or state.get("stopping").is_set():
            # Lightweight test doubles and early startup use the synchronous
            # path; the live app installs the worker during init_db().
            self._db_commit(reason=reason)
            return
        with state["reasons_lock"]:
            state["reasons"].add(reason or "general")
        state["event"].set()

    def _stop_db_commit_worker(self, *, close=False, timeout=0.35):
        state = getattr(self, "_db_commit_worker_state", None)
        if not state:
            return True
        state["close"] = bool(close)
        state["stopping"].set()
        state["event"].set()
        state["thread"].join(timeout=max(0.0, float(timeout)))
        finished = not state["thread"].is_alive()
        if finished and getattr(self, "_db_commit_worker_state", None) is state:
            self._db_commit_worker_state = None
        return finished

    def _commit_connection(self, conn, reason="", background=False):
        t0 = time.perf_counter()
        conn.commit()
        self._db_last_commit_ts = time.time()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if hasattr(self, "_trace_record_ms"):
            try:
                self._trace_record_ms(f"db_commit:{reason or 'general'}", elapsed_ms)
            except Exception:
                pass
        if elapsed_ms >= 25.0:
            message = f"PERF SPIKE [db_commit:{reason or 'general'}] {elapsed_ms:.1f} ms"
            if background:
                logging.warning(message)
            else:
                self.log(message)

    def _db_commit(self, reason=""):
        self._commit_connection(self.conn, reason=reason)

    def _db_maybe_commit(self, reason=""):
        if self.batch_mode:
            return
        self._request_db_commit(reason=reason)

    def import_scan_cache_json(self):
        scan_cache_file = self._copy_legacy_profile_file(SCAN_CACHE_FILE)
        if not os.path.exists(scan_cache_file):
            return
        try:
            with open(scan_cache_file, "r", encoding="utf-8") as f:
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
            os.rename(scan_cache_file, scan_cache_file + ".bak")
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
            try:
                body_id = int(body_id)
            except Exception:
                return
            with self.db_lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO scan_hud_items (system_name, body_id, data_json, ts) VALUES (?, ?, ?, ?)",
                    (system_name, body_id, payload, int(ts)),
                )
                self._db_maybe_commit(reason="scan_item")
                if hasattr(self, "_refresh_value_ledger_window"):
                    self._refresh_value_ledger_window()
                if hasattr(self, "_refresh_exploration_window"):
                    self._refresh_exploration_window()
        except Exception as e:
            try:
                self.log(f"Scan item save skipped: {e}")
            except Exception:
                pass
            return

    def migrate_json_history(self):
        self.log("📦 MIGRATING HISTORY TO DATABASE...")
        try:
            scan_history_file = self._copy_legacy_profile_file(SCAN_HISTORY_FILE)
            with open(scan_history_file, "r") as f:
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

            os.rename(scan_history_file, scan_history_file + ".bak")
            self.log("✅ MIGRATION COMPLETE.")
        except Exception as e:
            self.log(f"❌ MIGRATION FAILED: {e}")

    def scan_all_logs_threaded(self):
        import threading

        # Snapshot the profile preference on the UI thread so this rebuild is
        # not affected by a later profile switch or checkbox change.
        upload_history_to_edsm = bool(
            self.config.get("edsm_backfill_on_cache_rebuild", True)
        )
        threading.Thread(
            target=self.scan_all_logs,
            kwargs={"upload_history_to_edsm": upload_history_to_edsm},
            daemon=True,
        ).start()

    def scan_all_logs(self, upload_history_to_edsm=None):
        if upload_history_to_edsm is None:
            upload_history_to_edsm = bool(
                self.config.get("edsm_backfill_on_cache_rebuild", True)
            )
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

        if self.config.get("edsm_upload_enabled") and upload_history_to_edsm:
            self.edsm.run_backfill(self.config.get("journal_path", ""))
        elif self.config.get("edsm_upload_enabled"):
            self.log("ℹ️ EDSM history upload skipped for this cache rebuild.")

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
        # Every caller now receives matching Navigation HUD progress as well
        # as the raw counts. This covers startup snapshots, profile switches,
        # history repairs and manual database rebuilds from one source.
        if hasattr(self, "_seed_navigation_scan_progress"):
            self._seed_navigation_scan_progress()

    def db_update_system(self, sys_name, total, scanned):
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                row = cursor.fetchone()
                if row:
                    total = max(int(total or 0), int(row[0] or 0))
                    # Survey knowledge is cumulative. A return visit may emit
                    # Location before any Scan events, but that must never erase
                    # a previous FSSAllBodiesFound/NavBeacon completion.
                    scanned = max(int(scanned or 0), int(row[1] or 0))
                else:
                    total = int(total or 0)
                    scanned = int(scanned or 0)
                total = max(total, scanned)
                self.conn.execute(
                    "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                    (sys_name, total, scanned),
                )
                self._db_maybe_commit(reason="system")
                if hasattr(self, "_refresh_exploration_window"):
                    self._refresh_exploration_window()
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
                if self.batch_mode:
                    hidden = self.conn.execute(
                        "SELECT 1 FROM bgs_hidden_systems WHERE system_name=?",
                        (system_name,),
                    ).fetchone()
                    if hidden:
                        return
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
                if hasattr(self, "_refresh_bgs_window"):
                    self._refresh_bgs_window()
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (BGS): {e}")

    def db_record_visit(self, system_name: str, system_address, ts: float = None):
        """Record that the commander visited system_name. Called on every jump."""
        if not system_name or system_name in ("---", "Unknown"):
            return
        now = ts or time.time()
        with self.db_lock:
            try:
                if not self.batch_mode:
                    # A real revisit restores a system that was explicitly
                    # removed from BGS. Startup journal replay leaves it hidden.
                    self.conn.execute(
                        "DELETE FROM bgs_hidden_systems WHERE system_name=?",
                        (system_name,),
                    )
                self.conn.execute(
                    "INSERT INTO visited_systems (system_name, system_address, last_visited_at) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(system_name) DO UPDATE SET "
                    "last_visited_at=excluded.last_visited_at, "
                    "system_address=excluded.system_address",
                    (system_name, system_address, now),
                )
                self._db_maybe_commit(reason="visit")
                if hasattr(self, "_refresh_bgs_window"):
                    self._refresh_bgs_window()
                if hasattr(self, "_refresh_exploration_window"):
                    self._refresh_exploration_window()
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (visit): {e}")

    def db_load_bgs_systems(self) -> list:
        """Return [(system_name, last_visited_at, has_factions)] for all visited systems."""
        cached = list(getattr(self, "_bgs_systems_cache", []))
        if not self.db_lock.acquire(blocking=False):
            return cached
        results = []
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT v.system_name, v.last_visited_at, "
                "       EXISTS(SELECT 1 FROM bgs_snapshots b "
                "              WHERE b.system_name = v.system_name) "
                "FROM visited_systems v "
                "WHERE NOT EXISTS(SELECT 1 FROM bgs_hidden_systems h "
                "                 WHERE h.system_name = v.system_name) "
                "ORDER BY v.last_visited_at DESC"
            )
            results = [(row[0], row[1], bool(row[2])) for row in cur.fetchall()]
            self._bgs_systems_cache = list(results)
        except sqlite3.Error:
            return cached
        finally:
            self.db_lock.release()
        return results

    def db_delete_bgs_system(self, system_name: str) -> bool:
        """Remove one system from BGS without deleting shared exploration history."""
        if not system_name or not self.db_lock.acquire(blocking=False):
            return False
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO bgs_hidden_systems (system_name, hidden_at) VALUES (?, ?)",
                (system_name, time.time()),
            )
            self.conn.execute("DELETE FROM bgs_snapshots WHERE system_name=?", (system_name,))
            self._request_db_commit(reason="bgs_delete")
            self._bgs_systems_cache = [
                row for row in getattr(self, "_bgs_systems_cache", [])
                if row[0] != system_name
            ]
            cache = dict(getattr(self, "_bgs_factions_cache", {}))
            cache.pop(system_name, None)
            self._bgs_factions_cache = cache
            return True
        except sqlite3.Error as exc:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            self.log(f"❌ DB ERROR (BGS delete): {exc}")
            return False
        finally:
            self.db_lock.release()

    def db_purge_bgs(self) -> bool:
        """Clear the BGS list and snapshots while retaining exploration visits."""
        if not self.db_lock.acquire(blocking=False):
            return False
        try:
            now = time.time()
            self.conn.execute(
                "INSERT OR REPLACE INTO bgs_hidden_systems (system_name, hidden_at) "
                "SELECT system_name, ? FROM visited_systems",
                (now,),
            )
            self.conn.execute("DELETE FROM bgs_snapshots")
            self._request_db_commit(reason="bgs_purge")
            self._bgs_systems_cache = []
            self._bgs_factions_cache = {}
            return True
        except sqlite3.Error as exc:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            self.log(f"❌ DB ERROR (BGS purge): {exc}")
            return False
        finally:
            self.db_lock.release()

    def db_purge_empty_bgs_systems(self) -> int | None:
        """Hide visible BGS systems with no faction snapshots; return the count."""
        if not self.db_lock.acquire(blocking=False):
            return None
        try:
            cursor = self.conn.execute(
                "INSERT OR REPLACE INTO bgs_hidden_systems (system_name, hidden_at) "
                "SELECT v.system_name, ? FROM visited_systems v "
                "WHERE NOT EXISTS(SELECT 1 FROM bgs_snapshots b "
                "                 WHERE b.system_name = v.system_name) "
                "  AND NOT EXISTS(SELECT 1 FROM bgs_hidden_systems h "
                "                 WHERE h.system_name = v.system_name)",
                (time.time(),),
            )
            removed = max(0, int(cursor.rowcount or 0))
            self._request_db_commit(reason="bgs_purge_empty")
            self._bgs_systems_cache = [
                row for row in getattr(self, "_bgs_systems_cache", [])
                if len(row) > 2 and row[2]
            ]
            return removed
        except sqlite3.Error as exc:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            self.log(f"❌ DB ERROR (BGS purge empty): {exc}")
            return None
        finally:
            self.db_lock.release()

    def db_load_bgs_factions(self, system_name: str) -> list:
        """Return all snapshots for system_name, newest first (up to 500 rows)."""
        cache = getattr(self, "_bgs_factions_cache", {})
        cached = list(cache.get(system_name, []))
        if not self.db_lock.acquire(blocking=False):
            return cached
        results = []
        try:
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
            cache = dict(cache)
            cache[system_name] = list(results)
            self._bgs_factions_cache = cache
        except sqlite3.Error:
            return cached
        finally:
            self.db_lock.release()
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
