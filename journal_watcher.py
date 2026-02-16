import os
import json
import time
import threading
import logging

class JournalWatcher:
    def __init__(self, journal_path):
        self.journal_path = journal_path
        self.is_running = False
        self.last_journal = None
        self.file_pos = 0
        # Startup catch-up reads only the recent tail of the active journal to avoid UI stalls.
        self.startup_tail_bytes = 512 * 1024  # 512 KB
        self._startup_catchup_done = False
        self._skip_partial_line_once = False
        
        self.event_callback = None
        self.batch_event_callback = None
        self.cargo_callback = None
        self.nav_route_callback = None
        self.status_callback = None
        
        self.last_cargo_mtime = 0
        self.last_nav_mtime = 0
        self.last_status_mtime = 0
        self.thread = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()

    def stop(self):
        self.is_running = False

    def register_callback(self, event_cb=None, batch_cb=None, cargo_cb=None, nav_cb=None, status_cb=None):
        if event_cb: self.event_callback = event_cb
        if batch_cb: self.batch_event_callback = batch_cb
        if cargo_cb: self.cargo_callback = cargo_cb
        if nav_cb: self.nav_route_callback = nav_cb
        if status_cb: self.status_callback = status_cb

    def force_check_cargo(self):
        self.last_cargo_mtime = 0
        self._check_special_files()

    def force_check_status(self):
        self.last_status_mtime = 0
        self._check_special_files()

    def _worker(self):
        while self.is_running:
            try:
                if self.journal_path and os.path.exists(self.journal_path):
                    self._check_journal()
                    self._check_special_files()
            except Exception as e:
                logging.error(f"Watcher Error: {e}")
            time.sleep(1)

    def _check_journal(self):
        try:
            files = sorted([os.path.join(self.journal_path, f) for f in os.listdir(self.journal_path) if f.startswith("Journal.") and f.endswith(".log")])
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
                lines = f.readlines()
                
                if lines:
                    events = []
                    for line in lines:
                        try:
                            raw = json.loads(line)
                        except Exception:
                            continue
                        events.append(self._normalize_event(raw))

                    if events:
                        if len(events) > 50 and self.batch_event_callback:
                            self.batch_event_callback(events)
                        elif self.event_callback:
                            for ev in events:
                                self.event_callback(ev)
                
                self.file_pos = f.tell()
                self._startup_catchup_done = True
        except Exception as e:
            logging.error(f"Error reading journal: {e}")

    def _normalize_event(self, data):
        ev = data.get("event")
        if not ev:
            return {"type": None, "raw": data, "data": {}}

        if ev == "Fileheader":
            return {
                "type": ev,
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
                    "cargo_capacity": data.get("CargoCapacity", 0)
                }
            }
        if ev == "Commander":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "name": data.get("Name")
                }
            }
        if ev == "LoadGame":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "commander": data.get("Commander"),
                    "gameversion": data.get("gameversion"),
                    "build": data.get("build")
                }
            }
        if ev in ("Location", "FSDJump", "StartJump"):
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "star_system": data.get("StarSystem"),
                    "star_pos": data.get("StarPos"),
                    "star_class": data.get("StarClass")
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
                    "body_count": data.get("BodyCount", 0)
                }
            }
        if ev == "FSSAllBodiesFound":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "system_name": data.get("SystemName"),
                    "count": data.get("Count", 0)
                }
            }
        if ev == "FSSBodySignals":
            bio_count = 0
            geo_count = 0
            for signal in data.get("Signals", []):
                if signal.get("Type") == "$SAA_SignalType_Biological;":
                    bio_count = signal.get("Count", 0)
                elif signal.get("Type") == "$SAA_SignalType_Geological;":
                    geo_count = signal.get("Count", 0)
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_id": data.get("BodyID"),
                    "bio_count": bio_count,
                    "geo_count": geo_count
                }
            }
        if ev == "SAAScanComplete":
            return {
                "type": ev,
                "raw": data,
                "data": {
                    "body_id": data.get("BodyID")
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
                    "is_complete": bool(data.get("IsComplete")),
                    "body_name": data.get("BodyName") or data.get("Body"),
                    "body_id": data.get("BodyID"),
                    "max_samples": data.get("MaxSamples", 3),
                    "biome": data.get("Biome"),
                    "planet_class": data.get("PlanetClass"),
                    "sample_distance": data.get("SampleDistance")
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
                    "bio_signals_count": bio_signals_count
                }
            }

        return {"type": ev, "raw": data, "data": data}

    def _check_special_files(self):
        # Cargo.json
        if self.cargo_callback:
            c_file = os.path.join(self.journal_path, "Cargo.json")
            if os.path.exists(c_file):
                try:
                    mtime = os.path.getmtime(c_file)
                    if mtime != self.last_cargo_mtime:
                        self.last_cargo_mtime = mtime
                        with open(c_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                data = json.loads(content)
                                self.cargo_callback(data.get("Inventory", []))
                except: pass

        # NavRoute.json
        if self.nav_route_callback:
            n_file = os.path.join(self.journal_path, "NavRoute.json")
            if os.path.exists(n_file):
                try:
                    mtime = os.path.getmtime(n_file)
                    if mtime != self.last_nav_mtime:
                        self.last_nav_mtime = mtime
                        with open(n_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.nav_route_callback(data)
                except: pass

        # Status.json
        if self.status_callback:
            s_file = os.path.join(self.journal_path, "Status.json")
            if os.path.exists(s_file):
                try:
                    mtime = os.path.getmtime(s_file)
                    if mtime != self.last_status_mtime:
                        self.last_status_mtime = mtime
                        with open(s_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.status_callback(data)
                except: pass

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

                            if ev in ["FSDJump", "Location"]:
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
