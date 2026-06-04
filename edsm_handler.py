import collections
import json
import threading
import requests
import logging
import re
import html
import time
from version import APP_VERSION

# Events EDSM discards — matches the list served by api-journal-v1/discard.
# Keeping these client-side avoids sending noise and saves round-trips.
_EDSM_DISCARD_EVENTS = frozenset({
    "ShutDown", "Shutdown",
    "Music", "Screenshot",
    "ReceiveText", "SendText",
    "DockingRequested", "DockingGranted", "DockingDenied",
    "DockingCancelled", "DockingTimeout",
    "Market", "Shipyard", "Outfitting",
    "StoredModules", "StoredShips",
    "ModuleBuy", "ModuleSell", "ModuleRetrieve", "ModuleStore",
    "ModuleSwap", "ModuleTransfer",
    "ShipyardBuy", "ShipyardNew", "ShipyardSell", "ShipyardSwap", "ShipyardTransfer",
    "Bounty", "RedeemVoucher", "CrimeVictim",
    "PowerplayCollect", "PowerplayDeliver", "PowerplayDefect", "PowerplayEnlist",
    "PowerplayFastTrack", "PowerplayJoin", "PowerplayLeave", "PowerplaySalary",
    "PowerplayVote", "PowerplayVoucher",
    "NpcCrewRank", "NpcCrewPaidWage", "CrewAssign", "CrewFire", "CrewHire",
    "Passengers", "PassengerManifest",
    "MissionAccepted", "MissionCompleted", "MissionFailed",
    "MissionAbandoned", "MissionRedirected",
    "Cargo", "CargoDepot", "CargoTransfer",
    "NavRoute", "NavRouteClear",
    "Status",
})

_BATCH_SIZE = 50          # send when queue reaches this many events
_FLUSH_INTERVAL_S = 30    # also flush after this many seconds of inactivity


class EDSMHandler:
    def __init__(self, config):
        self.config = config
        self.status = "ACTIVE"
        self._http_limiter = threading.BoundedSemaphore(6)
        self._session = requests.Session()

        # Upload queue state
        self._upload_queue = collections.deque()
        self._queue_lock = threading.Lock()
        self._flush_timer = None
        self._game_version = ""
        self._game_build = ""
        self._log_callback = None  # set by dashboard: fn(tag, msg, severity)

    def set_log_callback(self, callback):
        """Wire up a function(tag, msg, severity) to post feed entries on upload."""
        self._log_callback = callback

    # ------------------------------------------------------------------
    # Upload queue helpers
    # ------------------------------------------------------------------

    def set_game_version(self, version, build):
        """Record the game version/build from FileHeader or LoadGame events."""
        if version:
            self._game_version = str(version)
        if build:
            self._game_build = str(build)

    def queue_journal_event(self, raw_event, system_name=None, system_coords=None, system_address=None):
        """Queue a journal event for batched upload to EDSM.

        Enriches the event with system context fields the way EDDiscovery does,
        then adds it to the outbound queue. Skips events on the EDSM discard list.
        """
        if not self.config.get("edsm_upload_enabled"):
            return
        if not self.config.get("edsm_cmdr_name", "").strip():
            return
        if not self.config.get("edsm_api_key", "").strip():
            return

        ev_name = raw_event.get("event", "")
        if ev_name in _EDSM_DISCARD_EVENTS:
            return

        # Enrich with system context (mirrors EDDiscovery _systemName etc.)
        enriched = dict(raw_event)
        if system_name:
            enriched["_systemName"] = system_name
        if system_address is not None:
            enriched["_systemAddress"] = system_address
        if system_coords:
            enriched["_systemCoordinates"] = system_coords

        with self._queue_lock:
            self._upload_queue.append(enriched)
            queue_size = len(self._upload_queue)

        if queue_size >= _BATCH_SIZE:
            self._arm_flush(immediate=True)
        else:
            self._arm_flush(immediate=False)

    def flush_upload_queue(self):
        """Force an immediate flush — call this on system jumps."""
        self._arm_flush(immediate=True)

    def _arm_flush(self, immediate=False):
        with self._queue_lock:
            if self._flush_timer is not None:
                if not immediate:
                    return  # existing timer is fine
                self._flush_timer.cancel()
                self._flush_timer = None
            delay = 0 if immediate else _FLUSH_INTERVAL_S
            t = threading.Timer(delay, self._do_flush)
            t.daemon = True
            self._flush_timer = t
        t.start()

    def _do_flush(self):
        with self._queue_lock:
            self._flush_timer = None
            if not self._upload_queue:
                return
            batch = []
            while self._upload_queue and len(batch) < _BATCH_SIZE:
                batch.append(self._upload_queue.popleft())

        if not batch:
            return

        cmdr = self.config.get("edsm_cmdr_name", "").strip()
        key = self.config.get("edsm_api_key", "").strip()
        if not cmdr or not key:
            return

        def _send():
            try:
                payload = {
                    "commanderName": cmdr,
                    "apiKey": key,
                    "fromSoftware": "VoidCompass",
                    "fromSoftwareVersion": APP_VERSION,
                    "message": json.dumps(batch),
                }
                if self._game_version:
                    payload["fromGameVersion"] = self._game_version
                if self._game_build:
                    payload["fromGameBuild"] = self._game_build

                with self._http_limiter:
                    headers = {"User-Agent": f"VoidCompass/{APP_VERSION}"}
                    r = self._session.post(
                        "https://www.edsm.net/api-journal-v1",
                        data=payload,
                        headers=headers,
                        timeout=20,
                    )
                    r.raise_for_status()
                    logging.debug(f"EDSM upload OK: {len(batch)} events")
                    if self._log_callback:
                        self._log_callback("EDSM", f"Uploaded {len(batch)} event(s) to EDSM", "INFO")
            except Exception as e:
                logging.warning(f"EDSM batch upload failed ({len(batch)} events): {e}")
                if self._log_callback:
                    self._log_callback("EDSM", f"Upload failed: {e}", "ERROR")

        threading.Thread(target=_send, daemon=True).start()

    # ------------------------------------------------------------------
    # Read-only EDSM / Spansh fetch helpers (unchanged)
    # ------------------------------------------------------------------

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

                blurb = " ".join(cleaned[:2]).strip()
                if len(blurb) > 420:
                    blurb = blurb[:417].rstrip() + "..."
                callback(blurb or None)
            except Exception as e:
                logging.warning(f"System blurb fetch failed: {e}")
                callback(None)

        threading.Thread(target=_fetch, daemon=True).start()
