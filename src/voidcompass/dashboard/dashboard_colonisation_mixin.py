"""Colonisation (5.5.2): the journal, Raven Colonial and the Construction
Needs overlay, after SrvSurvey's colonisation features.

Raven Colonial is only contacted when the commander has entered their key in
Settings > Integrations and left sync on; then deliveries, depot updates,
completion, fleet carrier cargo and the beacon's architect are published as
they happen, under the commander's name. Nothing is sent while the journal is
being replayed at startup.
"""

from __future__ import annotations

import logging
import time

from voidcompass.colonisation import catalogue
from voidcompass.colonisation.colony import ColonyState
from voidcompass.colonisation.views import overlay_model, overlay_options
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.services.raven_colonial import RavenColonialClient, RavenWorker

# Overlay visibility (SrvSurvey's rules): GuiFocus values.
_GUI_RIGHT_PANEL = 1
_GUI_STATION_SERVICES = 5
_GUI_MAPS = {6, 7, 8}


class DashboardColonisationMixin:
    # -- lifecycle -------------------------------------------------------
    def _colony_init(self):
        self.colony = ColonyState(get_profile_file(get_active_profile(self.config), "colony.json"))
        if getattr(self, "raven", None) is None:
            self.raven = RavenColonialClient()
            self.raven_worker = RavenWorker()
        self.raven.set_api_key(self.config.get("raven_api_key"))
        self._colony_market = None
        self._colony_market_seen = False
        self._colony_docked = None

    def _colony_switch_profile(self, profile_key):
        if getattr(self, "colony", None) is not None:
            self.colony.save()
        self.colony = ColonyState(get_profile_file(profile_key, "colony.json"))
        self.raven.set_api_key(self.config.get("raven_api_key"))
        self._colony_docked = None
        self._colony_refresh()

    def _raven_active(self):
        return bool(str(self.config.get("raven_api_key") or "").strip()
                    and self.config.get("raven_sync_enabled", True)
                    and getattr(self, "raven", None) is not None)

    def _colony_cmdr(self):
        return str(getattr(self, "cmdr_name", "") or "").strip()

    def _colony_changed(self):
        """Repaint the tab and the overlay after any colonisation change."""
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish()
        self._colony_update_overlay()

    def _raven_call(self, call, on_done=None, pending=None, label="Raven Colonial"):
        """Run a Raven Colonial call in the background; results come back on
        the UI thread. ``pending`` marks the overlay "Updating..."."""
        if not self._raven_active():
            return False
        colony = self.colony
        if pending is not None:
            colony.start_pending(pending)
            self._colony_update_overlay()

        def done(result):
            def apply():
                if pending is not None:
                    colony.end_pending()
                colony.sync_error = ""
                if on_done is not None and colony is self.colony:
                    on_done(result)
                self._colony_changed()
            self._ui_post(apply, key=None)

        def failed(exc):
            def apply():
                if pending is not None:
                    colony.end_pending()
                colony.sync_error = f"{label}: {exc}"[:240]
                self._colony_changed()
            self._ui_post(apply, key=None)

        self.raven_worker.submit(call, on_done=done, on_error=failed)
        return True

    def _colony_refresh(self, build_id=None):
        """Fetch the commander's projects, primary, hidden ids and carriers
        (or one project) from Raven Colonial."""
        cmdr = self._colony_cmdr()
        if not cmdr or not self._raven_active():
            return False
        raven = self.raven
        if build_id:
            return self._raven_call(lambda: raven.project(build_id), self.colony.replace_project, pending={})

        def fetch():
            return {"projects": raven.active_projects(cmdr), "primary": raven.primary(cmdr) or "",
                    "hidden": raven.hidden_ids(cmdr), "carriers": raven.commander_carriers(cmdr)}

        return self._raven_call(fetch, lambda data: self.colony.apply_sync(**data), pending={}, label="Raven sync")

    # -- journal ---------------------------------------------------------
    def _colony_observe(self, event, raw, startup_replay=False):
        if getattr(self, "colony", None) is None or not isinstance(raw, dict):
            return
        handler = getattr(self, f"_colony_on_{event}", None)
        if callable(handler):
            try:
                handler(raw, startup_replay)
            except Exception as exc:
                logging.warning("Colonisation %s skipped: %s", event, exc)

    def _colony_on_LoadGame(self, raw, startup_replay):
        if not startup_replay:
            self._colony_refresh()

    def _colony_on_Docked(self, raw, startup_replay):
        self._colony_docked = {
            "station_name": raw.get("StationName") or "", "station_type": raw.get("StationType") or "",
            "market_id": raw.get("MarketID"), "system_address": raw.get("SystemAddress"),
            "system_name": raw.get("StarSystem") or "", "services": list(raw.get("StationServices") or ()),
            "faction": (raw.get("StationFaction") or {}).get("Name") or "",
        }
        self._colony_market_seen = False
        self.colony.last_depot = None
        self.colony.untracked_project = None
        docked = self._colony_docked
        if not catalogue.is_construction_site(docked["station_name"], docked["services"]):
            self._colony_update_overlay()
            return
        # Keep the site's name on the local (journal) project record.
        local = (getattr(self, "colonisation_projects", None) or {}).get(docked["market_id"])
        if isinstance(local, dict):
            local["site_name"] = catalogue.default_project_name(docked["station_name"])
            local["system_address"] = docked["system_address"]
        if startup_replay:
            # Launched while docked here: the panel shows from the journal alone.
            self._colony_update_overlay()
            return
        project = self.colony.project_at(docked["system_address"], docked["market_id"])
        raven = self.raven
        if project is None:
            # Someone else may be tracking this site.
            self._raven_call(lambda: raven.project_at(docked["system_address"], docked["market_id"]),
                             lambda found: setattr(self.colony, "untracked_project", found), pending={})
        else:
            changes = {}
            if docked["faction"] and project.get("factionName") != docked["faction"]:
                changes["factionName"] = docked["faction"]
            body_id = getattr(self, "current_body_id", None)
            body_name = getattr(self, "current_body_name", None)
            if body_id is not None and body_name and (project.get("bodyNum") != body_id or project.get("bodyName") != body_name):
                changes.update(bodyNum=body_id, bodyName=body_name)
            if changes:
                build_id = project["buildId"]
                self._raven_call(lambda: raven.update_project(build_id, changes), self.colony.replace_project, pending={})
        self._colony_update_overlay()

    def _colony_site_name(self, market_id):
        """The docked construction site's name, for the journal's record."""
        docked = getattr(self, "_colony_docked", None) or {}
        if str(docked.get("market_id")) != str(market_id):
            return ""
        if not catalogue.is_construction_site(docked.get("station_name"), docked.get("services")):
            return ""
        return catalogue.default_project_name(docked.get("station_name"))

    def _colony_on_Undocked(self, raw, startup_replay):
        self._colony_docked = None
        self._colony_market_seen = False
        self.colony.last_depot = None
        self.colony.untracked_project = None
        self._colony_update_overlay()

    def _colony_on_ColonisationConstructionDepot(self, raw, startup_replay):
        previous = self.colony.last_depot
        self.colony.last_depot = raw
        docked = self._colony_docked or {}
        address = docked.get("system_address") or getattr(self, "current_system_address", None)
        if startup_replay:
            self._colony_update_overlay()
            return
        market_id = raw.get("MarketID")
        raven = self.raven
        if raw.get("ConstructionComplete"):
            project = next((row for row in self.colony.projects if str(row.get("marketId")) == str(market_id)), None)
            if project and not project.get("complete"):
                build_id = project["buildId"]

                def finished(_result):
                    project["complete"] = True
                    self.colony.save()
                    self._colony_refresh()
                self._raven_call(lambda: raven.complete_project(build_id), finished, pending={})
            self._colony_update_overlay()
            return
        unchanged = bool(previous and previous.get("MarketID") == market_id
                         and previous.get("ConstructionProgress") == raw.get("ConstructionProgress")
                         and catalogue.depot_needs(previous.get("ResourcesRequired")) == catalogue.depot_needs(raw.get("ResourcesRequired")))
        project = self.colony.project_at(address, market_id)
        if project is None and self.colony.untracked_project and str(self.colony.untracked_project.get("marketId")) == str(market_id):
            project = self.colony.untracked_project
        needed = catalogue.depot_needs(raw.get("ResourcesRequired"))
        if project and not unchanged:
            current = {catalogue.commodity_id(key): int(value or 0) for key, value in (project.get("commodities") or {}).items()}
            if sum(needed.values()) != sum(current.get(key, 0) for key in needed) or needed != {key: current.get(key, 0) for key in needed}:
                build_id = project["buildId"]
                fields = {"commodities": needed, "maxNeed": catalogue.depot_total(raw.get("ResourcesRequired")),
                          "colonisationConstructionDepot": raw}

                def saved(result):
                    if not self.colony.replace_project(result):
                        self._colony_refresh()  # newly joined: fetch everything
                self._raven_call(lambda: raven.update_project(build_id, fields), saved, pending={})
        self._colony_update_overlay()

    def _colony_on_ColonisationContribution(self, raw, startup_replay):
        docked = self._colony_docked
        if startup_replay or not docked or not catalogue.is_construction_site(docked["station_name"], docked["services"]):
            return
        delivered = {}
        for row in raw.get("Contributions") or ():
            name = catalogue.commodity_id((row or {}).get("Name"))
            if name:
                delivered[name] = delivered.get(name, 0) + int((row or {}).get("Amount", 0) or 0)
        project = self.colony.project_at(docked["system_address"], docked["market_id"]) or self.colony.untracked_project
        if not delivered or not project or not project.get("buildId"):
            return
        build_id, cmdr, raven = project["buildId"], self._colony_cmdr(), self.raven
        self._raven_call(lambda: raven.contribute(build_id, cmdr, delivered),
                         lambda _r: self._colony_refresh(build_id), pending=delivered, label="Delivery")

    def _colony_on_ColonisationBeaconDeployed(self, raw, startup_replay):
        system = getattr(self, "current_sys", "") or ""
        if startup_replay or not system:
            return
        cmdr, raven = self._colony_cmdr(), self.raven
        self._raven_call(lambda: raven.update_system(system, {"update": [], "delete": [], "architect": cmdr}),
                         label="Architect")

    def _colony_linked_carrier(self, market_id):
        docked = self._colony_docked or {}
        return (str(docked.get("station_type") or "").casefold() == "fleetcarrier"
                and self.colony.has_carrier(market_id))

    def _colony_supply_carrier(self, market_id, delta):
        raven = self.raven
        self._raven_call(lambda: raven.supply_carrier(market_id, delta),
                         lambda cargo: self.colony.apply_carrier_cargo(market_id, cargo),
                         pending=delta, label="Carrier cargo")

    def _colony_on_MarketBuy(self, raw, startup_replay):
        market_id = raw.get("MarketID")
        if not startup_replay and self._colony_linked_carrier(market_id):
            self._colony_supply_carrier(market_id, {catalogue.commodity_id(raw.get("Type")): -int(raw.get("Count") or 0)})
        self._colony_update_overlay()

    def _colony_on_MarketSell(self, raw, startup_replay):
        market_id = raw.get("MarketID")
        if not startup_replay and self._colony_linked_carrier(market_id):
            self._colony_supply_carrier(market_id, {catalogue.commodity_id(raw.get("Type")): int(raw.get("Count") or 0)})
        self._colony_update_overlay()

    def _colony_on_CargoTransfer(self, raw, startup_replay):
        docked = self._colony_docked or {}
        market_id = docked.get("market_id")
        if startup_replay or not self._colony_linked_carrier(market_id):
            return
        delta = {}
        for row in raw.get("Transfers") or ():
            name = catalogue.commodity_id((row or {}).get("Type"))
            count = int((row or {}).get("Count") or 0)
            direction = str((row or {}).get("Direction") or "").casefold()
            if direction == "tocarrier":
                delta[name] = delta.get(name, 0) + count
            elif direction == "toship":
                delta[name] = delta.get(name, 0) - count
        if delta:
            self._colony_supply_carrier(market_id, delta)

    # -- Market.json and Cargo.json --------------------------------------
    def _colony_on_market_file(self, data):
        """Market.json: what is in stock here, and a linked carrier's cargo."""
        if getattr(self, "colony", None) is None or not isinstance(data, dict):
            return
        market_id = data.get("MarketID")
        items = data.get("Items") or []
        self._colony_market = {"market_id": market_id, "at": time.time(),
                               "items": {catalogue.commodity_id(item.get("Name")) for item in items
                                         if int(item.get("Stock") or 0) > 0}}
        self._colony_market_seen = True
        if self.colony.has_carrier(market_id):
            raven = self.raven

            def reconcile():
                carrier = raven.carrier(market_id) or {}
                known = {catalogue.commodity_id(key): int(value or 0) for key, value in (carrier.get("cargo") or {}).items()}
                changes = {}
                for item in items:
                    name = catalogue.commodity_id(item.get("Name"))
                    stock = int(item.get("Stock") or 0)
                    if item.get("Producer") and known.get(name) != stock:
                        changes[name] = stock
                    elif not item.get("Producer") and not item.get("Consumer") and known.get(name, 0) > 0:
                        changes[name] = stock  # for sale, now sold out
                return raven.set_carrier_cargo(market_id, changes) if changes else carrier.get("cargo") or known
            self._raven_call(reconcile, lambda cargo: self.colony.apply_carrier_cargo(market_id, cargo), pending={}, label="Carrier market")
        self._colony_update_overlay()

    def _colony_on_cargo_file(self):
        """Cargo.json: optionally share the ship's cargo with Raven Colonial."""
        if getattr(self, "colony", None) is None:
            return
        if self.config.get("raven_share_ship_cargo", False) and self.colony.visible_projects():
            cmdr, raven = self._colony_cmdr(), self.raven
            known = getattr(self, "cmdr_ship", None) or {}
            ship = {"cmdr": cmdr,
                    "name": str(known.get("ship_name") or known.get("ship_ident") or "Ship"),
                    "type": str(known.get("ship") or ""),
                    "maxCargo": int(self._active_cargo_capacity() or 0),
                    "cargo": {catalogue.commodity_id(row.get("Name")): int(row.get("Count") or 0)
                              for row in getattr(self, "current_cargo_inventory", None) or () if isinstance(row, dict)}}
            self._raven_call(lambda: raven.publish_current_ship(ship), label="Ship cargo")
        self._colony_update_overlay()

    # -- the Construction Needs overlay ----------------------------------
    def _colony_market_items(self):
        market = self._colony_market
        docked = self._colony_docked
        if not market or not docked or str(market.get("market_id")) != str(docked.get("market_id")):
            return None
        return market["items"]

    def _colony_overlay_model(self):
        return overlay_model(
            self.colony, self._colony_cmdr(), docked=self._colony_docked,
            current_address=getattr(self, "current_system_address", None),
            ship_cargo=getattr(self, "current_cargo_inventory", None) or (),
            capacity=self._active_cargo_capacity(), market_items=self._colony_market_items(),
            options=overlay_options(self.config),
        )

    def _colony_overlay_wanted(self, model):
        """SrvSurvey's rules for showing the panel on its own."""
        if model is None:
            return False
        focus = getattr(self, "current_gui_focus", -1)
        if focus in _GUI_MAPS:
            return False
        docked = self._colony_docked
        if docked and catalogue.is_construction_site(docked["station_name"], docked["services"]):
            return True
        has_projects = bool(self.colony.visible_projects())
        if docked and focus == _GUI_STATION_SERVICES:
            if (self._colony_market_seen and has_projects) or self.colony.project_at(docked["system_address"], docked["market_id"]):
                return True
            if "squadronbank" in {str(item).casefold() for item in docked["services"]}:
                return True
        if self.config.get("colony_show_on_right_panel", True) and focus == _GUI_RIGHT_PANEL and has_projects:
            return True
        return False

    def _colony_update_overlay(self):
        hud = getattr(self, "colony_needs_hud", None)
        if hud is None or getattr(self, "colony", None) is None:
            return False
        try:
            model = self._colony_overlay_model()
        except Exception as exc:
            logging.warning("Construction Needs model failed: %s", exc)
            model = None
        if self._colony_overlay_wanted(model):
            return hud.update(model)
        return hud.clear()
