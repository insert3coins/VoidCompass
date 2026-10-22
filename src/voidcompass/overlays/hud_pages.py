"""The Navigation HUD's pages (5.5.17): one overlay for everything.

With pages on, the HUD's lower half changes with what you're doing: the
route and survey while you travel, the next system while the drive charges,
the planet while you're on it, the rigs in the Rhino, the rock you just
prospected, your target in a fight, the station you're docked at, and so on.
The overlays each page covers can stay off while the HUD shows them.

Every page is made of the same few blocks the page draws (hero, stats,
bars, list, compass, dials, note), built here from the models the separate
overlays already use, so the HUD reads the same journal facts they do.
"""

from __future__ import annotations

PAGES = ("nav", "jump", "survey", "planet", "rhino", "mining", "combat", "station", "colony", "carrier", "trade",
         "powerplay")
LABELS = {"nav": "NAV", "jump": "JUMP", "survey": "SURVEY", "planet": "PLANET", "rhino": "RHINO", "mining": "MINING",
          "combat": "COMBAT", "station": "STATION", "colony": "COLONY", "carrier": "CARRIER", "trade": "TRADE",
          "powerplay": "POWER"}
# The overlays each page shows, which can stay off while the HUD does.
COVERS = {
    "jump": ("jump_info_hud",),
    "survey": ("survey_status_hud", "contact_scope_hud"),
    "planet": ("planet_materials_hud", "gravity_warning_hud", "ground_popup"),
    "rhino": ("rig_tracker_hud",),
    "mining": ("prospector_hud", "cargo_hud"),
    "combat": ("contact_scope_hud",),
    "station": ("station_info_hud",),
    "colony": ("colony_needs_hud",),
    "carrier": ("carrier_hud",),
    "trade": ("trade_route_hud",),
    "powerplay": ("powerplay_hud",),
}
# Off: the HUD as it always was. Auto: the page follows what you're doing.
# Manual: the page hotkey chooses, and it stays put.
MODES = ("off", "auto", "manual")
# A rock prospected this long ago still keeps the Mining page up.
PROSPECT_HOLD_S = 45.0

_COMBAT_MOTIONS = {"combat", "heavy_combat", "srv_threat", "interdiction", "interdicted", "capital_contact",
                   "unknown_contact"}
_JUMP_MOTIONS = {"fsd_charge", "hyper_charge", "jump", "fsd_lock"}
_SCAN_MOTIONS = {"scanner", "map", "phenomena", "exploration"}
_SURFACE_MOTIONS = {"orbital_approach", "glide", "surface_approach", "surface_hold", "landed", "surface_vehicle",
                    "on_foot", "settlement_area", "surface_departure", "srv_handbrake", "srv_turret",
                    "srv_drive_assist", "surface_station"}
_DOCK_MOTIONS = {"docked", "station", "docking_clearance", "docking_assist", "maintenance", "station_services"}


def pages_options(config):
    config = config or {}
    mode = str(config.get("hud_pages") or "off").casefold()
    return {
        "mode": mode if mode in MODES else "off",
        "takeover": bool(config.get("hud_pages_takeover", True)),
        "enabled": [page for page in PAGES if page == "nav" or bool(config.get(f"hud_page_{page}", True))],
    }


def covered_overlays(config):
    """The overlays the HUD shows for you right now (so they stay off)."""
    options = pages_options(config)
    if options["mode"] == "off" or not options["takeover"]:
        return set()
    return {attr for page in options["enabled"] for attr in COVERS.get(page, ())}


def pick_page(state, facts, enabled):
    """The page for this moment. ``state`` is the HUD's own state (motion,
    category); ``facts`` what else is known (docked, in the Rhino...)."""
    motion = str((state or {}).get("motion") or "")
    category = str((state or {}).get("category") or "")
    facts = facts or {}
    allowed = set(enabled or ())

    def first(*pages):
        return next((page for page in pages if page in allowed and facts.get(f"has_{page}", True)), None)

    if motion in _COMBAT_MOTIONS or category == "alert" and facts.get("target"):
        page = first("combat")
        if page:
            return page
    if motion in _JUMP_MOTIONS or motion.startswith("carrier_") and motion != "carrier_deck":
        page = first("carrier") if motion.startswith("carrier_") else first("jump")
        if page:
            return page
    if facts.get("docked") or motion in _DOCK_MOTIONS or motion == "carrier_deck":
        if facts.get("at_colony"):
            page = first("colony")
            if page:
                return page
        if facts.get("on_own_carrier") or motion == "carrier_deck":
            page = first("carrier")
            if page:
                return page
        page = first("station")
        if page:
            return page
    if facts.get("in_rhino") or facts.get("rigs_here"):
        page = first("rhino")
        if page:
            return page
    if motion in _SURFACE_MOTIONS or facts.get("on_planet"):
        page = first("planet")
        if page:
            return page
    if facts.get("prospecting") or motion == "asteroid_field":
        page = first("mining")
        if page:
            return page
    if motion in _SCAN_MOTIONS or category == "scan":
        page = first("survey")
        if page:
            return page
    if facts.get("trading"):
        page = first("trade")
        if page:
            return page
    return "nav"


def next_page(current, auto, available):
    """The page after ``current`` for the page hotkey: round ``available``
    (every page switched on), starting from ``auto`` and back to it."""
    pages = [page for page in PAGES if page in set(available or ()) or page == auto]
    ring = pages[pages.index(auto):] + pages[:pages.index(auto)] if auto in pages else pages
    if current not in ring:
        return ring[1] if len(ring) > 1 else auto
    return ring[(ring.index(current) + 1) % len(ring)]


# -- blocks ------------------------------------------------------------------------
def hero(title, value="", sub="", tone="hud"):
    return {"type": "hero", "title": str(title or ""), "value": str(value or ""), "sub": str(sub or ""), "tone": tone}


def stats(*items):
    return {"type": "stats", "items": [{"label": label, "value": str(value), "tone": tone}
                                      for label, value, tone in items if value not in (None, "")]}


def bars(items, columns=1):
    return {"type": "bars", "columns": columns, "items": [
        {"label": str(label), "value": str(value), "ratio": max(0.0, min(1.0, float(ratio or 0))), "tone": tone}
        for label, value, ratio, tone in items]}


# The HUD grows to fit its page, so a list shows it all, up to this many
# rows; only past that does it say "+n MORE".
LIST_ROWS = 10


def listing(items, more=0, title="", rows=LIST_ROWS):
    items = list(items)
    more = int(more or 0) + max(0, len(items) - rows)
    return {"type": "list", "title": title, "more": more, "items": [
        {"name": str(name), "detail": str(detail or ""), "value": str(value or ""), "tone": tone}
        for name, detail, value, tone in items[:rows]]}


def note(text, tone="dim"):
    return {"type": "note", "text": str(text or ""), "tone": tone}


def _page(page_id, title, *blocks, tone="hud"):
    return {"id": page_id, "label": LABELS.get(page_id, page_id.upper()), "title": title, "tone": tone,
            "blocks": [block for block in blocks if _shown(block)]}


def waiting_page(page_id):
    """A chosen page with nothing on it yet says so."""
    hints = {"jump": "SHOWS WHILE THE DRIVE CHARGES", "planet": "SHOWS NEAR A PLANET", "rhino": "SHOWS IN THE RHINO OR WITH RIGS OUT",
             "mining": "PROSPECT A ROCK TO FILL IT", "combat": "TARGET A SHIP TO FILL IT", "station": "SHOWS WHILE DOCKED",
             "colony": "SHOWS AT A CONSTRUCTION SITE", "carrier": "NEEDS YOUR CARRIER'S DATA",
             "trade": "PLAN A TRADE ROUTE TO FILL IT", "powerplay": "PLEDGE TO A POWER TO FILL IT",
             "survey": "SCAN A SYSTEM TO FILL IT"}
    return _page(page_id, LABELS.get(page_id, page_id.upper()), note(hints.get(page_id, "NOTHING TO SHOW YET"), "dim"), tone="hud")


def _shown(block):
    if not block:
        return False
    if block["type"] in {"hero", "note"}:
        return bool(block.get("title") or block.get("text"))
    return bool(block.get("items")) if "items" in block else True


def _ly(value):
    try:
        return f"{float(value):,.1f} LY"
    except (TypeError, ValueError):
        return ""


def _metres(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{value / 1000:,.1f} KM" if value >= 1000 else f"{value:,.0f} M"


def _credits(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if value >= 1e9:
        return f"{value / 1e9:,.2f} BN CR"
    if value >= 1e6:
        return f"{value / 1e6:,.1f} M CR"
    return f"{value:,.0f} CR"


def _short(name, system):
    name, system = str(name or ""), str(system or "")
    return name[len(system) + 1:].strip() if system and name.casefold().startswith(system.casefold() + " ") else name


# -- the pages -------------------------------------------------------------------------
def jump_page(model):
    if not model:
        return None
    star = model.get("star") or {}
    route = model.get("route") or {}
    phase = str(model.get("phase") or "")
    title = {"charging": "FRAME SHIFT CHARGING", "hyperspace": "IN WITCH SPACE", "arrival": "ARRIVED"}.get(phase, "NEXT JUMP")
    facts = [(item.get("label"), item.get("value"), line.get("tone") or "text")
             for line in model.get("lines") or () for item in line.get("items") or ()]
    return _page(
        "jump", title,
        hero(model.get("system"), _ly(route.get("jump_ly")), star.get("label") or "", star.get("tone") or "accent"),
        stats(("JUMP", f"{route['hop']} / {route['hops']}" if route.get("hops") else "", "text"),
              ("LEFT", route.get("remaining"), "text"),
              ("TO GO", _ly(route.get("total_ly")) if route.get("hops") else "", "text"),
              ("ROUTE ENDS", route.get("destination") if route.get("remaining") else "", "accent")),
        listing([(label, "", value, tone) for label, value, tone in facts]),
        tone=star.get("tone") or "accent",
    )


def survey_page(model, contacts=None):
    if not model and not contacts:
        return None
    model = model or {}
    system = str(model.get("system") or "")
    scanned, total = int(model.get("scanned") or 0), int(model.get("total") or 0)
    blocks = []
    if model.get("mode") == "body":
        body = model.get("body") or {}
        lo, hi = model.get("min_value") or 0, model.get("max_value") or 0
        blocks.append(hero(model.get("body_display") or body.get("name"), _credits(hi or lo),
                           " · ".join(str(part) for part in (body.get("class_label") or body.get("planet_class"),
                                                             body.get("atmosphere_label")) if part), "accent"))
        blocks.append(stats(("BIO", f"{body.get('organic_complete_count') or 0} / {body.get('bio_count')}" if body.get("bio_count") else "", "green"),
                            ("GEO", body.get("geo_count") or "", "yellow"),
                            ("GRAVITY", f"{float(body['gravity_g']):.2f} G" if body.get("gravity_g") is not None else "", "text"),
                            ("MAPPED", "YES" if body.get("dss_complete") else "NO" if body.get("landable") else "", "text")))
        rows = [(row.get("display_name") or row.get("name"), str(row.get("status") or row.get("kind") or "").upper(),
                 _credits(row.get("value")) if row.get("value") else "", "green" if row.get("kind") == "complete" else "text")
                for row in model.get("rows") or ()]
        blocks.append(listing(rows))
    else:
        rows = []
        for row in model.get("rows") or ():
            signals = " · ".join(part for part in (
                f"{row['bio_count']} BIO" if row.get("bio_count") else "", f"{row['geo_count']} GEO" if row.get("geo_count") else "",
                f"{row['mining_count']} MINE" if row.get("mining_count") else "",
                f"RHINO {str(row['rhino']).upper()}" if row.get("rhino") else "",
                "MAP IT" if row.get("needs_dss") and (row.get("bio_count") or row.get("geo_count")) else "") if part)
            value = row.get("max_value") or row.get("min_value") or 0
            if not (signals or value >= 300000 or row.get("recent_scan")):
                continue
            tone = ("green" if row.get("bio_count") and not row.get("bio_complete") else "yellow" if value >= 1000000
                    else "hud" if row.get("rhino") or row.get("mining_count") else "text")
            rows.append((_short(row.get("display_name") or row.get("name"), system), signals, _credits(value) if value else "", tone))
        # The system's name is on the line above: lead with what's in it.
        found = " · ".join(part for part in (
            f"{sum(int(row.get('bio_count') or 0) for row in model.get('rows') or ())} BIO",
            f"{sum(int(row.get('geo_count') or 0) for row in model.get('rows') or ())} GEO") if not part.startswith("0 "))
        worth = sum(int(row.get("max_value") or 0) for row in model.get("rows") or ())
        blocks.append(hero(f"{scanned} OF {total} BODIES" if total and model.get("total_known") else f"{scanned} BODIES",
                           f"UP TO {_credits(worth)}" if worth else "", found or "SCANNING", "accent"))
        if total and model.get("total_known"):
            blocks.append(bars([("SCANNED", f"{round(scanned / total * 100)}%", scanned / total, "accent")]))
        blocks.append(listing(rows, title="WORTH A LOOK"))
    signals = [(group.get("name"), "", group.get("count"), "red" if group.get("kind") in {"threat", "combat"} else "text")
               for group in (contacts or {}).get("groups") or ()]
    if signals and len(blocks) < 4:
        blocks.append(stats(*[(name.upper(), count, tone) for name, _detail, count, tone in signals[:4]]))
    return _page("survey", "SYSTEM SURVEY", *blocks, tone="accent")


def planet_page(body="", materials=None, target=None, sampling=None, gravity=None, threshold=None):
    materials = materials or {}
    details = materials.get("details") or {}
    name = materials.get("short_body") or body
    if not name and not target and not sampling:
        return None
    g = gravity if gravity is not None else details.get("gravity")
    heavy = g is not None and threshold and float(g) >= float(threshold)
    blocks = [hero(name or "SURFACE", f"{float(g):.2f} G" if g is not None else "",
                   " · ".join(part for part in (details.get("class"), "HEAVY GRAVITY" if heavy else "") if part),
                   "red" if heavy else "hud")]
    if target and target.get("state") == "OK":
        blocks.append({"type": "compass", "label": str(target.get("label") or "TARGET").upper(),
                       "distance": _metres(target.get("distance_m")), "relative": target.get("heading_delta"),
                       "detail": str(target.get("direction") or ""), "tone": "green"})
    if sampling and sampling.get("species"):
        progress = int(sampling.get("progress") or 0)
        clear = bool(sampling.get("clear"))
        minimum = sampling.get("min_distance_m")
        blocks.append(stats((str(sampling.get("species")).upper(), f"{progress} / 3", "green"),
                            ("NEXT SAMPLE", "CLEAR" if clear else _metres(sampling.get("colony_m")) + " AWAY", "green" if clear else "yellow"),
                            ("NEAREST", _metres(minimum) if minimum is not None else "", "text")))
    found = [(row.get("name"), "RARE" if row.get("rare") else "", f"{row.get('percent', 0):.1f}%", "yellow" if row.get("rare") else "text")
             for row in materials.get("materials") or ()]
    if found:
        blocks.append(bars([(name, value, min(1.0, float(value.rstrip('%')) / 30.0), tone) for name, _rare, value, tone in found[:8]],
                           columns=2))
    elif details.get("mining_locations"):
        blocks.append(note(f"{details['mining_locations']} MINING LOCATIONS ON THIS BODY", "yellow"))
    # For the Rhino: what this kind of ground tends to hold, best first.
    best = [row for row in materials.get("best_materials") or () if row.get("material")]
    if best:
        sites = details.get("mining_locations")
        blocks.append(listing([(str(row["material"]), f"{float(row.get('pct') or 0):.0f}% OF SITES",
                                _credits(row.get("median")) + " / T" if row.get("median") else "", "yellow" if index == 0 else "text")
                               for index, row in enumerate(best[:3])],
                              title=f"RHINO GROUND{f' · {sites} MINING SITES' if sites else ''}"))
    return _page("planet", "ON THE SURFACE", *blocks, tone="red" if heavy else "hud")


def rhino_page(rig_model, holds=(), signals=0, spacing_m=78.0, warn_m=3500.0):
    if not rig_model:
        return None
    from voidcompass.overlays.rig_tracker import rig_advice
    advice = rig_advice(rig_model.get("slots"), spacing_m, warn_m)
    slots = rig_model.get("slots") or ()
    order = list(rig_model.get("order") or ())
    dials = []
    for row in slots:
        if not row.get("tracked"):
            dials.append({"slot": row["slot"], "state": "empty"})
            continue
        state = "here" if row.get("here") else "next" if order and row["slot"] == order[0] else "out"
        dials.append({"slot": row["slot"], "state": state, "distance": _metres(row.get("distance_m")),
                      "relative": row.get("relative")})
    tracked = sum(1 for row in slots if row.get("tracked"))
    nearest = next((row for row in slots if row.get("nearest")), None)
    blocks = []
    for row in advice["too_far"]:
        blocks.append(note(f"RIG {row['slot']} {row['distance'] / 1000:.1f} KM AWAY · LOST AT 5 KM", "red"))
    if advice["ready"]:
        blocks.append(note(f"COLLECT RIG {', '.join(str(slot) for slot in advice['ready'])}: IT'S HAD TWO MINUTES", "accent"))
    elif advice["too_close"] is not None and tracked < 6:
        blocks.append(note(f"TOO CLOSE TO RIG {advice['too_close']} FOR ANOTHER · {spacing_m:.0f} M APART", "yellow"))
    blocks.insert(0, {"type": "dials", "items": dials})
    hold_bars = [(row["name"], f"{row['used']} / {row['capacity']} T", row["used"] / row["capacity"] if row.get("capacity") else 0,
                  "red" if row.get("free") == 0 else "green") for row in holds or () if row.get("capacity")]
    if hold_bars:
        blocks.append(bars(hold_bars, columns=2))
    blocks.append(stats(("RIGS OUT", tracked, "text"),
                        ("COLLECT NEXT", f"RIG {order[0]}" if order else "", "hud"),
                        ("NEAREST", f"RIG {nearest['slot']} · {_metres(nearest.get('distance_m'))}" if nearest else "", "text"),
                        ("MINING SITES", signals or "", "yellow")))
    if not tracked:
        blocks.append(note(rig_model.get("hint") or "PRESS THE RIG KEY AS YOU DEPLOY EACH RIG", "dim"))
    return _page("rhino", "RHINO MINING", *blocks, tone="hud")


def mining_page(prospect=None, cargo=None):
    if not prospect and not cargo:
        return None
    blocks = []
    if prospect and prospect.get("materials"):
        core = prospect.get("core_material")
        remaining = prospect.get("remaining")
        blocks.append(hero(prospect.get("content_label") or "ROCK", f"MOTHERLODE · {core}".upper() if core else "",
                           f"{remaining:.0f}% LEFT" if remaining is not None else "", prospect.get("content_tone") or "hud"))
        blocks.append(bars([(row["name"], f"{row['proportion']:.1f}%", row["proportion"] / 50.0,
                             "yellow" if index == 0 else "text") for index, row in enumerate(prospect["materials"][:8])],
                           columns=2))
    if cargo and cargo.get("capacity_known"):
        used, capacity = cargo.get("total") or 0, cargo.get("capacity") or 0
        blocks.append(bars([("HOLD", f"{used} / {capacity} T", used / capacity if capacity else 0,
                             "red" if cargo.get("free") == 0 else "green")]))
    refined = (prospect or {}).get("refined") or ()
    if refined:
        blocks.append(stats(*[(row["name"].upper(), f"{row['tonnes']} T", "green") for row in refined[:4]]))
    if not blocks:
        return None
    return _page("mining", "MINING", *blocks, tone=(prospect or {}).get("content_tone") or "hud")


# ShipTargeted reveals more as your scanner works on the target: the pilot at
# stage 1, shields and hull at 2, faction, legal status, bounty and the
# subsystem you've picked at 3. Each stage repeats what came before.
_STAGE_FIELDS = {
    1: (("pilot", "PilotName_Localised", str), ("rank", "PilotRank", str)),
    2: (("shields", "ShieldHealth", float), ("hull", "HullHealth", float)),
    3: (("faction", "Faction", str), ("legal_status", "LegalStatus", str), ("bounty", "Bounty", float),
        ("subsystem", "Subsystem_Localised", str), ("subsystem_health", "SubsystemHealth", float), ("power", "Power", str)),
}
_HOSTILE = ("WANTED", "ENEMY", "HOSTILE", "WARRANT", "HUNTER")


def ship_name(symbol, localised=None):
    """The ship's name: the journal's own, else its symbol made readable
    (Ship_Localised is missing for anaconda, python, mandalay...)."""
    if localised:
        return str(localised)
    words = str(symbol or "").replace("_", " ").split()
    return " ".join(word.upper() if word in {"mkii", "mkiii", "mkiv", "mkv", "nx"} else word.capitalize() for word in words)


def read_target(raw, previous=None):
    """Your target from a ShipTargeted event, or None when the lock is lost.
    A different ship, or the same type with another pilot, starts afresh;
    fields a stage no longer reports (a subsystem let go) are dropped."""
    if not raw.get("TargetLocked") or not raw.get("Ship"):
        return None
    symbol = str(raw.get("Ship")).casefold()
    pilot = raw.get("PilotName_Localised") or raw.get("PilotName")
    previous = previous or {}
    same = previous.get("symbol") == symbol and (not pilot or previous.get("pilot") in (None, str(pilot)))
    target = dict(previous) if same else {}
    try:
        stage = int(raw.get("ScanStage") or 0)
    except (TypeError, ValueError):
        stage = 0
    target.update(symbol=symbol, ship=ship_name(symbol, raw.get("Ship_Localised")), stage=max(stage, target.get("stage", 0)))
    for level, fields in _STAGE_FIELDS.items():
        if stage < level:
            continue
        for key, field, kind in fields:
            value = raw.get(field)
            if value in (None, ""):
                target.pop(key, None)
                continue
            try:
                target[key] = kind(value)
            except (TypeError, ValueError):
                target.pop(key, None)
    return target


def combat_page(target=None, session=None, contacts=None):
    if not target and not session and not (contacts or {}).get("threat"):
        return None
    blocks = []
    if target:
        legal = str(target.get("legal_status") or "").upper()
        wanted = any(word in legal for word in _HOSTILE)
        blocks.append(hero(target.get("ship") or "TARGET", _credits(target.get("bounty")) if target.get("bounty") else "",
                           " · ".join(part for part in (target.get("pilot"), str(target.get("rank") or "").upper(), legal) if part),
                           "red" if wanted else "hud"))
        health = [(label, f"{value:.0f}%", value / 100.0, "accent" if label == "SHIELDS" else "hud")
                  for label, value in (("SHIELDS", target.get("shields")), ("HULL", target.get("hull")),
                                       (str(target.get("subsystem") or "").upper(), target.get("subsystem_health")))
                  if label and value is not None]
        if health:
            blocks.append(bars(health, columns=min(3, len(health))))
        if target.get("faction"):
            blocks.append(note(str(target["faction"]).upper(), "dim"))
    if session and session.get("active"):
        blocks.append(stats(("KILLS", session.get("kills") or 0, "text"),
                            ("BOUNTIES", _credits(session.get("bounty_cr")) if session.get("bounty_cr") else "", "green"),
                            ("BONDS", _credits(session.get("bond_cr")) if session.get("bond_cr") else "", "green"),
                            ("THARGOIDS", session.get("ax_kills") or "", "red")))
    threats = [(row.get("name") or row.get("label"), row.get("detail") or "", f"THREAT {row['threat']}" if row.get("threat") else "",
                "red" if (row.get("threat") or 0) >= 3 else "yellow")
               for row in (contacts or {}).get("rows") or () if row.get("threat")]
    if threats:
        blocks.append(listing(threats, title="THREATS HERE"))
    return _page("combat", "COMBAT", *blocks, tone="red")


def station_page(model=None, trade_step=None):
    if not model or not model.get("station"):
        return None
    services = [row for row in model.get("core_services") or () if row.get("available")]
    data = [(row["label"], row.get("service") or "", row["value"], "green" if row.get("available") else "yellow")
            for row in model.get("data_rows") or ()]
    blocks = [hero(model.get("station"), model.get("pads") or "", model.get("type") or "", "accent"),
              note(model.get("authority") or "", "dim")]
    if trade_step and not trade_step.get("done") and trade_step.get("here"):
        blocks.append(stats(("TRADE ROUTE", str(trade_step.get("action") or "").upper(), "green")))
    if data:
        blocks.append(listing(data, title="TO SELL HERE"))
    if services:
        blocks.append(note(" · ".join(str(row.get("label") or "").upper() for row in services[:8]), "text"))
    return _page("station", model.get("badge") or "DOCKED", *blocks, tone="accent")


def colony_page(model=None):
    if not model:
        return None
    if model.get("complete"):
        return _page("colony", "CONSTRUCTION", hero(model.get("header") or "PROJECT", "COMPLETE", "", "green"), tone="green")
    rows = [row for group in model.get("groups") or () for row in group.get("rows") or ()]
    rows.sort(key=lambda row: -int(row.get("need") or 0))
    needs = [(row["name"], f"{row['need']:,} T" + (f" · {row['ship']} ABOARD" if row.get("ship") else ""),
              (row.get("ship") or 0) / row["need"] if row.get("need") else 1, "green" if row.get("ship") else "hud")
             for row in rows[:6]]
    return _page("colony", "CONSTRUCTION NEEDS",
                 hero(model.get("header") or "PROJECT", f"{int(model.get('remaining') or 0):,} T",
                      f"{model['trips']} TRIPS" if model.get("trips") else model.get("subheader") or "", "hud"),
                 bars(needs, columns=2), tone="hud")


def carrier_page(model=None):
    if not model or not model.get("name"):
        return None
    blocks = [hero(model.get("name"), model.get("callsign") or "", model.get("location") or "", "accent")]
    if model.get("movement_visible"):
        blocks.append(stats((model.get("movement_label") or "JUMP", model.get("movement_value"), model.get("movement_tone") or "hud"),
                            ("", model.get("movement_detail") or "", "text")))
    if model.get("fuel") is not None:
        blocks.append(bars([("TRITIUM", f"{model['fuel']:,.0f} / {model.get('fuel_capacity') or 1000:,.0f} T",
                             model.get("fuel_ratio") or 0, model.get("fuel_tone") or "green")]))
    blocks.append(stats(("STATUS", model.get("badge") or "", model.get("badge_tone") or "text"),
                        ("RANGE", _ly(model.get("range")) if model.get("range") is not None else "", "text"),
                        ("CARGO", f"{model['cargo']:,.0f} T" if model.get("cargo") is not None else "", "text"),
                        ("FREE", f"{model['free']:,.0f} T" if model.get("free") is not None else "", "text")))
    return _page("carrier", model.get("carrier_type") or "FLEET CARRIER", *blocks, tone="accent")


def trade_page(step=None, cargo=None):
    if not step:
        return None
    if step.get("done"):
        return _page("trade", "TRADE ROUTE", hero("ROUTE COMPLETE", _credits(step.get("profit")), "PROFIT", "green"), tone="green")
    blocks = [hero(step.get("station") or "STATION", _credits(step.get("expected")),
                   f"{step.get('system') or ''} · {_ly(step.get('distance'))}".strip(" ·"), "green"),
              stats(("LEG", f"{step.get('hop')} / {step.get('hops')}", "text"),
                    ("NOW", "BUY" if step.get("phase") == "buy" else "SELL", "hud"),
                    ("MADE SO FAR", _credits(step.get("profit")) if step.get("profit") else "", "green")),
              note(str(step.get("action") or "").upper(), "text")]
    if cargo and cargo.get("capacity_known"):
        used, capacity = cargo.get("total") or 0, cargo.get("capacity") or 0
        blocks.append(bars([("HOLD", f"{used} / {capacity} T", used / capacity if capacity else 0, "green")]))
    for warning in step.get("warnings") or ():
        blocks.append(note(str(warning).upper(), "yellow"))
    return _page("trade", "TRADE ROUTE", *blocks, tone="green")


def powerplay_page(model=None):
    if not model or not model.get("active"):
        return None
    objective = model.get("objective") or {}
    blocks = [hero(model.get("power"), f"RANK {model['rank']}" if model.get("rank") is not None else "",
                   f"{model.get('cycle_merits', 0):,} MERITS THIS CYCLE", "hud")]
    if objective.get("title"):
        current, target = int(objective.get("current") or 0), max(1, int(objective.get("target") or 1))
        blocks.append(bars([(objective["title"], f"{current:,} / {target:,}", current / target, "hud")]))
    blocks.append(stats(("SYSTEM", model.get("controlling_power") or "", "text"),
                        ("STATE", str(model.get("system_state") or "").upper(), "text"),
                        ("COLLECTED", model.get("cargo_collected") or "", "text"),
                        ("DELIVERED", model.get("cargo_delivered") or "", "text")))
    return _page("powerplay", "POWERPLAY", *blocks, tone="hud")

