"""The status tiles (5.7.8): Where, Commander, Fuel, Carrier, Unsold and Data
across the top of every page, folding to one line, and the in-game route
under them. Outrider's tile row (github.com/weslocke/ED-Outrider, GPLv3), with
its small touches: "31 of 73 not visited", your last 20 arrivals as dots,
how old the unsold data is, and which outside services are in trouble.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from voidcompass.core import companion_features, ranks
from voidcompass.exploration import nearby
from voidcompass.exploration.galactic_regions import find_region
from voidcompass.outrider import fsd
from voidcompass.services import spansh

COLONIA = (-9530.5, -910.28125, 19808.125)
STREAK = 20


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _epoch(stamp):
    try:
        return datetime.strptime(str(stamp)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def _rank(cmdr_ranks, progress, kind):
    number = None
    for key in (kind, kind.casefold(), kind.lower()):
        if key in (cmdr_ranks or {}):
            number = cmdr_ranks[key]
            break
    percent = None
    for key in (kind, kind.casefold()):
        if key in (progress or {}):
            percent = progress[key]
            break
    title = ranks.name(kind, number) if number is not None else ""
    following = ranks.name(kind, int(number) + 1) if number is not None else ""
    return {"name": title, "percent": _num(percent), "next": following}


class DashboardStatusMixin:

    def _status_where(self):
        system = str(getattr(self, "current_sys", "") or "")
        coords = getattr(self, "current_coords", None)
        history = getattr(self, "travel_history", None)
        streak, previous, visit = [], None, None
        if history is not None:
            with history.lock:
                history._ensure_index()
                rows = history.rows[-STREAK - 1:]
                firsts = {key: value[1] for key, value in history._visits.items()}
                seen = history._visits.get(system.casefold())
            for row in rows[-STREAK:]:
                streak.append(1 if firsts.get(str(row[1]).casefold()) == str(row[0]) else 0)
            if len(rows) >= 2:
                previous = {"name": str(rows[-2][1]), "ly": _num(rows[-1][6])}
            visit = seen[0] if seen else None
        sol = math.dist(coords, (0, 0, 0)) if coords else None
        colonia = math.dist(coords, COLONIA) if coords else None
        region = find_region(*coords) if coords else None
        survey = getattr(self, "_survey_state", None) or {}
        near = (survey.get("nearby") or {}) if isinstance(survey, dict) else {}
        known = not_visited = None
        if near.get("results") and (near.get("centre") or {}).get("kind") == "here" \
                and str((near.get("centre") or {}).get("name") or "").casefold() == system.casefold():
            cache = survey.get("rows_cache")
            rows = cache[1] if cache else None
            if rows:
                known = len(rows)
                not_visited = sum(1 for row in rows if not row["visited"])
        return {"system": system, "body": str(getattr(self, "current_body_name", "") or ""),
                "region": region[1] if region else "", "sol": round(sol) if sol is not None else None,
                "colonia": round(colonia) if colonia is not None else None,
                "coords": [round(float(v), 2) for v in coords] if coords else None,
                "from": previous, "visit": visit, "streak": streak, "new": sum(streak),
                "known": known, "not_visited": not_visited, "radius": near.get("radius")}

    def _status_cmdr(self):
        ship = getattr(self, "cmdr_ship", None) or {}
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        max_range = None
        try:
            max_range = self._expedition_jump_range()
        except Exception:
            pass
        laden = None
        try:
            figures = fsd.fleet_figures(loadout) if loadout.get("Modules") else None
            cargo = sum(int(row.get("count") or row.get("Count") or 0) for row in getattr(self, "current_cargo_inventory", None) or ()
                        if isinstance(row, dict))
            if figures and figures.get("unladen"):
                laden = fsd.fleet_range(figures, cargo=cargo, fuel=_num(getattr(self, "current_fuel_main", None)))
        except Exception:
            laden = None
        cmdr_ranks = getattr(self, "cmdr_ranks", None) or {}
        progress = getattr(self, "cmdr_rank_progress", None) or {}
        return {"name": str(getattr(self, "cmdr_name", "") or self.config.get("active_commander_name") or ""),
                "credits": getattr(self, "cmdr_balance", None),
                "ship": str(ship.get("ship_name") or ship.get("user_ship_name") or ""),
                "ship_type": str(ship.get("ship_localised") or ship.get("ship") or ""),
                "max_range": round(max_range, 1) if max_range else None, "laden": round(laden, 1) if laden else None,
                "explorer": _rank(cmdr_ranks, progress, "Explore"),
                "exobiologist": _rank(cmdr_ranks, progress, "Exobiologist")}

    def _status_fuel(self):
        fuel = _num(getattr(self, "current_fuel_main", None))
        capacity = _num(getattr(self, "fuel_capacity_main", None))
        loadout = ((getattr(self, "companion_state", None) or {}).get("loadout") or {})
        jumps = None
        try:
            figures = fsd.fleet_figures(loadout) if loadout.get("Modules") else None
            if figures and fuel is not None:
                model = fsd.fuel_model({"unladen": figures.get("unladen"), "max_range": figures.get("max_range"),
                                        "booster_ly": figures.get("booster_ly"), "fsd": figures.get("fsd"),
                                        "max_fuel": figures.get("max_fuel")}, [])
                cargo = sum(int(row.get("count") or row.get("Count") or 0) for row in getattr(self, "current_cargo_inventory", None) or ()
                            if isinstance(row, dict))
                jumps = fsd.jumps_left(model, fuel, cargo)
        except Exception:
            jumps = None
        history = getattr(self, "travel_history", None)
        scoopable = since = None
        if history is not None:
            with history.lock:
                rows = history.rows[-STREAK:]
            classes = [str(row[5] or "") for row in rows if row[5]]
            if classes:
                scoopable = sum(1 for cls in classes if nearby.star_class(cls) in nearby.SCOOPABLE)
            scooped = getattr(self, "_last_scoop_at", None)
            if scooped:
                since = sum(1 for row in rows if (_epoch(row[0]) or 0) > scooped)
        own = {}
        try:
            own = self._fuel_from_jumps() if hasattr(self, "_fuel_from_jumps") else {}
        except Exception:
            own = {}
        return {"own": own, "fuel": round(fuel, 1) if fuel is not None else None, "capacity": capacity,
                "percent": round(fuel * 100 / capacity) if fuel is not None and capacity else None,
                "jumps": jumps[0] if jumps else None, "ly": jumps[1] if jumps else None,
                "scoopable": scoopable, "of": min(STREAK, len(rows)) if history is not None else None,
                "since_scoop": since}

    def _status_carrier(self):
        tracker = getattr(self, "carrier_tracker", None)
        carrier = tracker.display_carrier() if tracker is not None and hasattr(tracker, "display_carrier") else None
        if not carrier or not (carrier.get("name") or carrier.get("callsign")):
            return None
        here = str(carrier.get("system") or "").casefold() == str(getattr(self, "current_sys", "") or "").casefold()
        return {"name": str(carrier.get("name") or ""), "callsign": str(carrier.get("callsign") or ""),
                "kind": "SC" if carrier.get("carrier_type") == "SquadronCarrier" else "FC",
                "system": str(carrier.get("system") or ""), "here": here,
                "status": str(carrier.get("status") or ""), "destination": str(carrier.get("jump_destination") or ""),
                "fuel": carrier.get("fuel_level"), "fuel_capacity": carrier.get("fuel_capacity"),
                "balance": carrier.get("balance"), "jump_range": carrier.get("jump_range_curr"),
                "departure": str(carrier.get("jump_departure_time") or "")}

    def _status_unsold(self):
        companion = getattr(self, "companion_state", None) or {}
        carto = int(companion.get("unsold_exploration_cr") or 0)
        bio = companion_features.unsold_bio_value(companion)
        last = max(filter(None, (_epoch(companion.get("last_exploration_sale")), _epoch(companion.get("last_bio_sale")))),
                   default=None)
        days = round((time.time() - last) / 86400, 1) if last else None
        sell_here = []
        if getattr(self, "current_docked", False):
            services = " ".join(str(s).casefold() for s in getattr(self, "current_station_services", None) or ())
            if "exploration" in services or "cartographics" in services:
                sell_here.append("Universal Cartographics")
            if "vistagenomics" in services or "vista genomics" in services:
                sell_here.append("Vista Genomics")
        return {"total": carto + bio, "carto": carto, "bio": bio,
                "samples": int(companion.get("unsold_bio_samples") or 0), "days": days,
                "sell_here": sell_here, "station": str(getattr(self, "current_station_name", "") or "")}

    def _status_data(self):
        now = time.time()
        last = getattr(self, "last_journal_event_ts", None)
        states = {}
        try:
            states = self._html_service_states(now)
        except Exception:
            states = {}
        health = dict(getattr(spansh, "HEALTH", {}) or {})
        trouble = health.get("error_at") and (not health.get("ok_at") or health["error_at"] > health["ok_at"])
        return {"journal_at": round(last) if last else None,
                "spansh": {"state": "warn" if trouble else "live" if health.get("ok_at") else "idle",
                           "label": "TROUBLE" if trouble else "OK" if health.get("ok_at") else "NOT ASKED",
                           "error": health.get("error") if trouble else ""},
                "edsm": states.get("edsm") or {}, "inara": states.get("inara") or {},
                "eddn": {"state": "live" if self.config.get("eddn_market_upload_enabled", True) else "off",
                         "label": "ON" if self.config.get("eddn_market_upload_enabled", True) else "OFF"}}

    def _status_route_line(self):
        route = [row for row in getattr(self, "nav_route_entries", None) or () if isinstance(row, dict)]
        current = str(getattr(self, "current_sys", "") or "").casefold()
        index = next((i for i, row in enumerate(route) if str(row.get("StarSystem") or "").casefold() == current), -1)
        ahead = route[index + 1:] if route else []
        if not ahead:
            return self._status_plotted_line()
        total = 0.0
        previous = getattr(self, "current_coords", None)
        for row in ahead:
            pos = row.get("StarPos")
            if previous and pos:
                total += math.dist(previous, pos)
            previous = pos or previous
        chips = [{"name": str(row.get("StarSystem") or ""), "cls": nearby.star_class(row.get("StarClass")),
                  "scoop": nearby.star_class(row.get("StarClass")) in nearby.SCOOPABLE}
                 for row in ahead[:40]]
        to_scoop = next((i + 1 for i, chip in enumerate(chips) if chip["scoop"]), None)
        nxt = chips[0]
        return {"jumps": len(ahead), "ly": round(total), "chips": chips, "more": max(0, len(ahead) - len(chips)),
                "next": nxt["name"], "next_cls": nxt["cls"], "neutron": nxt["cls"] in ("N", "D", "DA", "DB", "DC", "DQ"),
                "to_scoop": to_scoop, "destination": str(ahead[-1].get("StarSystem") or ""), "source": "game"}

    def _status_plotted_line(self):
        """No route in the game: the one on PLOT ROUTE, stop by stop (5.7.8)."""
        plotted = getattr(self, "_route", lambda: None)()
        if not plotted or plotted.get("done_at"):
            return None
        rows = plotted.get("rows") or []
        current = str(getattr(self, "current_sys", "") or "").casefold()
        at = next((i for i, row in enumerate(rows) if str(row.get("system") or "").casefold() == current), None)
        if at is None:
            at = plotted.get("at") if isinstance(plotted.get("at"), int) else -1
        skipped = {i for i in plotted.get("skipped") or () if isinstance(i, int)}
        ahead = [row for i, row in enumerate(rows) if i > at and i not in skipped]
        if not ahead:
            return None
        total, previous = 0.0, getattr(self, "current_coords", None)
        for row in ahead:
            pos = row.get("coords")
            if previous and pos:
                total += math.dist(previous, pos)
            previous = pos or previous
        chips = [{"name": str(row.get("system") or ""), "cls": str(row.get("star_class") or ("N" if row.get("neutron") else "")),
                  "scoop": bool(row.get("scoopable"))} for row in ahead[:40]]
        to_scoop = next((i + 1 for i, chip in enumerate(chips) if chip["scoop"]), None)
        refuel = next((i + 1 for i, row in enumerate(ahead) if row.get("refuel")), None)
        nxt = chips[0]
        return {"jumps": sum(max(1, int(row.get("jumps") or 1)) for row in ahead), "ly": round(total), "chips": chips,
                "more": max(0, len(ahead) - len(chips)), "next": nxt["name"], "next_cls": nxt["cls"],
                "neutron": bool(ahead[0].get("neutron")), "to_scoop": refuel or to_scoop,
                "destination": str(rows[-1].get("system") or ""), "source": "plot",
                "label": str(plotted.get("label") or "Plot Route"), "stops": len(ahead)}

    def _status_tiles(self):
        # While the journal catches up at start, the replay walks through recent
        # systems: the tiles hold what they first showed until it's done.
        if getattr(self, "_startup_restore_active", False):
            frozen = getattr(self, "_status_tiles_frozen", None)
            if frozen is None:
                frozen = self._status_tiles_frozen = self._status_tiles_live()
            return frozen
        self._status_tiles_frozen = None
        return self._status_tiles_live()

    def _status_tiles_live(self):
        tiles = {}
        for key, build in (("where", self._status_where), ("cmdr", self._status_cmdr), ("fuel", self._status_fuel),
                           ("carrier", self._status_carrier), ("unsold", self._status_unsold), ("data", self._status_data),
                           ("route", self._status_route_line)):
            try:
                tiles[key] = build()
            except Exception:
                tiles[key] = None
        tiles["folded"] = bool(self.config.get("status_tiles_folded", False))
        return tiles
