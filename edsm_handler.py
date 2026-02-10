import threading
import requests
import logging
from version import APP_VERSION

class EDSMHandler:
    def __init__(self, config):
        self.config = config
        self.status = "ACTIVE"

    def fetch_traffic(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name}
                url = "https://www.edsm.net/api-system-v1/traffic"
                headers = {'User-Agent': f'VoidCompass/{APP_VERSION}'}
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

    def fetch_system_coords(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name, 'showCoordinates': 1}
                url = "https://www.edsm.net/api-v1/system"
                headers = {'User-Agent': f'VoidCompass/{APP_VERSION}'}
                r = requests.get(url, params=params, headers=headers, timeout=10)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict) and "coords" in data:
                    callback(data.get("name", system_name), data["coords"])
                else:
                    callback(system_name, None)
            except Exception as e:
                logging.warning(f"Coords fetch failed: {e}")
                callback(system_name, None)
        
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_system_details(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name, 'showInformation': 1, 'showPrimaryStar': 1}
                url = "https://www.edsm.net/api-v1/system"
                headers = {'User-Agent': f'VoidCompass/{APP_VERSION}'}
                r = requests.get(url, params=params, headers=headers, timeout=10)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict) and "name" in data:
                    callback(data)
                else:
                    callback(None)
            except Exception as e:
                logging.warning(f"System details fetch failed: {e}")
                callback(None)
        
        threading.Thread(target=_fetch, daemon=True).start()
