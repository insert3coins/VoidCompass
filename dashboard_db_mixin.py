import json
import logging
import os
import shutil
import sqlite3
import threading
import time

from config import get_active_profile, get_profile_dir, get_profile_file
from profile_backups import automatic_backup

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


def scan_single_system_journal_evidence(journal_path, system_name, commander=None, fid=None):
    """Read only the journal facts needed to repair one system record."""
    result = {
        "system": str(system_name or "").strip(), "files": 0, "events": 0,
        "total": 0, "scanned": 0, "complete": False, "bodies": set(),
        "latest_timestamp": "",
    }
    if not result["system"] or not journal_path or not os.path.isdir(journal_path):
        return result
    try:
        files = sorted(
            os.path.join(journal_path, name) for name in os.listdir(journal_path)
            if name.startswith("Journal.") and name.endswith(".log")
        )
    except OSError:
        return result
    wanted_system = result["system"].casefold()
    markers = tuple(f'"{event}"' for event in _SCAN_HISTORY_EVENTS)
    for path in files:
        active = not bool(commander or fid)
        context = None
        matched_file = False
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not any(marker in line for marker in markers):
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
                    if event in ("Location", "FSDJump") or (event == "CarrierJump" and raw.get("Docked")):
                        context = raw.get("StarSystem") or context
                        continue
                    system = raw.get("SystemName") or raw.get("StarSystem") or context
                    if str(system or "").casefold() != wanted_system:
                        continue
                    matched_file = True
                    result["events"] += 1
                    result["latest_timestamp"] = max(
                        result["latest_timestamp"], str(raw.get("timestamp") or ""),
                    )
                    if event == "FSSDiscoveryScan":
                        count = int(raw.get("BodyCount") or 0)
                        result["total"] = max(result["total"], count)
                        try:
                            complete = float(raw.get("Progress")) >= 1.0
                        except (TypeError, ValueError):
                            complete = False
                        if complete:
                            result["complete"] = True
                            result["scanned"] = max(result["scanned"], count)
                    elif event == "FSSAllBodiesFound":
                        count = int(raw.get("Count") or raw.get("BodyCount") or 0)
                        result["total"] = max(result["total"], count)
                        result["scanned"] = max(result["scanned"], count)
                        result["complete"] = True
                    elif event == "NavBeaconScan":
                        count = int(raw.get("NumBodies") or 0)
                        result["total"] = max(result["total"], count)
                        result["scanned"] = max(result["scanned"], count)
                        result["complete"] = True
                    elif event == "Scan" and ("StarType" in raw or "PlanetClass" in raw):
                        try:
                            result["bodies"].add(int(raw.get("BodyID")))
                        except (TypeError, ValueError):
                            pass
        except OSError:
            continue
        if matched_file:
            result["files"] += 1
    body_count = len(result["bodies"])
    result["scanned"] = max(result["scanned"], body_count)
    result["total"] = max(result["total"], result["scanned"])
    if result["complete"] and result["total"]:
        result["scanned"] = result["total"]
    return result


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

    def survey_evidence_snapshot(self, system=None):
        system = str(system or getattr(self, "current_sys", "") or "Unknown")
        db = {"total": 0, "scanned": 0, "body ids": 0, "cached body details": 0,
              "latest cached detail": "-", "journal imports indexed": 0}
        with self.db_lock:
            try:
                row = self.conn.execute(
                    "SELECT total, scanned_count FROM systems WHERE name=?", (system,),
                ).fetchone() or (0, 0)
                db["total"], db["scanned"] = int(row[0] or 0), int(row[1] or 0)
                db["body ids"] = int(self.conn.execute(
                    "SELECT COUNT(*) FROM bodies WHERE system_name=?", (system,),
                ).fetchone()[0] or 0)
                detail = self.conn.execute(
                    "SELECT COUNT(*), MAX(ts) FROM scan_hud_items WHERE system_name=?", (system,),
                ).fetchone() or (0, None)
                db["cached body details"] = int(detail[0] or 0)
                db["latest cached detail"] = (
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(detail[1])))
                    if detail[1] else "-"
                )
                db["journal imports indexed"] = int(self.conn.execute(
                    "SELECT COUNT(*) FROM scan_journal_imports"
                ).fetchone()[0] or 0)
            except sqlite3.Error as exc:
                db["database error"] = str(exc)
        tracker = getattr(self, "deep_survey", None)
        deep = tracker.snapshot() if tracker else {}
        route_rows = [
            row for row in (deep.get("route_points") or [])
            if str(row.get("system") or "").casefold() == system.casefold()
        ]
        edsm = {}
        try:
            cache_path = self._profile_file("exploration_edsm_cache.json")
            with open(cache_path, "r", encoding="utf-8") as handle:
                edsm = (json.load(handle) or {}).get(system) or {}
        except (OSError, ValueError, TypeError):
            pass
        return {
            "system": system,
            "live_ui": {
                "scanned": int(getattr(self, "scanned", 0) or 0),
                "total": int(getattr(self, "total", 0) or 0),
                "body details": len(getattr(self, "scan_items", []) or []),
                "navigation progress": getattr(self, "navigation_scan_progress", None),
                "navigation source": getattr(self, "navigation_scan_progress_source", "-") or "-",
            },
            "profile_database": db,
            "deep_survey": {
                "route observations": len(route_rows),
                "latest event": str(route_rows[-1].get("timestamp") or "-") if route_rows else "-",
            },
            "edsm_cache": {
                "record present": bool(edsm),
                "body count": edsm.get("bodyCount") or edsm.get("bodies") or "-",
                "estimated value": edsm.get("estimatedValue") or "-",
                "estimated mapped value": edsm.get("estimatedValueMapped") or "-",
            },
            "traffic": dict(getattr(self, "system_traffic", {}) or {}),
        }

    def repair_system_from_journals(self, system):
        """Repair one system from authoritative local journals without EDSM activity."""
        system = str(system or "").strip()
        evidence = scan_single_system_journal_evidence(
            self.config.get("journal_path") or getattr(getattr(self, "watcher", None), "journal_path", ""),
            system, getattr(self, "cmdr_name", None), getattr(self, "cmdr_fid", None),
        )
        if not evidence.get("events"):
            return evidence
        with self.db_lock:
            try:
                old = self.conn.execute(
                    "SELECT total, scanned_count FROM systems WHERE name=?", (system,),
                ).fetchone() or (0, 0)
                for body_id in evidence.get("bodies") or ():
                    self.conn.execute(
                        "INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)",
                        (system, body_id),
                    )
                total = max(int(old[0] or 0), int(evidence.get("total") or 0))
                scanned = max(int(old[1] or 0), int(evidence.get("scanned") or 0))
                total = max(total, scanned)
                self.conn.execute(
                    "INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)",
                    (system, total, scanned),
                )
                self.conn.commit()
                evidence["total"], evidence["scanned"] = total, scanned
            except sqlite3.Error:
                self.conn.rollback()
                raise
        repaired = {"systems": {system}, "files": evidence.get("files", 0)}
        post = getattr(self, "_ui_post", None)
        if callable(post):
            post(self._apply_scan_history_repair, repaired, get_active_profile(self.config),
                 key=f"system-evidence-repair:{system.casefold()}")
        return evidence

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
                "CREATE TABLE IF NOT EXISTS visited_systems ("
                " system_name TEXT PRIMARY KEY,"
                " system_address INTEGER,"
                " last_visited_at REAL NOT NULL"
                ")"
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

        if getattr(self, "_cache_rebuild_running", False):
            self._cache_rebuild_feed("Cache rebuild is already in progress.")
            return

        # Snapshot the profile preference on the UI thread so this rebuild is
        # not affected by a later profile switch or checkbox change.
        upload_history_to_edsm = bool(
            self.config.get("edsm_backfill_on_cache_rebuild", True)
        )
        self._cache_rebuild_running = True
        update_button = getattr(self, "_update_cache_rebuild_button", None)
        if callable(update_button):
            update_button(True, 0)
        threading.Thread(
            target=self.scan_all_logs,
            kwargs={"upload_history_to_edsm": upload_history_to_edsm},
            daemon=True,
        ).start()

    def _cache_rebuild_feed(self, message, severity="INFO"):
        publish = getattr(self, "add_event_feed_entry", None)
        if callable(publish):
            publish("CACHE", message, severity=severity)

    def _post_cache_rebuild_progress(self, running, percent=None):
        update_button = getattr(self, "_update_cache_rebuild_button", None)
        post = getattr(self, "_ui_post", None)
        if callable(update_button) and callable(post):
            post(
                update_button, running, percent,
                key="cache-rebuild-button",
            )

    def scan_all_logs(self, upload_history_to_edsm=None):
        if upload_history_to_edsm is None:
            upload_history_to_edsm = bool(
                self.config.get("edsm_backfill_on_cache_rebuild", True)
            )
        self._cache_rebuild_running = True
        started_at = time.monotonic()
        edsm_enabled = bool(self.config.get("edsm_upload_enabled"))
        edsm_requested = edsm_enabled and bool(upload_history_to_edsm)
        edsm_mode = "EDSM history enabled" if edsm_requested else "local cache only"
        self._cache_rebuild_feed(f"Cache rebuild started · {edsm_mode}.")
        try:
            profile_key = get_active_profile(self.config)
            backup = automatic_backup(
                profile_key, get_profile_dir(profile_key), reason="before_cache_rebuild", keep=5,
            )
            if backup:
                self._cache_rebuild_feed("Profile safety snapshot ready; scanning journals.")
        except Exception as exc:
            self._cache_rebuild_feed(
                f"Profile safety snapshot skipped: {exc}", severity="WARN",
            )

        last_progress_milestone = -10

        def report_progress(processed, total):
            nonlocal last_progress_milestone
            try:
                processed = max(0, int(processed))
                total = max(1, int(total))
                percent = max(0, min(99, int((processed / total) * 100)))
            except (TypeError, ValueError, ZeroDivisionError):
                return
            self._post_cache_rebuild_progress(True, percent)
            milestone = (percent // 10) * 10
            if milestone >= 10 and milestone > last_progress_milestone:
                last_progress_milestone = milestone
                self._cache_rebuild_feed(
                    f"Cache rebuild progress · {milestone}% "
                    f"({min(processed, total)}/{total} journal files)."
                )

        try:
            try:
                new_history = self.watcher.scan_history(report_progress)
            except Exception as exc:
                logging.exception("History cache rebuild failed while scanning journals")
                self._cache_rebuild_feed(
                    f"Cache rebuild failed while scanning journals: {exc}",
                    severity="FAIL",
                )
                return

            if not new_history:
                self._cache_rebuild_feed(
                    "Cache rebuild found no matching journal history.",
                    severity="WARN",
                )
                return

            self._post_cache_rebuild_progress(True, 100)
            self._cache_rebuild_feed(
                f"Journal scan complete · {len(new_history):,} systems found; updating cache."
            )
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
                except sqlite3.Error as exc:
                    self.conn.rollback()
                    self._cache_rebuild_feed(
                        f"Cache rebuild database update failed: {exc}",
                        severity="FAIL",
                    )
                    return

            self.load_system_from_db(self.current_sys)
            self._ui_post(
                lambda: self.scan_stat.config(text=self._scan_progress_count_text()),
                key="cache-rebuild-scan-progress",
            )
            self.update_hud()

            if edsm_requested:
                self.edsm.run_backfill(self.config.get("journal_path", ""))

            elapsed = max(0.0, time.monotonic() - started_at)
            if edsm_requested:
                completion = "EDSM history backfill requested"
            elif edsm_enabled:
                completion = "EDSM history skipped"
            else:
                completion = "EDSM upload disabled"
            self._cache_rebuild_feed(
                f"Cache rebuild complete · {len(new_history):,} systems · "
                f"{elapsed:.1f}s · {completion}."
            )
        finally:
            self._cache_rebuild_running = False
            self._post_cache_rebuild_progress(False)

    def load_system_from_db(self, sys_name, preserve_total_confirmation=False):
        with self.db_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                row = cursor.fetchone()
                if row:
                    self.total = row[0] or 0
                    if not preserve_total_confirmation:
                        self.scan_total_confirmed = self.total > 0
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
                    elif preserve_total_confirmation and self.total > self.scanned:
                        # An N/M cache row (N < M) necessarily contains a
                        # separately observed system total, so it is safe to
                        # improve an older unconfirmed shutdown snapshot.
                        self.scan_total_confirmed = True
                else:
                    self.scan_total_confirmed = False
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
                if hasattr(self, "_refresh_exploration_window"):
                    self._refresh_exploration_window()
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (visit): {e}")

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
