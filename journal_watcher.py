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
        
        try:
            with open(self.last_journal, 'r', encoding='utf-8') as f:
                f.seek(self.file_pos)
                lines = f.readlines()
                
                if lines:
                    events = []
                    for line in lines:
                        try:
                            events.append(json.loads(line))
                        except: pass
                    
                    if events:
                        if len(events) > 50 and self.batch_event_callback:
                            self.batch_event_callback(events)
                        elif self.event_callback:
                            for ev in events:
                                self.event_callback(ev)
                
                self.file_pos = f.tell()
        except Exception as e:
            logging.error(f"Error reading journal: {e}")

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
