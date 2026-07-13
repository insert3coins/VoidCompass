import os
import json
import time
import threading
import logging

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

        if not files: return
        
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
                    events.append(ev)

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
        """Dispatch the newest known location immediately while startup catch-up replays."""
        if self._startup_location_seeded:
            return
        self._startup_location_seeded = True
        if not self.last_journal or not self.event_callback:
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
                    self.event_callback(self._normalize_event(raw))
                    return
                # CarrierJump sets player location when they were on board
                if ev == "CarrierJump" and raw.get("Docked"):
                    self.event_callback(self._normalize_event(raw))
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
                    "ship": data.get("Ship"),
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
                }
            }
        # CarrierJump fires when the player is docked on a carrier that jumps.
        # Normalize the same location fields so dashboard location logic can reuse them.
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
                    "first_footfall": data.get("FirstFootfall", False),
                    "mass_em": data.get("MassEM"),
                    "stellar_mass": data.get("StellarMass"),
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
                })
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "market_id":      data.get("MarketID"),
                    "system_name":    data.get("SystemName", ""),
                    "system_address": data.get("SystemAddress"),
                    "body_name":      data.get("BodyName", ""),
                    "progress":       float(data.get("Progress") or 0),
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
                    "count":   int(c.get("Count") or 0),
                })
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "market_id":     data.get("MarketID"),
                    "progress":      float(data.get("Progress") or 0),
                    "contributions": contributions,
                }
            }

        if ev == "ColonisationSystemClaimed":
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
                                    self.cargo_callback(data.get("Inventory", []))
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

        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    current_sys_context = None
                    for line in f:
                        try:
                            data = json.loads(line)
                            ev = data.get("event")

                            if ev in ["FSDJump", "Location"] or (
                                ev == "CarrierJump" and data.get("Docked")
                            ):
                                sys_name = data.get("StarSystem")
                                current_sys_context = sys_name
                                if sys_name and sys_name not in new_history:
                                    new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}

                            elif ev == "FSSDiscoveryScan":
                                sys_name = data.get("SystemName", current_sys_context)
                                if sys_name:
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    count = data.get("BodyCount", 0)
                                    if count > new_history[sys_name]["total"]: new_history[sys_name]["total"] = count

                            elif ev == "DiscoveryScan":
                                sys_name = current_sys_context
                                if sys_name:
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    discovered = data.get("Bodies", 0)
                                    if isinstance(discovered, int) and discovered > 0:
                                        estimated_total = new_history[sys_name]["scanned_count"] + discovered
                                        if estimated_total > new_history[sys_name]["total"]:
                                            new_history[sys_name]["total"] = estimated_total

                            elif ev == "NavBeaconScan":
                                sys_name = current_sys_context
                                if sys_name:
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    count = data.get("NumBodies", 0)
                                    if count > new_history[sys_name]["total"]: new_history[sys_name]["total"] = count

                            elif ev == "FSSAllBodiesFound":
                                sys_name = data.get("SystemName", current_sys_context)
                                if sys_name:
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    count = data.get("Count", 0)
                                    new_history[sys_name]["total"] = count
                                    new_history[sys_name]["scanned_count"] = count

                            elif ev == "Scan":
                                sys_name = data.get("StarSystem", current_sys_context)
                                if sys_name and ("StarType" in data or "PlanetClass" in data):
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    body_id = data.get("BodyID")
                                    if body_id is not None:
                                        if "bodies" not in new_history[sys_name]: new_history[sys_name]["bodies"] = []
                                        if body_id not in new_history[sys_name]["bodies"]: new_history[sys_name]["bodies"].append(body_id)
                        except ValueError: continue
            except Exception: pass
            
            processed += 1
            if progress_callback and processed % 10 == 0:
                progress_callback(processed, total_files)
        
        return new_history
