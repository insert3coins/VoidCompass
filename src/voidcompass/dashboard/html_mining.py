"""The Mining page (5.5.12), rebuilt for asteroid and Rhino mining alike:
where you are and what you're mining with, the live run, finding rings and
Rhino ground, selling the haul, and your whole mining record.

The live run itself is the specialist engine's (mining/specialist_engine.py);
this adds what the page shows around it."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
import webbrowser

from voidcompass.core.config import get_active_profile
from voidcompass.mining.mining_data import GROUND_SPANSH, MINING_MATERIALS, search_spansh_grounds
from voidcompass.mining.mining_record import MiningRecord, material_name
from voidcompass.mining.planet_materials import mining_material_catalogue
from voidcompass.mining.rhino_intelligence import GROUND_LABELS, describe_tons, ground_intelligence, mining_sheet

# The record is read again at most this often while the page is open.
RECORD_FRESH_S = 120


def _key(name):
    return "".join(char for char in str(name or "").casefold() if char.isalnum())


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


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mined_keys():
    keys = {_key(name) for name in mining_material_catalogue()}
    # Trading symbols that aren't their names.
    return keys | {"opal", "lowtemperaturediamond"}


def material_grounds():
    """For each material, the Rhino grounds it turns up on, likeliest first."""
    out = {}
    for ground, rows in (mining_sheet().get("grounds") or {}).items():
        for row in rows or ():
            if not isinstance(row, dict) or not row.get("material"):
                continue
            out.setdefault(row["material"], []).append({
                "ground": ground, "label": GROUND_LABELS.get(ground, ground),
                "pct": _float(row.get("pct"), 0.0), "median": _int(row.get("median")), "best": _int(row.get("best")),
                "searchable": ground in GROUND_SPANSH})
    for rows in out.values():
        rows.sort(key=lambda row: (-row["pct"], -row["median"]))
    return out


def typical_prices():
    """The best median sale price the mining sheet saw for each material."""
    out = {}
    for rows in (mining_sheet().get("grounds") or {}).values():
        for row in rows or ():
            if isinstance(row, dict) and row.get("material"):
                out[row["material"]] = max(out.get(row["material"], 0), _int(row.get("median")))
    return out


def mining_prices(trades):
    """What you've been paid for what you mined: sales with nothing paid for
    them, kept to mining commodities. ``trades`` oldest first."""
    wanted = _mined_keys()
    prices, months = {}, {}
    total = 0
    for trade in trades or ():
        symbol = str(trade.get("commodity") or "")
        if _key(symbol) not in wanted:
            continue
        name = material_name(trade.get("name") or symbol)
        count, credits = _int(trade.get("count")), _int(trade.get("total"))
        row = prices.setdefault(name, {"sold_t": 0, "credits": 0, "best": 0, "last": 0, "last_at": 0})
        row["sold_t"] += count
        row["credits"] += credits
        row["best"] = max(row["best"], _int(trade.get("price")))
        row["last"], row["last_at"] = _int(trade.get("price")), _float(trade.get("ts"), 0.0)
        total += credits
        month = datetime.fromtimestamp(_float(trade.get("ts"), 0.0), timezone.utc).strftime("%Y-%m")
        months[month] = months.get(month, 0) + credits
    for row in prices.values():
        row["avg"] = round(row["credits"] / row["sold_t"]) if row["sold_t"] else 0
    return {"prices": prices, "total": total,
            "months": [{"month": month, "credits": credits} for month, credits in sorted(months.items())]}


class HtmlMiningMixin:
    # -- where, and what with -----------------------------------------------------
    def _mining_where(self):
        system = str(getattr(self, "current_sys", "") or "")
        body = str(getattr(self, "current_body_name", "") or "")
        field = str(getattr(self, "current_asteroid_field_kind", "") or "")
        in_rhino = callable(getattr(self, "_rig_in_rhino", None)) and self._rig_in_rhino()
        if in_rhino:
            mode = "rhino"
        elif getattr(self, "current_in_srv", False):
            mode = "srv"
        elif getattr(self, "current_on_foot", False):
            mode = "foot"
        elif getattr(self, "current_docked", False):
            mode = "docked"
        elif field:
            mode = "field"
        elif getattr(self, "on_planet", False):
            mode = "planet"
        else:
            mode = "flight"
        return {"system": system, "body": body, "mode": mode, "field": field,
                "field_name": str(getattr(self, "current_local_space_name", "") or "") if field else "",
                "station": str(getattr(self, "current_station_name", "") or "") if mode == "docked" else ""}

    def _mining_haul(self, prices):
        """What's in the holds now, with what it might fetch."""
        vessel = str(getattr(self, "current_cargo_vessel", "Ship") or "Ship").casefold()
        inventory = list(getattr(self, "current_cargo_inventory", None) or [])
        ship = inventory if vessel != "srv" else list(((getattr(self, "_cargo_inventory_by_hold", None) or {}).get("Ship")) or [])
        rhino = inventory if vessel == "srv" else []
        typical = typical_prices()
        rows, limpets = {}, 0
        for hold, items in (("ship", ship), ("rhino", rhino)):
            for item in items:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("Name") or item.get("name") or "")
                count = _int(item.get("Count", item.get("count")))
                if _key(symbol) == "drones":
                    limpets += count if hold == "ship" else 0
                    continue
                if count <= 0:
                    continue
                name = material_name(symbol, item.get("Name_Localised"))
                row = rows.setdefault(name, {"name": name, "ship": 0, "rhino": 0, "mined": _key(symbol) in _mined_keys()})
                row[hold] += count
        out = []
        for row in rows.values():
            mine = (prices.get(row["name"]) or {}).get("avg") or 0
            each, source = (mine, "yours") if mine else ((typical.get(row["name"]) or 0), "typical")
            out.append({**row, "each": each, "source": source if each else "", "value": each * (row["ship"] + row["rhino"])})
        out.sort(key=lambda row: (not row["mined"], -row["value"], -(row["ship"] + row["rhino"])))
        return out, limpets

    def _mining_ground_here(self, where):
        body = where.get("body")
        if not body:
            return None
        for item in getattr(self, "scan_items", None) or ():
            if item.get("is_star") or item.get("star_type"):
                continue
            name = str(item.get("full_name") or item.get("name") or "")
            if body not in (name, str(item.get("name") or "")):
                continue
            details = {"class": item.get("planet_class") or item.get("class"), "volcanism": item.get("volcanism"),
                       "landable": item.get("landable")}
            intel = ground_intelligence(details)
            if not intel.get("ground"):
                return None
            return {"body": name, "gravity": _float(item.get("gravity_g")), "class": details["class"] or "",
                    "volcanism": details["volcanism"] or "", **intel}
        return None

    def _mining_sites_here(self, where):
        store = getattr(self, "_planet_materials_store", None)
        if not callable(store) or not where.get("body"):
            return []
        try:
            rows = store().rows()
        except Exception as exc:
            logging.debug("Mining page sites skipped: %s", exc)
            return []
        system, body = where["system"].casefold(), where["body"].casefold()
        out = []
        for row in rows:
            if str(row.get("system") or "").casefold() != system or str(row.get("body") or "").casefold() != body:
                continue
            materials = row.get("materials")
            out.append({"name": str(row.get("name") or ""), "materials": materials if isinstance(materials, list) else [],
                        "amount": str(row.get("amount") or ""), "rigs": _int(row.get("rigs")),
                        "depleted": bool(row.get("depleted")), "estimate": describe_tons(row.get("rigs"), row.get("amount")),
                        "location": row.get("location_index")})
        return out[:20]

    # -- your record ----------------------------------------------------------------
    def _mining_record_view(self, refresh=False):
        state = self._html_profile_transient("_html_mining_record", {"status": "idle", "summary": None, "at": 0.0})
        due = state["status"] == "idle" or (state["status"] == "ready" and time.time() - state["at"] > RECORD_FRESH_S)
        if (refresh and state["status"] != "reading") or due:
            self._mining_record_read(state)
        return {"status": state["status"], "summary": state["summary"], "at": state["at"]}

    def _mining_record_read(self, state):
        config = getattr(self, "config", None) or {}
        journal_path = str(config.get("journal_path") or getattr(getattr(self, "watcher", None), "journal_path", "") or "")
        commander = str(config.get("active_commander_name") or getattr(self, "cmdr_name", "") or "") or None
        fid = str(config.get("active_commander_fid") or "") or None
        record = getattr(self, "_mining_record", None)
        if record is None:
            record = self._mining_record = MiningRecord()
        state["status"] = "reading" if state["summary"] is None else "refreshing"

        def work():
            try:
                summary = record.summary(journal_path, commander, fid)
            except Exception as exc:
                logging.warning("Mining record not read: %s", exc)
                summary = None

            def finish():
                state.update(status="ready", at=time.time(), summary=summary if summary is not None else state["summary"])
                self._schedule_html_dashboard_publish(immediate=True)
            self._ui_post(finish, key="html-mining-record")

        threading.Thread(target=work, name="MiningRecord", daemon=True).start()

    def _mining_income(self):
        store = getattr(self, "trading_store", None)
        if store is None:
            return mining_prices(())
        try:
            trades = store.query(
                "SELECT t.ts, t.commodity, t.count, t.price, t.total, n.name FROM trades t "
                "LEFT JOIN names n ON n.symbol = t.commodity "
                "WHERE t.kind = 'sell' AND COALESCE(t.avg_paid, 0) = 0 AND COALESCE(t.stolen, 0) = 0 ORDER BY t.ts")
        except Exception as exc:
            logging.debug("Mining income skipped: %s", exc)
            trades = ()
        return mining_prices(trades)

    # -- the page -------------------------------------------------------------------
    def _mining_extras(self):
        where = self._mining_where()
        income = self._mining_income()
        haul, limpets = self._mining_haul(income["prices"])
        rigs = None
        if callable(getattr(self, "api_rigs", None)) and where["mode"] in ("rhino", "srv", "foot", "planet"):
            try:
                rigs = self.api_rigs()
            except Exception as exc:
                logging.debug("Mining page rigs skipped: %s", exc)
        holds = self._rig_holds() if callable(getattr(self, "_rig_holds", None)) else []
        finder = self._html_profile_transient("_html_mining_ground", {"status": "ready", "detail": "", "results": []})
        sell = self._html_profile_transient("_html_mining_sell", {"status": "ready", "detail": "", "commodity": "", "results": []})
        options = self._trading_cargo_options() if callable(getattr(self, "_trading_cargo_options", None)) else {"radius": 50}
        return {
            "where": where, "holds": holds, "limpets": limpets, "haul": haul,
            "income": {"total": income["total"], "months": income["months"],
                       "prices": [{"name": name, **row} for name, row in
                                  sorted(income["prices"].items(), key=lambda item: -item[1]["credits"])]},
            "record": self._mining_record_view(),
            "rigs": rigs, "ground": self._mining_ground_here(where), "sites": self._mining_sites_here(where),
            "material_grounds": material_grounds(),
            "grounds": [{"key": key, "label": GROUND_LABELS.get(key, key)} for key in GROUND_SPANSH],
            "ring_materials": sorted(MINING_MATERIALS), "surface_materials": mining_material_catalogue(),
            "finder": {key: finder.get(key) for key in ("status", "detail", "results", "ground", "reference")},
            "sell": {key: sell.get(key) for key in ("status", "detail", "commodity", "results", "nearest", "radius")},
            "sell_radius": options.get("radius", 50),
            "srv_fuel": self._mining_srv_fuel(),
        }

    def _mining_srv_fuel(self):
        active = getattr(self, "_surface_vehicle_fuel_active", None)
        if not callable(active) or not active():
            return None
        percent = getattr(self, "_surface_fuel_percent", None)
        return {"tonnes": getattr(self, "current_surface_fuel_reservoir", None),
                "percent": percent() if callable(percent) else None}

    def api_mining_record(self):
        record = self._mining_record_view()
        income = self._mining_income()
        return {"status": record["status"], "read_at": record["at"] or None, "record": record["summary"],
                "income": {"total": income["total"], "months": income["months"],
                           "prices": [{"name": name, **row} for name, row in sorted(income["prices"].items())]}}

    # -- what the page asks for --------------------------------------------------------
    def _html_mining_operation(self, operation, payload):
        """The page's own operations; None for the ones the run handles."""
        if operation == "record_refresh":
            self._mining_record_view(refresh=True)
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "forget_rigs":
            clear = getattr(self, "_rig_clear_here", None)
            forgotten = bool(clear()) if callable(clear) else False
            self._schedule_html_dashboard_publish(immediate=True)
            return forgotten
        if operation in ("ring_clear", "ground_clear", "sell_clear"):
            return self._mining_clear(operation)
        if operation == "ground_search":
            return self._mining_ground_search(payload)
        if operation in ("ground_copy", "ground_open"):
            rows = (self._html_profile_transient("_html_mining_ground", {}).get("results") or [])
            index = _int(payload.get("result_index"), -1)
            if not 0 <= index < len(rows):
                return False
            if operation == "ground_copy":
                return self._html_copy_text(rows[index].get("system"))
            body_id = rows[index].get("body_id64")
            webbrowser.open_new_tab(f"https://spansh.co.uk/body/{body_id}" if body_id else "https://spansh.co.uk/bodies")
            return True
        if operation == "sell_search":
            return self._mining_sell_search(payload)
        if operation == "sell_copy":
            rows = self._html_profile_transient("_html_mining_sell", {}).get("results") or []
            index = _int(payload.get("result_index"), -1)
            return self._html_copy_text(rows[index].get("system")) if 0 <= index < len(rows) else False
        return None

    def _mining_clear(self, operation):
        """Done with a search: its results go, and one still running is
        dropped when it answers (a new generation)."""
        generation = time.time_ns()
        if operation == "ring_clear":
            self._html_profile_transient("_html_mining_tool_state", {}).update(
                ring_generation=generation, ring_status="ready", ring_detail="", ring_results=[])
        elif operation == "ground_clear":
            self._html_profile_transient("_html_mining_ground", {}).update(
                generation=generation, status="ready", detail="", results=[], ground="", reference="")
        else:
            self._html_profile_transient("_html_mining_sell", {}).update(
                generation=generation, status="ready", detail="", commodity="", results=[], nearest=[])
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _mining_ground_search(self, payload):
        reference = str(payload.get("reference") or getattr(self, "current_sys", "") or "").strip()[:140]
        ground = str(payload.get("ground") or "")
        if not reference or ground not in GROUND_SPANSH:
            return False
        max_distance = _int(payload.get("range"), 200, 1, 5000)
        gravity = _float(payload.get("gravity"))
        max_ls = _int(payload.get("max_ls"), 0, 0, 10_000_000) or None
        profile = get_active_profile(self.config)
        generation = time.time_ns()
        tool = self._html_profile_transient("_html_mining_ground", {})
        label = GROUND_LABELS.get(ground, ground)
        tool.update(generation=generation, status="working", results=[], ground=ground, reference=reference,
                    detail=f"Looking for {label} planets within {max_distance:,} ly of {reference}…")
        self._schedule_html_dashboard_publish(immediate=True)

        def work():
            try:
                rows = search_spansh_grounds(reference, ground, max_distance, gravity if gravity and gravity > 0 else None, max_ls)
                result, error = [{
                    "system": str(row.get("system_name") or "")[:140], "body": str(row.get("body_name") or "")[:180],
                    "volcanism": str(row.get("volcanism") or "")[:80], "gravity": _float(row.get("gravity")),
                    "distance": _float(row.get("distance_ly")), "arrival": _float(row.get("ls_distance")),
                    "body_id64": row.get("body_id64"),
                } for row in rows], None
            except Exception as exc:
                result, error = [], exc

            def finish():
                active = self._html_profile_transient("_html_mining_ground", {})
                if active.get("profile") != profile or active.get("generation") != generation:
                    return
                if error:
                    active.update(status="failed", results=[], detail=f"Spansh didn't answer: {error}")
                else:
                    active.update(status="ready", results=result,
                                  detail=f"{len(result):,} {label} planets you can land on, nearest first.")
                self._schedule_html_dashboard_publish(immediate=True)
            self._ui_post(finish, key="html-mining-ground")

        threading.Thread(target=work, name="HtmlMiningGround", daemon=True).start()
        return True

    def _mining_sell_search(self, payload):
        """Best payers for one mined commodity within your Sell cargo radius,
        and the nearest that will take it."""
        from voidcompass.services import spansh
        from voidcompass.trading import market as trade_market
        commodity = str(payload.get("commodity") or "").strip()[:80]
        system = str(getattr(self, "current_sys", "") or "")
        amount = _int(payload.get("amount"), 1, 1, 100_000)
        if not commodity or not system:
            return False
        options = self._trading_cargo_options() if callable(getattr(self, "_trading_cargo_options", None)) else {"radius": 50}
        profile = get_active_profile(self.config)
        generation = time.time_ns()
        tool = self._html_profile_transient("_html_mining_sell", {})
        tool.update(generation=generation, status="working", commodity=commodity, results=[], nearest=[],
                    radius=options.get("radius", 50),
                    detail=f"Finding who pays most for {amount:,} t of {commodity} within {options.get('radius', 50):,} ly…")
        self._schedule_html_dashboard_publish(immediate=True)

        def work():
            try:
                names = getattr(self, "_trading_spansh_names", None)
                if callable(names):
                    names()
                lookup = getattr(getattr(self, "trading_names", None), "spansh_name", None)
                name = lookup(commodity) if callable(lookup) else commodity
                choice = {"large_pad": bool(options.get("large")), "carriers": bool(options.get("carriers")),
                          "planetary": bool(options.get("planetary", True)), "radius": options.get("radius", 50)}
                best = trade_market.parse_commodity(
                    spansh.commodity_stations("sell", system, name, amount, size=10, sort="price", **choice), name, "sell")
                close = trade_market.parse_commodity(
                    spansh.commodity_stations("sell", system, name, amount, size=10, **choice), name, "sell")
                best.sort(key=lambda row: -row["price"])
                result, nearest, error = best[:10], sorted(close, key=lambda row: row.get("distance") or 0.0)[:5], None
            except Exception as exc:
                result, nearest, error = [], [], exc

            def finish():
                active = self._html_profile_transient("_html_mining_sell", {})
                if active.get("profile") != profile or active.get("generation") != generation:
                    return
                if error:
                    active.update(status="failed", results=[], nearest=[], detail=f"Spansh didn't answer: {error}")
                else:
                    active.update(status="ready", results=result, nearest=nearest,
                                  detail=f"{len(result)} buyers for {commodity} within {choice['radius']:,} ly." if result
                                  else f"Nobody within {choice['radius']:,} ly wants {amount:,} t of {commodity}.")
                self._schedule_html_dashboard_publish(immediate=True)
            self._ui_post(finish, key="html-mining-sell")

        threading.Thread(target=work, name="HtmlMiningSell", daemon=True).start()
        return True
