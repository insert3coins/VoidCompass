"""The Trading tab (5.5.2.6): your trading at a glance with charts, the
Spansh trade router and loop routes, selling what's in your hold, finding any
commodity, the market where you're docked, and your trade history. The record
and the Spansh work are dashboard_trading_mixin's."""

from __future__ import annotations

import math
import time
from urllib.parse import quote
import webbrowser

from voidcompass.services import spansh
from voidcompass.trading import market as trade_market
from voidcompass.trading import route as trade_route
from voidcompass.trading import views

_VIEWS = ("overview", "route", "cargo", "find", "station", "history")
# Ships that need a large landing pad (journal Ship symbols, folded).
LARGE_SHIPS = {"anaconda", "cutter", "federation_corvette", "belugaliner", "type7", "type9", "type9_military",
               "panthermkii"}


def _text(value, limit=200):
    return str(value if value is not None else "").strip()[:limit]


def _int(value, default=0, low=None, high=None):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    if low is not None:
        number = max(low, number)
    if high is not None:
        number = min(high, number)
    return number


def _flag(value):
    return 1 if value in (True, 1, "1", "true", "on") else 0


class HtmlTradingMixin:
    def _trading_ui(self):
        return self._html_profile_transient("_html_trading_state", {
            "view": "overview", "days": 30, "form": None, "route": {}, "loop": {}, "cargo": {},
            "find": {"kind": "sell", "commodity": "", "system": "", "amount": 1, "sort": "price",
                     "large": 0, "carriers": 1, "planetary": 1},
            "station": {}, "notice": "", "error": "", "report": "",
        })

    def _trading_form_defaults(self):
        """The route form, filled from the journal: where you are, your hold,
        your credits, your pad size and jump range. All of it editable."""
        ship = getattr(self, "cmdr_ship", None) or {}
        station = getattr(self, "current_station_name", "") if getattr(self, "current_docked", False) else ""
        system = getattr(self, "current_sys", "") or ""
        if not station and getattr(self, "trading_store", None) is not None:
            last = self.trading_store.query("SELECT station, system FROM markets ORDER BY ts DESC LIMIT 1")
            if last and (not system or last[0]["system"] == system):
                station, system = last[0]["station"], last[0]["system"]
        jump = ship.get("max_jump_range") or 0
        return {
            "system": system, "station": station or "",
            "max_cargo": _int(ship.get("cargo_capacity") or getattr(self, "cargo_capacity", 0), 0, 0),
            "starting_capital": _int(getattr(self, "cmdr_balance", 0), 0, 0),
            "max_hop_distance": max(10, math.floor(float(jump))) if jump else 20,
            "max_hops": 3, "max_system_distance": 5000, "max_price_age_days": 3,
            "requires_large_pad": 1 if str(ship.get("ship") or "").casefold() in LARGE_SHIPS else 0,
            "allow_planetary": 1, "allow_player_owned": 0, "allow_prohibited": 0,
            "allow_restricted_access": 0, "permit": 0, "unique": 0,
        }

    # -- snapshot ------------------------------------------------------------
    def _html_trading_workspace(self):
        ui = self._trading_ui()
        self._trading_warm_up()
        store = getattr(self, "trading_store", None)
        data = {"view": ui["view"], "notice": ui["notice"], "error": ui["error"], "online": self._trading_online(),
                "ready": store is not None, "busy": sorted(getattr(self, "_trading_busy", {}) or ())}
        if store is None:
            return data
        if ui["form"] is None:
            ui["form"] = self._trading_form_defaults()
        state = getattr(self, "_trading_import_state", {}) or {}
        data["import"] = {"running": bool(state.get("running")), "done": bool(state.get("done"))}
        data["where"] = {"system": getattr(self, "current_sys", "") or "",
                         "station": getattr(self, "current_station_name", "") if getattr(self, "current_docked", False) else "",
                         "docked": bool(getattr(self, "current_docked", False)),
                         "credits": getattr(self, "cmdr_balance", None),
                         "cargo_capacity": ui["form"]["max_cargo"]}
        data["followed"] = trade_route.next_step(getattr(self, "trading_route", None))
        names = self.trading_names
        view = ui["view"]
        if view == "overview":
            data["summary"] = views.summary(store, names, ui["days"])
            data["summary"]["recent"] = data["summary"]["recent"][:8]
        elif view == "route":
            data["form"] = ui["form"]
            data["route"] = ui["route"]
            data["loop"] = ui["loop"]
        elif view == "cargo":
            data["hold"] = self._trading_cargo()
            data["cargo"] = ui["cargo"]
        elif view == "find":
            data["find"] = ui["find"]
            data["names"] = names.all_names()
        elif view == "station":
            local = self._trading_local_market()
            data["station"] = {"local": local, "remote": ui["station"].get("remote"),
                               "error": ui["station"].get("error", "")}
        elif view == "history":
            summary = views.summary(store, names, ui["days"])
            data["summary"] = summary
            data["report"] = views.report(summary)
        data["days"] = ui["days"]
        return data

    # -- commands ------------------------------------------------------------
    def _handle_trading_command(self, operation, payload):
        ui = self._trading_ui()
        ui["notice"], ui["error"] = "", ""
        if getattr(self, "trading_store", None) is None:
            return False
        if ui["form"] is None:
            ui["form"] = self._trading_form_defaults()
        if operation == "view":
            view = _text(payload.get("view"), 20)
            ui["view"] = view if view in _VIEWS else "overview"
            return True
        if operation == "days":
            days = _int(payload.get("days"), 30)
            ui["days"] = days if days in views.RANGES else 30
            return True
        if operation == "form_reset":
            ui["form"] = self._trading_form_defaults()
            return True
        if operation == "plan":
            return self._trading_plan(ui, payload)
        if operation == "loop":
            return self._trading_loop(ui, _int(payload.get("market_a")), _int(payload.get("market_b")))
        if operation == "stop_plan":
            return self._trading_stop_route(ui)
        if operation == "pick_station":
            return self._trading_plan(ui, {"system": _text(payload.get("system"), 120), "station": _text(payload.get("station"), 120)})
        if operation == "follow":
            result = ui["route"].get("result")
            if not result or not result.get("hops"):
                return False
            self.trading_route = trade_route.start(result, ui["form"], time.time())
            self.trading_store.set_value("route", self.trading_route)
            self._trading_update_overlay()
            ui["notice"] = "Following this route: it ticks along as you buy and sell."
            return True
        if operation == "follow_loop":
            return self._trading_follow_loop(ui)
        if operation == "skip_hop":
            trade_route.skip(getattr(self, "trading_route", None))
            self.trading_store.set_value("route", self.trading_route)
            self._trading_update_overlay()
            return True
        if operation == "stop_route":
            self.trading_route = None
            self.trading_store.set_value("route", None)
            self._trading_update_overlay()
            return True
        if operation == "cargo":
            return self._trading_sell_cargo(ui)
        if operation == "find":
            return self._trading_find(ui, payload)
        if operation == "find_sort":
            sort = _text(payload.get("sort"), 20)
            ui["find"]["sort"] = sort if sort in ("price", "distance") else "price"
            return True
        if operation == "station":
            return self._trading_station(ui, _int(payload.get("market_id")))
        if operation == "sell_here":
            ui["view"] = "find"
            ui["find"].update(kind="sell", commodity=_text(payload.get("commodity"), 80),
                              system=getattr(self, "current_sys", "") or "", amount=1)
            return self._trading_find(ui, ui["find"])
        if operation == "plan_from":
            ui["form"].update(system=_text(payload.get("system"), 120), station=_text(payload.get("station"), 120))
            ui["view"] = "route"
            return True
        if operation == "copy":
            return self._html_copy_text(_text(payload.get("text"), 300))
        if operation == "copy_report":
            summary = views.summary(self.trading_store, self.trading_names, ui["days"])
            return self._html_copy_text(views.report(summary))
        if operation == "open":
            kind, name = _text(payload.get("kind"), 20), _text(payload.get("name"), 160)
            market_id = _int(payload.get("market_id"))
            if kind == "station" and market_id:
                webbrowser.open_new_tab(f"https://spansh.co.uk/station/{market_id}")
            elif kind == "system" and name:
                webbrowser.open_new_tab(f"https://spansh.co.uk/search/{quote(name)}")
            return True
        return False

    def _trading_plan(self, ui, payload):
        form = dict(ui["form"])
        for key in ("system", "station"):
            form[key] = _text(payload.get(key, form[key]), 120)
        for key, low, high in (("max_cargo", 1, 2000), ("starting_capital", 0, 10 ** 13), ("max_hop_distance", 1, 1000),
                               ("max_hops", 1, 20), ("max_system_distance", 10, 10 ** 6), ("max_price_age_days", 1, 365)):
            form[key] = _int(payload.get(key, form[key]), form[key], low, high)
        for key in ("requires_large_pad", "allow_planetary", "allow_player_owned", "allow_prohibited",
                    "allow_restricted_access", "permit", "unique"):
            form[key] = _flag(payload.get(key, form[key]))
        ui["form"] = form
        if not form["system"] or not form["station"]:
            ui["error"] = "A trade route starts from a station: give its system and station."
            return True
        request = {key: form[key] for key in spansh.TRADE_ROUTE_FIELDS if key in form}
        request["max_price_age"] = form["max_price_age_days"] * 86400
        started = time.time()
        progress = {"pending": True, "stage": "station", "started": started, "hops": form["max_hops"]}
        ui["route"] = progress
        ui["loop"] = {}
        token = self.__dict__["_trading_route_token"] = getattr(self, "_trading_route_token", 0) + 1

        def stage(name):
            # From the worker thread: the deck shows each step as it happens.
            progress.update(stage=name, stage_at=time.time())
            self._ui_post(lambda: self._schedule_html_dashboard_publish(immediate=True), key="trading-progress")

        def work():
            system, station = request["system"], request["station"]
            # Planned from where you're docked: the game's names are Spansh's.
            here = getattr(self, "current_station_name", "") if getattr(self, "current_docked", False) else ""
            if here and station.casefold() == here.casefold() \
                    and system.casefold() == str(getattr(self, "current_sys", "") or "").casefold():
                system, station = getattr(self, "current_sys", system), here
            else:
                # Otherwise the router only knows a station by its exact name
                # in that system: match what was typed (any case) first.
                system, stations = self._trading_system_stations(system)
                match = next((row for row in stations if row["name"].casefold() == station.casefold()), None)
                if match is None:
                    return {"choices": {"system": system, "typed": station, "stations": stations[:40]}}
                station = match["name"]
            exact = {**request, "system": system, "station": station}
            result, job = spansh.trade_route(exact, on_state=stage,
                                             should_stop=lambda: getattr(self, "_trading_route_token", 0) != token)
            return {"result": trade_market.parse_route(result), "job": job, "system": system, "station": station,
                    "took": round(time.time() - started)}

        def done(result, error):
            if getattr(self, "_trading_route_token", 0) != token:
                return  # stopped, or a newer search took over
            if result and "choices" in result:
                ui["route"] = {"choices": result["choices"]}
                return
            ui["route"] = {"error": error} if error else {**result, "planned_at": time.time()}
            if result:
                ui["form"].update(system=result["system"], station=result["station"])
                if not result["result"]["hops"]:
                    ui["route"]["error"] = "Spansh found no profitable route with these settings. Try more hops, a longer hop distance or older prices."
        return self._trading_task("route", work, done, cache_key=("route", tuple(sorted(request.items()))))

    def _trading_stop_route(self, ui):
        """Stop waiting for Spansh (the job finishes on their side unseen)."""
        self._trading_route_token = getattr(self, "_trading_route_token", 0) + 1
        getattr(self, "_trading_busy", {}).pop("route", None)
        ui["route"] = {}
        ui["notice"] = "Stopped the route search."
        return True

    def _trading_system_stations(self, system):
        """A system's stations with markets, from Spansh, once a session."""
        cache = self.__dict__.setdefault("_trading_station_lists", {})
        key = system.casefold()
        if key not in cache:
            cache[key] = spansh.system_stations(system)
        return cache[key]

    def _trading_loop(self, ui, market_a, market_b):
        if not market_a or not market_b:
            return False
        form = ui["form"]
        ui["loop"] = {"pending": True}

        def work():
            a = trade_market.parse_station(spansh.station_market(market_a))
            b = trade_market.parse_station(spansh.station_market(market_b))
            if not a or not b:
                raise spansh.SpanshError("Spansh has no market for one of these stations.")
            return trade_market.loop_route(a, b, form["max_cargo"], form["starting_capital"])

        def done(result, error):
            ui["loop"] = {"error": error} if error else {"result": result}
        return self._trading_task("loop", work, done, cache_key=("loop", market_a, market_b, form["max_cargo"],
                                                                 form["starting_capital"]))

    def _trading_follow_loop(self, ui):
        loop = (ui["loop"] or {}).get("result")
        if not loop or not (loop["out"] or loop["back"]):
            return False
        hops = []
        for leg, a, b in ((loop["out"], loop["a"], loop["b"]), (loop["back"], loop["b"], loop["a"])):
            if leg:
                hops.append({"from": {**a, "arrival_ls": None}, "to": {**b, "arrival_ls": None}, "distance": 0,
                             "goods": [leg], "profit": leg["total"], "cumulative": 0})
        plan = {"hops": hops, "profit": loop["profit"], "distance": 0}
        self.trading_route = trade_route.start(plan, ui["form"], time.time())
        self.trading_store.set_value("route", self.trading_route)
        self._trading_update_overlay()
        ui["notice"] = "Following this loop: it ticks along as you buy and sell."
        return True

    def _trading_sell_cargo(self, ui):
        hold = [row for row in self._trading_cargo() if row["count"] > 0][:12]
        system = getattr(self, "current_sys", "") or ""
        if not hold or not system:
            ui["cargo"] = {"error": "Your hold is empty." if system else "Waiting for your location from the journal."}
            return True
        progress = {"pending": True, "done": 0, "total": len(hold), "current": ""}
        ui["cargo"] = progress

        def work():
            from concurrent.futures import ThreadPoolExecutor
            self._trading_spansh_names()
            finished = []

            def look_up(item):
                # Each commodity asked side by side on the shared connection
                # (5.5.3.2), not one after another.
                name = self.trading_names.spansh_name(self.trading_names.name(item["symbol"]))
                stations = trade_market.parse_commodity(
                    spansh.commodity_stations("sell", system, name, item["count"]), name, "sell")
                stations.sort(key=lambda row: -row["price"])
                finished.append(name)
                progress.update(done=len(finished), current=name)
                self._ui_post(lambda: self._schedule_html_dashboard_publish(immediate=True), key="trading-progress")
                return {**item, "name": name, "stations": stations[:5]}
            if len(hold) == 1:
                rows = [look_up(hold[0])]
            else:
                with ThreadPoolExecutor(max_workers=4, thread_name_prefix="trading-cargo") as pool:
                    rows = list(pool.map(look_up, hold))
            return {"rows": rows, "system": system, "at": time.time()}

        def done(result, error):
            ui["cargo"] = {"error": error} if error else result
        key = ("cargo", system, tuple((row["symbol"], row["count"]) for row in hold))
        return self._trading_task("cargo", work, done, cache_key=key)

    def _trading_find(self, ui, payload):
        find = ui["find"]
        kind = _text(payload.get("kind"), 10)
        find.update(kind=kind if kind in ("buy", "sell") else "sell",
                    commodity=_text(payload.get("commodity"), 80),
                    system=_text(payload.get("system"), 120) or getattr(self, "current_sys", "") or "",
                    amount=_int(payload.get("amount"), 1, 1, 100000),
                    large=_flag(payload.get("large", find.get("large"))),
                    carriers=_flag(payload.get("carriers", find.get("carriers"))),
                    planetary=_flag(payload.get("planetary", find.get("planetary"))))
        if not find["commodity"] or not find["system"]:
            find["error"] = "Give a commodity and a system."
            return True
        find.update(pending=True, error="")
        request = (find["kind"], find["system"], find["commodity"], find["amount"],
                   bool(find["large"]), bool(find["carriers"]), bool(find["planetary"]))

        def work():
            self._trading_spansh_names()
            name = self.trading_names.spansh_name(request[2])
            rows = trade_market.parse_commodity(
                spansh.commodity_stations(request[0], request[1], name, request[3],
                                          large_pad=request[4], carriers=request[5], planetary=request[6]),
                name, request[0])
            return {"name": name, "rows": rows}

        def done(result, error):
            find.update(pending=False, error=error, results=(result or {}).get("rows") or [],
                        resolved=(result or {}).get("name") or "", searched=request)
            if result and not result["rows"]:
                find["error"] = (f"No station near {request[1]} {'sells' if request[0] == 'buy' else 'buys'} "
                                 f"{result['name']} in Spansh's data. Check the spelling, or try another system.")
        return self._trading_task("find", work, done, cache_key=("find",) + request)

    def _trading_station(self, ui, market_id):
        if not market_id:
            return False
        ui["view"] = "station"
        ui["station"] = {"pending": True}

        def work():
            self._trading_spansh_names()
            station = trade_market.parse_station(spansh.station_market(market_id))
            if not station:
                raise spansh.SpanshError("Spansh has no market for this station.")
            return station

        def done(result, error):
            ui["station"] = {"error": error} if error else {"remote": result}
        return self._trading_task("station", work, done, cache_key=("station", market_id))
