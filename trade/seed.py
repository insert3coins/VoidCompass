"""Downloads the Spansh galaxy_populated dump and imports station markets into
the local SQLite database. Runs in a background thread; progress is polled via
Seeder.progress() -> /api/marketdb/status."""

import gzip
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from . import marketdb

DUMP_URL = "https://downloads.spansh.co.uk/galaxy_populated.json.gz"
DUMP_PATH = marketdb.DATA_DIR / "galaxy_populated.json.gz"
PROGRESS_PATH = marketdb.DATA_DIR / "market_seed_progress.json"
BUILD_DB_PATH = marketdb.DATA_DIR / "market_build.db"
HEADERS = {"User-Agent": "EliteTrader/1.0 (personal ED companion app)"}
COMMIT_EVERY = 2000  # build DB runs in its own process; larger batches are much faster
DOWNLOAD_THROTTLE_S = 0.008
IMPORT_YIELD_EVERY = 250
IMPORT_THROTTLE_S = 0.001

MARKET_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(name COLLATE NOCASE)",
    "CREATE INDEX IF NOT EXISTS idx_systems_x ON systems(x)",
    "CREATE INDEX IF NOT EXISTS idx_systems_xyz ON systems(x, y, z)",
    "CREATE INDEX IF NOT EXISTS idx_stations_system ON stations(system_id64)",
    "CREATE INDEX IF NOT EXISTS idx_stations_system_updated ON stations(system_id64, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_stations_updated ON stations(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_stations_pad_updated ON stations(large_pad, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_commodities_symbol_market ON commodities(symbol, market_id)",
    "CREATE INDEX IF NOT EXISTS idx_commodities_symbol_supply ON commodities(symbol, supply, buy_price)",
    "CREATE INDEX IF NOT EXISTS idx_commodities_symbol_demand ON commodities(symbol, demand, sell_price)",
    "CREATE INDEX IF NOT EXISTS idx_commodity_names_name ON commodity_names(name COLLATE NOCASE)",
)


class Seeder:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._process = None
        self._progress_file_enabled = False
        self._last_progress_write = 0.0
        self.reset()

    def reset(self):
        self.phase = "idle"  # idle | downloading | importing | indexing | done | error
        self.error = None
        self.downloaded = 0
        self.total_bytes = 0
        self.systems_done = 0
        self.stations_done = 0
        self.started_at = None
        self.finished_at = None
        self.polite = True

    def progress(self):
        worker_progress = None
        if self._process is not None:
            worker_progress = self._read_worker_progress()
            if worker_progress:
                if self._process.poll() is not None and worker_progress.get("phase") not in ("done", "error"):
                    worker_progress["phase"] = "error"
                    worker_progress["error"] = "Market database worker exited before reporting completion."
                return worker_progress
        with self._lock:
            return {
                "phase": self.phase,
                "error": self.error,
                "downloaded_mb": round(self.downloaded / 1e6),
                "total_mb": round(self.total_bytes / 1e6),
                "systems_done": self.systems_done,
                "stations_done": self.stations_done,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "polite": self.polite,
            }

    def running(self):
        if self._process is not None:
            return self._process.poll() is None
        return self._thread is not None and self._thread.is_alive()

    def start(self, include_carriers=False, keep_dump=False, polite=True):
        if self.running():
            return False
        self.reset()
        self.polite = bool(polite)
        self._set(phase="starting", started_at=marketdb.utc_now_iso())
        self._write_progress(force=True)
        try:
            self._process = self._start_worker_process(include_carriers, keep_dump, bool(polite))
        except Exception as exc:
            self._set(phase="error", error=f"{type(exc).__name__}: {exc}", finished_at=marketdb.utc_now_iso())
            self._write_progress(force=True)
            return False
        return True

    # ---------- internals ----------

    def _set(self, **kw):
        with self._lock:
            for k, v in kw.items():
                setattr(self, k, v)
        if self._progress_file_enabled:
            self._write_progress()

    def _start_worker_process(self, include_carriers, keep_dump, polite):
        marketdb.DATA_DIR.mkdir(parents=True, exist_ok=True)
        script = os.environ.get("VC_TRADE_SEED_WORKER_SCRIPT") or str(Path(__file__).resolve().parent.parent / "market_builder.py")
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--trade-seed-worker"]
        else:
            cmd = [sys.executable, script, "--trade-seed-worker"]
        cmd.extend([
            f"--include-carriers={1 if include_carriers else 0}",
            f"--keep-dump={1 if keep_dump else 0}",
            f"--polite={1 if polite else 0}",
        ])
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.Popen(
            cmd,
            cwd=str(marketdb.DATA_DIR.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    def _write_progress(self, force=False):
        now = time.monotonic()
        if not force and now - self._last_progress_write < 0.2:
            return
        self._last_progress_write = now
        try:
            marketdb.DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = self.progress()
            tmp = PROGRESS_PATH.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            tmp.replace(PROGRESS_PATH)
        except Exception:
            pass

    def _read_worker_progress(self):
        try:
            if not PROGRESS_PATH.exists():
                return None
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _run(self, include_carriers, keep_dump, polite):
        if polite:
            self._lower_thread_priority()
        self._set(started_at=marketdb.utc_now_iso())
        try:
            self._download(polite)
            self._import(include_carriers, polite)
            if not keep_dump:
                DUMP_PATH.unlink(missing_ok=True)
            self._set(phase="done", finished_at=marketdb.utc_now_iso())
        except Exception as exc:  # surfaced to the UI, not raised into the void
            self._set(phase="error", error=f"{type(exc).__name__}: {exc}")
        finally:
            if self._progress_file_enabled:
                self._write_progress(force=True)

    def _lower_thread_priority(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentThread()
            # THREAD_MODE_BACKGROUND_BEGIN tells Windows this thread is doing
            # background work, reducing CPU, disk, and memory scheduling impact.
            if not kernel32.SetThreadPriority(handle, 0x00010000):
                kernel32.SetThreadPriority(handle, -1)  # THREAD_PRIORITY_BELOW_NORMAL
        except Exception:
            pass

    def _download(self, polite):
        marketdb.DATA_DIR.mkdir(parents=True, exist_ok=True)
        head = requests.head(DUMP_URL, headers=HEADERS, timeout=30)
        head.raise_for_status()
        total = int(head.headers.get("Content-Length", 0))
        self._set(phase="downloading", total_bytes=total)

        if DUMP_PATH.exists() and total and DUMP_PATH.stat().st_size == total:
            self._set(downloaded=total)  # already fully downloaded earlier
            return

        part = DUMP_PATH.with_suffix(".gz.part")
        with requests.get(DUMP_URL, headers=HEADERS, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            done = 0
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    self._set(downloaded=done)
                    if polite:
                        time.sleep(DOWNLOAD_THROTTLE_S)
        part.replace(DUMP_PATH)

    def _import(self, include_carriers, polite):
        self._set(phase="importing")
        self._remove_build_db()
        conn = marketdb.connect(BUILD_DB_PATH)
        try:
            self._prepare_build_connection(conn)
            cur = conn.cursor()
            names_seen = set()
            in_batch = 0
            with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
                yielded = 0
                for line in f:
                    line = line.strip().rstrip(",")
                    if not line or line in ("[", "]"):
                        continue
                    try:
                        system = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._import_system(cur, system, include_carriers, names_seen)
                    in_batch += 1
                    yielded += 1
                    if in_batch >= COMMIT_EVERY:
                        conn.commit()
                        in_batch = 0
                        if self._progress_file_enabled:
                            self._write_progress()
                    if polite and yielded >= IMPORT_YIELD_EVERY:
                        yielded = 0
                        if self._progress_file_enabled:
                            self._write_progress()
                        time.sleep(IMPORT_THROTTLE_S)
            marketdb.set_meta(cur, "seeded_at", marketdb.utc_now_iso())
            marketdb.set_meta(cur, "seed_source", DUMP_URL)
            conn.commit()
            self._create_build_indexes(conn)
        finally:
            conn.close()
        self._swap_build_db()

    def _prepare_build_connection(self, conn):
        try:
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA locking_mode = EXCLUSIVE")
            conn.execute("PRAGMA cache_size = -131072")
        except Exception:
            pass
        cur = conn.cursor()
        for name in (
            "idx_systems_name",
            "idx_systems_x",
            "idx_systems_xyz",
            "idx_stations_system",
            "idx_stations_system_updated",
            "idx_stations_updated",
            "idx_stations_pad_updated",
            "idx_commodities_symbol_market",
            "idx_commodities_symbol_supply",
            "idx_commodities_symbol_demand",
            "idx_commodity_names_name",
        ):
            cur.execute(f"DROP INDEX IF EXISTS {name}")
        conn.commit()

    def _create_build_indexes(self, conn):
        self._set(phase="indexing")
        cur = conn.cursor()
        for sql in MARKET_INDEXES:
            cur.execute(sql)
        conn.commit()

    def _remove_build_db(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                Path(str(BUILD_DB_PATH) + suffix).unlink(missing_ok=True)
            except Exception:
                pass

    def _swap_build_db(self):
        for suffix in ("-wal", "-shm"):
            try:
                Path(str(BUILD_DB_PATH) + suffix).unlink(missing_ok=True)
            except Exception:
                pass
        backup = marketdb.DB_PATH.with_suffix(".db.bak")
        try:
            backup.unlink(missing_ok=True)
        except Exception:
            pass
        if marketdb.DB_PATH.exists():
            try:
                marketdb.DB_PATH.replace(backup)
                BUILD_DB_PATH.replace(marketdb.DB_PATH)
            except OSError:
                self._copy_build_into_live()
                self._remove_build_db()
                try:
                    backup.unlink(missing_ok=True)
                except Exception:
                    pass
                return
        else:
            BUILD_DB_PATH.replace(marketdb.DB_PATH)
        try:
            backup.unlink(missing_ok=True)
        except Exception:
            pass

    def _copy_build_into_live(self):
        conn = marketdb.connect()
        try:
            cur = conn.cursor()
            cur.execute("ATTACH DATABASE ? AS build", (str(BUILD_DB_PATH),))
            for table in ("commodities", "stations", "systems", "commodity_names", "meta"):
                cur.execute(f"DELETE FROM main.{table}")
                cur.execute(f"INSERT INTO main.{table} SELECT * FROM build.{table}")
            conn.commit()
            cur.execute("DETACH DATABASE build")
        finally:
            conn.close()

    def _import_system(self, cur, system, include_carriers, names_seen):
        coords = system.get("coords") or {}
        id64, name = system.get("id64"), system.get("name")
        if id64 is None or not name or not coords:
            return

        stations = list(system.get("stations") or [])
        for body in system.get("bodies") or []:
            stations.extend(body.get("stations") or [])

        station_rows = []
        for st in stations:
            market = st.get("market") or {}
            commodities = market.get("commodities") or []
            market_id = st.get("id")
            if not commodities or market_id is None:
                continue
            if not include_carriers and marketdb.is_carrier(st.get("type"), st.get("name")):
                continue
            updated = marketdb.parse_update_time(market.get("updateTime") or st.get("updateTime"))
            if updated is None:
                continue
            pads = st.get("landingPads") or {}
            rows = []
            for c in commodities:
                buy, sell = c.get("buyPrice") or 0, c.get("sellPrice") or 0
                supply, demand = c.get("supply") or 0, c.get("demand") or 0
                symbol = (c.get("symbol") or c.get("name") or "").lower()
                if not symbol or not marketdb.keep_commodity(buy, sell, supply, demand):
                    continue
                rows.append((symbol, buy, sell, supply, demand))
                if symbol not in names_seen:
                    names_seen.add(symbol)
                    cur.execute(
                        "INSERT OR IGNORE INTO commodity_names(symbol, name, category) VALUES(?, ?, ?)",
                        (symbol, c.get("name") or symbol.title(), c.get("category")),
                    )
            if not rows:
                continue
            station_rows.append(
                (market_id, id64, st.get("name"), st.get("type"),
                 st.get("distanceToArrival"), 1 if (pads.get("large") or 0) > 0 else 0, updated)
            )
            cur.executemany(
                "INSERT OR REPLACE INTO commodities(market_id, symbol, buy_price, sell_price, supply, demand)"
                " VALUES(?, ?, ?, ?, ?, ?)",
                [(market_id, s, b, sl, sp, d) for (s, b, sl, sp, d) in rows],
            )

        if not station_rows:
            return
        cur.execute(
            "INSERT OR REPLACE INTO systems(id64, name, x, y, z) VALUES(?, ?, ?, ?, ?)",
            (id64, name, coords.get("x"), coords.get("y"), coords.get("z")),
        )
        cur.executemany(
            "INSERT OR REPLACE INTO stations(market_id, system_id64, name, type, dist_ls, large_pad, updated_at)"
            " VALUES(?, ?, ?, ?, ?, ?, ?)",
            station_rows,
        )
        with self._lock:
            self.systems_done += 1
            self.stations_done += len(station_rows)


SEEDER = Seeder()


def _arg_bool(args, name, default=False):
    prefix = f"--{name}="
    for arg in args:
        if arg.startswith(prefix):
            return arg[len(prefix):].strip().lower() in ("1", "true", "yes", "on")
    return default


def run_worker(args):
    seeder = Seeder()
    seeder._progress_file_enabled = True
    include_carriers = _arg_bool(args, "include-carriers", False)
    keep_dump = _arg_bool(args, "keep-dump", False)
    polite = _arg_bool(args, "polite", True)
    seeder.polite = polite
    seeder._write_progress(force=True)
    seeder._run(include_carriers, keep_dump, polite)
    final = seeder.progress()
    return 0 if final.get("phase") == "done" else 1
