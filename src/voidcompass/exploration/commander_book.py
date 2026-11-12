"""The commander's books (5.7.8): one pass over the journal for the CMDR page's
fleet, stored modules, missions, Community Goals, vouchers, sessions, earnings
and ring hotspots. The folds are ED-Outrider's (outrider/commander.py,
github.com/weslocke/ED-Outrider, GPLv3); the earnings follow its rule that only
ore you mined yourself counts as mining income. Pure: hand it the events.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from voidcompass.exploration import journal_events
from voidcompass.outrider import commander as cmdr

EXTRA = frozenset({"SellExplorationData", "MultiSellExplorationData", "SellOrganicData", "MarketSell", "MarketBuy",
                   "RedeemVoucher", "MissionCompleted", "CommunityGoalReward", "SearchAndRescue", "PowerplaySalary",
                   "Docked", "Location", "FSDJump", "CarrierJump", "SupercruiseExit", "SupercruiseEntry", "Undocked",
                   "Embark", "Disembark", "LaunchSRV", "DockSRV", "Statistics", "Rank", "Progress"})
EVENTS = frozenset(cmdr.EVENTS) | EXTRA
journal_events.register(EVENTS)
KINDS = ("exploration", "exobiology", "trade", "mining", "bounties", "bonds", "missions", "other")


def _money(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def read(events, hotspot_names=None):
    """Fold every event: {folds, loadouts, sessions, sales, stats, hotspots}."""
    hotspot_names = hotspot_names or {}
    folds = {key: None for key in cmdr.FOLD_EVENTS}
    loadouts = {}
    here = {"system": None, "station": None, "market": None, "login": None}
    ship = None
    srv = False
    mined = defaultdict(int)
    logins, current = [], None
    sales = []
    stats = None
    ring = None
    stints = []
    stint = None
    id64 = None

    def end_stint():
        nonlocal stint
        if stint and (stint["tons"] or stint["prospected"]):
            stints.append(stint)
        stint = None

    for raw in events:
        name = raw.get("event")
        ts = str(raw.get("timestamp") or "")
        if not name or not ts:
            continue
        if name == "LoadGame":
            current = {"login_ts": ts, "commander": raw.get("Commander"), "ship": raw.get("ShipName") or raw.get("Ship_Localised") or raw.get("Ship")}
            logins.append(current)
            here["login"] = ts
        elif name in ("Location", "FSDJump", "CarrierJump"):
            here["system"] = raw.get("StarSystem")
            id64 = raw.get("SystemAddress")
            if name != "Location" or not raw.get("Docked"):
                here.update(station=raw.get("StationName") if raw.get("Docked") else None,
                            market=raw.get("MarketID") if raw.get("Docked") else None)
            end_stint()
            ring = None
        elif name == "Docked":
            here.update(system=raw.get("StarSystem") or here["system"], station=raw.get("StationName"), market=raw.get("MarketID"))
            end_stint()
        elif name == "Undocked":
            here.update(station=None, market=None)
        elif name == "Loadout":
            ship = raw.get("ShipName") or raw.get("Ship_Localised") or raw.get("Ship")
            sid = raw.get("ShipID")
            if sid is not None:
                loadouts[sid] = {"ship_id": sid, "name": raw.get("ShipName") or "", "ship_type": raw.get("Ship") or "",
                                 "ident": raw.get("ShipIdent") or "", "ts": ts,
                                 "value": (_money(raw.get("HullValue")) + _money(raw.get("ModulesValue"))) or None,
                                 "loadout": json.dumps(raw)}
        elif name in ("LaunchSRV", "Disembark"):
            srv = name == "LaunchSRV" or bool(raw.get("SRV"))
        elif name in ("DockSRV", "Embark"):
            srv = False if name == "DockSRV" else bool(raw.get("SRV"))
        elif name == "SupercruiseExit":
            end_stint()
            ring = raw.get("Body") if raw.get("BodyType") == "PlanetaryRing" else None
            if ring:
                stint = {"ring": ring, "system": raw.get("StarSystem") or here["system"], "start": ts, "end": ts,
                         "tons": 0, "prospected": 0, "high": 0, "refined": defaultdict(int)}
        elif name == "SupercruiseEntry":
            end_stint()
            ring = None
        elif name == "Statistics":
            stats = raw

        for key in cmdr.FOLD_OF.get(name, ()):
            try:
                folds[key] = cmdr.apply(key, folds[key], raw, here)
            except Exception:
                pass

        sold_mined = 0
        if name == "MiningRefined":
            what = str(raw.get("Type_Localised") or raw.get("Type") or "?")
            key = re.sub(r"^\$|_name;$", "", str(raw.get("Type") or "")).casefold()
            mined[key] += 1
            if stint is not None:
                stint["tons"] += 1
                stint["refined"][what] += 1
                stint["end"] = ts
        elif name == "ProspectedAsteroid" and stint is not None:
            stint["prospected"] += 1
            stint["high"] += "High" in str(raw.get("Content") or "")
            stint["end"] = ts
        elif name == "MarketSell":
            key = str(raw.get("Type") or "").casefold()
            count = _money(raw.get("Count"))
            ours = min(count, mined.get(key, 0))
            if ours:
                mined[key] -= ours
                total = _money(raw.get("TotalSale"))
                sold_mined = round(total * ours / count) if count else 0
        if current is not None:
            current.setdefault("acts", {})
            try:
                cmdr.activity_apply(current["acts"], raw, srv=srv, mined=sold_mined,
                                    place={"id64": id64, "system": here["system"], "body": ring}, ship=ship)
            except Exception:
                pass

        sale = None
        where = {"system": here["system"], "station": here["station"], "ship": ship}
        if name in ("SellExplorationData", "MultiSellExplorationData"):
            sale = {"kind": "exploration", "amount": _money(raw.get("TotalEarnings") or raw.get("BaseValue")),
                    "detail": f"{len(raw.get('Discovered') or raw.get('Systems') or [])} systems"}
        elif name == "SellOrganicData":
            species = [{"name": s.get("Species_Localised") or s.get("Species"), "value": _money(s.get("Value")) + _money(s.get("Bonus"))}
                       for s in raw.get("BioData") or () if isinstance(s, dict)]
            sale = {"kind": "exobiology", "amount": sum(s["value"] for s in species), "detail": f"{len(species)} samples", "species": species}
        elif name == "MarketSell":
            total = _money(raw.get("TotalSale"))
            paid = _money(raw.get("AvgPricePaid")) * _money(raw.get("Count"))
            commodity = raw.get("Type_Localised") or raw.get("Type")
            if sold_mined:
                sales.append({"ts": ts, "kind": "mining", "amount": sold_mined, "detail": str(commodity), **where})
            rest = total - sold_mined
            if rest > 0:
                profit = rest - round(paid * (rest / total)) if total else rest
                if profit:
                    sale = {"kind": "trade", "amount": profit, "detail": f"{commodity} (profit)"}
        elif name == "RedeemVoucher":
            kind = {"bounty": "bounties", "CombatBond": "bonds"}.get(raw.get("Type"), "other")
            sale = {"kind": kind, "amount": _money(raw.get("Amount")), "detail": str(raw.get("Type") or "")}
        elif name == "MissionCompleted":
            sale = {"kind": "missions", "amount": _money(raw.get("Reward")), "detail": str(raw.get("LocalisedName") or raw.get("Name") or "")}
        elif name in ("CommunityGoalReward", "SearchAndRescue", "PowerplaySalary"):
            sale = {"kind": "other", "amount": _money(raw.get("Reward") or raw.get("Amount")), "detail": name}
        if sale and sale["amount"]:
            sales.append({"ts": ts, **sale, **where})
    end_stint()
    sessions = []
    for login in reversed(logins):
        row = {"login_ts": login["login_ts"], "commander": login.get("commander"), "ship": login.get("ship"), **(login.get("acts") or {})}
        try:
            session = cmdr.session(row)
        except Exception:
            session = None
        if session:
            sessions.append(session)
    loadout_rows = sorted(loadouts.values(), key=lambda row: row["ts"], reverse=True)
    return {"folds": folds, "loadouts": loadout_rows, "sessions": sessions, "sales": sales, "stats": stats,
            "hotspots": hotspots(stints, sales, hotspot_names)}


def hotspots(stints, sales, names=None):
    """Every ring you've mined: stints, the high-content share of your prospects,
    best tons an hour, credits an hour at your average mined-ore price, last visit."""
    names = names or {}
    mined_income = sum(s["amount"] for s in sales if s["kind"] == "mining")
    mined_tons = sum(stint["tons"] for stint in stints) or 1
    per_ton = mined_income / mined_tons if mined_income else 0
    rings = {}
    from voidcompass.outrider import ts_seconds
    for stint in stints:
        key = stint["ring"]
        entry = rings.setdefault(key, {"ring": key, "system": stint["system"], "stints": 0, "tons": 0, "prospected": 0, "high": 0,
                                       "best_tph": None, "last": stint["end"], "refined": defaultdict(int), "hotspot": names.get(key) or ""})
        entry["stints"] += 1
        entry["tons"] += stint["tons"]
        entry["prospected"] += stint["prospected"]
        entry["high"] += stint["high"]
        entry["last"] = max(entry["last"], stint["end"])
        for what, n in stint["refined"].items():
            entry["refined"][what] += n
        try:
            hours = max(600.0, ts_seconds(stint["end"]) - ts_seconds(stint["start"])) / 3600
        except (TypeError, ValueError):
            hours = None
        # A stint shorter than ten minutes counts as ten: a few quick tons aren't a rate.
        if hours and stint["tons"] >= 10:
            tph = stint["tons"] / hours
            entry["best_tph"] = max(entry["best_tph"] or 0, round(tph, 1))
    out = []
    for entry in rings.values():
        entry["hit_rate"] = round(100 * entry["high"] / entry["prospected"]) if entry["prospected"] else None
        entry["cr_h"] = round(entry["best_tph"] * per_ton) if entry["best_tph"] and per_ton else None
        entry["refined"] = dict(sorted(entry["refined"].items(), key=lambda kv: -kv[1]))
        out.append(entry)
    out.sort(key=lambda entry: entry["last"], reverse=True)
    return out


def earnings(sales, period=None):
    """Earnings for a period ("all", "2026", "2026-11"): totals by kind, a monthly
    series, the sales, where you sold most, species that paid most, each ship's."""
    period = str(period or "all")
    rows = [sale for sale in sales if period == "all" or sale["ts"].startswith(period)]
    totals = {kind: 0 for kind in KINDS}
    months = defaultdict(lambda: {kind: 0 for kind in KINDS})
    stations, species, ships = defaultdict(int), defaultdict(int), defaultdict(int)
    for sale in rows:
        totals[sale["kind"]] += sale["amount"]
        months[sale["ts"][:7]][sale["kind"]] += sale["amount"]
        if sale.get("station"):
            stations[f"{sale['station']} · {sale.get('system') or ''}"] += sale["amount"]
        if sale.get("ship"):
            ships[str(sale["ship"])] += sale["amount"]
        for item in sale.get("species") or ():
            species[str(item["name"])] += item["value"]
    top = lambda counter, n=10: [{"name": name, "amount": amount} for name, amount in sorted(counter.items(), key=lambda kv: -kv[1])[:n]]
    years = sorted({sale["ts"][:4] for sale in sales}, reverse=True)
    month_list = sorted({sale["ts"][:7] for sale in sales}, reverse=True)
    return {"period": period, "total": sum(totals.values()), "totals": totals,
            "months": [{"month": month, **values} for month, values in sorted(months.items())],
            "sales": sorted(rows, key=lambda sale: sale["ts"], reverse=True)[:1500], "count": len(rows),
            "stations": top(stations), "species": top(species), "ships": top(ships), "kinds": list(KINDS),
            "periods": ["all", *years, *month_list[:24]]}
