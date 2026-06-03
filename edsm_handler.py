import threading
import requests
import logging
import re
import html
import time
from version import APP_VERSION

class EDSMHandler:
    def __init__(self, config):
        self.config = config
        self.status = "ACTIVE"
        self._http_limiter = threading.BoundedSemaphore(6)
        self._session = requests.Session()

    def _limited_get(self, url, params=None, timeout=10, retries=2):
        last_exc = None
        for attempt in range(retries + 1):
            with self._http_limiter:
                try:
                    headers = {'User-Agent': f'VoidCompass/{APP_VERSION}'}
                    r = self._session.get(url, params=params, headers=headers, timeout=timeout)
                    r.raise_for_status()
                    return r
                except Exception as e:
                    last_exc = e
            if attempt < retries:
                time.sleep(0.25 * (attempt + 1))
        raise last_exc

    def fetch_traffic(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name}
                url = "https://www.edsm.net/api-system-v1/traffic"
                r = self._limited_get(url, params=params, timeout=10, retries=1)
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
                r = self._limited_get(url, params=params, timeout=12, retries=2)
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
                r = self._limited_get(url, params=params, timeout=12, retries=2)
                data = r.json()
                if isinstance(data, dict) and "name" in data:
                    callback(data)
                else:
                    callback(None)
            except Exception as e:
                logging.warning(f"System details fetch failed: {e}")
                callback(None)
        
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_spansh_system(self, system_address, callback):
        """Fetch full system dump from Spansh (stations, services, etc.)."""
        def _fetch():
            try:
                url = f"https://spansh.co.uk/api/dump/{system_address}/"
                r = self._limited_get(url, timeout=15, retries=1)
                data = r.json()
                callback(data if isinstance(data, dict) else None)
            except Exception as e:
                logging.warning(f"Spansh system dump failed: {e}")
                callback(None)
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_system_blurb(self, system_name, callback):
        def _fetch():
            try:
                params = {"systemName": system_name}
                url = "https://www.edsm.net/en/system"
                r = self._limited_get(url, params=params, timeout=15, retries=2)
                text = r.text

                match = re.search(
                    r"Galactic Mapping Project entry.*?<div class=\"card-body\">(.*?)</div>",
                    text,
                    re.S | re.I
                )
                if not match:
                    callback(None)
                    return

                block = match.group(1)
                paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", block, re.S | re.I)
                cleaned = []
                for p in paragraphs:
                    p = re.sub(r"<[^>]+>", "", p)
                    p = html.unescape(p).strip()
                    if p:
                        cleaned.append(p)
                if not cleaned:
                    callback(None)
                    return

                # Keep concise for notes: first two paragraphs max.
                blurb = " ".join(cleaned[:2]).strip()
                if len(blurb) > 420:
                    blurb = blurb[:417].rstrip() + "..."
                callback(blurb or None)
            except Exception as e:
                logging.warning(f"System blurb fetch failed: {e}")
                callback(None)

        threading.Thread(target=_fetch, daemon=True).start()
