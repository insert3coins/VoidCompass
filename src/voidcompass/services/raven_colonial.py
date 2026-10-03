"""Raven Colonial client: shared colonisation projects (5.5.2).

Raven Colonial (https://ravencolonial.com) keeps build projects, their
commodity needs, who is assigned what, fleet carrier cargo and each system's
planned sites. These are the calls SrvSurvey makes; the API is documented at
<SERVICE_URL>/about and <SERVICE_URL>/openapi/v1.json.

* Commodity ids are lower case (``liquidoxygen``); commander names are
  lower-cased by the service; path parts are URL encoded.
* Calls that change a commander's own data (fleet carrier cargo, system
  sites, current ship) carry the ``rcc-key`` header, and the commander's
  name (base64, ``rcc-cmdr0``) as the website sends it. Void Compass sends no
  request at all unless the commander has entered a key and left sync on.
* Every call runs on one background worker, in order, so deliveries and
  carrier cargo changes reach the service as they happened.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
from urllib.parse import quote

import requests

from voidcompass.core.version import APP_VERSION

SERVICE_URL = "https://ravencolonial100-awcbdvabgze4c5cq.canadacentral-01.azurewebsites.net"
SITE_URL = "https://ravencolonial.com"


# A fleet carrier loading project: stock a carrier rather than build a site.
FC_LOADING = "fc_loading"


def project_url(build_id):
    return f"{SITE_URL}/#build={quote(str(build_id or ''), safe='')}"


def system_url(system_name):
    return f"{SITE_URL}/#sys={quote(str(system_name or ''), safe='')}"


def nexus_url(nexus_id):
    return f"{SITE_URL}/#nexus={quote(str(nexus_id or ''), safe='')}"


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
        self.cmdr = ""
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._lock = threading.Lock()
        self.last_ok_at = 0.0
        self.last_error = ""
        self.last_error_at = 0.0

    def set_api_key(self, api_key):
        self.api_key = str(api_key or "").strip()

    def set_commander(self, cmdr):
        self.cmdr = str(cmdr or "").strip()

    # -- transport -------------------------------------------------------
    def _request(self, method, path, body=None, keyed=False, missing_ok=False, key=None):
        headers = {"User-Agent": f"VoidCompass/{APP_VERSION}", "Accept": "application/json"}
        api_key = key if key is not None else self.api_key
        if (keyed or key is not None) and api_key:
            headers["rcc-key"] = api_key
            if self.cmdr and key is None:
                headers["rcc-cmdr0"] = base64.b64encode(self.cmdr.encode("utf-8")).decode("ascii")
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

    def assigned_active(self, cmdr):
        """``{buildId: {commodity: need}}``: what is assigned to the
        commander across their active projects."""
        return dict(self._request("GET", f"/api/cmdr/{_part(cmdr)}/assigned/active", missing_ok=True) or {})

    def system_snapshots(self):
        """Snapshots of every system the keyed commander architects."""
        return list(self._request("GET", "/api/v2/system/snapshots/", keyed=True, missing_ok=True) or [])

    # -- projects --------------------------------------------------------
    def create_project(self, project):
        return self._request("PUT", "/api/project/", project, keyed=True)

    def create_fc_loading_project(self, name):
        """A project for stocking a fleet carrier (the website's way)."""
        return self.create_project({"buildName": name, "buildType": FC_LOADING, "marketId": 1,
                                    "systemAddress": 1, "prepBuilds": {}})

    def create_project_from_site(self, id64, site_id, build_type=""):
        """Start a project from a system's planned site, without docking."""
        return self._request("POST", f"/api/project/from/{_part(id64)}/{_part(site_id)}/{_part(build_type)}", keyed=True)

    def delete_project(self, build_id):
        self._request("DELETE", f"/api/project/{_part(build_id)}", keyed=True)

    def project_stats(self, build_id):
        return self._request("GET", f"/api/project/{_part(build_id)}/stats", missing_ok=True) or {}

    def set_ready(self, build_id, commodities, ready=True):
        """Mark commodities ready (loaded and on the way) or not."""
        self._request("POST" if ready else "DELETE", f"/api/project/{_part(build_id)}/ready", list(commodities), keyed=True)

    def find_markets(self, options):
        """Markets near a reference system selling what projects need."""
        return self._request("POST", "/api/project/markets", dict(options)) or {}

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

    def rename_carrier(self, market_id, display_name):
        return self._request("PATCH", f"/api/fc/{_part(market_id)}", {"displayName": display_name}, keyed=True)

    def find_carriers(self, name):
        """Carriers whose callsign or name matches (Spansh search)."""
        return list(self._request("GET", f"/api/fc/query/{_part(name)}", missing_ok=True) or [])

    def check_carrier(self, market_id):
        """Look a carrier up on Spansh and record it on Raven Colonial."""
        return self._request("POST", f"/api/fc/{_part(market_id)}/spansh", keyed=True)

    def refresh_carrier(self, name_or_market_id):
        """Ask the service to refresh a carrier (location, market orders)."""
        return self._request("POST", f"/api/fc/{_part(name_or_market_id)}/refresh", keyed=True)

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

    def system_revision(self, name_or_id, rev):
        return self._request("GET", f"/api/v2/system/{_part(name_or_id)}/.{_part(rev)}", missing_ok=True)

    def system_named_save(self, name_or_id, save_name):
        return self._request("POST", f"/api/v2/system/{_part(name_or_id)}/!", str(save_name), keyed=True)

    def delete_system_named_save(self, name_or_id, save_name):
        self._request("DELETE", f"/api/v2/system/{_part(name_or_id)}/!{_part(save_name)}", keyed=True)

    def system_snapshot(self, id64, architect):
        return self._request("GET", f"/api/v2/system/{_part(id64)}/snapshot/{_part(architect)}", missing_ok=True)

    def save_system_snapshot(self, id64, snapshot):
        return self._request("PUT", f"/api/v2/system/{_part(id64)}/snapshot", snapshot, keyed=True)

    def set_system_favourite(self, id64, favourite):
        flag = "true" if favourite else "false"
        return self._request("POST", f"/api/v2/system/{_part(id64)}/fav/{flag}", keyed=True)

    def set_body_features(self, name_or_id, body_num, features):
        return list(self._request("PUT", f"/api/v2/system/{_part(name_or_id)}/{_part(body_num)}/features",
                                  list(features), keyed=True) or [])

    def import_system(self, name_or_id, kind=""):
        """Import from Spansh: ``bodies``, or "" for bodies and stations."""
        return self._request("POST", f"/api/v2/system/{_part(name_or_id)}/import/{_part(kind)}", keyed=True)

    def refresh_population(self, id64):
        return self._request("POST", f"/api/v2/system/{_part(id64)}/refreshPop", keyed=True)

    def population_history(self, id64):
        return list(self._request("GET", f"/api/v2/system/{_part(id64)}/popHistory", missing_ok=True) or [])

    # -- nexus (multi-system plans; the service calls them chains) --------
    def my_nexuses(self):
        return list(self._request("GET", "/api/cmdr/nexus", keyed=True, missing_ok=True) or [])

    def nexus(self, nexus_id):
        return self._request("GET", f"/api/chain/{_part(nexus_id)}", keyed=True, missing_ok=True)

    def create_nexus(self, name):
        return self._request("PUT", "/api/chain/create", {"name": name}, keyed=True)

    def delete_nexus(self, nexus_id):
        self._request("DELETE", f"/api/chain/delete/{_part(nexus_id)}", keyed=True)

    NEXUS_FIELDS = ("setName", "setNotes", "setPrivate", "setCmdrs", "setFCs", "setSystems")

    def update_nexus(self, nexus_id, field, value):
        """``field`` is one of NEXUS_FIELDS."""
        if field not in self.NEXUS_FIELDS:
            raise ValueError(field)
        return self._request("POST", f"/api/chain/{_part(nexus_id)}/{field}", value, keyed=True)

    def set_nexus_system_carriers(self, nexus_id, id64, market_ids):
        return self._request("POST", f"/api/chain/{_part(nexus_id)}/{_part(id64)}/setFCs", list(market_ids), keyed=True)

    # -- statistics ------------------------------------------------------
    def global_stats(self):
        return self._request("GET", "/api/stats/") or {}


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
