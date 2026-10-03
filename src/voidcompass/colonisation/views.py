"""Renderer-neutral colonisation models: the Construction Needs overlay and
the Colonisation tab's project rows. The overlay follows SrvSurvey's build
commodities panel: which projects it covers, need / carriers / hold per
commodity, what is assigned, and how many trips are left.
"""

from __future__ import annotations

import math

from voidcompass.colonisation import catalogue

# What the overlay shows besides need and hold (Overlay Studio).
OVERLAY_OPTION_DEFAULTS = {
    "colony_show_carriers": True,       # a column of linked carriers' cargo
    "colony_carrier_delta": False,      # carriers minus need, rather than their total
    "colony_collapse_covered": True,    # fold a category the carriers already cover
    "colony_highlight_almost": False,   # flag what one more trip from here completes
    "colony_inline_carriers": False,    # one HAVE column: the ship's count, else the carriers'
}


def overlay_options(config):
    return {key: bool((config or {}).get(key, default)) for key, default in OVERLAY_OPTION_DEFAULTS.items()}


def _cargo_counts(inventory):
    counts = {}
    for row in inventory or ():
        if isinstance(row, dict):
            name = catalogue.commodity_id(row.get("Name") or row.get("name"))
            counts[name] = counts.get(name, 0) + int(row.get("Count", row.get("count", 0)) or 0)
    return counts


def _project_header(project, current_address):
    header = f"{project.get('buildName') or 'Project'} · {catalogue.build_type_label(project.get('buildType'))}"
    system = str(project.get("systemName") or "")
    away = current_address is not None and str(project.get("systemAddress")) != str(current_address)
    return header, (system if away and system.casefold() not in header.casefold() else "")


def overlay_model(state, cmdr, docked=None, current_address=None, ship_cargo=(), capacity=0,
                  market_items=None, options=None):
    """The Construction Needs overlay, or None when there is nothing to show.

    ``docked``: {station_name, station_type, market_id, system_address,
    services} while docked. ``market_items``: commodity ids in stock at the
    docked market when its Market.json is current, else None.
    """
    options = {**OVERLAY_OPTION_DEFAULTS, **(options or {})}
    docked = docked or None
    ship = _cargo_counts(ship_cargo)
    capacity = max(0, int(capacity or 0))
    at_site = bool(docked and catalogue.is_construction_site(docked.get("station_name"), docked.get("services")))
    at_squadron_bank = bool(docked and "squadronbank" in {str(item).casefold() for item in docked.get("services") or ()})
    depot = state.last_depot if at_site else None

    if depot and depot.get("ConstructionComplete"):
        return {"complete": True, "header": catalogue.default_project_name(docked.get("station_name")), "at_site": True}

    projects = state.visible_projects()
    carrier_ids = {str(fc.get("marketId")) for project in projects for fc in project.get("linkedFC") or ()}
    header, subheader, names, warnings = f"{len(projects)} projects", "", [], []
    tracked = None
    if at_site:
        tracked = state.project_at(docked.get("system_address"), docked.get("market_id"))
        if tracked:
            projects = [tracked]
            carrier_ids = {str(fc.get("marketId")) for fc in tracked.get("linkedFC") or ()}
        else:
            projects = []
            carrier_ids = set(state.carriers)
            header = catalogue.default_project_name(docked.get("station_name"))
            warnings.append("Not a member of this project" if state.untracked_project else "Untracked project")
    elif state.primary_build_id and state.project(state.primary_build_id):
        primary = state.project(state.primary_build_id)
        projects = [primary]
        carrier_ids = {str(fc.get("marketId")) for fc in primary.get("linkedFC") or ()}

    if len(projects) == 1:
        header, subheader = _project_header(projects[0], current_address)
    elif len(projects) > 1:
        names = sorted(f"{row.get('buildName')} · {catalogue.build_type_label(row.get('buildType'))}" for row in projects)
    elif not at_site:
        return None
    if docked and str(docked.get("station_type") or "").casefold() == "fleetcarrier" and not state.has_carrier(docked.get("market_id")):
        warnings.append("Untracked fleet carrier")

    needs = state.needs(projects, cmdr)
    if at_site and depot:
        required = catalogue.depot_needs(depot.get("ResourcesRequired"))
    elif at_site and state.untracked_project:
        required = {catalogue.commodity_id(key): int(value or 0) for key, value in (state.untracked_project.get("commodities") or {}).items()}
    else:
        required = needs["commodities"]
    carriers = [state.carriers[key] for key in sorted(carrier_ids) if key in state.carriers]
    fc_cargo = state.carrier_cargo(carrier_ids)
    show_fc = bool(options["colony_show_carriers"] and fc_cargo)
    docked_at_linked_fc = bool(docked and state.has_carrier(docked.get("market_id")))
    pending = state.pending_diff if state.pending else {}

    def row_for(name, need):
        fc = fc_cargo.get(name, 0)
        have = ship.get(name, 0)
        row = {"id": name, "name": catalogue.commodity_name(name), "need": need, "ship": have,
               "fc": fc if show_fc else None, "fc_delta": (fc - need) if show_fc else None,
               "state": "", "check": "", "warn": False, "almost": False,
               "assigned": "me" if name in needs["assigned_me"] else "others" if name in needs["assigned_others"] else ""}
        if name in pending:
            row["state"] = "pending"
        elif have > need:
            row["state"], row["warn"] = "surplus", True
        elif have == need:
            row["state"], row["check"] = "surplus", "ship"
        elif docked and market_items is not None and market_items and name not in market_items and not at_site:
            row["state"] = "dim"
        if show_fc:
            if (options["colony_highlight_almost"] and docked and not at_site and not docked_at_linked_fc
                    and market_items is not None and name in market_items and fc < need and capacity > need - fc):
                row["almost"] = True
                row["state"] = "surplus" if have >= need - fc else "almost"
            if not row["check"] and (fc >= need or fc + have >= need):
                row["check"] = "fc"
        return row

    groups = []
    fc_counted = 0
    if at_site or at_squadron_bank:
        rows = [row_for(name, need) for name, need in sorted(required.items(), key=lambda item: catalogue.commodity_name(item[0]).casefold()) if need > 0]
        groups.append({"name": "", "collapsed": False, "rows": rows})
        fc_counted = sum(min(row["need"], fc_cargo.get(row["id"], 0)) for row in rows) if show_fc else 0
    else:
        by_category = {}
        for name, need in required.items():
            if need > 0:
                by_category.setdefault(catalogue.commodity_category(name), []).append(name)
        for category in sorted(by_category, key=str.casefold):
            members = sorted(by_category[category], key=lambda name: catalogue.commodity_name(name).casefold())
            covered = (options["colony_collapse_covered"] and show_fc and not docked_at_linked_fc
                       and all(fc_cargo.get(name, 0) >= required[name] and not ship.get(name) for name in members))
            fc_counted += sum(min(required[name], fc_cargo.get(name, 0)) for name in members) if show_fc else 0
            groups.append({"name": category, "collapsed": covered,
                           "rows": [] if covered else [row_for(name, required[name]) for name in members]})

    remaining = sum(int(value or 0) for value in required.values())
    trips = math.ceil(remaining / capacity) if capacity and remaining else (0 if capacity else None)
    fc_line = None
    if carriers:
        deficit = max(0, remaining - fc_counted)
        fc_line = {"count": len(carriers), "deficit": deficit,
                   "trips": math.ceil(deficit / capacity) if capacity else None,
                   "names": [str(fc.get("name") or fc.get("displayName") or fc.get("marketId")) for fc in carriers]}
    return {
        "complete": False, "at_site": at_site, "header": header, "subheader": subheader,
        "projects": names[:8], "warnings": warnings,
        "columns": {"fc": show_fc, "fc_delta": bool(show_fc and options["colony_carrier_delta"]),
                    "ship": bool(ship) or show_fc, "fc_count": len(carriers),
                    "inline": bool(show_fc and options["colony_inline_carriers"])},
        "groups": groups, "remaining": remaining, "trips": trips, "carriers": fc_line,
        "pending": bool(state.pending), "pinned": bool(needs["assigned_me"] or needs["assigned_others"]),
    }


def project_rows(state, capacity=0):
    """The tab's project list: progress, remaining and trips per project."""
    hidden = set(state.hidden_ids)
    rows = []
    for project in sorted(state.projects, key=lambda row: (str(row.get("systemName") or "").casefold(), str(row.get("buildName") or "").casefold())):
        max_need = int(project.get("maxNeed") or 0)
        remaining = int(project.get("sumNeed") if project.get("sumNeed") is not None
                        else sum(int(value or 0) for value in (project.get("commodities") or {}).values()))
        loading = str(project.get("buildType") or "").casefold() == catalogue.FC_LOADING
        rows.append({
            "build_id": project.get("buildId"), "name": project.get("buildName") or "Project",
            "type": catalogue.build_type_label(project.get("buildType")),
            "system": project.get("systemName") or "", "body": project.get("bodyName") or "",
            "max_need": max_need, "remaining": remaining,
            "progress": None if loading or not max_need else round(1 - remaining / max_need, 4),
            "trips": math.ceil(remaining / capacity) if capacity and remaining else None,
            "visible": project.get("buildId") not in hidden,
            "primary": project.get("buildId") == state.primary_build_id,
            "complete": bool(project.get("complete")),
            "architect": project.get("architectName") or "", "faction": project.get("factionName") or "",
            "commanders": sorted((project.get("commanders") or {}).keys(), key=str.casefold),
            "carriers": [fc.get("name") or fc.get("displayName") for fc in project.get("linkedFC") or ()],
        })
    return rows
