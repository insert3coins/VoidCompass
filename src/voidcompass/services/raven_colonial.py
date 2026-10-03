"""Raven Colonial client: shared colonisation projects (5.5.2).

Raven Colonial (https://ravencolonial.com) keeps build projects, their
commodity needs, who is assigned what, fleet carrier cargo and each system's
planned sites. These are the calls SrvSurvey makes; the API is documented at
<SERVICE_URL>/about and <SERVICE_URL>/openapi/v1.json.

* Commodity ids are lower case (``liquidoxygen``); commander names are
  lower-cased by the service; path parts are URL encoded.
* Calls that change a commander's own data (fleet carrier cargo, system
  sites, current ship) carry the ``rcc-key`` header. Void Compass sends no
  request at all unless the commander has entered a key and left sync on.
* Every call runs on one background worker, in order, so deliveries and
  carrier cargo changes reach the service as they happened.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
from urllib.parse import quote

import requests

from voidcompass.core.version import APP_VERSION

SERVICE_URL = "https://ravencolonial100-awcbdvabgze4c5cq.canadacentral-01.azurewebsites.net"
SITE_URL = "https://ravencolonial.com"


def project_url(build_id):
    return f"{SITE_URL}/#build={quote(str(build_id or ''), safe='')}"


def system_url(system_name):
    return f"{SITE_URL}/#sys={quote(str(system_name or ''), safe='')}"


class RavenError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _text_value(value):
    """A plain string reply (the service may send a JSON string as text)."""
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text or None


def _part(value):
    return quote(str(value if value is not None else ""), safe="")


class RavenColonialClient:
    def __init__(self, api_key="", base_url=SERVICE_URL, session=None, timeout=20):
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._lock = threading.Lock()
        self.last_ok_at = 0.0
        self.last_error = ""
        self.last_error_at = 0.0

    def set_api_key(self, api_key):
        self.api_key = str(api_key or "").strip()

    # -- transport -------------------------------------------------------
    def _request(self, method, path, body=None, keyed=False, missing_ok=False, key=None):
        headers = {"User-Agent": f"VoidCompass/{APP_VERSION}", "Accept": "application/json"}
        api_key = key if key is not None else self.api_key
        if (keyed or key is not None) and api_key:
            headers["rcc-key"] = api_key
        url = f"{self.base_url}{path}"
        try:
            with self._lock:
                response = self._session.request(method, url, json=body, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            self._failed(f"{method} {path}: {exc}")
            raise RavenError(str(exc)) from exc
        if missing_ok and response.status_code == 404:
            self.last_ok_at = time.time()
            return None
        if not response.ok:
            detail = (response.text or response.reason or "").strip()[:240]
            self._failed(f"{method} {path}: HTTP {response.status_code} {detail}")
            raise RavenError(f"HTTP {response.status_code}: {detail}", response.status_code)
        self.last_ok_at = time.time()
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _failed(self, message):
        self.last_error = message[:300]
        self.last_error_at = time.time()
        logging.warning("Raven Colonial: %s", message)

    # -- commander -------------------------------------------------------
    def commander_for_key(self, api_key):
        """The Raven Colonial commander a key belongs to, or None."""
        try:
            data = self._request("GET", "/api/cmdr/", key=str(api_key or "").strip())
        except RavenError:
            return None
        return str((data or {}).get("displayName") or "") or None if isinstance(data, dict) else None

    def active_projects(self, cmdr):
        return list(self._request("GET", f"/api/cmdr/{_part(cmdr)}/active") or [])

    def primary(self, cmdr):
        return _text_value(self._request("GET", f"/api/cmdr/{_part(cmdr)}/primary", missing_ok=True))

    def set_primary(self, cmdr, build_id):
        if build_id:
            self._request("PUT", f"/api/cmdr/{_part(cmdr)}/primary/{_part(build_id)}")
        else:
            self._request("DELETE", f"/api/cmdr/{_part(cmdr)}/primary/")

    def hidden_ids(self, cmdr):
        return [str(item) for item in self._request("GET", f"/api/cmdr/{_part(cmdr)}/hiddenIDs") or []]

    def set_hidden_ids(self, cmdr, build_ids):
        return [str(item) for item in self._request("POST", f"/api/cmdr/{_part(cmdr)}/hiddenIDs", list(build_ids)) or []]

    def commander_carriers(self, cmdr):
        return list(self._request("GET", f"/api/cmdr/{_part(cmdr)}/fc/all") or [])

    def link_carrier(self, cmdr, market_id):
        self._request("PUT", f"/api/cmdr/{_part(cmdr)}/fc/{_part(market_id)}", keyed=True)

    def unlink_carrier(self, cmdr, market_id):
        self._request("DELETE", f"/api/cmdr/{_part(cmdr)}/fc/{_part(market_id)}", keyed=True)

    def publish_current_ship(self, ship):
        self._request("POST", "/api/cmdr/currentShip", ship, keyed=True)

    # -- projects --------------------------------------------------------
    def create_project(self, project):
        return self._request("PUT", "/api/project/", project, keyed=True)

    def project(self, build_id):
        return self._request("GET", f"/api/project/{_part(build_id)}", missing_ok=True)

    def project_at(self, system_address, market_id):
        """The active project at a construction site, or None."""
        return self._request("GET", f"/api/system/{_part(system_address)}/{_part(market_id)}", missing_ok=True)

    def update_project(self, build_id, fields):
        return self._request("POST", f"/api/project/{_part(build_id)}", {"buildId": build_id, **fields}, keyed=True)

    def complete_project(self, build_id):
        self._request("POST", f"/api/project/{_part(build_id)}/complete", keyed=True)

    def link_commander(self, build_id, cmdr):
        self._request("PUT", f"/api/project/{_part(build_id)}/link/{_part(cmdr)}", keyed=True)

    def unlink_commander(self, build_id, cmdr):
        self._request("DELETE", f"/api/project/{_part(build_id)}/link/{_part(cmdr)}", keyed=True)

    def assign(self, build_id, cmdr, commodity):
        self._request("PUT", f"/api/project/{_part(build_id)}/assign/{_part(cmdr)}/{_part(commodity)}", keyed=True)

    def unassign(self, build_id, cmdr, commodity):
        self._request("DELETE", f"/api/project/{_part(build_id)}/assign/{_part(cmdr)}/{_part(commodity)}", keyed=True)

    def contribute(self, build_id, cmdr, delivered):
        """Credit a ColonisationContribution to the commander."""
        self._request("POST", f"/api/project/{_part(build_id)}/contribute/{_part(cmdr)}", dict(delivered), keyed=True)

    def link_project_carrier(self, build_id, market_id):
        self._request("PUT", f"/api/project/{_part(build_id)}/fc/{_part(market_id)}", keyed=True)

    def unlink_project_carrier(self, build_id, market_id):
        self._request("DELETE", f"/api/project/{_part(build_id)}/fc/{_part(market_id)}", keyed=True)

    # -- fleet carriers --------------------------------------------------
    def carrier(self, market_id):
        return self._request("GET", f"/api/fc/{_part(market_id)}", missing_ok=True)

    def publish_carrier(self, carrier):
        """Create or replace a carrier (its cargo is untouched when None)."""
        return self._request("PUT", f"/api/fc/{_part(carrier.get('marketId'))}", carrier, keyed=True)

    def supply_carrier(self, market_id, delta):
        """Add (or, negative, take) cargo on a carrier; returns its cargo."""
        return dict(self._request("PATCH", f"/api/fc/{_part(market_id)}/cargo", dict(delta), keyed=True) or {})

    def set_carrier_cargo(self, market_id, cargo):
        """Set carrier cargo counts outright; returns its cargo."""
        return dict(self._request("POST", f"/api/fc/{_part(market_id)}/cargo", dict(cargo), keyed=True) or {})

    # -- systems (architect) ---------------------------------------------
    def system(self, name_or_id):
        return self._request("GET", f"/api/v2/system/{_part(name_or_id)}", missing_ok=True)

    def system_sites(self, name_or_id):
        return list(self._request("GET", f"/api/v2/system/{_part(name_or_id)}/sites", missing_ok=True) or [])

    def update_system(self, name_or_id, sites_put):
        """``{"update": [site], "delete": [id], "architect"?, "open"?, "reserveLevel"?}``."""
        return self._request("PUT", f"/api/v2/system/{_part(name_or_id)}/sites", sites_put, keyed=True)

    def system_architect(self, name_or_id):
        return _text_value(self._request("GET", f"/api/v2/system/{_part(name_or_id)}/architect", missing_ok=True))

    def import_system_bodies(self, name_or_id):
        return self._request("POST", f"/api/v2/system/{_part(name_or_id)}/import/bodies", keyed=True)

    def update_system_bodies(self, system_address, bodies):
        return self._request("PUT", f"/api/v2/system/{_part(system_address)}/bodies", list(bodies), keyed=True)


class RavenWorker:
    """One background thread for every Raven Colonial call, in order."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raven-colonial")

    def submit(self, call, on_done=None, on_error=None):
        def run():
            try:
                result = call()
            except Exception as exc:  # RavenError, or a bad reply
                if on_error is not None:
                    on_error(exc)
                else:
                    logging.debug("Raven Colonial call failed: %s", exc)
                return None
            if on_done is not None:
                on_done(result)
            return result
        return self._executor.submit(run)

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
