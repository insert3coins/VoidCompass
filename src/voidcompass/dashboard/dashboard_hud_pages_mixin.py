"""The Navigation HUD's pages (5.5.17): gathering each page's facts.

Every page is built from the same state the separate overlays read, so the
HUD can show them while those overlays stay off (overlays.hud_pages has
the pages themselves and the rules for which one shows).
"""

from __future__ import annotations

import logging
import time

from voidcompass.overlays import hud_pages
from voidcompass.overlays.hud_pages import pages_options

def page_label(page):
    return hud_pages.LABELS.get(str(page or "nav"), "NAV")


# The pages tip waits this long after starting, past the boot and the first jumps.
TIP_DELAY_S = 90.0
PAGES_TICK_MS = 500
PAGES_IDLE_MS = 1500
# The Planet Materials workspace reads the database: once a few seconds.
PLANET_DATA_S = 3.0
# Signals heard here, by name, on the Survey and Combat pages (5.6.1).
CONTACT_ROWS = 60


class DashboardHudPagesMixin:
    # -- what the journal tells only the pages ------------------------------------------
    def _hud_pages_observe(self, event, raw, startup_replay=False):
        """Your target in a fight, and the rock you last prospected."""
        if startup_replay or not isinstance(raw, dict):
            return
        if event == "ShipTargeted":
            before = getattr(self, "_hud_target", None)
            self._hud_target = hud_pages.read_target(raw, before)
            # The combat scene flies your target's own hull (5.6.9).
            if self._hud_target != before and callable(getattr(self, "update_hud", None)):
                self.update_hud()
        elif event in {"FSDJump", "SupercruiseEntry", "Docked", "Died", "LoadGame"}:
            self._hud_target = None
        elif event == "ProspectedAsteroid":
            self._hud_prospect = {"raw": raw, "at": time.monotonic(), "refined": {}}
        elif event == "MiningRefined" and not getattr(self, "current_in_srv", False):
            prospect = getattr(self, "_hud_prospect", None)
            if prospect:
                name = str(raw.get("Type_Localised") or raw.get("Type") or "").strip()
                prospect["refined"][name] = prospect["refined"].get(name, 0) + 1
                prospect["at"] = time.monotonic()

    # -- the takeover ---------------------------------------------------------------------
    def _hud_pages_covered(self):
        """The overlays the HUD shows instead, while its pages are on."""
        config = getattr(self, "config", None) or {}
        if not config.get("overlay_enabled", True):
            return set()
        return hud_pages.covered_overlays(config)

    def _hud_pages_apply_settings(self):
        """Pages on or off, or another page: the covered overlays follow."""
        self._apply_runtime_feature_toggles()
        self.ground_popup_enabled = self._overlay_enabled("ground_popup")
        if not self.ground_popup_enabled and getattr(self, "ground_popup", None) is not None:
            self._destroy_ground_popup()
        self._tick_hud_pages(reschedule=False)

    # -- the facts the page choice needs -------------------------------------------------
    def _hud_pages_facts(self):
        docked = bool(getattr(self, "current_docked", False))
        surface = bool(getattr(self, "on_planet", False)) and bool(
            getattr(self, "current_in_srv", False) or getattr(self, "current_on_foot", False)
            or getattr(self, "current_landed", False))
        prospect = getattr(self, "_hud_prospect", None)
        hold = float((getattr(self, "config", None) or {}).get("prospector_hud_timeout_s") or hud_pages.PROSPECT_HOLD_S)
        # Rigs out on this planet count from the ship or on foot too.
        place = self._rig_place() if getattr(self, "on_planet", False) else None
        rigs_here = bool(place and self.rig_store().rigs(place[0], place[1]))
        phase = str(getattr(self, "_navigation_jump_phase", "") or "")
        colony = False
        if docked and getattr(self, "colony", None) is not None:
            try:
                colony = bool(self._colony_overlay_wanted(self._colony_overlay_model()))
            except Exception:
                colony = False
        carrier = getattr(getattr(self, "carrier_tracker", None), "carrier_data", None) or {}
        own_carrier = bool(docked and carrier.get("carrier_id") is not None
                           and str(getattr(self, "current_station_market_id", "")) == str(carrier.get("carrier_id")))
        route = getattr(self, "trading_route", None)
        return {
            "docked": docked, "on_planet": surface, "in_rhino": self._rig_in_rhino(), "rigs_here": rigs_here,
            "at_colony": colony, "on_own_carrier": own_carrier,
            "prospecting": bool(prospect and time.monotonic() - prospect["at"] < hold),
            "target": bool(getattr(self, "_hud_target", None)),
            "trading": bool(route),
            "has_jump": phase in {"charging", "hyperspace"},
            "system": str(getattr(self, "current_sys", "") or ""),
            "expedition": self._hud_expedition_active(),
            "has_carrier": bool(carrier.get("name") or carrier.get("callsign")),
        }

    def _hud_pages_available(self, facts):
        """Pages with something to show now, for the page hotkey's round."""
        config = getattr(self, "config", None) or {}
        available = ["nav", "survey"]
        if facts["has_jump"]:
            available.append("jump")
        if facts["on_planet"] or getattr(self, "on_planet", False):
            available.append("planet")
        if facts["in_rhino"] or facts["rigs_here"]:
            available.append("rhino")
        if facts["prospecting"] or (getattr(self, "current_cargo_inventory", None) and not facts["docked"]):
            available.append("mining")
        session = (((getattr(getattr(self, "specialist_engine", None), "state", None) or {}).get("combat") or {})
                   .get("session") or {})
        if facts["target"] or session.get("active"):
            available.append("combat")
        if facts["docked"]:
            available.append("station")
        if facts["at_colony"]:
            available.append("colony")
        if facts["has_carrier"]:
            available.append("carrier")
        if facts["trading"]:
            available.append("trade")
        if facts.get("expedition"):
            available.append("expedition")
        if config.get("hud_page_powerplay", True):
            available.append("powerplay")
        return [page for page in hud_pages.PAGES if page in set(available)]

    # -- building a page ----------------------------------------------------------------------
    def _hud_page_build(self, page):
        builder = getattr(self, f"_hud_page_{page}", None)
        if not callable(builder):
            return None
        try:
            return builder()
        except Exception:
            logging.debug("HUD page %s skipped", page, exc_info=True)
            return None

    def _hud_page_jump(self):
        phase = str(getattr(self, "_navigation_jump_phase", "") or "") or "charging"
        return hud_pages.jump_page(self._jump_info_model(phase))

    def _hud_expedition_active(self):
        manager = getattr(self, "expedition_manager", None)
        try:
            return bool(manager is not None and (manager.active() or {}).get("status") == "active")
        except Exception:
            return False

    def _hud_survey_left(self):
        """Whether this system still has survey work in it: bodies left to
        scan, or biology not yet finished."""
        model = self._hud_survey_model() or {}
        total, scanned = int(model.get("total") or 0), int(model.get("scanned") or 0)
        if not model.get("total_known") or scanned < total:
            return True
        return any(row.get("bio_count") and not row.get("bio_complete") for row in model.get("rows") or ())

    def _hud_survey_model(self):
        from voidcompass.overlays.survey_status_hud import build_survey_model
        config = getattr(self, "config", None) or {}
        try:
            minimum = int(float(config.get("survey_min_body_value") or 50000))
        except (TypeError, ValueError):
            minimum = 50000
        return build_survey_model(
            getattr(self, "current_sys", ""), getattr(self, "scan_items", None) or [],
            getattr(self, "current_body_id", None), getattr(self, "current_body_name", None),
            self._sampling_snapshot(), getattr(self, "scanned", 0), getattr(self, "total", 0), minimum, None,
            bool(getattr(self, "scan_total_confirmed", False)), body_signals=getattr(self, "body_signals", None),
            belt_clusters=list(getattr(self, "belt_clusters", None) or ()), dss_stats=self._dss_efficiency_snapshot())

    def _hud_page_survey(self, limit=None):
        model = self._hud_survey_model()
        self._hud_rhino_hints(model)
        return hud_pages.survey_page(model, self._hud_contacts())

    def _hud_contacts(self):
        ledger = getattr(self, "contact_ledger", None)
        return ledger.model(max_rows=CONTACT_ROWS) if ledger is not None else None

    def _hud_hold_contents(self, *holds):
        """((title, cargo model), ...) for the pages' hold lists, or nothing
        with the Cargo switch off (Overlay Studio › Navigation HUD)."""
        from voidcompass.overlays.cargo_hud import build_cargo_model
        if not (getattr(self, "config", None) or {}).get("hud_hold_lists", True):
            return ()
        return tuple((title, build_cargo_model(inventory)) for title, inventory in holds if inventory)

    def _hud_rhino_hints(self, model):
        """Each body row's Rhino hint and mining sites, from the scans."""
        from voidcompass.mining.rhino_intelligence import rhino_hint
        scans = {}
        for item in getattr(self, "scan_items", None) or ():
            for name in (item.get("full_name"), item.get("name")):
                if name:
                    scans[str(name).casefold()] = item
        signals = {str((value or {}).get("body_name") or "").casefold(): value
                   for value in (getattr(self, "body_signals", None) or {}).values() if isinstance(value, dict)}
        for row in (model or {}).get("rows") or ():
            key = str(row.get("name") or row.get("display_name") or "").casefold()
            item = scans.get(key) or {}
            row["mining_count"] = int((signals.get(key) or {}).get("mining") or 0)
            if item.get("landable"):
                row["rhino"] = rhino_hint({"class": item.get("planet_class") or item.get("class"),
                                           "volcanism": item.get("volcanism"), "landable": True})
        return model

    def _hud_page_planet(self):
        from voidcompass.overlays.planet_materials_hud import build_planet_materials_model
        body = str(getattr(self, "current_body_name", "") or "")
        cached = getattr(self, "_hud_planet_cache", None)
        if not cached or cached[0] != body or time.monotonic() - cached[1] > PLANET_DATA_S:
            workspace = self._html_planet_materials_workspace()
            cached = self._hud_planet_cache = (body, time.monotonic(), workspace)
        materials = build_planet_materials_model(
            cached[2], latitude=getattr(self, "current_latitude", None), longitude=getattr(self, "current_longitude", None),
            heading=getattr(self, "current_heading", None), radius_m=getattr(self, "current_planet_radius", None),
            vehicle_name=getattr(self, "current_vehicle_name", ""))
        target = None
        if getattr(self, "target_latlon_active", False):
            target = self._ground_target_solution()
            if target:
                target["label"] = getattr(self, "ground_target_label", "") or "Target"
        config = getattr(self, "config", None) or {}
        gravity = getattr(getattr(self, "gravity_warning_hud", None), "_last_gravity", None)
        return hud_pages.planet_page(body, materials, target, self._sampling_snapshot(), gravity,
                                     float(config.get("gravity_warning_threshold_g") or 3.0))

    def _hud_page_rhino(self):
        from voidcompass.overlays.rig_tracker import rig_spacing_m, rig_warn_m
        place = self._rig_place()
        # Each hold the page has a bar for, and what's in it: the Rhino's
        # while you drive it, and the ship's as it was last seen.
        inventory = getattr(self, "current_cargo_inventory", None) or []
        if str(getattr(self, "current_cargo_vessel", "Ship") or "Ship").strip().casefold() == "srv":
            kept = (getattr(self, "_cargo_inventory_by_hold", None) or {}).get("Ship") or []
            contents = self._hud_hold_contents(("IN THE RHINO", inventory if self._rig_in_rhino() else []), ("IN THE SHIP", kept))
        else:
            contents = self._hud_hold_contents(("IN THE SHIP", inventory))
        return hud_pages.rhino_page(self._rig_model(), self._rig_holds(),
                                    self._surface_mining_signals(place[1]) if place else 0,
                                    rig_spacing_m(self.config), rig_warn_m(self.config), contents)

    def _hud_page_mining(self):
        from voidcompass.overlays.cargo_hud import build_cargo_model
        from voidcompass.overlays.prospector_hud import build_prospector_model
        prospect = getattr(self, "_hud_prospect", None)
        model = build_prospector_model(prospect["raw"], prospect["refined"]) if prospect else None
        inventory, capacity, vessel, owner = self._cargo_hold_snapshot()
        return hud_pages.mining_page(model, build_cargo_model(inventory, capacity, vessel, owner),
                                     self._hud_hold_contents(("IN THE HOLD", inventory)))

    def _hud_page_combat(self):
        engine = getattr(self, "specialist_engine", None)
        session = None
        if engine is not None and hasattr(engine, "combat_snapshot"):
            session = (engine.combat_snapshot() or {}).get("session")
        return hud_pages.combat_page(getattr(self, "_hud_target", None), session, self._hud_contacts())

    def _hud_page_station(self):
        from voidcompass.overlays.station_info_hud import build_station_model
        from voidcompass.trading import route as trade_route
        if not getattr(self, "current_docked", False):
            return None
        route = getattr(self, "trading_route", None)
        inventory = self._cargo_hold_snapshot()[0]
        return hud_pages.station_page(build_station_model(self), trade_route.next_step(route) if route else None,
                                      self._hud_hold_contents(("ABOARD", inventory)))

    def _hud_page_colony(self):
        if getattr(self, "colony", None) is None:
            return None
        return hud_pages.colony_page(self._colony_overlay_model())

    def _hud_page_carrier(self):
        from voidcompass.overlays.carrier_hud import build_carrier_hud_model
        carrier = getattr(getattr(self, "carrier_tracker", None), "carrier_data", None) or {}
        return hud_pages.carrier_page(build_carrier_hud_model(carrier) if carrier else None)

    def _hud_page_trade(self):
        from voidcompass.overlays.cargo_hud import build_cargo_model
        from voidcompass.trading import route as trade_route
        route = getattr(self, "trading_route", None)
        if not route:
            return None
        inventory, capacity, vessel, owner = self._cargo_hold_snapshot()
        return hud_pages.trade_page(trade_route.next_step(route), build_cargo_model(inventory, capacity, vessel, owner),
                                    self._hud_hold_contents(("IN THE HOLD", inventory)))

    def _hud_page_powerplay(self):
        from voidcompass.overlays.powerplay_hud import build_powerplay_overlay_model
        return hud_pages.powerplay_page(build_powerplay_overlay_model(self._html_powerplay_workspace()))

    # -- the page shown ---------------------------------------------------------------------------
    def _hud_pages_payload(self):
        config = getattr(self, "config", None) or {}
        options = pages_options(config)
        hud = getattr(self, "hud", None)
        if options["mode"] == "off" or hud is None:
            return None
        state = ((getattr(hud, "_html_last_model", None) or {}).get("state")) or {}
        facts = self._hud_pages_facts()
        auto = hud_pages.pick_page(state, facts, options["enabled"])
        # Nothing needs the screen: keep what you were doing (5.5.18).
        memory = getattr(self, "_hud_pages_memory", None)
        if memory is None:
            memory = self._hud_pages_memory = {}
        now = time.monotonic()
        hud_pages.remember_page(memory, auto, state, facts, now)
        auto = hud_pages.hold_page(auto, memory, facts, now, options["enabled"], self._hud_survey_left)
        manual = options["mode"] == "manual"
        active = (getattr(self, "_hud_pages_manual", None) or "nav") if manual else auto
        if active not in options["enabled"]:
            active = "nav"
        page = self._hud_page_build(active) if active != "nav" else None
        if page is None and active != "nav":
            # Nothing to show on that page right now: a note, never an empty panel.
            page = hud_pages.waiting_page(active) if manual else None
            active = active if manual else "nav"
        available = set(self._hud_pages_available(facts))
        # Every page switched on, in the order the page key goes round; the
        # ones with nothing on them now are only a dim pip.
        return {
            "active": active, "auto": auto, "mode": options["mode"], "alert": self._hud_pages_alert(active),
            "text_scale": hud_pages.page_text_percent(config) / 100.0,
            "tabs": [{"id": item, "label": hud_pages.LABELS[item], "empty": item not in available}
                     for item in options["enabled"]],
            "page": page,
        }

    def _hud_pages_alert(self, active):
        """A warning shown over whatever page is up (5.6.1), unless that page
        already shows it: heavy gravity on the way down, then the rigs."""
        gravity = None
        heavy = getattr(self, "_hud_heavy_body", None)
        flying = not any(getattr(self, name, False) for name in ("current_docked", "current_landed", "current_in_srv", "current_on_foot"))
        if (active != "planet" and heavy and flying and getattr(self, "current_body_id", None) is not None
                and str(getattr(self, "current_body_name", "") or "").casefold() == str(heavy[0]).casefold()):
            gravity = heavy
        rigs = None
        if active != "rhino" and getattr(self, "on_planet", False):
            from voidcompass.overlays.rig_tracker import rig_advice, rig_spacing_m, rig_warn_m
            try:
                model = self._rig_model()
            except Exception:
                model = None
            if model:
                rigs = rig_advice(model.get("slots"), rig_spacing_m(self.config), rig_warn_m(self.config))
        return hud_pages.alert_line(gravity, rigs)

    def _tick_hud_pages(self, reschedule=True):
        if not getattr(self, "is_running", True):
            return
        payload = None
        try:
            payload = self._hud_pages_payload()
            hud = getattr(self, "hud", None)
            if hud is not None and hasattr(hud, "set_pages"):
                hud.set_pages(payload)
        except Exception:
            logging.debug("HUD pages tick skipped", exc_info=True)
        self._hud_pages_tip()
        if reschedule:
            self.root.call_later(PAGES_TICK_MS if payload else PAGES_IDLE_MS, self._tick_hud_pages)

    def _hud_pages_tip(self):
        """Once per commander, a while after starting with the pages off:
        where to switch them on (they're off by default)."""
        config = getattr(self, "config", None) or {}
        if config.get("hud_pages_tip_shown") or pages_options(config)["mode"] != "off":
            return False
        started = getattr(self, "_hud_pages_tip_clock", None)
        if started is None:
            self._hud_pages_tip_clock = time.monotonic()
            return False
        toast = getattr(self, "toast_hud", None)
        if time.monotonic() - started < TIP_DELAY_S or toast is None or not hasattr(toast, "push"):
            return False
        toast.push("ONE OVERLAY FOR EVERYTHING", "The Navigation HUD can follow what you're doing: "
                   "Overlay Studio › Navigation HUD › Pages", severity="info", duration_s=12.0)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("SYSTEM", "Tip: the Navigation HUD's pages (Overlay Studio › Navigation HUD › Pages) can stand in for most overlays",
                 severity="INFO")
        config["hud_pages_tip_shown"] = True
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        return True

    # -- the page hotkeys -------------------------------------------------------------------------
    # Two keys: the page mode (follow what you're doing, or choose), and the
    # next page (which chooses, so it switches to choosing if need be).
    def _hud_pages_flash(self, text, detail="", tone="accent"):
        hud = getattr(self, "hud", None)
        if hud is not None and hasattr(hud, "flash"):
            hud.flash(text, detail, tone)

    def _hud_pages_set_mode(self, mode):
        self.config["hud_pages"] = mode
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        self._hud_pages_apply_settings()
        self._schedule_html_dashboard_publish(immediate=True)

    def _hud_page_now(self):
        payload = self._hud_pages_payload() or {}
        return page_label(payload.get("active"))

    def _hud_pages_mode_key(self):
        """Follow what you're doing, or choose: switching to choosing keeps the page you're on."""
        if getattr(self, "hud", None) is None:
            return False
        mode = pages_options(self.config)["mode"]
        if mode == "auto":
            self._hud_pages_manual = (self._hud_pages_payload() or {}).get("active") or "nav"
            self._hud_pages_set_mode("manual")
            self._hud_pages_flash("PAGES · MANUAL", f"{self._hud_page_now()} · NEXT PAGE KEY CHANGES IT", "yellow")
        else:
            self._hud_pages_set_mode("auto")
            self._hud_pages_flash("PAGES · AUTO", f"FOLLOWING YOU · {self._hud_page_now()}", "green")
        return True

    def _hud_page_next(self):
        if getattr(self, "hud", None) is None:
            return False
        options = pages_options(self.config)
        current = (self._hud_pages_payload() or {}).get("active") or "nav" if options["mode"] != "off" else "nav"
        # Every page you've switched on, not only those with something on them
        # now: a quiet one says what it's waiting for.
        self._hud_pages_manual = hud_pages.next_page(current, "nav", options["enabled"])
        if options["mode"] != "manual":
            self._hud_pages_set_mode("manual")
        else:
            self._tick_hud_pages(reschedule=False)
        self._hud_pages_flash(f"PAGE · {page_label(self._hud_pages_manual)}", "MANUAL", "yellow")
        return True
