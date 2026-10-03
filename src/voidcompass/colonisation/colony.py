"""The commander's colonisation state (per profile), after SrvSurvey's
ColonyData: Raven Colonial projects, the primary and hidden ones, linked fleet
carriers and their cargo, and where the commander is docked.

Projects are Raven Colonial's own records (``buildId``, ``buildName``,
``buildType``, ``systemName``, ``systemAddress``, ``marketId``,
``commodities`` {id: still needed}, ``maxNeed``, ``sumNeed``, ``commanders``
{cmdr: [assigned ids]}, ``linkedFC`` [{marketId, name, displayName}], ...).
"""

from __future__ import annotations

import json
import os
import threading
import time

from voidcompass.colonisation import catalogue
from voidcompass.core.persistence_queue import persistence_queue

SCHEMA = 1


class ColonyState:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.projects = []
        self.primary_build_id = None
        self.hidden_ids = []
        self.carriers = {}  # str(marketId) -> {marketId, name, displayName, cargo}
        self.synced_at = 0.0
        self.revision = 0
        # Live, not saved: where the commander is docked and the site's depot.
        self.docked = None
        self.last_depot = None
        self.untracked_project = None
        self.pending = 0
        self.pending_diff = {}
        self.sync_error = ""
        self.load()

    # -- storage ---------------------------------------------------------
    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self.lock:
            self.projects = [row for row in data.get("projects") or [] if isinstance(row, dict)]
            self.primary_build_id = data.get("primary_build_id") or None
            self.hidden_ids = [str(item) for item in data.get("hidden_ids") or []]
            self.carriers = {str(key): value for key, value in (data.get("carriers") or {}).items() if isinstance(value, dict)}
            self.synced_at = float(data.get("synced_at") or 0)

    def _payload(self):
        with self.lock:
            return {"schema": SCHEMA, "projects": list(self.projects), "primary_build_id": self.primary_build_id,
                    "hidden_ids": list(self.hidden_ids), "carriers": dict(self.carriers), "synced_at": self.synced_at}

    def save(self):
        with self.lock:
            self.revision += 1
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=1.0)

    # -- sync results ----------------------------------------------------
    def apply_sync(self, projects=None, primary=None, hidden=None, carriers=None):
        with self.lock:
            if projects is not None:
                self.projects = [row for row in projects if isinstance(row, dict)]
            if hidden is not None:
                self.hidden_ids = [str(item) for item in hidden]
            if primary is not None or projects is not None:
                primary = primary or None
                self.primary_build_id = primary if primary and self.project(primary) else None
            if carriers is not None:
                self.carriers = {str(row.get("marketId")): row for row in carriers if isinstance(row, dict) and row.get("marketId") is not None}
            self.synced_at = time.time()
        self.save()

    def replace_project(self, project):
        if not isinstance(project, dict) or not project.get("buildId"):
            return False
        with self.lock:
            for index, row in enumerate(self.projects):
                if row.get("buildId") == project["buildId"]:
                    self.projects[index] = project
                    break
            else:
                return False
        self.save()
        return True

    def apply_carrier_cargo(self, market_id, cargo):
        with self.lock:
            carrier = self.carriers.get(str(market_id))
            if carrier is None:
                return False
            carrier["cargo"] = {catalogue.commodity_id(key): int(value or 0) for key, value in (cargo or {}).items()}
        self.save()
        return True

    # -- lookups ---------------------------------------------------------
    def project(self, build_id):
        if not build_id:
            return None
        return next((row for row in self.projects if row.get("buildId") == build_id), None)

    def project_at(self, system_address, market_id):
        if system_address is None or market_id is None:
            return None
        return next((row for row in self.projects
                     if str(row.get("systemAddress")) == str(system_address) and str(row.get("marketId")) == str(market_id)), None)

    def has_carrier(self, market_id):
        return market_id is not None and str(market_id) in self.carriers

    def visible_projects(self):
        hidden = set(self.hidden_ids)
        return [row for row in self.projects if row.get("buildId") not in hidden]

    def carrier_cargo(self, market_ids=None):
        """Summed cargo of the given (or every) linked carrier."""
        wanted = None if market_ids is None else {str(item) for item in market_ids}
        total = {}
        for key, carrier in self.carriers.items():
            if wanted is not None and key not in wanted:
                continue
            for name, count in (carrier.get("cargo") or {}).items():
                name = catalogue.commodity_id(name)
                total[name] = total.get(name, 0) + int(count or 0)
        return total

    @staticmethod
    def needs(projects, cmdr):
        """Summed needs of projects, and which commodities are assigned to
        this commander or to others (SrvSurvey's Needs)."""
        commodities, mine, others = {}, set(), set()
        me = str(cmdr or "").casefold()
        for project in projects:
            commanders = project.get("commanders") or {}
            for name, need in (project.get("commodities") or {}).items():
                name = catalogue.commodity_id(name)
                commodities[name] = commodities.get(name, 0) + int(need or 0)
                assigned = [who for who, items in commanders.items()
                            if name in {catalogue.commodity_id(item) for item in items or ()}]
                if any(str(who).casefold() == me for who in assigned):
                    mine.add(name)
                elif assigned:
                    others.add(name)
        return {"commodities": commodities, "assigned_me": mine, "assigned_others": others}

    # -- pending (Updating...) -------------------------------------------
    def start_pending(self, diff=None):
        with self.lock:
            self.pending += 1
            self.pending_diff = {catalogue.commodity_id(key): value for key, value in (diff or {}).items()}
            self.revision += 1

    def end_pending(self):
        with self.lock:
            self.pending = max(0, self.pending - 1)
            if not self.pending:
                self.pending_diff = {}
            self.revision += 1
