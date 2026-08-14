import os
import json
import time
import threading
import logging


def carrier_jump_moves_player(data):
    """Return whether a CarrierJump is also the commander's location event.

    Odyssey reports commanders walking inside a carrier with ``Docked:false``
    and ``OnFoot:true``. Those jumps replace the usual Location/FSDJump event
    just as a ship-docked carrier jump does.
    """
    return bool(
        isinstance(data, dict)
        and data.get("event") == "CarrierJump"
        and (data.get("Docked") or data.get("OnFoot"))
    )


class JournalWatcher:
    def __init__(self, journal_path, trace_callback=None, config=None):
        self.journal_path = journal_path
        self.trace_callback = trace_callback
        self.config = config or {}
        self.is_running = False
        self.last_journal = None
        self.file_pos = 0
        # Startup catch-up reads only the recent tail of the active journal to avoid UI stalls.
        self.startup_tail_bytes = int(self.config.get("watcher_startup_tail_bytes", 131072) or 131072)
        if self.startup_tail_bytes < 32768:
            self.startup_tail_bytes = 32768
        self.max_journal_lines_per_cycle = int(self.config.get("watcher_max_journal_lines_per_cycle", 160) or 160)
        if self.max_journal_lines_per_cycle < 20:
            self.max_journal_lines_per_cycle = 20
        self.startup_max_journal_lines_per_cycle = int(
            self.config.get("watcher_startup_max_lines_per_cycle", 20) or 20
        )
        if self.startup_max_journal_lines_per_cycle < 5:
            self.startup_max_journal_lines_per_cycle = 5
        self.special_file_settle_s = float(self.config.get("watcher_special_file_settle_ms", 200) or 200) / 1000.0
        if self.special_file_settle_s < 0.0:
            self.special_file_settle_s = 0.0
        self._startup_catchup_done = False
        self._skip_partial_line_once = False
        self._startup_location_seeded = False
        self._startup_location_event = None
        
        self.event_callback = None
        self.batch_event_callback = None
        self.cargo_callback = None
        self.nav_route_callback = None
        self.status_callback = None
        self.market_callback = None
        self.ship_locker_callback = None
        
        self.last_cargo_mtime = 0
        self.last_nav_mtime = 0
        self.last_status_mtime = 0
        self.last_market_mtime = 0
        self.last_ship_locker_mtime = 0
        self.thread = None
        self._journal_files = []
        self._journal_files_refresh_ts = 0.0
        self._journal_files_refresh_interval_s = 5.0
        self._force_special_check = False

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()

    def stop(self):
        self.is_running = False

    def register_callback(self, event_cb=None, batch_cb=None, cargo_cb=None, nav_cb=None,
                          status_cb=None, market_cb=None, ship_locker_cb=None):
        if event_cb: self.event_callback = event_cb
        if batch_cb: self.batch_event_callback = batch_cb
        if cargo_cb: self.cargo_callback = cargo_cb
        if nav_cb: self.nav_route_callback = nav_cb
        if status_cb: self.status_callback = status_cb
        if market_cb: self.market_callback = market_cb
        if ship_locker_cb: self.ship_locker_callback = ship_locker_cb

    def force_check_cargo(self):
        self.last_cargo_mtime = 0
        self._force_special_check = True

    def force_check_status(self):
        self.last_status_mtime = 0
        self._force_special_check = True

    def force_check_market(self):
        self.last_market_mtime = 0
        self._force_special_check = True

    def force_check_ship_locker(self):
        self.last_ship_locker_mtime = 0
        self._force_special_check = True

    def prime_market_file(self):
        """Treat the current Market.json as already seen so startup does not publish it."""
        if not self.journal_path:
            return
        m_file = os.path.join(self.journal_path, "Market.json")
        try:
            if os.path.exists(m_file):
                self.last_market_mtime = os.path.getmtime(m_file)
        except Exception:
            pass

    def force_check_nav(self):
        self.last_nav_mtime = 0
        self._force_special_check = True

    def get_latest_cargo_capacity(self, tail_bytes=2 * 1024 * 1024):
        """Best-effort lookup of the most recent Loadout CargoCapacity."""
        if not self.journal_path or not os.path.exists(self.journal_path):
            return 0
        try:
            files = sorted(
                [
                    os.path.join(self.journal_path, f)
                    for f in os.listdir(self.journal_path)
                    if f.startswith("Journal.") and f.endswith(".log")
                ]
            )
            if not files:
                return 0
            latest = files[-1]
            size = os.path.getsize(latest)
            start = max(0, size - tail_bytes)
            with open(latest, "rb") as f:
                f.seek(start)
                content = f.read().decode("utf-8", errors="ignore")
            lines = content.splitlines()
            for line in reversed(lines):
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                if data.get("event") == "Loadout":
                    capacity = data.get("CargoCapacity", 0)
                    try:
                        return max(0, int(capacity))
                    except Exception:
                        return 0
        except Exception:
            return 0
        return 0

    def get_latest_fuel_capacity(self, tail_bytes=2 * 1024 * 1024):
        """Return the active ship's latest verified main-tank capacity.

        Startup journal recovery intentionally reads only a small tail of the
        current log.  A ship swap/loadout can therefore predate that tail, so
        the cached cockpit state's capacity must be checked against journal
        history instead of being allowed to follow a different ship.
        """
        if not self.journal_path or not os.path.exists(self.journal_path):
            return 0.0
        try:
            files = sorted(
                (
                    os.path.join(self.journal_path, filename)
                    for filename in os.listdir(self.journal_path)
                    if filename.startswith("Journal.") and filename.endswith(".log")
                ),
                reverse=True,
            )
            if not files:
                return 0.0
            # Do not cross into an older journal: it may belong to another
            # commander profile. The active session's LoadGame/Loadout is the
            # only safe source for the active ship.
            path = files[0]
            size = os.path.getsize(path)
            start = max(0, size - int(tail_bytes))
            with open(path, "rb") as handle:
                handle.seek(start)
                content = handle.read().decode("utf-8", errors="ignore")
            for line in reversed(content.splitlines()):
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                if data.get("event") not in ("Loadout", "LoadGame"):
                    continue
                capacity = data.get("FuelCapacity")
                if isinstance(capacity, dict):
                    capacity = capacity.get("Main")
                try:
                    capacity = float(capacity)
                except (TypeError, ValueError):
                    continue
                if capacity > 0:
                    return capacity
        except Exception:
            return 0.0
        return 0.0

    def get_completed_organic_scans(self, system_address=None):
        """Return completed organic analyses from the active journal.

        The ordinary startup replay deliberately reads only a small recent
        tail.  A large Loadout or ShipLocker event can push an otherwise recent
        ``ScanOrganic/Analyse`` beyond that presentation window, so completed
        biology also gets a cheap, event-filtered pass over the active journal.
        This is recovery evidence only; live events remain the primary writer.
        """
        path = self.last_journal
        if not path:
            try:
                files = sorted(
                    os.path.join(self.journal_path, filename)
                    for filename in os.listdir(self.journal_path)
                    if filename.startswith("Journal.") and filename.endswith(".log")
                )
            except (OSError, TypeError):
                files = []
            path = files[-1] if files else None
        if not path or not os.path.exists(path):
            return []

        try:
            wanted_address = int(system_address) if system_address is not None else None
        except (TypeError, ValueError):
            wanted_address = system_address

        completed = {}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if "ScanOrganic" not in line or "Analyse" not in line:
                        continue
                    try:
                        raw = json.loads(line)
                    except (TypeError, ValueError):
                        continue
                    if raw.get("event") != "ScanOrganic":
                        continue
                    if str(raw.get("ScanType") or "").strip().casefold() != "analyse":
                        continue
                    address = raw.get("SystemAddress")
                    try:
                        address = int(address) if address is not None else None
                    except (TypeError, ValueError):
                        pass
                    if wanted_address is not None and address != wanted_address:
                        continue
                    body = raw.get("BodyID")
                    if body is None:
                        body = raw.get("Body")
                    species = (
                        raw.get("Species_Localised") or raw.get("Species")
                        or raw.get("Genus_Localised") or raw.get("Genus")
                        or "Organic"
                    )
                    completed[f"{body}|{species}"] = raw
        except OSError:
            return []
        return list(completed.values())

    @staticmethod
    def detect_latest_commander(journal_path, tail_bytes=2 * 1024 * 1024):
        """Best-effort commander/FID detection from the newest journal file."""
        if not journal_path or not os.path.exists(journal_path):
            return None
        try:
            files = sorted(
                os.path.join(journal_path, f)
                for f in os.listdir(journal_path)
                if f.startswith("Journal.") and f.endswith(".log")
            )
            if not files:
                return None
            latest = files[-1]
            size = os.path.getsize(latest)
            start = max(0, size - int(tail_bytes))
            with open(latest, "rb") as f:
                f.seek(start)
                content = f.read().decode("utf-8", errors="ignore")
            lines = content.splitlines()
            if start > 0 and lines:
                lines = lines[1:]
            commander = None
            fid = None
            for line in reversed(lines):
                try:
                    raw = json.loads(line)
                except Exception:
                    continue
                ev = raw.get("event")
                if ev == "LoadGame":
                    commander = raw.get("Commander") or commander
                    fid = raw.get("FID") or fid
                    if commander:
                        return {"commander": commander, "fid": fid or "", "journal_file": latest}
                if ev == "Commander":
                    commander = raw.get("Name") or commander
                    fid = raw.get("FID") or fid
                    if commander:
                        return {"commander": commander, "fid": fid or "", "journal_file": latest}
        except Exception:
            return None
        return None

    def _worker(self):
        while self.is_running:
            t0 = time.perf_counter()
            try:
                if self.journal_path and os.path.exists(self.journal_path):
                    self._check_journal()
                    self._check_special_files()
                    self._force_special_check = False
            except Exception as e:
                logging.error(f"Watcher Error: {e}")
            if callable(self.trace_callback):
                try:
                    self.trace_callback("watcher.worker_cycle", (time.perf_counter() - t0) * 1000.0)
                except Exception:
                    pass
            time.sleep(1)

    def _check_journal(self):
        t0 = time.perf_counter()
        try:
            now = time.time()
            need_refresh = (
                (now - self._journal_files_refresh_ts) >= self._journal_files_refresh_interval_s
                or not self._journal_files
                or (self.last_journal and not os.path.exists(self.last_journal))
            )
            if need_refresh:
                self._journal_files = sorted(
                    [
                        os.path.join(self.journal_path, f)
                        for f in os.listdir(self.journal_path)
                        if f.startswith("Journal.") and f.endswith(".log")
                    ]
                )
                self._journal_files_refresh_ts = now
            files = self._journal_files
        except Exception:
            return

        if not files:
            if not self._startup_catchup_done:
                completion = {
                    "type": "StartupCatchupComplete",
                    "raw": {},
                    "data": {},
                    "startup_catchup": True,
                    "startup_catchup_final": True,
                }
                if self.batch_event_callback:
                    self.batch_event_callback([completion])
                elif self.event_callback:
                    self.event_callback(completion)
                self._startup_catchup_done = True
            return
        
        latest = files[-1]
        
        if latest != self.last_journal:
            if self.last_journal is not None:
                logging.info(f"New journal detected: {os.path.basename(latest)}")
            self.last_journal = latest
            self.file_pos = 0
            self._skip_partial_line_once = False
            # First watcher attach can be very large; jump near EOF and process recent lines only.
            if not self._startup_catchup_done:
                try:
                    sz = os.path.getsize(self.last_journal)
                    if sz > self.startup_tail_bytes:
                        self.file_pos = sz - self.startup_tail_bytes
                        self._skip_partial_line_once = True
                except Exception:
                    self.file_pos = 0
            self._seed_startup_location()
        
        try:
            with open(self.last_journal, 'r', encoding='utf-8') as f:
                f.seek(self.file_pos)
                # If we jumped into the middle of the file, discard partial first line.
                if self._skip_partial_line_once and self.file_pos > 0:
                    try:
                        f.readline()
                    except Exception:
                        pass
                    self._skip_partial_line_once = False
                startup_catchup = not self._startup_catchup_done
                line_budget = self.max_journal_lines_per_cycle
                if startup_catchup:
                    line_budget = min(line_budget, self.startup_max_journal_lines_per_cycle)
                lines_read = 0
                events = []
                eof_reached = False
                while lines_read < line_budget:
                    line_offset = f.tell()
                    line = f.readline()
                    if not line:
                        eof_reached = True
                        break
                    lines_read += 1
                    # Yield periodically so the UI thread can run between parse bursts.
                    if (lines_read % 5) == 0:
                        time.sleep(0)
                    try:
                        raw = json.loads(line)
                    except Exception:
                        continue
                    ev = self._normalize_event(raw)
                    if isinstance(ev, dict):
                        ev["startup_catchup"] = startup_catchup
                        ev["_journal_uid"] = f"{os.path.basename(self.last_journal)}:{line_offset}"
                    events.append(ev)

                # A read can land exactly on the line budget and also be at
                # EOF. Detect that case now so the dashboard receives one
                # definitive end-of-restore marker instead of treating the
                # next empty poll as completion.
                if startup_catchup and not eof_reached:
                    try:
                        eof_reached = f.tell() >= os.fstat(f.fileno()).st_size
                    except OSError:
                        pass
                if startup_catchup and eof_reached and self._startup_location_event:
                    events.append(self._startup_location_event)
                    self._startup_location_event = None
                if startup_catchup and eof_reached and not events:
                    # Complete the restore handshake even for a new/empty
                    # journal so a cached UI cannot remain frozen forever.
                    events.append({
                        "type": "StartupCatchupComplete",
                        "raw": {},
                        "data": {},
                        "startup_catchup": True,
                    })
                if startup_catchup and eof_reached and events:
                    events[-1]["startup_catchup_final"] = True

                if events:
                    if self.batch_event_callback and (startup_catchup or len(events) > 1):
                        self.batch_event_callback(events)
                    elif self.event_callback:
                        for idx, ev in enumerate(events, start=1):
                            try:
                                self.event_callback(ev)
                            except Exception as cb_err:
                                ev_type = (ev.get("type") or "?") if isinstance(ev, dict) else "?"
                                logging.error(f"Event callback error [{ev_type}]: {cb_err}")
                            if (idx % 5) == 0:
                                time.sleep(0)

                self.file_pos = f.tell()
                if eof_reached:
                    self._startup_catchup_done = True
        except Exception as e:
            logging.error(f"Error reading journal: {e}")
        finally:
            if callable(self.trace_callback):
                try:
                    self.trace_callback("watcher.check_journal", (time.perf_counter() - t0) * 1000.0)
                except Exception:
                    pass

    def _seed_startup_location(self, tail_bytes=2 * 1024 * 1024):
        """Retain the newest known location for the final startup restore batch."""
        if self._startup_location_seeded:
            return
        self._startup_location_seeded = True
        if not self.last_journal:
            return
        try:
            size = os.path.getsize(self.last_journal)
            start = max(0, size - int(tail_bytes))
            with open(self.last_journal, "rb") as f:
                f.seek(start)
                content = f.read().decode("utf-8", errors="ignore")
            lines = content.splitlines()
            if start > 0 and lines:
                lines = lines[1:]
            for line in reversed(lines):
                try:
                    raw = json.loads(line)
                except Exception:
                    continue
                ev = raw.get("event")
                if ev in ("FSDJump", "Location"):
                    seeded = self._normalize_event(raw)
                    seeded["type"] = "Location"
                    seeded["startup_catchup"] = True
                    seeded["startup_location_seed"] = True
                    self._startup_location_event = seeded
                    return
                # CarrierJump sets player location while ship-docked or walking
                # on the carrier concourse.
                if carrier_jump_moves_player(raw):
                    seeded = self._normalize_event(raw)
                    seeded["type"] = "Location"
                    seeded["startup_catchup"] = True
                    seeded["startup_location_seed"] = True
                    self._startup_location_event = seeded
                    return
        except Exception:
            return

    def _normalize_event(self, data):
        ev = data.get("event")
        if not ev:
            return {"type": None, "raw": data, "data": {}}

        if ev in ("FileHeader", "Fileheader", "fileheader"):
            return {
                "type": "FileHeader",
                "raw": data,
                "data": {
                    "gameversion": data.get("gameversion"),
                    "build": data.get("build")
                }
            }
        if ev == "Loadout":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "cargo_capacity": data.get("CargoCapacity", 0),
                    "fuel_capacity": data.get("FuelCapacity"),
                    "ship": data.get("Ship"),
                    "ship_localised": data.get("Ship_Localised"),
                    "ship_id": data.get("ShipID"),
                    "ship_name": data.get("ShipName"),
                    "ship_ident": data.get("ShipIdent"),
                    "modules_value": data.get("ModulesValue"),
                    "hull_health": data.get("HullHealth"),
                    "max_jump_range": data.get("MaxJumpRange"),
                    "rebuy": data.get("Rebuy"),
                }
            }
        if ev == "Commander":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "name": data.get("Name"),
                    "fid": data.get("FID"),
                }
            }
        if ev == "LoadGame":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "commander": data.get("Commander"),
                    "fid": data.get("FID"),
                    "gameversion": data.get("gameversion"),
                    "build": data.get("build"),
                    "credits": data.get("Credits"),
                    "loan": data.get("Loan"),
                    "ship": data.get("Ship"),
                    "ship_localised": data.get("Ship_Localised"),
                    "ship_id": data.get("ShipID"),
                    "ship_name": data.get("ShipName"),
                    "ship_ident": data.get("ShipIdent"),
                    "fuel_level": data.get("FuelLevel"),
                    "fuel_capacity": data.get("FuelCapacity"),
                    "game_mode": data.get("GameMode"),
                    "group": data.get("Group"),
                    "horizons": data.get("Horizons"),
                    "odyssey": data.get("Odyssey"),
                }
            }
        if ev in ("Rank", "Progress", "Reputation"):
            return {
                "type": ev,
                "raw": data,
                "data": {
                    key: value for key, value in data.items()
                    if key not in ("timestamp", "event")
                }
            }
        if ev in ("Location", "FSDJump", "StartJump"):
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "star_system": data.get("StarSystem"),
                    "system_address": data.get("SystemAddress"),
                    "star_pos": data.get("StarPos"),
                    "star_class": data.get("StarClass"),
                    "jump_type": data.get("JumpType"),
                    "docked": data.get("Docked"),
                    "on_foot": data.get("OnFoot"),
                    "in_taxi": data.get("Taxi"),
                    "in_multicrew": data.get("Multicrew"),
                    "in_srv": data.get("InSRV"),
                    "station_name": data.get("StationName"),
                    "station_type": data.get("StationType"),
                    "market_id": data.get("MarketID"),
                }
            }
        # CarrierJump replaces the player's location event while aboard a
        # jumping carrier, including Odyssey concourse/on-foot travel.
        if ev == "CarrierJump":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "star_system": data.get("StarSystem"),
                    "system_address": data.get("SystemAddress"),
                    "star_pos": data.get("StarPos"),
                    "star_class": None,  # CarrierJump doesn't carry StarClass
                    "docked": data.get("Docked", False),
                    "on_foot": data.get("OnFoot", False),
                    "player_location": carrier_jump_moves_player(data),
                    "body": data.get("Body"),
                    "body_id": data.get("BodyID"),
                }
            }
        if ev in ("Touchdown", "Liftoff"):
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "star_system": data.get("StarSystem"),
                    "body": data.get("Body"),
                    "body_id": data.get("BodyID"),
                    "on_station": data.get("OnStation"),
                    "on_planet": data.get("OnPlanet"),
                    "latitude": data.get("Latitude"),
                    "longitude": data.get("Longitude"),
                    "player_controlled": data.get("PlayerControlled")
                }
            }
        if ev == "FSSDiscoveryScan":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "system_name": data.get("SystemName"),
                    "system_address": data.get("SystemAddress"),
                    "progress": data.get("Progress"),
                    "body_count": data.get("BodyCount", 0)
                }
            }
        if ev == "DiscoveryScan":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "system_address": data.get("SystemAddress"),
                    "bodies": data.get("Bodies", 0)
                }
            }
        if ev == "NavBeaconScan":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "system_address": data.get("SystemAddress"),
                    "num_bodies": data.get("NumBodies", 0)
                }
            }
        if ev == "FSSAllBodiesFound":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "system_name": data.get("SystemName"),
                    "system_address": data.get("SystemAddress"),
                    "count": data.get("Count", 0)
                }
            }
        if ev == "FSSBodySignals":
            bio_count = 0
            geo_count = 0
            for signal in data.get("Signals", []):
                signal_type = signal.get("Type")
                signal_label = signal.get("Type_Localised")
                if signal_type == "$SAA_SignalType_Biological;" or signal_label == "Biological":
                    bio_count = signal.get("Count", 0)
                elif signal_type == "$SAA_SignalType_Geological;" or signal_label == "Geological":
                    geo_count = signal.get("Count", 0)
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_name": data.get("BodyName"),
                    "body_id": data.get("BodyID"),
                    "system_address": data.get("SystemAddress"),
                    "bio_count": bio_count,
                    "geo_count": geo_count
                }
            }
        if ev == "SAASignalsFound":
            bio_count = 0
            geo_count = 0
            for signal in data.get("Signals", []):
                signal_type = signal.get("Type")
                signal_label = signal.get("Type_Localised")
                if signal_type == "$SAA_SignalType_Biological;" or signal_label == "Biological":
                    bio_count += signal.get("Count", 0)
                elif signal_type == "$SAA_SignalType_Geological;" or signal_label == "Geological":
                    geo_count += signal.get("Count", 0)
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_name": data.get("BodyName"),
                    "body_id": data.get("BodyID"),
                    "system_address": data.get("SystemAddress"),
                    "bio_count": bio_count,
                    "geo_count": geo_count,
                    "genuses": data.get("Genuses", [])
                }
            }
        if ev == "SAAScanComplete":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_id": data.get("BodyID"),
                    "system_address": data.get("SystemAddress")
                }
            }
        if ev == "ScanOrganic":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "species": data.get("Species_Localised") or data.get("Species"),
                    "genus": data.get("Genus_Localised") or data.get("Genus"),
                    "variant": data.get("Variant_Localised") or data.get("Variant"),
                    "sample_idx": data.get("Sample"),
                    "scan_type": data.get("ScanType_Localised") or data.get("ScanType"),
                    "is_new_entry": bool(data.get("IsNewEntry")),
                    "is_new_sample": bool(data.get("IsNewSample")),
                    # Live ScanOrganic events do not actually carry an "IsComplete"
                    # field (confirmed against real journals) — completion has to
                    # be derived from ScanType == "Analyse". Keep the flag check
                    # too in case some journal variant ever does emit it.
                    "is_complete": bool(data.get("IsComplete")) or str(data.get("ScanType") or "").casefold() == "analyse",
                    # ScanOrganic uses "Body" (integer) for the body ID, not "BodyID".
                    # "BodyName" is not present in this event.
                    "body_name": data.get("BodyName") or "",
                    "body_id": data.get("BodyID") if data.get("BodyID") is not None else data.get("Body"),
                    "system_address": data.get("SystemAddress"),
                    "max_samples": data.get("MaxSamples", 3),
                    "biome": data.get("Biome"),
                    "planet_class": data.get("PlanetClass"),
                    "sample_distance": data.get("SampleDistance")
                }
            }
        if ev == "CodexEntry":
            # Category for geological features: "$Codex_Category_Geology;"
            # Category for biological features: "$Codex_Category_Biology;"
            category     = data.get("Category", "")
            category_loc = data.get("Category_Localised", "")
            is_geological = (
                category == "$Codex_Category_Geology;"
                or category_loc.lower() == "geology"
            )
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_id":       data.get("BodyID"),
                    "body_name":     data.get("NearestDestination_Localised") or data.get("NearestDestination") or "",
                    "system_address": data.get("SystemAddress"),
                    "name":          data.get("Name_Localised") or data.get("Name") or "",
                    "category":      category_loc or category,
                    "is_geological": is_geological,
                }
            }
        if ev == "Scan":
            star_type = data.get("StarType")
            planet_class = data.get("PlanetClass")
            bio_signals_count = 0
            for signal in data.get("BioSignals", []):
                if signal.get("Type_Localised") == "Biological":
                    bio_signals_count += signal.get("Count", 0)
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_name": data.get("BodyName", ""),
                    "body_id": data.get("BodyID"),
                    "star_system": data.get("StarSystem"),
                    "system_address": data.get("SystemAddress"),
                    "star_type": star_type,
                    "planet_class": planet_class,
                    "terraform_state": data.get("TerraformState"),
                    "landable": data.get("Landable", False),
                    "was_discovered": data.get("WasDiscovered", True),
                    "was_mapped": data.get("WasMapped", True),
                    "was_footfalled": data.get("WasFootfalled"),
                    # Elite reports whether somebody had already made first
                    # footfall when the body was scanned.  Keep the existing
                    # UI key as an availability flag for landable planets.
                    "first_footfall": bool(
                        data.get("Landable", False)
                        and data.get("WasFootfalled") is False
                    ),
                    "mass_em": data.get("MassEM"),
                    "stellar_mass": data.get("StellarMass"),
                    "distance_from_arrival_ls": data.get("DistanceFromArrivalLS"),
                    "is_body_scan": bool(star_type or planet_class),
                    "bio_signals_count": bio_signals_count,
                    # Body conditions for bio prediction (planets only)
                    "surface_gravity":  data.get("SurfaceGravity"),      # g
                    "surface_temp":     data.get("SurfaceTemperature"),  # K
                    "surface_pressure": data.get("SurfacePressure"),     # atm
                    "atmosphere_type":  data.get("AtmosphereType") or "",
                    "volcanism":        data.get("Volcanism") or "",
                    "materials":        {m.get("Name", "").title(): float(m.get("Percent", 0))
                                         for m in (data.get("Materials") or [])},
                    "atmos_comp":       {c.get("Name", ""): float(c.get("Percent", 0))
                                         for c in (data.get("AtmosphereComposition") or [])},
                    "parents":          data.get("Parents") or [],
                    "rings":            data.get("Rings") or [],
                }
            }

        if ev == "ApproachBody":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_name":     data.get("Body", ""),
                    "body_id":       data.get("BodyID"),
                    "star_system":   data.get("StarSystem", ""),
                    "system_address": data.get("SystemAddress"),
                }
            }

        if ev == "LeaveBody":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_name":     data.get("Body", ""),
                    "body_id":       data.get("BodyID"),
                    "star_system":   data.get("StarSystem", ""),
                    "system_address": data.get("SystemAddress"),
                }
            }

        if ev == "ColonisationConstructionDepot":
            resources = []
            for r in (data.get("ResourcesRequired") or []):
                raw_name = r.get("Name", "")
                # "$Steel_Name;" → "Steel" when no localised name provided
                display = r.get("Name_Localised") or raw_name
                if display.startswith("$") and "_Name;" in display:
                    display = display.split("_Name;")[0].lstrip("$").replace("_", " ").title()
                resources.append({
                    "name":     raw_name,
                    "display":  display,
                    "required": int(r.get("RequiredAmount") or 0),
                    "provided": int(r.get("ProvidedAmount") or 0),
                    "payment":  int(r.get("Payment") or 0),
                })
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "market_id":      data.get("MarketID"),
                    "system_name":    data.get("SystemName", ""),
                    "system_address": data.get("SystemAddress"),
                    "body_name":      data.get("BodyName", ""),
                    "progress":       float(
                        data.get("ConstructionProgress", data.get("Progress", 0)) or 0
                    ),
                    "complete":       bool(data.get("ConstructionComplete", False)),
                    "failed":         bool(data.get("ConstructionFailed", False)),
                    "resources":      resources,
                }
            }

        if ev == "ColonisationContribution":
            contributions = []
            for c in (data.get("Contributions") or []):
                raw_name = c.get("Name", "")
                display = c.get("Name_Localised") or raw_name
                if display.startswith("$") and "_Name;" in display:
                    display = display.split("_Name;")[0].lstrip("$").replace("_", " ").title()
                contributions.append({
                    "name":    raw_name,
                    "display": display,
                    "count":   int(c.get("Amount", c.get("Count", 0)) or 0),
                })
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "market_id":     data.get("MarketID"),
                    "contributions": contributions,
                }
            }

        if ev in ("ColonisationSystemClaim", "ColonisationSystemClaimRelease"):
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "star_system":    data.get("StarSystem", ""),
                    "system_address": data.get("SystemAddress"),
                }
            }

        return {"type": ev, "raw": data, "data": data}

    def _check_special_files(self):
        t0 = time.perf_counter()
        now = time.time()
        # Cargo.json
        if self.cargo_callback:
            c_file = os.path.join(self.journal_path, "Cargo.json")
            if os.path.exists(c_file):
                try:
                    mtime = os.path.getmtime(c_file)
                    if mtime != self.last_cargo_mtime:
                        # Avoid reading while the game may still be writing this file.
                        if (now - mtime) < self.special_file_settle_s and not self._force_special_check:
                            pass
                        else:
                            with open(c_file, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if content:
                                    data = json.loads(content)
                                    self.cargo_callback(
                                        data.get("Inventory", []),
                                        data.get("Vessel", "Ship"),
                                    )
                                    self.last_cargo_mtime = mtime
                except:
                    pass

        # NavRoute.json
        if self.nav_route_callback:
            n_file = os.path.join(self.journal_path, "NavRoute.json")
            if os.path.exists(n_file):
                try:
                    mtime = os.path.getmtime(n_file)
                    if mtime != self.last_nav_mtime:
                        if (now - mtime) < self.special_file_settle_s and not self._force_special_check:
                            pass
                        else:
                            with open(n_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                self.nav_route_callback(data)
                                self.last_nav_mtime = mtime
                except:
                    pass

        # Status.json
        if self.status_callback:
            s_file = os.path.join(self.journal_path, "Status.json")
            if os.path.exists(s_file):
                try:
                    mtime = os.path.getmtime(s_file)
                    if mtime != self.last_status_mtime:
                        # Status drives live HUD/ground target; don't defer it with settle timing.
                        with open(s_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.status_callback(data)
                            self.last_status_mtime = mtime
                except:
                    pass
        # Market.json is written when the commodity market screen is opened.
        if self.market_callback:
            m_file = os.path.join(self.journal_path, "Market.json")
            if os.path.exists(m_file):
                try:
                    mtime = os.path.getmtime(m_file)
                    if mtime != self.last_market_mtime:
                        if (now - mtime) < self.special_file_settle_s and not self._force_special_check:
                            pass
                        else:
                            with open(m_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                self.market_callback(data)
                                self.last_market_mtime = mtime
                except:
                    pass
        # ShipLocker.json is the complete Odyssey goods/assets/data snapshot.
        if self.ship_locker_callback:
            locker_file = os.path.join(self.journal_path, "ShipLocker.json")
            if os.path.exists(locker_file):
                try:
                    mtime = os.path.getmtime(locker_file)
                    if mtime != self.last_ship_locker_mtime:
                        if (now - mtime) < self.special_file_settle_s and not self._force_special_check:
                            pass
                        else:
                            with open(locker_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            self.ship_locker_callback(data)
                            self.last_ship_locker_mtime = mtime
                except Exception:
                    pass
        if callable(self.trace_callback):
            try:
                self.trace_callback("watcher.check_special_files", (time.perf_counter() - t0) * 1000.0)
            except Exception:
                pass

    def scan_history(self, progress_callback=None):
        if not self.journal_path or not os.path.exists(self.journal_path):
            return {}

        try:
            files = sorted([os.path.join(self.journal_path, f) for f in os.listdir(self.journal_path) if f.startswith("Journal.") and f.endswith(".log")])
        except Exception:
            return {}

        total_files = len(files)
        if total_files == 0:
            return {}

        new_history = {}
        processed = 0
        expected_name = str(self.config.get("active_commander_name") or "").strip().casefold()
        expected_fid = str(self.config.get("active_commander_fid") or "").strip().casefold()

        def commander_matches(data):
            actual_name = str(data.get("Commander") or data.get("Name") or "").strip().casefold()
            actual_fid = str(data.get("FID") or "").strip().casefold()
            if expected_fid and actual_fid:
                return expected_fid == actual_fid
            if expected_name and actual_name:
                return expected_name == actual_name
            return not bool(expected_name or expected_fid)

        def system_row(name):
            return new_history.setdefault(
                name, {"total": 0, "bodies": [], "scanned_count": 0},
            )

        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    current_sys_context = None
                    active_commander = not bool(expected_name or expected_fid)
                    for line in f:
                        try:
                            data = json.loads(line)
                            ev = data.get("event")

                            if ev in ("Commander", "LoadGame"):
                                active_commander = commander_matches(data)
                                current_sys_context = None
                                continue
                            if not active_commander:
                                continue

                            if ev in ["FSDJump", "Location"] or carrier_jump_moves_player(data):
                                sys_name = data.get("StarSystem")
                                current_sys_context = sys_name
                                if sys_name:
                                    system_row(sys_name)

                            elif ev == "FSSDiscoveryScan":
                                sys_name = data.get("SystemName", current_sys_context)
                                if sys_name:
                                    row = system_row(sys_name)
                                    count = int(data.get("BodyCount") or 0)
                                    row["total"] = max(row["total"], count)
                                    try:
                                        complete = float(data.get("Progress")) >= 1.0
                                    except (TypeError, ValueError):
                                        complete = False
                                    if complete:
                                        row["scanned_count"] = max(row["scanned_count"], count)

                            elif ev == "DiscoveryScan":
                                sys_name = current_sys_context
                                if sys_name:
                                    row = system_row(sys_name)
                                    discovered = data.get("Bodies", 0)
                                    if isinstance(discovered, int) and discovered > 0:
                                        estimated_total = row["scanned_count"] + discovered
                                        row["total"] = max(row["total"], estimated_total)

                            elif ev == "NavBeaconScan":
                                sys_name = current_sys_context
                                if sys_name:
                                    row = system_row(sys_name)
                                    count = int(data.get("NumBodies") or 0)
                                    row["total"] = max(row["total"], count)
                                    row["scanned_count"] = max(row["scanned_count"], count)

                            elif ev == "FSSAllBodiesFound":
                                sys_name = data.get("SystemName", current_sys_context)
                                if sys_name:
                                    row = system_row(sys_name)
                                    count = int(data.get("Count") or data.get("BodyCount") or 0)
                                    row["total"] = max(row["total"], count)
                                    row["scanned_count"] = max(row["scanned_count"], count)

                            elif ev == "Scan":
                                sys_name = data.get("StarSystem", current_sys_context)
                                if sys_name and ("StarType" in data or "PlanetClass" in data):
                                    row = system_row(sys_name)
                                    body_id = data.get("BodyID")
                                    if body_id is not None and body_id not in row["bodies"]:
                                        row["bodies"].append(body_id)
                        except (ValueError, TypeError):
                            continue
            except OSError:
                pass
            
            processed += 1
            if progress_callback and processed % 10 == 0:
                progress_callback(processed, total_files)
        
        return new_history
