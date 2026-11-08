"""Crew Orders (5.7.7): the deck's side of the officers' orders.

The ledger (orders/ledger.py) is kept per commander profile and fed every
journal event, live and in the startup catch-up alike. A five-second clock
looks after offers, reminders, campaign stages, Order Files and the
objectives that need time. Lines go through the companion's mind as crew
lines: said by the officer the order belongs to, in its own voice, or, when
that voice is off, passed on by the companion on watch.
"""

from __future__ import annotations

import logging
import math
import time

from voidcompass.core.discovery import our_first
from voidcompass.colonisation import catalogue as colony_catalogue
from voidcompass.core import companion_features, companions, crew_rota, home_anchor
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.exploration import codex_index as codex_module
from voidcompass.orders import campaigns, generators, pacing, places, ribbons
from voidcompass.orders import talk as orders_talk
from voidcompass.orders import objectives as objective_rules
from voidcompass.orders.ledger import STANDINGS, OrderLedger, current_target, epoch, objectives_of, progress, service_level, standing
from voidcompass.overlays import order_campaign_words, order_files, order_lines
from voidcompass.services import spansh

ORDERS_TICK_S = 5.0
BIO_REST_S = 30 * 60.0        # nearby biology is searched again after this long
BIO_MOVE_LY = 150.0           # or once we've moved this far
NEUTRON_REST_S = 6 * 3600.0
SALE_REST_S = 20 * 60.0
REMIND_AFTER_S = 8 * 60.0     # into a session before standing orders are mentioned
AFTER_DELAY_S = 3 * 3600.0    # a finished campaign is looked back on this long after
FILE_GAP_S = 45 * 60.0        # between two Order Files passages
WORTHY_WEIGHT = {"earthlike body": 5, "earth-like world": 5, "water world": 4, "ammonia world": 4}
ARRIVALS = {"FSDJump", "CarrierJump", "Location"}


def _fresh_place():
    return {"address": None, "system": "", "arrived_at": 0.0, "bodies": {}, "body_count": 0, "fss_done": False,
            "undiscovered": False, "bio_signals": 0}


class DashboardOrdersMixin:
    # -- setup -----------------------------------------------------------------
    def _orders_init(self, profile_key=None):
        key = profile_key or get_active_profile(self.config)
        self.order_ledger = OrderLedger(get_profile_file(key, "crew_orders.json"))
        self._orders_place = _fresh_place()
        self._orders_lookups = {}
        self._orders_reminded = None
        self._orders_why = "Waiting for the game"
        self._orders_home_far = None
        self._orders_regions = None
        self._orders_file_last = 0.0
        self._orders_generation = getattr(self, "_orders_generation", 0) + 1

    def _orders_switch_profile(self, profile_key):
        old = getattr(self, "order_ledger", None)
        if old is not None:
            old.flush()
        self._orders_init(profile_key)

    def _orders_close(self):
        ledger = getattr(self, "order_ledger", None)
        if ledger is not None:
            ledger.flush()

    def _orders_enabled(self):
        return bool(self.config.get("orders_enabled", True)) and getattr(self, "order_ledger", None) is not None

    def _orders_schedule(self):
        if getattr(self, "_orders_job", None) is not None:
            return
        call_later = getattr(getattr(self, "root", None), "call_later", None)
        if not callable(call_later):
            return

        def look():
            self._orders_job = None
            try:
                self._orders_tick()
            except Exception:
                logging.debug("Crew orders tick skipped", exc_info=True)
            # Crew banter shares this clock (dashboard_banter_mixin).
            if hasattr(self, "_banter_tick"):
                try:
                    self._banter_tick()
                except Exception:
                    logging.debug("Crew banter tick skipped", exc_info=True)
            if not getattr(self, "_closing", False):
                self._orders_schedule()

        try:
            self._orders_job = call_later(int(ORDERS_TICK_S * 1000), look)
        except Exception:
            self._orders_job = None

    # -- the journal ---------------------------------------------------------------
    def _orders_observe(self, event, raw, startup_replay=False):
        ledger = getattr(self, "order_ledger", None)
        if ledger is None or not isinstance(raw, dict):
            return
        event = str(event or raw.get("event") or "")
        try:
            self._orders_note_place(event, raw)
        except Exception:
            logging.debug("Crew orders place note skipped", exc_info=True)
        try:
            changes = ledger.observe(dict(raw, event=event), self._orders_ctx())
        except Exception:
            logging.debug("Crew orders event skipped [%s]", event, exc_info=True)
            return
        if changes:
            self._orders_react(changes, replay=startup_replay)

    def _orders_note_place(self, event, raw):
        place = self._orders_place
        if event in ARRIVALS:
            address = raw.get("SystemAddress")
            if address != place.get("address"):
                self._orders_place = place = _fresh_place()
                place["arrived_at"] = epoch(raw.get("timestamp"), time.time())
            place.update(address=address, system=raw.get("StarSystem") or place["system"])
            if self._orders_regions is not None and raw.get("StarPos"):
                region = places.region_of(raw["StarPos"])[0]
                if region:
                    self._orders_regions.add(region)
            far = self._orders_home_far
            home = home_anchor.home(self.config).get("pos")
            if far is not None and home and raw.get("StarPos"):
                gap = places.distance(home, raw["StarPos"])
                if gap:
                    self._orders_home_far = max(far, gap)
            return
        if raw.get("SystemAddress") is not None and place.get("address") is not None and raw["SystemAddress"] != place["address"]:
            return
        if event == "Scan" and raw.get("BodyName"):
            name = str(raw["BodyName"])
            row = place["bodies"].setdefault(name.casefold(), {"name": name})
            kind = str(raw.get("PlanetClass") or raw.get("StarType") or "")
            row.update(type=kind, terraformable=str(raw.get("TerraformState") or "").casefold() == "terraformable",
                       discovered=raw.get("WasDiscovered"), footfalled=raw.get("WasFootfalled"),
                       landable=bool(raw.get("Landable")))
            row["mapped"] = bool(row.get("mapped") or raw.get("WasMapped"))
            # Mapped by someone before you (the Scan's own word): no first map to be had.
            row["mapped_before"] = raw.get("WasMapped") is True
            row["value"] = WORTHY_WEIGHT.get(kind.casefold(), 3 if row["terraformable"] else 0)
            if raw.get("StarType") and float(raw.get("DistanceFromArrivalLS") or 0) == 0 and our_first(raw):
                place["undiscovered"] = True
        elif event == "SAAScanComplete" and raw.get("BodyName"):
            place["bodies"].setdefault(str(raw["BodyName"]).casefold(), {"name": raw["BodyName"]})["mapped"] = True
        elif event == "FSSDiscoveryScan":
            place["body_count"] = int(raw.get("BodyCount") or 0)
            if raw.get("SystemName"):
                place["system"] = raw["SystemName"]
        elif event == "FSSAllBodiesFound":
            place["fss_done"] = True
        elif event in {"FSSBodySignals", "SAASignalsFound"}:
            bio = sum(int(row.get("Count") or 0) for row in raw.get("Signals") or ()
                      if isinstance(row, dict) and "biological" in str(row.get("Type") or "").casefold())
            if bio:
                key = f"bio:{raw.get('BodyID')}"
                place.setdefault("bio_bodies", {})[key] = bio
                place["bio_signals"] = sum(place["bio_bodies"].values())

    def _orders_ctx(self):
        place = self._orders_place
        coords = getattr(self, "current_coords", None)
        region = places.region_of(coords)[0] if coords and list(coords) != [0, 0, 0] else None
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        return {"system": place.get("system") or getattr(self, "current_sys", ""),
                "address": place.get("address") if place.get("address") is not None else getattr(self, "current_system_address", None),
                "region_id": region, "bodies": place["bodies"], "star_class": getattr(self, "star_class", "") or "",
                "undiscovered": place.get("undiscovered") or bool(getattr(self, "system_undiscovered", False)),
                "arrived_at": place.get("arrived_at"), "in_danger": bool(getattr(mind, "_in_danger", False))}

    # -- the clock --------------------------------------------------------------------
    def _orders_tick(self, now=None):
        if not self._orders_enabled():
            return
        now = time.time() if now is None else now
        ledger = self.order_ledger
        changes = ledger.tick(self._orders_ctx(), now)
        if changes:
            self._orders_react(changes)
        changed = bool(changes)
        changed |= self._orders_build_stages(now)
        changed |= self._orders_remind(now)
        changed |= self._orders_tell_file(now)
        changed |= self._orders_tell_after(now)
        pending = getattr(self, "_orders_ask_pending", None)
        if pending and not any(key.endswith("_busy") for key in self._orders_lookups):
            self._orders_ask_pending = None
            if now - pending < 60 and not self.order_ledger.offered():
                found = self._orders_maybe_offer(now, force=True)
                self._orders_notice = {"text": "The crew has an order for you." if found else "Nobody has anything for you right now.",
                                       "ok": found, "at": now}
                changed = True
        changed |= self._orders_maybe_offer(now)
        try:
            self._orders_update_overlay(only_if_changed=True)
        except Exception:
            logging.debug("Crew Orders overlay refresh skipped", exc_info=True)
        notice = getattr(self, "_orders_notice", None)
        if notice and now - float(notice.get("at") or 0) > 8:
            self._orders_notice = None
            changed = True
        if changed:
            self._orders_publish()

    def _orders_mind(self):
        return getattr(getattr(self, "heartbeat_hud", None), "mind", None)

    def _orders_session(self):
        mind = self._orders_mind()
        return getattr(mind, "_session_start", None)

    def _orders_pacing_facts(self, now):
        mind = self._orders_mind()
        flags = int(getattr(self, "current_status_flags", 0) or 0)
        # FSD charging (bit 17), in witch space (bit 30): no offers.
        jumping = bool(flags & (1 << 17)) or bool(flags & (1 << 30))
        focus = getattr(self, "current_gui_focus", 0) or 0
        return {"session_start": self._orders_session(), "in_danger": bool(getattr(mind, "_in_danger", False)),
                "jumping": jumping, "gui_focus": focus if focus not in (0, None) else 0,
                "arrived_at": self._orders_place.get("arrived_at") or 0, "last_spoke": getattr(mind, "_last_spoke", 0) or 0,
                "offered_open": bool(self.order_ledger.offered() and not all(row.get("later") for row in self.order_ledger.offered()))}

    # -- facts for the generators --------------------------------------------------------
    def _orders_categories(self):
        return tuple(name for name in generators.DEFAULT_CATEGORIES if self.config.get(f"orders_kind_{name}", True) is not False)

    def _orders_visited(self):
        history = getattr(self, "travel_history", None)
        if history is None:
            return lambda name: False
        return lambda name: history.recall(name) is not None

    def _orders_visited_regions(self):
        if self._orders_regions is None:
            history = getattr(self, "travel_history", None)
            cells = set()
            for row in list(getattr(history, "rows", ()) or ()):
                try:
                    cells.add((round(float(row[2]) / 200), round(float(row[4]) / 200)))
                except (TypeError, ValueError, IndexError):
                    continue
            regions = set()
            for cx, cz in cells:
                found = places.region_of((cx * 200.0, 0.0, cz * 200.0))[0]
                if found:
                    regions.add(found)
            self._orders_regions = regions
        return self._orders_regions

    def _orders_far_from_home(self, home):
        if self._orders_home_far is None:
            far = 0.0
            if home:
                for row in list(getattr(getattr(self, "travel_history", None), "rows", ()) or ()):
                    try:
                        far = max(far, math.dist(home, (float(row[2]), float(row[3]), float(row[4]))))
                    except (TypeError, ValueError, IndexError):
                        continue
            self._orders_home_far = far
        return self._orders_home_far

    def _orders_codex(self):
        index = getattr(self, "codex_index", None)
        names = getattr(self, "_orders_codex_names", None)
        if names is None:
            names = {}
            for key, (english, category) in codex_module.reference().items():
                if english:
                    names[english.casefold()] = key
            self._orders_codex_names = names
        flag = (lambda entry, region: index.entry_flag(entry, region)) if index is not None else None
        return flag, (lambda english: names.get(str(english or "").casefold()))

    def _orders_facts(self, now):
        coords = getattr(self, "current_coords", None)
        if not coords or list(coords) == [0, 0, 0]:
            coords = None
        home = home_anchor.home(self.config)
        try:
            home_ly = home_anchor.distance(coords, self.config) if coords else None
        except Exception:
            home_ly = None
        region_id, region = places.region_of(coords) if coords else (None, "")
        place = self._orders_place
        state = getattr(self, "companion_state", {}) or {}
        flag, keyof = self._orders_codex()
        visited = self._orders_visited()
        route = self._orders_route()
        facts = {
            "now": now, "system": place.get("system") or getattr(self, "current_sys", ""),
            "address": self._orders_ctx()["address"], "coords": coords, "region_id": region_id, "region": region,
            "home": home, "home_ly": home_ly, "jump_range": self._expedition_jump_range() if hasattr(self, "_expedition_jump_range") else None,
            "docked": bool(getattr(self, "current_docked", False)),
            "unsold_bio": int(companion_features.unsold_bio_value(state) or 0),
            "unsold_carto": int(state.get("unsold_exploration_cr") or 0),
            "rebuy": int((getattr(self, "cmdr_ship", {}) or {}).get("rebuy") or 0),
            "codex_flag": flag, "codex_key": keyof, "visited": visited,
            "system_bodies": list(place["bodies"].values()), "undiscovered_here": bool(place.get("undiscovered")),
            "body_count": 0 if place.get("fss_done") else int(place.get("body_count") or 0),
            "bodies_found": sum(1 for row in place["bodies"].values() if row.get("type") and "belt" not in str(row.get("name", "")).casefold()),
            "bio_signals_here": int(place.get("bio_signals") or 0),
            "cargo_capacity": self._active_cargo_capacity() if hasattr(self, "_active_cargo_capacity") else 0,
            "route": route, "power": self._orders_power(),
        }
        # 5.7.7: a busy system (more than five visits a year) isn't one to ask you to survey.
        if hasattr(self, "_system_quiet"):
            facts["system_quiet"] = self._system_quiet(facts["system"])
        if home.get("pos") and home_ly is not None:
            facts["record_far_ly"] = self._orders_far_from_home(home["pos"])
        if coords:
            cached = getattr(self, "_orders_region_cache", None)
            visited = self._orders_visited_regions()
            if cached is None or cached[1] != len(visited) or (places.distance(cached[0], coords) or 0) > 50:
                cached = (list(coords), len(visited), places.nearest_unvisited_region(coords, visited, max_ly=3000))
                self._orders_region_cache = cached
            facts["nearest_region"] = cached[2]
        try:
            facts["trades"] = int(self.trading_store.query("SELECT COUNT(*) FROM trades WHERE kind='sell'")[0][0])
        except Exception:
            facts["trades"] = 0
        bio = self._orders_lookups.get("bio")
        if bio and bio.get("rows"):
            facts["bio_nearby"], facts["bio_at"] = bio["rows"], bio["at"]
        neutron = self._orders_lookups.get("neutron")
        if neutron and route and neutron.get("key") == str(route.get("destination") or "").casefold():
            facts["neutron"], facts["neutron_at"] = neutron.get("value") or {}, neutron["at"]
        sale = self._orders_lookups.get("sale")
        if sale and sale.get("value"):
            facts["sale"] = sale["value"]
        colony = self._orders_colony()
        if colony:
            facts["colony"] = colony
        return facts

    def _orders_route(self):
        entries = list(getattr(self, "nav_route_entries", None) or ())
        if len(entries) < 2:
            return None
        last = entries[-1] if isinstance(entries[-1], dict) else {}
        destination = last.get("StarSystem") or last.get("system")
        if not destination:
            return None
        here = str(getattr(self, "current_sys", "") or "").casefold()
        left = len(entries) - 1
        for index, row in enumerate(entries):
            if isinstance(row, dict) and str(row.get("StarSystem") or row.get("system") or "").casefold() == here:
                left = len(entries) - 1 - index
        pos = last.get("StarPos") or last.get("coords")
        return {"destination": destination, "jumps": left, "coords": list(pos) if pos else None}

    def _orders_power(self):
        state = (getattr(self, "companion_state", {}) or {}).get("powerplay") or {}
        return str(state.get("power") or "") if isinstance(state, dict) and state.get("pledged") else ""

    def _orders_colony(self):
        colony = getattr(self, "colony", None)
        if colony is None:
            return None
        try:
            projects = colony.visible_projects()
        except Exception:
            return None
        here = getattr(self, "current_system_address", None)
        projects = sorted(projects, key=lambda row: 0 if str(row.get("systemAddress")) == str(here) else 1)
        for project in projects:
            needs = [{"symbol": key, "name": colony_catalogue.commodity_name(key),
                      "left": int(value or 0)} for key, value in (project.get("commodities") or {}).items() if int(value or 0) > 0]
            if needs and project.get("marketId") is not None:
                return {"site": project.get("buildName") or "the construction site", "system": project.get("systemName") or "",
                        "market_id": project["marketId"], "needs": needs}
        return None

    # -- searches (Spansh, through the Trading page's gate) ---------------------------------
    def _orders_refresh_lookups(self, facts, now):
        if not hasattr(self, "_trading_task") or not self._trading_online():
            return
        system = facts.get("system")
        if not system:
            return
        generation = self._orders_generation
        bio = self._orders_lookups.get("bio")
        moved = bio is None or not bio.get("coords") or not facts.get("coords") or (
            (places.distance(bio["coords"], facts["coords"]) or 0) > BIO_MOVE_LY)
        if "exobiology" in self._orders_categories() and (bio is None or moved or now - bio["at"] > BIO_REST_S) \
                and not self._orders_lookups.get("bio_busy"):
            self._orders_lookups["bio_busy"] = True
            coords = facts.get("coords")

            def bio_done(result, error):
                if generation != self._orders_generation:
                    return
                self._orders_lookups.pop("bio_busy", None)
                self._orders_lookups["bio"] = {"at": time.time(), "rows": result or [], "coords": coords, "error": error}
            self._trading_task("orders-bio", lambda: spansh.bio_landmarks(system, 500, 80), bio_done)
        route = facts.get("route")
        jump_range = facts.get("jump_range")
        if route and int(route.get("jumps") or 0) >= 15 and jump_range and "travel" in self._orders_categories():
            key = str(route["destination"]).casefold()
            known = self._orders_lookups.get("neutron")
            if (known is None or known.get("key") != key or now - known["at"] > NEUTRON_REST_S) and not self._orders_lookups.get("neutron_busy"):
                self._orders_lookups["neutron_busy"] = True

                def neutron_done(result, error):
                    if generation != self._orders_generation:
                        return
                    self._orders_lookups.pop("neutron_busy", None)
                    value = dict(result or {})
                    waypoints = value.get("waypoints") or []
                    if len(waypoints) > 1:
                        value["first"] = waypoints[1].get("system")
                    self._orders_lookups["neutron"] = {"at": time.time(), "key": key, "value": value if not error else {}}
                destination = route["destination"]
                self._trading_task("orders-neutron", lambda: spansh.neutron_route(system, destination, jump_range), neutron_done)
        if "trade" in self._orders_categories():
            self._orders_sale_lookup(system, now, generation)

    def _orders_sale_lookup(self, system, now, generation):
        known = self._orders_lookups.get("sale")
        if (known and now - known["at"] < SALE_REST_S) or self._orders_lookups.get("sale_busy"):
            return
        try:
            held = [row for row in self._trading_cargo() if row["count"] > 0 and not row.get("stolen")
                    and row["symbol"] not in {"drones", "limpet"}]
        except Exception:
            held = []
        if not held:
            self._orders_lookups["sale"] = {"at": now, "value": None}
            return
        best = held[0]
        try:
            rows = self.trading_store.query("SELECT price FROM trades WHERE kind='sell' AND commodity=? ORDER BY ts DESC LIMIT 1",
                                            (best["symbol"],))
            last = int(rows[0][0]) if rows else 0
        except Exception:
            last = 0
        if not last:
            self._orders_lookups["sale"] = {"at": now, "value": None}
            return
        self._orders_lookups["sale_busy"] = True
        options = self._trading_cargo_options()
        from voidcompass.trading import market as trade_market

        def work():
            self._trading_spansh_names()
            name = self.trading_names.spansh_name(best["symbol"])
            choice = {"large_pad": options["large"], "carriers": options["carriers"], "planetary": options["planetary"]}
            rows = trade_market.parse_commodity(spansh.commodity_stations(
                "sell", system, name, best["count"], size=5, sort="price", radius=options["radius"], max_age_days=2, **choice),
                name, "sell")
            rows.sort(key=lambda row: -row["price"])
            return rows[0] if rows else None

        def done(result, error):
            if generation != self._orders_generation:
                return
            self._orders_lookups.pop("sale_busy", None)
            value = None
            if result and not error:
                value = {"commodity": best["symbol"], "name": best["name"], "count": best["count"], "price": result["price"],
                         "last_price": last, "station": result.get("station"), "system": result.get("system"),
                         "market_id": result.get("market_id"), "distance": result.get("distance"), "updated": result.get("updated")}
            self._orders_lookups["sale"] = {"at": time.time(), "value": value}
        self._trading_task("orders-sale", work, done)

    # -- offering ---------------------------------------------------------------------------
    def _orders_maybe_offer(self, now, force=False):
        ledger = self.order_ledger
        session = self._orders_session()
        if not force:
            allowed, why = pacing.may_offer(self._orders_pacing_facts(now), ledger.offers(), now, self.config, session)
            self._orders_why = why
            if not allowed:
                return False
            # Nothing found last time: look again in a minute, or as soon as we arrive somewhere new.
            retry = getattr(self, "_orders_retry", None)
            if retry and now < retry[0] and retry[1] == self._orders_place.get("address"):
                return False
        facts = self._orders_facts(now)
        self._orders_refresh_lookups(facts, now)
        on_watch = companions.identity(self.config)
        duty = None
        try:
            duty = crew_rota.duty_of(self._crew_rota_facts())
        except Exception:
            pass
        fresh = lambda key: ledger.may_offer_key(key, now, repeatable=str(key).startswith(("campaign:", "cashbio:", "cashcarto:", "disc:", "merits:")))
        drafts = generators.candidates(facts, categories=self._orders_categories(), watcher=self.config.get("orders_watcher", True),
                                       muted=ledger.is_muted, fresh=fresh, on_watch=on_watch, duty=duty)
        if self.config.get("orders_campaigns", True) and ledger.campaign() is None:
            for row in campaigns.candidates(facts, categories=self._orders_categories(), watcher=self.config.get("orders_watcher", True),
                                            fresh=fresh, last_ended=ledger.last_campaign_ended(), now=now):
                if row["officer"] == on_watch:
                    row["score"] += 25
                drafts.append(row)
        full = len(ledger.active_field()) >= 3
        drafts = [row for row in drafts if not (row["size"] == "field" and full)
                  and not (row["size"] == "long" and ledger.long_order())]
        if not drafts:
            self._orders_why = "Nothing worth offering right now"
            busy = any(key.endswith("_busy") for key in self._orders_lookups)
            self._orders_retry = (now + (10 if busy else 60), self._orders_place.get("address"))
            return False
        self._orders_retry = None
        drafts.sort(key=lambda row: -row["score"])
        order = ledger.offer(drafts[0], now, session)
        self._orders_why = ""
        self._orders_announce(order)
        return True

    def _orders_offer_swap(self, lost):
        """Overtaken: the same officer offers the next best target, if there is one."""
        ledger = self.order_ledger
        if ledger.offered():
            return False
        now = time.time()
        facts = self._orders_facts(now)
        fresh = lambda key: key != lost.get("key") and ledger.may_offer_key(key, now)
        drafts = [row for row in generators.candidates(facts, categories=self._orders_categories(),
                                                       watcher=self.config.get("orders_watcher", True),
                                                       muted=ledger.is_muted, fresh=fresh)
                  if row["officer"] == lost.get("officer") and row["size"] == "field"]
        if not drafts:
            return False
        order = ledger.offer(drafts[0], now, self._orders_session())
        self._orders_announce(order)
        return True

    def _orders_ask(self):
        """You asked for orders (the deck's button, or TALK): the crew looks now."""
        if not self._orders_enabled():
            return {"ok": False, "message": "Crew orders are off. Turn them on in Settings."}
        if self.order_ledger.offered():
            return {"ok": True, "message": "An order is already waiting for your answer."}
        if self._orders_maybe_offer(time.time(), force=True):
            return {"ok": True, "message": "The crew has an order for you."}
        if any(key.endswith("_busy") for key in self._orders_lookups):
            # The searches are still out: the clock tries again when they're back.
            self._orders_ask_pending = time.time()
            return {"ok": True, "message": "The crew is looking. An order will be on the board in a moment if they find one."}
        return {"ok": False, "message": "Nobody has anything for you right now. Try again somewhere new."}

    # -- what the crew says --------------------------------------------------------------------
    def _orders_fields(self, order, extra=None):
        fields = dict(order.get("fields") or {})
        fields.setdefault("title", order.get("title"))
        fields["count"] = fields.get("count") or len(self.order_ledger.active())
        what = generators.KINDS.get(order.get("kind"), (None, None, "orders like that"))[2]
        fields.setdefault("what", what)
        if extra:
            fields.update(extra)
        return fields

    def _orders_card(self, order):
        return {"id": order.get("id"), "title": order.get("title"), "kind": order.get("kind"), "officer": order.get("officer"),
                "status": order.get("status"), "size": order.get("size", "field")}

    def _orders_say(self, speaker, topic, fields, order=None, kind="news", delay=0.0, text=None):
        """One line, by ``speaker``. When that officer is off watch and its
        voice is off, the companion on watch passes it on, if it can speak."""
        mind = self._orders_mind()
        memory = self.order_ledger.line_memory()
        text = text or order_lines.pick(speaker, topic, fields, self.config, memory)
        if not text:
            return None
        if order is not None:
            order["last_line"] = {"speaker": speaker, "text": text, "at": time.time()}
        if mind is None or not hasattr(mind, "order_line"):
            return text
        say_as, words, heading = speaker, text, order_lines.heading(speaker, topic)
        on_watch = companions.identity(self.config)
        if speaker != on_watch and not self._orders_voice(speaker) and self._orders_voice(on_watch):
            relay = {"offer": "relay_offer", "done": "relay_done"}.get(kind, "relay_news")
            relayed = order_lines.pick(on_watch, relay, {"officer": order_lines.NAMES.get(speaker, speaker),
                                                         "title": fields.get("title") or ""}, self.config, memory)
            if relayed:
                say_as, words = on_watch, relayed
        try:
            mind.order_line(say_as, words, heading=heading, order=self._orders_card(order) if order else None, delay=delay)
        except Exception:
            logging.debug("Order line not queued", exc_info=True)
        self._orders_toast(order, speaker, text, topic)
        return text

    def _orders_voice(self, identity):
        try:
            if identity == companions.identity(self.config):
                return bool(self._watcher_voice_on())
            return bool(self._crewmate_voice_on(identity))
        except Exception:
            return False

    def _orders_toast(self, order, speaker, text, topic):
        """With thoughts switched off, an offer or a finished order still
        shows as a toast."""
        if order is None or topic not in {"done"} and not topic.startswith("offer_"):
            return
        if str(self.config.get("heartbeat_thoughts") or "rare").casefold() != "off" or not hasattr(self, "_toast_on_main"):
            return
        title = "NEW ORDER" if topic.startswith("offer_") else "ORDER COMPLETE"
        try:
            self._toast_on_main(title, f"{order_lines.NAMES.get(speaker, speaker)}: {text}", duration=14)
        except Exception:
            pass

    def _orders_scene(self, lines, fields, order, heading):
        """A campaign scene: a line from each officer in turn, in their own voices."""
        mind = self._orders_mind()
        said = []
        for speaker, line in lines:
            try:
                words = line.format(**{key: value for key, value in fields.items() if value is not None})
            except (KeyError, IndexError, ValueError):
                continue
            said.append({"speaker": speaker, "text": words})
            if mind is not None and hasattr(mind, "order_line"):
                try:
                    mind.order_line(speaker, words, heading=heading, order=self._orders_card(order), converse=True)
                except Exception:
                    logging.debug("Scene line not queued", exc_info=True)
        if said:
            order.setdefault("scenes", []).append({"at": time.time(), "lines": said})
            del order["scenes"][:-6]
        return said

    def _orders_offer_topic(self, order):
        if order.get("kind") == "errand":
            return f"offer_errand_{(order.get('fields') or {}).get('errand')}"
        return f"offer_{order.get('kind')}"

    def _orders_announce(self, order):
        owner = order.get("officer")
        on_watch = companions.identity(self.config)
        fields = self._orders_fields(order)
        if order.get("size") == "campaign":
            words = order_campaign_words.CAMPAIGNS.get(order.get("campaign"), {}).get("offer", {})
            lines = words.get(order_lines.style(owner, self.config)) or next(iter(words.values()), ())
            text = None
            if lines:
                import random
                for line in random.sample(list(lines), len(lines)):
                    try:
                        text = line.format(**fields)
                        break
                    except (KeyError, IndexError, ValueError):
                        continue
            if owner != on_watch and self._orders_voice(owner):
                self._orders_say(on_watch, "floor", {"officer": order_lines.NAMES.get(owner, owner)})
            self._orders_say(owner, "offer_campaign", fields, order=order, kind="offer", text=text or order.get("brief"))
            return
        if owner != on_watch and self._orders_voice(owner):
            self._orders_say(on_watch, "floor", {"officer": order_lines.NAMES.get(owner, owner)})
        topic = self._orders_offer_topic(order)
        if not self._orders_say(owner, topic, fields, order=order, kind="offer"):
            self._orders_say(owner, "offer_errand" if order.get("kind") == "errand" else topic, fields, order=order,
                             kind="offer", text=order.get("brief"))

    # -- reactions -------------------------------------------------------------------------------
    def _orders_react(self, changes, replay=False):
        ledger = self.order_ledger
        finished = False
        for change in changes:
            kind, order = change["type"], change["order"]
            stages = order.get("stages") or []
            stage = stages[int(order.get("stage") or 0)] if stages and 0 <= int(order.get("stage") or 0) < len(stages) else None
            owner = (stage or {}).get("officer") or order.get("officer")
            fields = self._orders_fields(order)
            if kind == "progress":
                continue
            if kind == "step" and not replay:
                left = sum(1 for row in objectives_of(order) if not objective_rules.done(row))
                self._orders_say(owner, "step", dict(fields, step=change["objective"].get("label"), left=left), order=order)
            elif kind == "halfway" and not replay:
                self._orders_say(owner, "halfway", fields, order=order)
            elif kind == "stage":
                self._orders_start_stage(order)
            elif kind == "done":
                finished = True
                self._orders_finished(order)
            elif kind == "overtaken":
                self._orders_say(order.get("officer"), "overtaken", dict(fields, body=change.get("body") or ""), order=order)
                if not replay:
                    self._orders_offer_swap(order)
            elif kind == "paused" and not replay:
                self._orders_say(order.get("officer"), "paused", fields, order=order)
            elif kind == "lapsed" and not replay:
                self._orders_say(order.get("officer"), "lapsed", fields, order=order)
        if finished:
            self._orders_awards()
        self._orders_publish()

    def _orders_start_stage(self, order):
        built = self._orders_build_stage(order)
        stage = order["stages"][int(order.get("stage") or 0)]
        words = order_campaign_words.CAMPAIGNS.get(order.get("campaign"), {}).get("stages", {}).get(stage["key"])
        fields = self._orders_fields(order, {"title": stage.get("title"), "campaign": order.get("title")})
        if words:
            speaker, line = words
            try:
                self._orders_say(speaker, "stage", fields, order=order, text=line.format(**fields))
                return built
            except (KeyError, IndexError, ValueError):
                pass
        self._orders_say(stage.get("officer") or order.get("officer"), "stage", fields, order=order)
        return built

    def _orders_build_stage(self, order, facts=None):
        """Fill the campaign's current stage, if it can be filled now."""
        stages = order.get("stages") or []
        index = int(order.get("stage") or 0)
        if not (0 <= index < len(stages)) or stages[index].get("built") or stages[index].get("choice"):
            return False
        objectives = campaigns.build_stage(order, facts or self._orders_facts(time.time()))
        if not objectives:
            if not stages[index].get("waiting_said"):
                stages[index]["waiting_said"] = time.time()
                self._orders_say(stages[index].get("officer") or order.get("officer"), "waiting",
                                 self._orders_fields(order, {"title": order.get("title")}), order=order)
            return False
        self.order_ledger.set_stage_objectives(order["id"], objectives)
        return True

    def _orders_build_stages(self, now):
        campaign = self.order_ledger.campaign()
        if campaign is None:
            return False
        stages = campaign.get("stages") or []
        index = int(campaign.get("stage") or 0)
        if not (0 <= index < len(stages)) or stages[index].get("built") or stages[index].get("choice"):
            return False
        last = float(stages[index].get("tried") or 0)
        if now - last < 60:
            return False
        stages[index]["tried"] = now
        facts = self._orders_facts(now)
        self._orders_refresh_lookups(facts, now)
        return self._orders_build_stage(campaign, facts)

    def _orders_finished(self, order):
        fields = self._orders_fields(order)
        if order.get("size") == "campaign":
            closing = order_campaign_words.CAMPAIGNS.get(order.get("campaign"), {}).get("closing", ())
            self._orders_scene(closing, fields, order, f"CAMPAIGN · {str(order.get('title') or '').upper()}")
            if order.get("campaign") in order_campaign_words.AFTER:
                self.order_ledger.schedule_after(order["campaign"], time.time() + AFTER_DELAY_S)
        else:
            self._orders_say(order.get("officer"), "done", fields, order=order, kind="done")
        before = order.get("standing_before")
        record = self.order_ledger.record(order.get("officer"))
        now_standing = standing(int(record.get("done") or 0))
        if before is not None and now_standing != before:
            self._orders_say(order.get("officer"), "standing", {"standing": now_standing}, delay=4.0)
        self._orders_note_elsewhere(order)
        if hasattr(self, "_banter"):
            self._banter("order_done", {"title": order.get("title")})

    def _orders_note_elsewhere(self, order):
        """A finished order is a moment: the Captain's Log and the Flight Recorder keep it."""
        log = getattr(self, "captains_log", None)
        if log is not None and hasattr(log, "add_manual_highlight"):
            try:
                log.add_manual_highlight("ORDER", f"Order complete: {order.get('title')}",
                                         f"For {order_lines.NAMES.get(order.get('officer'), 'the crew')}")
            except Exception:
                logging.debug("Captain's Log order note skipped", exc_info=True)

    def _orders_awards(self):
        ledger = self.order_ledger
        for ribbon_id in sorted(ribbons.earned(ledger.data)):
            if ledger.award(ribbon_id):
                name, reason = ribbons.RIBBONS.get(ribbon_id, (ribbon_id, ""))
                speaker = next((officer for officer in order_lines.SPEAKERS if ribbon_id.endswith(officer)), None) \
                    or companions.identity(self.config)
                self._orders_say(speaker, "ribbon", {"ribbon": name}, delay=6.0)
                self._orders_ribbon_popup(name, reason)
                self._orders_unlock_theme(ribbon_id)

    def _orders_unlock_theme(self, ribbon_id):
        """A commendation's postcard theme joins your own (an unlock, 5.7.7)."""
        from voidcompass.overlays import postcard_themes
        preset = ribbons.POSTCARD_THEMES.get(ribbon_id)
        if not preset:
            return False
        name, params = preset
        themes = self.config.get("postcard_themes")
        themes = dict(themes) if isinstance(themes, dict) else {}
        if name in themes or len(themes) >= postcard_themes.THEMES_MAX:
            return False
        themes[name] = postcard_themes.normalize(params)
        self.config["postcard_themes"] = themes
        if hasattr(self, "_persist_config"):
            try:
                self._persist_config()
            except Exception:
                logging.debug("Postcard theme unlock not saved", exc_info=True)
        self._orders_notice = {"text": f"New postcard theme: {name}", "ok": True, "at": time.time()}
        return True

    def _orders_ribbon_popup(self, name, reason):
        """A commendation pops up where achievements do."""
        hud = getattr(self, "achievement_hud", None)
        if hud is None or not hasattr(hud, "push"):
            return

        def show():
            try:
                hud.push(name, reason, severity="success", duration_s=15, icon="⚑", kind="achievement",
                         meta={"points": 0, "category": "Crew Orders", "description": reason})
            except Exception:
                logging.debug("Commendation popup skipped", exc_info=True)
        if hasattr(self, "_ui_post"):
            self._ui_post(show)
        else:
            show()

    def _orders_remind(self, now):
        session = self._orders_session()
        if not session or self._orders_reminded == session or now - float(session) < REMIND_AFTER_S:
            return False
        self._orders_reminded = session
        active = self.order_ledger.active()
        if not active:
            return False
        oldest = min(active, key=lambda row: float(row.get("accepted_at") or 0))
        self._orders_say(oldest.get("officer"), "reminder", self._orders_fields(oldest, {"count": len(active)}), order=oldest)
        return True

    def _orders_tell_file(self, now):
        mind = self._orders_mind()
        session = self._orders_session()
        if not session or now - float(session) < REMIND_AFTER_S or now - self._orders_file_last < FILE_GAP_S:
            return False
        if getattr(mind, "_in_danger", False):
            return False
        for officer in order_lines.SPEAKERS:
            done = int(self.order_ledger.record(officer).get("done") or 0)
            passage = order_files.due(officer, done, self.order_ledger.files_told(officer))
            if passage is None:
                continue
            passage_id, number, text = passage
            if self.order_ledger.unlock_file(officer, passage_id, now):
                self._orders_file_last = now
                if mind is not None and hasattr(mind, "order_line"):
                    mind.order_line(officer, text, heading=f"{order_files.heading(officer)} · {number}")
                return True
        return False

    def _orders_tell_after(self, now):
        """A finished campaign, looked back on in a quiet moment (an unlock)."""
        mind = self._orders_mind()
        session = self._orders_session()
        if not session or now - float(session) < REMIND_AFTER_S or now - self._orders_file_last < FILE_GAP_S:
            return False
        if getattr(mind, "_in_danger", False):
            return False
        campaign = self.order_ledger.after_due(now)
        if campaign is None:
            return False
        lines = order_campaign_words.AFTER.get(campaign, ())
        title = campaigns.CAMPAIGNS.get(campaign, {}).get("title", campaign)
        heading = f"AFTER · {str(title).upper()}"
        for speaker, text in lines:
            if mind is not None and hasattr(mind, "order_line"):
                mind.order_line(speaker, text, heading=heading, converse=True)
        self.order_ledger.after_told(campaign, now)
        self._orders_file_last = now
        return True

    # -- your answers ------------------------------------------------------------------------------
    def _orders_latest_offer(self):
        offered = self.order_ledger.offered()
        return max(offered, key=lambda row: float(row.get("offered_at") or 0)) if offered else None

    def _orders_accept(self, order_id=None):
        order = self.order_ledger.get(order_id) if order_id else self._orders_latest_offer()
        if order is None:
            return {"ok": False, "message": "No order is waiting."}
        order["standing_before"] = standing(int(self.order_ledger.record(order.get("officer")).get("done") or 0))
        result = self.order_ledger.accept(order["id"])
        if not result:
            return {"ok": False, "message": "That order can't be accepted now."}
        if result.get("error"):
            self._orders_say(order.get("officer"), "full", self._orders_fields(order), order=order)
            return {"ok": False, "message": "Finish or cancel an order first." if result["error"] == "full"
                    else "A campaign is already under way."}
        fields = self._orders_fields(order)
        if order.get("size") == "campaign":
            opening = order_campaign_words.CAMPAIGNS.get(order.get("campaign"), {}).get("opening", ())
            self._orders_scene(opening, fields, order, f"CAMPAIGN · {str(order.get('title') or '').upper()}")
            self._orders_build_stage(order)
        else:
            self._orders_say(order.get("officer"), "accepted", fields, order=order)
        if self.config.get("orders_copy_target", True):
            self._orders_plot(order, quiet=True)
        self._orders_publish()
        return {"ok": True, "message": f"Accepted: {order.get('title')}", "order": order["id"]}

    def _orders_decline(self, order_id=None):
        order = self.order_ledger.get(order_id) if order_id else self._orders_latest_offer()
        if order is None:
            return {"ok": False, "message": "No order is waiting."}
        result = self.order_ledger.decline(order["id"])
        if not result:
            return {"ok": False, "message": "That order can't be declined now."}
        fields = self._orders_fields(order)
        self._orders_say(order.get("officer"), "muted" if result.get("muted") else "declined", fields, order=order)
        self._orders_publish()
        return {"ok": True, "message": "Declined." + (" They won't offer that kind again." if result.get("muted") else "")}

    def _orders_later(self, order_id=None):
        order = self.order_ledger.get(order_id) if order_id else self._orders_latest_offer()
        if order is None or not self.order_ledger.later(order["id"]):
            return {"ok": False, "message": "No order is waiting."}
        self._orders_say(order.get("officer"), "later", self._orders_fields(order), order=order)
        self._orders_publish()
        return {"ok": True, "message": "Kept on the board for a day."}

    def _orders_abandon(self, order_id):
        order = self.order_ledger.get(order_id)
        if order is None or not self.order_ledger.abandon(order_id):
            return {"ok": False, "message": "That order isn't active."}
        self._orders_say(order.get("officer"), "abandoned", self._orders_fields(order), order=order)
        self._orders_publish()
        return {"ok": True, "message": f"Cancelled: {order.get('title')}"}

    def _orders_choose(self, order_id, option):
        order = self.order_ledger.get(order_id)
        if order is None:
            return {"ok": False, "message": "That campaign isn't active."}
        objectives = campaigns.choose(order, option)
        if not objectives or not self.order_ledger.choose(order_id, option, objectives):
            return {"ok": False, "message": "That choice isn't open."}
        lines = order_campaign_words.CAMPAIGNS.get(order.get("campaign"), {}).get(f"choose_{option}", ())
        self._orders_scene(lines, self._orders_fields(order), order, f"CAMPAIGN · {str(order.get('title') or '').upper()}")
        self._orders_publish()
        return {"ok": True, "message": f"You sided with {order_lines.NAMES.get(option, option)}."}

    def _orders_plot(self, order, quiet=False):
        """Copy the target's system name; with "open the galaxy map" on in
        Settings, open it too, so you can paste it into the search."""
        if isinstance(order, str):
            order = self.order_ledger.get(order)
        target = current_target(order or {})
        system = target.get("plot") or target.get("system")
        if not system:
            return {"ok": False, "message": "This order has no system to plot."}
        try:
            from voidcompass.core.native_services import copy_text
            copy_text(str(system))
        except Exception:
            return {"ok": False, "message": f"Couldn't copy {system}."}
        message = f"Copied {system}."
        if self.config.get("orders_open_map", False) and hasattr(self, "_watcher_ship"):
            try:
                self._watcher_ship("open the galaxy map")
                message += " Galaxy map opening: paste it into the search."
            except Exception:
                logging.debug("Galaxy map not opened for an order", exc_info=True)
        return {"ok": True, "message": message}

    def _orders_unmute(self, officer=None):
        self.order_ledger.unmute(officer or None)
        self._orders_publish()
        return {"ok": True, "message": "The crew may offer everything again."}

    def _orders_command(self, operation, payload):
        payload = payload or {}
        order_id = payload.get("id") or None
        handlers = {
            "accept": lambda: self._orders_accept(order_id),
            "decline": lambda: self._orders_decline(order_id),
            "later": lambda: self._orders_later(order_id),
            "abandon": lambda: self._orders_abandon(order_id),
            "choose": lambda: self._orders_choose(order_id, str(payload.get("option") or "")),
            "plot": lambda: self._orders_plot(order_id),
            "ask": self._orders_ask,
            "unmute": lambda: self._orders_unmute(payload.get("officer")),
            "view": lambda: {"ok": True},
        }
        handler = handlers.get(str(operation or ""))
        if handler is None:
            return {"ok": False, "message": f"Unknown orders command: {operation}"}
        if not self._orders_enabled() and operation not in {"view", "unmute"}:
            return {"ok": False, "message": "Crew orders are off. Turn them on in Settings."}
        if operation == "view":
            self._orders_view = str(payload.get("view") or "active")
        result = handler()
        if operation != "view" and isinstance(result, dict) and result.get("message"):
            # The command channel answers before this runs: the page reads the outcome from the next snapshot.
            self._orders_notice = {"text": result["message"], "ok": bool(result.get("ok")), "at": time.time()}
        return result

    # -- what the deck, the overlay and the API see -------------------------------------------------
    def _orders_publish(self):
        if hasattr(self, "_schedule_html_dashboard_publish"):
            try:
                self._schedule_html_dashboard_publish()
            except Exception:
                pass
        if hasattr(self, "_orders_update_overlay"):
            try:
                self._orders_update_overlay()
            except Exception:
                logging.debug("Active Order overlay update skipped", exc_info=True)
        if hasattr(self, "_update_galaxy_minimap"):
            try:
                self._update_galaxy_minimap()
            except Exception:
                logging.debug("Minimap order flags skipped", exc_info=True)

    def _orders_view_of(self, order, here=None):
        rows = objectives_of(order)
        target = current_target(order)
        if here and target.get("coords"):
            gap = places.distance(here, target["coords"])
            if gap is not None:
                target["distance"] = generators._ly(gap)
        stages = []
        for index, stage in enumerate(order.get("stages") or ()):
            stages.append({"title": stage.get("title"), "officer": stage.get("officer"), "done": bool(stage.get("done_at")),
                           "current": index == int(order.get("stage") or 0), "built": bool(stage.get("built")),
                           "choice": stage.get("choice") if not stage.get("chosen") else None, "chosen": stage.get("chosen")})
        return {
            "id": order.get("id"), "kind": order.get("kind"), "size": order.get("size", "field"), "status": order.get("status"),
            "officer": order.get("officer"), "officer_name": order_lines.NAMES.get(order.get("officer"), "Crew"),
            "title": order.get("title"), "brief": order.get("brief"), "why": order.get("why") or [],
            "objectives": [{"text": objective_rules.describe(row), "done": objective_rules.done(row),
                            "fraction": round(objective_rules.fraction(row), 3)} for row in rows],
            "progress": round(progress(order), 3), "target": target, "stages": stages, "later": bool(order.get("later")),
            "offered_at": order.get("offered_at"), "accepted_at": order.get("accepted_at"), "expires_at": order.get("expires_at"),
            "last_line": order.get("last_line"), "scenes": order.get("scenes") or [], "category": order.get("category"),
            "campaign": order.get("campaign"),
        }

    def _orders_snapshot(self):
        ledger = getattr(self, "order_ledger", None)
        if ledger is None:
            return {"enabled": False}
        here = getattr(self, "current_coords", None)
        here = here if here and list(here) != [0, 0, 0] else None
        record = {}
        for officer in order_lines.SPEAKERS:
            row = ledger.record(officer)
            told = ledger.files_told(officer)
            done = int(row.get("done") or 0)
            # The standing after this one, for the SERVICE RECORD's progress bar.
            ahead = next(((at, name) for at, name in STANDINGS if done < at), None)
            floor = max(at for at, _name in STANDINGS if done >= at)
            record[officer] = {"name": order_lines.NAMES[officer], "done": row.get("done", 0), "campaigns": row.get("campaigns", 0),
                               "declined": row.get("declined", 0), "abandoned": row.get("abandoned", 0),
                               "sided": row.get("sided", 0), "standing": standing(done),
                               "next_standing": ahead[1] if ahead else "", "next_at": ahead[0] if ahead else 0,
                               "standing_from": floor,
                               "kinds": row.get("kinds", {}), "file": order_files.page(officer, told),
                               "muted": sorted(key.split(":", 1)[1] for key in ledger.data["muted"] if key.startswith(f"{officer}:"))}
        earned = ledger.ribbons()
        after = [{"campaign": key, "title": campaigns.CAMPAIGNS.get(key, {}).get("title", key), "at": row.get("told"),
                  "lines": [{"speaker": speaker, "text": text} for speaker, text in order_campaign_words.AFTER.get(key, ())]}
                 for key, row in sorted(ledger.after_scenes().items(), key=lambda pair: -float(pair[1].get("told") or 0))]
        return {
            "enabled": self._orders_enabled(),
            "offered": [self._orders_view_of(row, here) for row in ledger.offered()],
            "active": [self._orders_view_of(row, here) for row in ledger.active()],
            "history": ledger.history(40),
            "record": record,
            "ribbons": [{"id": key, "name": name, "for": reason, "at": earned.get(key),
                         "theme": ribbons.POSTCARD_THEMES.get(key, ("",))[0]} for key, (name, reason) in ribbons.RIBBONS.items()],
            "after": after,
            "why": self._orders_why,
            "frequency": pacing.frequency(self.config),
            "frequencies": {key: value["label"] for key, value in pacing.FREQUENCIES.items() if value},
            "on_watch": companions.identity(self.config),
            "online": bool(hasattr(self, "_trading_online") and self._trading_online()),
            "view": getattr(self, "_orders_view", "active"),
            "notice": getattr(self, "_orders_notice", None),
        }

    # Which objectives belong on which Navigation HUD page (5.7.7).
    HUD_PAGE_TYPES = {"survey": {"map", "fss_all", "discover", "stay"}, "planet": {"bio", "footfall", "land", "screenshot"}}

    def _orders_page_line(self, page):
        """The active order with an open objective that fits this HUD page,
        the one aimed at this system first: {officer, title, next, distance}."""
        ledger = getattr(self, "order_ledger", None)
        types = self.HUD_PAGE_TYPES.get(page)
        if ledger is None or not types or not self._orders_enabled():
            return None
        here_system = str(self._orders_place.get("system") or getattr(self, "current_sys", "") or "").casefold()
        best = None
        for order in ledger.active():
            rows = [row for row in objectives_of(order) if not objective_rules.done(row) and row.get("type") in types]
            if not rows:
                continue
            target = current_target(order)
            rank = 0 if str(target.get("system") or "").casefold() == here_system and here_system else 1
            if best is None or rank < best[0]:
                best = (rank, order, rows[0])
        if best is None:
            return None
        _rank, order, row = best
        target = current_target(order)
        here = getattr(self, "current_coords", None)
        gap = places.distance(here, target["coords"]) if target.get("coords") and here and list(here) != [0, 0, 0] else None
        return {"officer": order_lines.NAMES.get(order.get("officer"), "Crew"), "title": order.get("title"),
                "next": objective_rules.describe(row), "distance": generators._ly(gap) if gap and gap > 1 else ""}

    def _orders_map_targets(self):
        """Every active order's target with a position, for the Galaxy Minimap and the Atlas."""
        ledger = getattr(self, "order_ledger", None)
        if ledger is None or not self._orders_enabled():
            return []
        out = []
        for order in ledger.active() + [row for row in ledger.offered() if not row.get("later")]:
            target = current_target(order)
            coords = target.get("coords")
            if not coords:
                continue
            try:
                coords = [round(float(value), 2) for value in coords][:3]
            except (TypeError, ValueError):
                continue
            out.append({"id": order.get("id"), "title": order.get("title"), "officer": order.get("officer"),
                        "officer_name": order_lines.NAMES.get(order.get("officer"), "Crew"), "status": order.get("status"),
                        "system": target.get("system") or target.get("region") or "", "coords": coords})
        return out[:8]

    def _orders_service_level(self, officer):
        """0 to 4: your standing with this officer past New to the watch, for
        the service pips on its display (an unlock, 5.7.7)."""
        ledger = getattr(self, "order_ledger", None)
        if ledger is None or not self._orders_enabled():
            return 0
        return service_level(int(ledger.record(officer).get("done") or 0))

    def _orders_field_cue(self):
        """The oldest active order, for the Mission Directive (field_cues)."""
        ledger = getattr(self, "order_ledger", None)
        if ledger is None:
            return None
        active = ledger.active()
        if not active:
            return None
        order = min(active, key=lambda row: float(row.get("accepted_at") or 0))
        rows = [row for row in objectives_of(order) if not objective_rules.done(row)]
        return {"title": order.get("title"), "officer": order_lines.NAMES.get(order.get("officer"), "Crew"),
                "next": objective_rules.describe(rows[0]) if rows else "", "system": current_target(order).get("system")}

    # -- the cockpit overlay -----------------------------------------------------------------------
    def _orders_overlay_model(self):
        """Every order for the Crew Orders overlay: those waiting for an answer
        first (newest on top), then the campaign, then the rest in the order you
        took them. None hides it."""
        ledger = getattr(self, "order_ledger", None)
        if ledger is None or not self._orders_enabled():
            return None
        here = getattr(self, "current_coords", None)
        here = here if here and list(here) != [0, 0, 0] else None
        offers = [row for row in sorted(ledger.offered(), key=lambda row: -float(row.get("offered_at") or 0))
                  if not row.get("later")]
        active = sorted(ledger.active(), key=lambda row: (row.get("size") != "campaign", float(row.get("accepted_at") or 0)))
        if not offers and not active:
            return None
        # The hotkeys answer the newest offer: only that one shows them.
        latest = self._orders_latest_offer()
        answers = latest.get("id") if latest else None
        items = [self._orders_overlay_item(order, here, True, order.get("id") == answers) for order in offers]
        items += [self._orders_overlay_item(order, here, False, False) for order in active]
        keys = lambda name: str(self.config.get(f"overlay_hotkey_{name}") or "").upper().replace("<", "").replace(">", "")
        return {"items": items, "accept_key": keys("orders_accept") if offers else "",
                "decline_key": keys("orders_decline") if offers else ""}

    def _orders_overlay_item(self, order, here, offer, answers):
        view = self._orders_view_of(order, here)
        stage = next((row for row in view["stages"] if row["current"]), None)
        steps = [row for row in view["objectives"] if not row["done"]] or view["objectives"][:1]
        tag = "NEW ORDER" if offer else ("CAMPAIGN" if order.get("size") == "campaign" else "LONG ORDER" if order.get("size") == "long" else "ORDER")
        return {
            "state": "offer" if offer else "active", "tag": tag, "title": view["title"], "officer": view["officer"],
            "officer_name": view["officer_name"], "stage": f"{order.get('title')}: {stage['title']}" if stage and not offer else "",
            "steps": [{"text": row["text"], "done": row["done"], "fraction": row["fraction"]} for row in steps],
            "line": (view.get("last_line") or {}).get("text", "") if offer else "",
            "distance": (view.get("target") or {}).get("distance", ""), "progress": None if offer else view["progress"],
            "keys": answers,
        }

    def _orders_update_overlay(self, only_if_changed=False):
        hud = getattr(self, "orders_hud", None)
        if hud is None or not hasattr(hud, "update_orders"):
            return
        model = self._orders_overlay_model()
        # The clock calls this every few seconds: the distance to a target
        # changes with each jump, but the window is only touched on a change.
        key = repr(model)
        if only_if_changed and key == getattr(self, "_orders_overlay_key", None):
            return
        self._orders_overlay_key = key
        hud.update_orders(model)

    # -- the Local API (5.7.7) ---------------------------------------------------------------------
    def api_orders(self):
        snapshot = self._orders_snapshot()
        snapshot.pop("view", None)
        return snapshot

    def api_orders_ask(self):
        from voidcompass.services.local_api import ApiError
        result = self._orders_ask()
        if not result.get("ok"):
            raise ApiError(409, result.get("message") or "No order right now")
        return {**result, "offered": self._orders_snapshot().get("offered", [])}

    def api_orders_answer(self, answer, order_id=""):
        from voidcompass.services.local_api import ApiError
        if not self._orders_enabled():
            raise ApiError(409, "Crew orders are off. Turn them on in Settings.")
        handler = {"accept": self._orders_accept, "decline": self._orders_decline, "later": self._orders_later}[answer]
        result = handler(order_id or None)
        if not result.get("ok"):
            raise ApiError(409, result.get("message") or "No order is waiting")
        return result

    def api_orders_abandon(self, order_id):
        from voidcompass.services.local_api import ApiError
        result = self._orders_abandon(order_id)
        if not result.get("ok"):
            raise ApiError(404, result.get("message") or "No such order")
        return result

    # -- TALK (5.7.7) ----------------------------------------------------------------------------------
    def _orders_talk(self, text):
        """A Crew Orders question in TALK: its answer, or None when none was asked."""
        asked = orders_talk.intent(text)
        if asked is None or getattr(self, "order_ledger", None) is None:
            return None
        if not self._orders_enabled():
            return "Crew orders are off. You can turn them on in Settings."
        ledger = self.order_ledger
        if asked == "ask":
            return self._orders_ask()["message"]
        if asked in {"accept", "decline", "later"}:
            handler = {"accept": self._orders_accept, "decline": self._orders_decline, "later": self._orders_later}[asked]
            return handler()["message"]
        active = ledger.active()
        current = ledger.campaign() or (min(active, key=lambda row: float(row.get("accepted_at") or 0)) if active else None)
        if asked == "list":
            if not active and not ledger.offered():
                return "No orders right now. Ask, and the crew will look."
            lines = [f"{order_lines.NAMES.get(row.get('officer'), 'Crew')}: {row.get('title')}, {round(progress(row) * 100)}% done"
                     for row in active[:4]]
            waiting = ledger.offered()
            if waiting:
                lines.append(f"Waiting for your answer: {waiting[0].get('title')}")
            return ". ".join(lines) + "."
        if current is None:
            return "There's no order under way."
        if asked == "who":
            return f"{order_lines.NAMES.get(current.get('officer'), 'The crew')} gave it: {current.get('title')}."
        if asked == "cancel":
            return self._orders_abandon(current["id"])["message"]
        if asked == "plot":
            return self._orders_plot(current)["message"]
        rows = [row for row in objectives_of(current) if not objective_rules.done(row)]
        nxt = objective_rules.describe(rows[0]) if rows else "nothing left"
        if asked == "far":
            here = getattr(self, "current_coords", None)
            target = current_target(current)
            gap = places.distance(here, target["coords"]) if here and target.get("coords") else None
            if gap is None:
                return f"{current.get('title')}: next, {nxt}. I don't have a position for the target."
            return f"{target.get('system') or current.get('title')} is {generators._ly(gap)} away. Next: {nxt}."
        return f"{current.get('title')}: {round(progress(current) * 100)}% done. Next: {nxt}."
