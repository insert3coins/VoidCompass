import os
import json
import threading
import requests
import queue
import time
import logging
from datetime import datetime, timezone
from config import EDSM_CACHE_FILE, COLOR_GREEN

class EDSMHandler:
    def __init__(self, config, update_status_cb, update_queue_cb):
        self.config = config
        self.update_status_cb = update_status_cb
        self.update_queue_cb = update_queue_cb
        self.queue = queue.Queue()
        self.cache = {}
        self.is_running = True
        self.game_version = None
        self.game_build = None
        self.status = "DISABLED"
        
        self.load_cache()
        
        if self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key"):
            self.status = "STANDBY"
        
        threading.Thread(target=self.worker, daemon=True).start()

    def set_game_version(self, version, build):
        self.game_version = version
        self.game_build = build

    def stop(self):
        self.is_running = False
        self.save_cache()

    def load_cache(self):
        if not os.path.exists(EDSM_CACHE_FILE):
            return
        try:
            with open(EDSM_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
        except (IOError, json.JSONDecodeError):
            return
        
        now = datetime.now(timezone.utc)
        expiry_days = 7
        cleaned_cache = {}
        for event_ts, upload_ts_str in cache_data.items():
            try:
                upload_ts = datetime.fromisoformat(upload_ts_str.replace('Z', '+00:00'))
                if (now - upload_ts).days <= expiry_days:
                    cleaned_cache[event_ts] = upload_ts_str
            except (ValueError, TypeError):
                continue
        
        self.cache = cleaned_cache
        if len(self.cache) < len(cache_data):
            self.save_cache()

    def save_cache(self):
        try:
            with open(EDSM_CACHE_FILE, 'w') as f:
                json.dump(self.cache, f)
        except Exception:
            pass

    def enqueue(self, log_data, current_sys, current_coords):
        if not (self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key")):
            return False

        event_type = log_data.get("event")
        if event_type in ["FSDJump", "Location", "Scan"]:
            log_data = log_data.copy()
            if "StarSystem" in log_data:
                log_data["systemName"] = log_data["StarSystem"]
            if "StarPos" in log_data:
                log_data["starPos"] = log_data["StarPos"]
        elif event_type == "ScanOrganic":
            log_data = log_data.copy()
            log_data["systemName"] = current_sys
            log_data["starPos"] = current_coords

        event_ts = log_data.get("timestamp")
        if event_ts and event_ts in self.cache:
            upload_ts_str = self.cache[event_ts]
            try:
                upload_ts = datetime.fromisoformat(upload_ts_str.replace('Z', '+00:00'))
                if (datetime.now(timezone.utc) - upload_ts).total_seconds() < 24 * 3600:
                    return False
            except (ValueError, TypeError):
                pass

        self.queue.put(log_data)
        if self.update_queue_cb:
            self.update_queue_cb(self.queue.qsize())
        return True

    def worker(self):
        while self.is_running:
            batch = []
            try:
                batch.append(self.queue.get(timeout=2))
                while len(batch) < 50:
                    try:
                        batch.append(self.queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                continue

            send_successful = False
            try:
                name = self.config.get("edsm_cmdr_name")
                key = self.config.get("edsm_api_key")
                
                if not (key and name):
                    send_successful = True
                else:
                    url = "https://www.edsm.net/api-journal-v1"
                    payload = {
                        "commanderName": name,
                        "apiKey": key,
                        "fromSoftware": "SurveyLogger",
                        "fromSoftwareVersion": "1.30",
                        "message": json.dumps(batch)
                    }
                    if self.game_version: payload['fromGameVersion'] = self.game_version
                    if self.game_build: payload['fromGameBuild'] = self.game_build
                    headers = {'User-Agent': 'SurveyLogger/1.30'}
                    
                    r = requests.post(url, data=payload, headers=headers, timeout=30)
                    
                    if r.status_code == 200:
                        res = r.json()
                        if res.get("msgnum") == 100:
                            self.status = "OK"
                            send_successful = True
                            if self.update_status_cb: self.update_status_cb("OK", COLOR_GREEN)
                            for item in batch:
                                event_ts = item.get("timestamp")
                                if event_ts:
                                    self.cache[event_ts] = datetime.now(timezone.utc).isoformat()
                            self.save_cache()
                        else:
                            self.status = f"ERR_{res.get('msgnum')}"
                            send_successful = True 
                            if self.update_status_cb: self.update_status_cb(self.status, "red")
                    else:
                        self.status = f"HTTP_{r.status_code}"
                        if self.update_status_cb: self.update_status_cb(self.status, "red")
            
            except requests.exceptions.RequestException:
                self.status = "NET_ERR"
                if self.update_status_cb: self.update_status_cb(self.status, "red")
            except Exception:
                send_successful = True

            if not send_successful and batch:
                for item in reversed(batch):
                    self.queue.put(item)
                time.sleep(10)
            
            if batch:
                for _ in batch:
                    self.queue.task_done()
                if self.update_queue_cb: self.update_queue_cb(self.queue.qsize())
            
            if send_successful:
                time.sleep(0.5)

    def fetch_traffic(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name}
                url = "https://www.edsm.net/api-system-v1/traffic"
                headers = {'User-Agent': 'SurveyLogger/1.30'}
                r = requests.get(url, params=params, headers=headers, timeout=10)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict):
                    traffic = data.get("traffic")
                    if traffic:
                        callback(traffic)
            except Exception as e:
                logging.warning(f"Traffic fetch failed: {e}")
        
        threading.Thread(target=_fetch, daemon=True).start()