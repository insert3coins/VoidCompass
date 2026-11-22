"""The Materials page (5.8.4): what you hold, what it's for, and what your
wishlists still need, on foot and for your ships. In the data the two are
"odyssey" (on foot) and "horizons" (ships), as the game's own journal names them.

Everything here is plain data in and out. The deck keeps the state in the
commander's engineer_materials file:

    locker     {"shiplocker": {symbol: n}, "backpack": {symbol: n}}
    raw/manufactured/encoded   {symbol: {"name", "count"}}   (the Materials event)
    engineers  {name: {"progress", "rank", "rank_progress"}}  (EngineerProgress)
    wishlists  {"odyssey": {"lists": [...], "selected": id}, "horizons": {...}}
    loadouts   the Odyssey loadout designs; suit_loadouts the game's own
    ship_builds the ship builder's saved builds; ship_loadout the last Loadout
    fleet      {ShipID: its latest Loadout} for every ship you own (saved as ship_fleet.json)
    goals     community goals seen, with their history
"""
from __future__ import annotations

import math
import re
import time
import uuid
from functools import lru_cache

from voidcompass.engineering import materials_reference as R
from voidcompass.engineering.engineering_data import GRADE_CAP, MATERIALS, convertible, material_info, material_source_hint

LIST_LIMIT = 30          # wishlists per game
ITEM_LIMIT = 200         # items per wishlist
BUILD_LIMIT = 60         # saved ship builds
LOADOUT_LIMIT = 40       # Odyssey loadout designs
GOAL_POINTS = 400        # history kept per community goal

SUIT_FAMILIES = {"tacticalsuit": "Dominator", "explorationsuit": "Artemis", "utilitysuit": "Maverick"}
WEAPON_MAKERS = {"Karma": "Kinematic Armaments", "TK": "Takada", "Manticore": "Manticore"}
# What each on-foot mod does to the numbers the loadout designer shows.
MOD_EFFECTS = {
    "weapon_clipsize": {"clip": 1.5}, "weapon_range": {"range": 1.5}, "weapon_headshotdamage": {"headshot": 1.5},
    "suit_increasedammoreserves": {"ammo": 1.5}, "suit_increasedbatterycapacity": {"battery": 1.5},
    "suit_increasedshieldregen": {"shield_regen": 1.5}, "suit_improvedjumpassist": {},
    "suit_increasedsprintduration": {}, "suit_improvedradar": {}, "suit_increasedo2capacity": {"oxygen": 2.0},
    "suit_backpackcapacity": {"items": 2, "components": 2, "data": 2},
}


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(value, limit=80):
    return " ".join(str(value or "").split())[:limit]


def _new_id():
    return uuid.uuid4().hex[:10]


# -- reference -------------------------------------------------------------

def suit_family(symbol):
    """'tacticalsuit_class3' -> ('tacticalsuit', 3)."""
    symbol = str(symbol or "").lower()
    match = re.match(r"([a-z]+suit)(?:_class(\d))?", symbol)
    if not match:
        return symbol, 0
    return match.group(1), _int(match.group(2), 1 if match.group(1) != "flightsuit" else 0)


def weapon_family(symbol):
    """'wpn_m_assaultrifle_kinetic_fauto' -> itself (weapons keep one symbol per model)."""
    return str(symbol or "").lower()


def weapon_maker(name):
    first = str(name or "").split(" ")[0]
    return WEAPON_MAKERS.get(first, first)


@lru_cache(maxsize=1)
def suit_models():
    out = {}
    for symbol, row in R.SUITS.items():
        family, grade = suit_family(symbol)
        if family not in SUIT_FAMILIES:
            continue
        model = out.setdefault(family, {"key": family, "name": row["name"], "kind": "suit", "maker": "Remlok",
                                        "primary": row["primary"], "secondary": row["secondary"], "grades": {}})
        model["grades"][grade] = row["stats"]
    return out


@lru_cache(maxsize=1)
def weapon_models():
    return {symbol: {"key": symbol, "name": row["name"], "kind": "weapon", "maker": weapon_maker(row["name"]),
                     "primary": row["primary"], "damage_type": row["damage_type"], "class": row["class"],
                     "fire_mode": row["fire_mode"], "grades": {i + 1: g for i, g in enumerate(row["grades"])}}
            for symbol, row in R.WEAPONS.items()}


def equipment(key):
    return suit_models().get(key) or weapon_models().get(key)


def upgrade_recipe(kind, maker, grade):
    for row in R.SUIT_WEAPON_UPGRADES:
        if row["kind"] == kind and row["grade"] == grade and (kind == "suit" or row["maker"] == maker):
            return row
    return None


def mod_recipe(kind, fdname, maker=""):
    rows = [row for row in R.ONFOOT_MODS if row["kind"] == kind and row["fdname"] == fdname]
    return next((row for row in rows if row["maker"] == maker), None) or next(
        (row for row in rows if row["maker"] == "All"), rows[0] if rows else None)


def mods_for(kind, maker=""):
    """The mods an item of this kind (and maker) can take, one row each."""
    seen = {}
    for row in R.ONFOOT_MODS:
        if row["kind"] != kind or (row["maker"] not in ("All", maker) and kind == "weapon"):
            continue
        if row["fdname"] not in seen or row["maker"] == maker:
            seen[row["fdname"]] = row
    return sorted(seen.values(), key=lambda row: row["name"])


@lru_cache(maxsize=1)
def ship_blueprints():
    """{module: {blueprint: {"fdname", "grades": {grade: {"ingredients", "engineers"}}}}}"""
    out = {}
    for row in R.SHIP_BLUEPRINTS:
        entry = out.setdefault(row["module"], {}).setdefault(row["name"], {"fdname": row["fdname"], "fdnames": [], "grades": {}})
        # One blueprint made for several sizes of module (Support Focused, Extended) has a game name per size.
        if row["fdname"] not in entry["fdnames"]:
            entry["fdnames"].append(row["fdname"])
        entry["grades"][row["grade"]] = {"ingredients": row["ingredients"], "engineers": row["engineers"],
                                         **({"pending": True} if row.get("pending") else {}),
                                         **({"coins": row["coins"]} if row.get("coins") else {})}
    return out


@lru_cache(maxsize=1)
def experimentals():
    out = {}
    for row in R.EXPERIMENTALS:
        out.setdefault(row["fdname"], {**row, "modules": list(row["modules"])})
    return out


@lru_cache(maxsize=1)
def engineers():
    """Every engineer with the work they do: on-foot mods, or ship blueprints and their best grade."""
    out = {}
    for row in R.ENGINEERS:
        out[row["name"]] = {**row, "mods": [], "blueprints": {}}
    for row in R.ONFOOT_MODS:
        for name in row["engineers"]:
            if name in out and row["name"] not in out[name]["mods"]:
                out[name]["mods"].append(row["name"])
    for module, blueprints in ship_blueprints().items():
        for name, entry in blueprints.items():
            for grade, recipe in entry["grades"].items():
                for engineer in recipe["engineers"]:
                    if engineer in out:
                        label = f"{module}: {name}"
                        out[engineer]["blueprints"][label] = max(grade, out[engineer]["blueprints"].get(label, 0))
    return out


@lru_cache(maxsize=1)
def uses():
    """symbol -> what it's used for: [{"game", "label"}], each once."""
    out = {}

    def add(symbol, game, label):
        rows = out.setdefault(symbol, [])
        if not any(row["label"] == label for row in rows):
            rows.append({"game": game, "label": label})

    for row in R.SUIT_WEAPON_UPGRADES:
        what = "Suit" if row["kind"] == "suit" else f"{row['maker']} weapon"
        for item in row["ingredients"]:
            add(item["symbol"], "odyssey", f"{what} upgrade G{row['grade']}")
    for row in R.ONFOOT_MODS:
        for item in row["ingredients"]:
            add(item["symbol"], "odyssey", f"{row['name']} ({row['kind']} mod)")
    # On-foot engineers ask for items to meet them or to give a referral.
    names = sorted(((row["name"].casefold(), symbol) for symbol, row in R.MICRORESOURCES.items()), key=lambda pair: -len(pair[0]))
    for engineer in R.ENGINEERS:
        if not engineer["odyssey"]:
            continue
        for field, what in (("meeting", "to meet"), ("unlock", "referral")):
            text = str(engineer.get(field) or "").casefold()
            for name, symbol in names:
                if name in text:
                    add(symbol, "odyssey", f"{engineer['name']} ({what})")
                    text = text.replace(name, "")
    for row in R.SHIP_BLUEPRINTS:
        for item in row["ingredients"]:
            add(item["symbol"], "horizons", f"{row['module']}: {row['name']}")
    for row in R.EXPERIMENTALS:
        for item in row["ingredients"]:
            add(item["symbol"], "horizons", f"Experimental: {row['name']}")
    for row in R.TECH_BROKER:
        for item in row["ingredients"]:
            add(item["symbol"], "horizons", f"Tech broker: {row['name']}")
    for row in R.SYNTHESIS:
        for item in row["ingredients"]:
            add(item["symbol"], "horizons", f"Synthesis: {row['name']} ({row['level']})")
    return out


@lru_cache(maxsize=1)
def reference():
    """The page's fixed tables, sent once (GET /api/data/materials-reference)."""
    horizons = [{"symbol": symbol, "name": row["name"], "category": row["category"], "family": row["family"],
                 "grade": row["grade"], "cap": GRADE_CAP.get(row["grade"] or 0, 0)}
                for symbol, row in MATERIALS.items()]
    return {
        "micro": R.MICRORESOURCES, "upgrades": R.SUIT_WEAPON_UPGRADES, "mods": R.ONFOOT_MODS,
        "suits": suit_models(), "weapons": weapon_models(), "mod_effects": MOD_EFFECTS,
        "engineers": engineers(), "horizons": horizons, "blueprints": ship_blueprints(),
        "experimentals": experimentals(), "broker": R.TECH_BROKER, "synthesis": R.SYNTHESIS,
        "permits": R.PERMITS, "uses": uses(),
        "hints": {symbol: material_source_hint(symbol) for symbol in MATERIALS}, "buildings": BUILDINGS,
    }


# -- what you hold ---------------------------------------------------------

def odyssey_have(state):
    """symbol -> count across the ship locker and the backpack."""
    locker = (state or {}).get("locker") or {}
    out = {}
    for where in ("shiplocker", "backpack"):
        for symbol, count in (locker.get(where) or {}).items():
            out[symbol] = out.get(symbol, 0) + _int(count)
    return out


def horizons_have(state):
    out = {}
    for category in ("raw", "manufactured", "encoded"):
        for symbol, item in ((state or {}).get(category) or {}).items():
            out[str(symbol).lower()] = _int(item.get("count") if isinstance(item, dict) else item)
    # Your ship's cargo: technology broker unlocks also ask for commodities (osmium, Thargoid parts).
    for symbol, count in ((state or {}).get("cargo") or {}).items():
        out.setdefault(str(symbol).lower(), _int(count))
    return out


def locker_from_event(rows_by_group):
    """ShipLocker/Backpack contents ({"Items": [...], "Components": [...], ...}) -> {symbol: count}."""
    out = {}
    for group in ("Items", "Components", "Data", "Consumables"):
        for item in rows_by_group.get(group) or ():
            symbol = str(item.get("Name") or "").lower()
            if symbol:
                out[symbol] = out.get(symbol, 0) + _int(item.get("Count"))
    return out


# -- wishlists -------------------------------------------------------------

def _wish_state(state, game):
    lists = state.setdefault("wishlists", {}).setdefault(game, {"lists": [], "selected": ""})
    lists.setdefault("lists", [])
    if not lists["lists"]:
        first = {"id": _new_id(), "name": "Wishlist", "items": []}
        lists["lists"].append(first)
        lists["selected"] = first["id"]
    if not any(row["id"] == lists.get("selected") for row in lists["lists"]):
        lists["selected"] = lists["lists"][0]["id"]
    return lists


def wishlist(state, game, list_id=""):
    lists = _wish_state(state, game)
    wanted = list_id or lists["selected"]
    return next((row for row in lists["lists"] if row["id"] == wanted), None)


def item_need(game, item):
    """{symbol: count} one wishlist item needs, and its credits (Odyssey mods cost some)."""
    need, credits = {}, 0
    qty = max(1, min(99, _int(item.get("qty"), 1)))
    if game == "odyssey":
        model = equipment(item.get("target"))
        if model is None:
            return need, credits
        if item.get("type") == "upgrade":
            for grade in range(max(1, _int(item.get("from"), 1)) + 1, min(5, _int(item.get("grade"), 5)) + 1):
                recipe = upgrade_recipe(model["kind"], model["maker"], grade)
                for ingredient in (recipe or {}).get("ingredients") or ():
                    need[ingredient["symbol"]] = need.get(ingredient["symbol"], 0) + ingredient["count"] * qty
        elif item.get("type") == "mod":
            recipe = mod_recipe(model["kind"], item.get("mod"), model["maker"])
            for ingredient in (recipe or {}).get("ingredients") or ():
                need[ingredient["symbol"]] = need.get(ingredient["symbol"], 0) + ingredient["count"] * qty
            credits = (recipe or {}).get("credits", 0) * qty
        return need, credits
    kind = item.get("type")
    rows = []
    if kind == "blueprint":
        entry = ship_blueprints().get(item.get("module"), {}).get(item.get("name"))
        done = item.get("done") or {}
        for grade, recipe in sorted(((entry or {}).get("grades") or {}).items()):
            if _int(item.get("from"), 0) < grade <= _int(item.get("grade"), 5):
                # Rolls left at this grade: every module's, less the ones the journal saw you make.
                left = max(0, rolls_at(item, grade) * qty - _int(done.get(str(grade))))
                for ingredient in recipe["ingredients"]:
                    need[ingredient["symbol"]] = need.get(ingredient["symbol"], 0) + ingredient["count"] * left
        return need, credits
    elif kind == "experimental":
        entry = experimentals().get(item.get("fdname"))
        rows = [(ingredient, 1) for ingredient in (entry or {}).get("ingredients") or ()]
    elif kind == "broker":
        entry = next((row for row in R.TECH_BROKER if row["fdname"] == item.get("fdname") and row["name"] == item.get("name", row["name"])), None)
        rows = [(ingredient, 1) for ingredient in (entry or {}).get("ingredients") or ()]
    elif kind == "synthesis":
        entry = next((row for row in R.SYNTHESIS if row["name"] == item.get("name") and row["level"] == item.get("level")), None)
        rows = [(ingredient, 1) for ingredient in (entry or {}).get("ingredients") or ()]
    for ingredient, times in rows:
        need[ingredient["symbol"]] = need.get(ingredient["symbol"], 0) + ingredient["count"] * times * qty
    return need, credits


def rolls_at(item, grade):
    rolls = item.get("rolls") or {}
    return max(0, min(20, _int(rolls.get(str(grade), rolls.get(grade, grade)), grade)))


def item_label(game, item):
    if game == "odyssey":
        model = equipment(item.get("target")) or {"name": item.get("target") or "?"}
        if item.get("type") == "upgrade":
            return f"{model['name']} to G{_int(item.get('grade'), 5)}"
        recipe = mod_recipe(model.get("kind", ""), item.get("mod"), model.get("maker", ""))
        return f"{model['name']}: {(recipe or {}).get('name') or item.get('mod')}"
    kind = item.get("type")
    if kind == "blueprint":
        grades = f"G{_int(item.get('from'), 0) + 1}-{_int(item.get('grade'), 5)}" if _int(item.get("from"), 0) + 1 < _int(item.get("grade"), 5) else f"G{_int(item.get('grade'), 5)}"
        return f"{item.get('module')}: {item.get('name')} {grades}"
    if kind == "experimental":
        return f"Experimental: {(experimentals().get(item.get('fdname')) or {}).get('name') or item.get('fdname')}"
    if kind == "broker":
        return f"Tech broker: {item.get('name') or item.get('fdname')}"
    if kind == "synthesis":
        return f"Synthesis: {item.get('name')} ({item.get('level')})"
    return str(kind or "?")


def _info(game, symbol):
    if game == "odyssey":
        row = R.MICRORESOURCES.get(symbol) or {}
        return {"symbol": symbol, "name": row.get("name") or symbol.title(), "kind": row.get("kind") or "",
                "grade": 0, "category": row.get("kind") or ""}
    row = MATERIALS.get(symbol)
    if row is None:
        micro = R.MICRORESOURCES.get(symbol)
        if micro:
            return {"symbol": symbol, "name": micro["name"], "kind": micro["kind"], "grade": 0, "category": micro["kind"]}
        name, category = R.NAMES.get(symbol) or (symbol.replace("_", " ").title(), "commodity")
        return {"symbol": symbol, "name": name, "kind": category, "grade": 0, "category": category}
    return {"symbol": symbol, "name": row["name"], "kind": row["category"], "grade": row["grade"],
            "category": row["category"], "family": row["family"]}


def trades(need, have):
    """Horizons only: material trader swaps that cover what's short, from what
    the wishlist doesn't need. [{"for", "covers", "from", "spend"}]"""
    out = []
    spare = {symbol: count - need.get(symbol, 0) for symbol, count in have.items()}
    for symbol, wanted in sorted(need.items()):
        short = wanted - have.get(symbol, 0)
        target = MATERIALS.get(symbol)
        if short <= 0 or target is None or target["family"] in ("unknown", "special", "guardian", "thargoid"):
            continue
        for candidate in sorted((row for row in MATERIALS.values() if row["family"] == target["family"] and row["symbol"] != symbol),
                                key=lambda row: -(spare.get(row["symbol"], 0) * (3 ** max(0, row["grade"] - target["grade"])))):
            surplus = spare.get(candidate["symbol"], 0)
            gain = convertible(surplus, candidate["grade"], target["grade"])
            if gain <= 0:
                continue
            covers = min(gain, short)
            if candidate["grade"] > target["grade"]:
                spend = math.ceil(covers / (3 ** (candidate["grade"] - target["grade"])))
            else:
                spend = covers * (6 ** (target["grade"] - candidate["grade"]))
            spare[candidate["symbol"]] = surplus - spend
            out.append({"for": target["name"], "covers": covers, "from": candidate["name"], "spend": spend})
            short -= covers
            if short <= 0:
                break
    return out


def summary(state, game, list_id=""):
    """A wishlist worked out: each item and whether it's ready, every material
    with need/have/missing, credits, trades (Horizons) and progress."""
    chosen = wishlist(state, game, list_id)
    have = odyssey_have(state) if game == "odyssey" else horizons_have(state)
    if chosen is None:
        return None
    total, credits, items = {}, 0, []
    for item in chosen.get("items") or ():
        need, cost = item_need(game, item)
        visible = item.get("visible", True)
        if visible:
            for symbol, count in need.items():
                total[symbol] = total.get(symbol, 0) + count
            credits += cost
        wanted = sum(need.values())
        items.append({**item, "label": item_label(game, item), "need": need, "credits": cost,
                      "ready": bool(need) and all(have.get(symbol, 0) >= count for symbol, count in need.items()),
                      "progress": round(100 * sum(min(have.get(symbol, 0), count) for symbol, count in need.items()) / wanted) if wanted else 100})
    rows = []
    for symbol, count in total.items():
        rows.append({**_info(game, symbol), "need": count, "have": have.get(symbol, 0),
                     "missing": max(0, count - have.get(symbol, 0))})
    rows.sort(key=lambda row: (row["missing"] == 0, row["kind"], -(row.get("grade") or 0), row["name"]))
    need_units = sum(row["need"] for row in rows)
    got_units = sum(min(row["need"], row["have"]) for row in rows)
    return {"id": chosen["id"], "name": chosen["name"], "items": items, "materials": rows, "credits": credits,
            "progress": round(100 * got_units / need_units) if need_units else 0,
            "complete": bool(rows) and all(row["missing"] == 0 for row in rows),
            "trades": trades(total, have) if game == "horizons" else []}


def wishlist_index(state, game):
    lists = _wish_state(state, game)
    return {"selected": lists["selected"],
            "lists": [{"id": row["id"], "name": row["name"], "count": len(row.get("items") or ())} for row in lists["lists"]]}


def _clean_item(game, item):
    item = dict(item or {})
    out = {"id": _text(item.get("id"), 16) or _new_id(), "type": _text(item.get("type"), 20),
           "qty": max(1, min(99, _int(item.get("qty"), 1))), "visible": bool(item.get("visible", True))}
    if game == "odyssey":
        out["target"] = _text(item.get("target"), 60)
        if equipment(out["target"]) is None or out["type"] not in ("upgrade", "mod"):
            return None
        if out["type"] == "upgrade":
            out["from"] = max(1, min(4, _int(item.get("from"), 1)))
            out["grade"] = max(out["from"] + 1, min(5, _int(item.get("grade"), 5)))
        else:
            out["mod"] = _text(item.get("mod"), 60)
            if mod_recipe(equipment(out["target"])["kind"], out["mod"]) is None:
                return None
        return out
    if out["type"] == "blueprint":
        out["module"], out["name"] = _text(item.get("module"), 60), _text(item.get("name"), 80)
        entry = ship_blueprints().get(out["module"], {}).get(out["name"])
        if entry is None:
            return None
        out["from"] = max(0, min(4, _int(item.get("from"), 0)))
        out["grade"] = max(out["from"] + 1, min(5, _int(item.get("grade"), 5)))
        # A grade whose materials aren't published yet would look ready with nothing to collect.
        if any(entry["grades"].get(grade, {}).get("pending") for grade in range(out["from"] + 1, out["grade"] + 1)):
            return None
        rolls = item.get("rolls") or {}
        out["rolls"] = {str(g): max(0, min(20, _int(rolls.get(str(g)), g))) for g in range(1, 6) if str(g) in rolls}
        out["slot"] = _text(item.get("slot"), 60)
        done = item.get("done") or {}
        out["done"] = {str(g): max(0, min(99, _int(done.get(str(g))))) for g in range(1, 6) if _int(done.get(str(g)))}
    elif out["type"] == "experimental":
        out["fdname"] = _text(item.get("fdname"), 60)
        if out["fdname"] not in experimentals():
            return None
        out["module"] = _text(item.get("module"), 60)
    elif out["type"] == "broker":
        out["fdname"], out["name"] = _text(item.get("fdname"), 80), _text(item.get("name"), 80)
        if not any(row["fdname"] == out["fdname"] for row in R.TECH_BROKER):
            return None
    elif out["type"] == "synthesis":
        out["name"], out["level"] = _text(item.get("name"), 60), _text(item.get("level"), 20)
        if not any(row["name"] == out["name"] and row["level"] == out["level"] for row in R.SYNTHESIS):
            return None
    else:
        return None
    return out


def wishlist_operation(state, game, operation, payload):
    """Change a wishlist; True when something changed."""
    if game not in ("odyssey", "horizons"):
        return False
    lists = _wish_state(state, game)
    chosen = wishlist(state, game, _text(payload.get("list_id"), 16))
    if operation == "wish_select":
        wanted = _text(payload.get("list_id"), 16)
        if any(row["id"] == wanted for row in lists["lists"]):
            lists["selected"] = wanted
            return True
        return False
    if operation == "wish_new":
        if len(lists["lists"]) >= LIST_LIMIT:
            return False
        row = {"id": _new_id(), "name": _text(payload.get("name"), 40) or f"Wishlist {len(lists['lists']) + 1}", "items": []}
        lists["lists"].append(row)
        lists["selected"] = row["id"]
        return True
    if chosen is None:
        return False
    if operation == "wish_rename":
        name = _text(payload.get("name"), 40)
        if name:
            chosen["name"] = name
        return bool(name)
    if operation == "wish_delete":
        lists["lists"] = [row for row in lists["lists"] if row["id"] != chosen["id"]]
        _wish_state(state, game)
        return True
    if operation == "wish_add":
        added = 0
        for raw in payload.get("items") or [payload.get("item")]:
            item = _clean_item(game, raw)
            if item is None or len(chosen["items"]) >= ITEM_LIMIT:
                continue
            item["id"] = _new_id()
            chosen["items"].append(item)
            added += 1
        return bool(added)
    item_id = _text(payload.get("item_id"), 16)
    item = next((row for row in chosen["items"] if row["id"] == item_id), None)
    if operation == "wish_remove":
        before = len(chosen["items"])
        chosen["items"] = [row for row in chosen["items"] if row["id"] != item_id]
        return len(chosen["items"]) != before
    if operation == "wish_clear":
        chosen["items"] = []
        return True
    if item is None:
        return False
    if operation == "wish_toggle":
        item["visible"] = not item.get("visible", True)
        return True
    if operation == "wish_edit":
        merged = _clean_item(game, {**item, **(payload.get("item") or {}), "id": item["id"]})
        if merged is None:
            return False
        item.clear()
        item.update(merged)
        return True
    if operation == "wish_done":
        # Crafted: take it off the list (the game's own events take the materials).
        chosen["items"] = [row for row in chosen["items"] if row["id"] != item_id]
        return True
    return False


# -- share codes (a wishlist or a design, copied as text) -------------------

def share_code(kind, payload):
    import base64
    import json
    raw = json.dumps({"v": 1, "kind": kind, "data": payload}, separators=(",", ":")).encode("utf-8")
    import zlib
    return "VCMAT-" + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


# A ship build's share code (5.8.4): only the plan, one short line a fitted slot.
#   line 1: ship key, armour, rolls, name
#   a slot: its index, module, blueprint, grade, experimental, its own rolls
#   H line (a hull from an import): name, symbol, core sizes, hardpoints, internals, figures
# Your ship's own engineered figures and empty slots stay out.
_MODULE_KIND = {"standard": "s", "hardpoints": "h", "internal": "i"}
_HULL_FIGURES = ("hullMass", "speed", "boost", "minthrust", "boostEnergy", "baseShieldStrength", "baseArmour", "hardness",
                 "heatCapacity", "masslock", "reserveFuelCapacity", "crew")


def _clean(value, limit=60):
    return " ".join(str(value or "").replace("\t", " ").replace("|", " ").split())[:limit]


def build_code(build):
    import base64
    import zlib
    # Since 5.8.4.1 the head also says how many slots and armour grades the hull had (older readers ignore them).
    head = [_clean(build.get("ship")), str(_int(build.get("bulkhead"))), str(_int(build.get("roll"), 100)), _clean(build.get("name"), 40)]
    if build.get("layout") is not None:
        head += [str(_int(build.get("layout"))), str(_int(build.get("armourGrades")))]
    lines = ["\t".join(head)]
    for index, slot in enumerate(build.get("slots") or ()):
        module = str(slot.get("module") or "")
        if not module:
            continue
        kind, _, ident = module.partition(":")
        roll = slot.get("roll")
        if roll is not None and _int(roll) == _int(build.get("roll"), 100):
            roll = None     # the build's own rolls: left out, read back the same
        # Since 5.8.4.2 a module switched off says so (a 7th field older readers ignore).
        lines.append("\t".join([str(index), _MODULE_KIND.get(kind, kind) + ident, _clean(slot.get("bp")), str(_int(slot.get("grade")) or ""),
                               _clean(slot.get("special")), "" if roll is None else str(_int(roll)), "0" if slot.get("off") else ""]).rstrip("\t"))
    # Since 5.8.4.2 the armour's engineering, on a line of its own (older readers skip it).
    armour = build.get("armourEng") or {}
    if armour.get("bp") or armour.get("special"):
        roll = armour.get("roll")
        lines.append("\t".join(["A", _clean(armour.get("bp")), str(_int(armour.get("grade")) or ""), _clean(armour.get("special")),
                                "" if roll is None or _int(roll) == _int(build.get("roll"), 100) else str(_int(roll))]).rstrip("\t"))
    hull = build.get("hull") or {}
    if hull:
        slots = hull.get("slots") or {}
        figures = ",".join(f"{key}={hull[key]:g}" for key in _HULL_FIGURES if isinstance(hull.get(key), (int, float)) and hull.get(key))
        lines.append("\t".join(["H", _clean(hull.get("name"), 40), _clean(hull.get("symbol")),
                                 ",".join(str(_int(size)) for size in slots.get("standard") or ()),
                                 ",".join(f"{_int(row.get('class'))}:{_clean(row.get('jname'))}" for row in slots.get("hardpoints") or ()),
                                 ",".join(f"{_int(row.get('class'))}:{_clean(row.get('jname'))}:{_clean(row.get('name'))}" for row in slots.get("internal") or ()),
                                 figures]))
    # VCB2: raw deflate against a fixed dictionary of the names a build uses (build_code_dict).
    from voidcompass.engineering.build_code_dict import VCB2_DICTIONARY
    packer = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, VCB2_DICTIONARY)
    packed = packer.compress("\n".join(lines).encode("utf-8")) + packer.flush()
    return "VCB2-" + base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")


def read_build_code(text):
    import base64
    import zlib
    code = str(text or "").strip()
    if code[:5] not in ("VCB1-", "VCB2-") or len(code) > 20_000:
        return None
    body = code[5:]
    try:
        packed = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        if code.startswith("VCB2-"):
            from voidcompass.engineering.build_code_dict import VCB2_DICTIONARY
            unpacker = zlib.decompressobj(-15, VCB2_DICTIONARY)
            text = unpacker.decompress(packed, 1 << 18)
        else:
            text = zlib.decompress(packed, bufsize=1 << 18)
        lines = text.decode("utf-8").split("\n")
    except Exception:
        return None
    head = lines[0].split("\t") + ["", "", "", "", "", ""]
    build = {"id": _new_id(), "ship": head[0], "bulkhead": _int(head[1]), "roll": _int(head[2], 100), "name": head[3] or "Shared build"}
    if head[4].isdigit():
        build.update(layout=int(head[4]), armourGrades=_int(head[5]))
    slots = {}
    kinds = {short: kind for kind, short in _MODULE_KIND.items()}
    for line in lines[1:]:
        parts = line.split("\t")
        if parts[0] == "A":
            parts += [""] * 5
            build["armourEng"] = {"bp": parts[1], "grade": _int(parts[2]), "special": parts[3], "roll": _int(parts[4]) if parts[4] != "" else None}
            continue
        if parts[0] == "H":
            parts += [""] * 8
            figures = {}
            for pair in parts[6].split(","):
                key, _, value = pair.partition("=")
                if key in _HULL_FIGURES:
                    try:
                        figures[key] = float(value)
                    except ValueError:
                        pass
            build["hull"] = {"symbol": parts[2], "name": parts[1], "manufacturer": "", "described": True, **figures,
                             "slots": {"standard": [_int(size, 1) for size in parts[3].split(",") if size],
                                       "hardpoints": [{"class": _int(a), "jname": b} for a, _, b in (row.partition(":") for row in parts[4].split(",") if row)],
                                       "internal": [{"class": _int(row.split(":")[0]), "jname": (row.split(":") + [""])[1], "name": (row.split(":") + ["", ""])[2]}
                                                    for row in parts[5].split(",") if row]},
                             "bulkheads": [], "defaults": {}}
            continue
        parts += [""] * 7
        if not parts[0].isdigit() or not parts[1]:
            continue
        kind = kinds.get(parts[1][0])
        if kind is None:
            continue
        slots[int(parts[0])] = {"module": f"{kind}:{parts[1][1:]}", "bp": parts[2], "grade": _int(parts[3]),
                                "special": parts[4], **({"roll": _int(parts[5])} if parts[5] != "" else {}),
                                **({"off": True} if parts[6] == "0" else {})}
    build["slots"] = [slots.get(index, {"module": None, "bp": "", "grade": 0, "special": ""}) for index in range(max(slots, default=-1) + 1)]
    return build


def read_share_code(text):
    import base64
    import json
    import zlib
    code = str(text or "").strip()
    if code[:5] in ("VCB1-", "VCB2-"):
        build = read_build_code(code)
        return {"v": 1, "kind": "build", "data": build} if build else None
    if not code.startswith("VCMAT-") or len(code) > 200_000:
        return None
    body = code[6:]
    try:
        data = json.loads(zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)), bufsize=1 << 20))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("v") != 1:
        return None
    return data


# -- the engineer route ----------------------------------------------------

def engineer_route(items, game, here, progress=None, pins=()):
    """The engineers to visit for a wishlist's items, nearest first then
    nearest to the last: [{"engineer", "system", "jump_ly", "items"}]. Of the
    engineers who could do the same work: the one you pinned it to, else one
    you've unlocked, else the nearest."""
    wanted = {}
    table = engineers()
    progress = progress or {}
    pinned = {(pin.get("module"), pin.get("name")): pin.get("engineer") for pin in pins or ()}
    pinned_for = {}
    for item in items:
        if not item.get("visible", True):
            continue
        names = []
        if game == "odyssey" and item.get("type") == "mod":
            model = equipment(item.get("target")) or {}
            names = (mod_recipe(model.get("kind", ""), item.get("mod"), model.get("maker", "")) or {}).get("engineers") or []
        elif game == "horizons" and item.get("type") == "blueprint":
            entry = ship_blueprints().get(item.get("module"), {}).get(item.get("name")) or {}
            top = (entry.get("grades") or {}).get(_int(item.get("grade"), 5)) or {}
            names = top.get("engineers") or []
        if not names:
            continue
        label = item.get("label") or item_label(game, item)
        if pinned.get((item.get("module"), item.get("name"))) in names:
            pinned_for.setdefault(pinned[(item.get("module"), item.get("name"))], set()).add(label)
        for name in names:
            wanted.setdefault(name, []).append(label)
    if not wanted:
        return []
    # Fewest stops: keep taking the engineer who covers the most items still open.
    open_items = {label for labels in wanted.values() for label in labels}
    chosen = []
    def far(name):
        info = table.get(name) or {}
        return math.dist(here, (info["x"], info["y"], info["z"])) if here and "x" in info else 0.0

    while open_items:
        best = max(wanted, key=lambda name: (len(open_items & set(wanted[name])), len(open_items & pinned_for.get(name, set())),
                                             (progress.get(name) or {}).get("progress") == "Unlocked", -far(name), name))
        covered = open_items & set(wanted[best])
        if not covered:
            break
        chosen.append((best, sorted(covered)))
        open_items -= covered
    stops, position = [], tuple(here) if here else None
    remaining = list(chosen)
    while remaining:
        def distance(entry):
            info = table.get(entry[0]) or {}
            if position is None or "x" not in info:
                return 0.0
            return math.dist(position, (info["x"], info["y"], info["z"]))
        nxt = min(remaining, key=distance)
        remaining.remove(nxt)
        info = table.get(nxt[0]) or {}
        stops.append({"engineer": nxt[0], "system": info.get("system", ""), "base": info.get("base", ""),
                      "jump_ly": round(distance(nxt), 1) if position is not None else None, "items": nxt[1]})
        if "x" in info:
            position = (info["x"], info["y"], info["z"])
    return stops


# -- community goals -------------------------------------------------------

def note_goals(state, raw):
    """A CommunityGoal event: every goal in it, with a point of history each time it moves."""
    goals = state.setdefault("goals", {})
    stamp = str(raw.get("timestamp") or "")
    for row in raw.get("CurrentGoals") or ():
        key = str(row.get("CGID") or row.get("Title") or "")
        if not key:
            continue
        goal = goals.setdefault(key, {"history": []})
        goal.update({"id": key, "title": row.get("Title") or "", "system": row.get("SystemName") or "",
                     "station": row.get("MarketName") or "", "expiry": row.get("Expiry") or "",
                     "complete": bool(row.get("IsComplete")), "total": _int(row.get("CurrentTotal")),
                     "mine": _int(row.get("PlayerContribution")), "contributors": _int(row.get("NumContributors")),
                     "percentile": _int(row.get("PlayerPercentileBand")), "top_tier": row.get("TopTier") or {},
                     "tier": row.get("TierReached") or "", "bonus": _int(row.get("Bonus")),
                     "top_rank": _int(row.get("TopRankSize")), "in_top": bool(row.get("PlayerInTopRank")),
                     "seen": stamp})
        history = goal["history"]
        point = [stamp, goal["total"], goal["mine"], goal["contributors"]]
        if not history or history[-1][1:] != point[1:]:
            history.append(point)
            del history[:-GOAL_POINTS]
    return goals


# -- Odyssey loadouts from the game ---------------------------------------

def note_suit_loadout(state, ev, raw):
    """SuitLoadout / CreateSuitLoadout / SwitchSuitLoadout and the equip events -> the game's loadouts."""
    loadouts = state.setdefault("suit_loadouts", {})
    key = str(raw.get("LoadoutID") or "")
    if not key:
        return False
    if ev == "DeleteSuitLoadout":
        return loadouts.pop(key, None) is not None
    row = loadouts.setdefault(key, {"id": key, "weapons": {}})
    if ev in ("SuitLoadout", "CreateSuitLoadout", "SwitchSuitLoadout"):
        family, grade = suit_family(raw.get("SuitName"))
        row.update({"name": raw.get("LoadoutName") or row.get("name") or "", "suit": family, "grade": grade,
                    "suit_mods": [str(m).lower() for m in raw.get("SuitMods") or ()]})
        row["weapons"] = {str(m.get("SlotName") or ""): {"key": weapon_family(m.get("ModuleName")), "grade": _int(m.get("Class"), 1),
                                                          "mods": [str(x).lower() for x in m.get("WeaponMods") or ()]}
                          for m in raw.get("Modules") or () if m.get("SlotName")}
    elif ev == "RenameSuitLoadout":
        row["name"] = raw.get("LoadoutName") or row.get("name") or ""
    elif ev == "LoadoutEquipModule":
        row["weapons"][str(raw.get("SlotName") or "")] = {"key": weapon_family(raw.get("ModuleName")), "grade": _int(raw.get("Class"), 1),
                                                          "mods": [str(x).lower() for x in raw.get("WeaponMods") or ()]}
    elif ev == "LoadoutRemoveModule":
        row["weapons"].pop(str(raw.get("SlotName") or ""), None)
    row["seen"] = str(raw.get("timestamp") or "")
    return True


def clean_design(design):
    """An Odyssey loadout design from the page: a suit and up to three weapons,
    each with its grade now, the grade it's going to, and mods had / wanted."""
    design = dict(design or {})

    def part(raw, kind):
        raw = dict(raw or {})
        key = _text(raw.get("key"), 60)
        model = equipment(key)
        if model is None or model["kind"] != kind:
            return None
        grade = max(1, min(5, _int(raw.get("grade"), 1)))
        known = {row["fdname"] for row in mods_for(kind, model["maker"])}
        mods = [m for m in (raw.get("mods") or ()) if m in known][:4]
        wanted = [m for m in (raw.get("want_mods") or ()) if m in known and m not in mods][:4 - len(mods)]
        return {"key": key, "grade": grade, "target": max(grade, min(5, _int(raw.get("target"), grade))),
                "mods": mods, "want_mods": wanted}

    out = {"id": _text(design.get("id"), 16) or _new_id(), "name": _text(design.get("name"), 40) or "Loadout",
           "suit": part(design.get("suit"), "suit"),
           "weapons": [w for w in (part(raw, "weapon") for raw in (design.get("weapons") or ())[:3]) if w]}
    out["updated"] = time.time()
    return out


def design_wishlist_items(design):
    """The wishlist items that take a design from what it is to what it's going to be."""
    items = []
    for part in [design.get("suit")] + list(design.get("weapons") or ()):
        if not part:
            continue
        if part["target"] > part["grade"]:
            items.append({"type": "upgrade", "target": part["key"], "from": part["grade"], "grade": part["target"]})
        for mod in part.get("want_mods") or ():
            items.append({"type": "mod", "target": part["key"], "mod": mod})
    return items


# -- your own call on what's used ------------------------------------------

def set_relevance(state, symbol, value):
    """Mark an on-foot item used or not used, overriding what the recipes say;
    "auto" takes the mark off."""
    symbol = _text(symbol, 60).lower()
    if symbol not in R.MICRORESOURCES:
        return False
    marks = state.setdefault("relevance", {})
    if value in ("used", "unused"):
        if marks.get(symbol) == value:
            return False
        marks[symbol] = value
        return True
    return marks.pop(symbol, None) is not None


# -- high grade emissions ----------------------------------------------------

HGE_KEEP = 400
HGE_OPEN_S = 1800
# The two manufactured materials only one superpower's systems give.
HGE_ALLEGIANCE = {"Empire": ["Imperial Shielding"], "Federation": ["Core Dynamics Composites", "Proprietary Composites"]}


def is_hge(raw):
    kind = f"{raw.get('USSType') or ''} {raw.get('USSType_Localised') or ''}".lower()
    return "veryvaluablesalvage" in kind or "high grade" in kind


def system_factions(raw):
    """FSDJump / Location / CarrierJump -> the system's factions as an HGE remembers them."""
    controlling = raw.get("SystemFaction")
    controlling = controlling.get("Name") if isinstance(controlling, dict) else controlling
    out = []
    for row in raw.get("Factions") or ():
        states = [str(s.get("State") or "") for s in row.get("ActiveStates") or () if s.get("State")]
        out.append({"name": row.get("Name") or "", "state": row.get("FactionState") or "",
                    "states": states, "allegiance": row.get("Allegiance") or "", "government": row.get("Government") or "",
                    "influence": round(float(row.get("Influence") or 0) * 100, 1)})
    return {"system": raw.get("StarSystem") or "", "allegiance": raw.get("SystemAllegiance") or "",
            "controlling": controlling or "", "factions": out}


def note_hge_drop(state, raw, where):
    """You dropped into a High Grade Emission: a visit, with the system as it stood."""
    visits = state.setdefault("hge", [])
    faction = str(raw.get("Faction") or raw.get("USSFaction") or "")
    found = next((row for row in (where or {}).get("factions") or () if row["name"] == faction), None)
    visit = {"id": _new_id(), "at": str(raw.get("timestamp") or ""), "system": (where or {}).get("system") or "",
             "allegiance": (where or {}).get("allegiance") or "", "faction": faction,
             "state": (found or {}).get("state") or "", "states": (found or {}).get("states") or [],
             "faction_allegiance": (found or {}).get("allegiance") or "", "threat": _int(raw.get("USSThreat")),
             "collected": {}}
    visits.append(visit)
    del visits[:-HGE_KEEP]
    return visit


def note_hge_material(visit, raw):
    symbol = str(raw.get("Name") or "").lower()
    if not symbol or visit is None:
        return False
    row = visit["collected"].setdefault(symbol, {"name": raw.get("Name_Localised") or material_info(symbol)["name"], "count": 0})
    row["count"] += max(1, _int(raw.get("Count"), 1))
    return True


def hge_summary(state, wanted=None):
    """Every HGE you've worked, newest first; per system and per faction state,
    what came out of them; and what your ship wishlist still wants that HGEs give."""
    visits = list(state.get("hge") or ())
    systems, by_state = {}, {}
    for visit in visits:
        row = systems.setdefault(visit["system"], {"system": visit["system"], "visits": 0, "last": "", "collected": {},
                                                   "allegiance": visit["allegiance"], "factions": set(), "states": set()})
        row["visits"] += 1
        row["last"] = max(row["last"], visit["at"])
        if visit["faction"]:
            row["factions"].add(visit["faction"])
        for name in [visit["state"], *visit.get("states", [])]:
            if name:
                row["states"].add(name)
        for symbol, item in visit["collected"].items():
            row["collected"][item["name"]] = row["collected"].get(item["name"], 0) + item["count"]
            for name in {visit["state"], *visit.get("states", [])} or {"None"}:
                if name:
                    tally = by_state.setdefault(name, {})
                    tally[item["name"]] = tally.get(item["name"], 0) + item["count"]
    rows = sorted(systems.values(), key=lambda row: row["last"], reverse=True)
    for row in rows:
        row["factions"], row["states"] = sorted(row["factions"]), sorted(row["states"])
    hge_grades = [row for row in MATERIALS.values() if row["category"] == "manufactured" and (row["grade"] or 0) >= 4
                  and row["family"] not in ("guardian", "thargoid", "special")]
    want = []
    for row in hge_grades:
        missing = (wanted or {}).get(row["symbol"])
        if missing:
            want.append({"name": row["name"], "grade": row["grade"], "missing": missing,
                         "states": sorted((name for name, tally in by_state.items() if row["name"] in tally),
                                          key=lambda name: -by_state[name][row["name"]])})
    return {"visits": list(reversed(visits))[:60], "systems": rows[:80],
            "by_state": {name: dict(sorted(tally.items(), key=lambda kv: -kv[1])) for name, tally in sorted(by_state.items())},
            "allegiance": HGE_ALLEGIANCE, "wanted": sorted(want, key=lambda row: (-row["grade"], row["name"]))}


# -- importing builds and wishlists ------------------------------------------

# Where a module's symbol says which kind of module it is (longest first wins).
_MODULE_BY_SYMBOL = sorted({
    "_armour_": "Armour", "int_repairer": "Auto Field Maintenance Unit", "hpt_beamlaser": "Beam Laser",
    "hpt_pulselaserburst": "Burst Laser", "hpt_pulselaser": "Pulse Laser", "hpt_cannon": "Cannon", "int_cargorack": "Cargo Rack",
    "hpt_cargoscanner": "Cargo Scanner", "hpt_chafflauncher": "Chaff Launcher", "int_dronecontrol_collection": "Collector Limpet Controller",
    "hpt_electroniccountermeasure": "Electronic Countermeasure", "hpt_slugshot": "Fragment Cannon", "int_hyperdrive": "Frame Shift Drive",
    "int_fsdinterdictor": "Frame Shift Drive Interdictor", "int_fuelscoop": "Fuel Scoop",
    "int_dronecontrol_fueltransfer": "Fuel Transfer Limpet Controller", "int_dronecontrol_resourcesiphon": "Hatch Breaker Limpet Controller",
    "hpt_heatsinklauncher": "Heat Sink Launcher", "int_hullreinforcement": "Hull Reinforcement Package",
    "hpt_crimescanner": "Kill Warrant Scanner", "int_lifesupport": "Life Support", "missilerack": "Missile Rack",
    "hpt_multicannon": "Multi Cannon", "hpt_plasmaaccelerator": "Plasma Accelerator", "hpt_plasmapointdefence": "Point Defence",
    "int_powerdistributor": "Power Distributor", "int_powerplant": "Power Plant", "int_dronecontrol_prospector": "Prospector Limpet Controller",
    "hpt_railgun": "Rail Gun", "int_refinery": "Refinery", "hpt_flakmortar": "Remote Release Flak Launcher", "int_sensors": "Sensor",
    "hpt_shieldbooster": "Shield Booster", "int_shieldcellbank": "Shield Cell Bank", "int_shieldgenerator": "Shield Generator",
    "int_detailedsurfacescanner": "Surface Scanner", "int_engine": "Thrusters", "torppylon": "Torpedo Pylon", "hpt_cloudscanner": "Wake Scanner",
    "hpt_mining_abrblstr": "Abrasion Blaster", "hpt_mininglaser": "Mining Laser", "int_modulereinforcement": "Module Reinforcement Package",
    "hpt_basicmissilerack": "Seeker Missile Rack", "hpt_causticmissile": "Enzyme Missile Rack", "hpt_atdumbfiremissile": "AX Missile Rack",
    "hpt_minelauncher": "Mine Launcher", "hpt_causticsinklauncher": "Caustic Sink Launcher",
}.items(), key=lambda pair: -len(pair[0]))


def module_kind(symbol):
    symbol = str(symbol or "").lower()
    return next((kind for fragment, kind in _MODULE_BY_SYMBOL if fragment in symbol), "")


def blueprint_for(fdname, symbol=""):
    """(module, blueprint name) for a game blueprint name, on the module its symbol names when it can."""
    wanted = str(fdname or "").lower()
    kind = module_kind(symbol)
    found = None
    for module, blueprints in ship_blueprints().items():
        for name, entry in blueprints.items():
            if wanted in (str(name).lower() for name in entry["fdnames"]):
                if module == kind:
                    return module, name
                found = found or (module, name)
    if found or "_" not in wanted:
        return found
    # A newer blueprint can go by another name in the journal (FuelScoop_ScoopRateEnhanced is
    # "Scoop Rate Enhanced"): match its words on the same kind of module.
    tail = re.sub(r"[^a-z]", "", wanted.split("_", 1)[1])
    for name in ship_blueprints().get(kind, {}):
        if re.sub(r"[^a-z]", "", name.lower()) == tail:
            return kind, name
    return None


def _decode_blob(text):
    """Base64 (either alphabet), maybe gzipped or zlibbed, to JSON; or JSON as it is."""
    import base64
    import gzip
    import json
    import zlib
    from urllib.parse import unquote
    text = unquote(str(text or "").strip())
    for attempt in (text,):
        try:
            return json.loads(attempt)
        except ValueError:
            pass
    body = text.replace("%3D", "=").strip()
    for decode in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            raw = decode(body + "=" * (-len(body) % 4))
        except Exception:
            continue
        for unpack in (gzip.decompress, zlib.decompress, lambda data: zlib.decompress(data, -15), lambda data: data):
            try:
                return json.loads(unpack(raw).decode("utf-8"))
            except Exception:
                continue
    return None


def _loadout_items(loadout):
    items = []
    for module in (loadout or {}).get("Modules") or ():
        eng = module.get("Engineering") if isinstance(module, dict) else None
        if not isinstance(eng, dict):
            continue
        found = blueprint_for(eng.get("BlueprintName"), module.get("Item"))
        if found and _int(eng.get("Level")):
            items.append({"type": "blueprint", "module": found[0], "name": found[1], "from": 0, "grade": _int(eng.get("Level")),
                          "slot": str(module.get("Slot") or "")})
        effect = str(eng.get("ExperimentalEffect") or "").lower()
        if effect in experimentals():
            items.append({"type": "experimental", "fdname": effect, "module": module_kind(module.get("Item"))})
    return items


def _wishlist_items(rows):
    """An EDSY or Coriolis wishlist export: item, blueprint, grade, best grade's %."""
    items = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        blueprint = str(row.get("blueprint") or row.get("Blueprint") or "")
        symbol = str(row.get("item") or row.get("Item") or "")
        if blueprint.lower().startswith("special_") and blueprint.lower() in experimentals():
            items.append({"type": "experimental", "fdname": blueprint.lower(), "module": module_kind(symbol)})
            continue
        found = blueprint_for(blueprint, symbol)
        grade = _int(row.get("grade") or row.get("Grade"), 5)
        if found:
            item = {"type": "blueprint", "module": found[0], "name": found[1], "from": 0, "grade": max(1, min(5, grade))}
            share = row.get("highestGradePercentage")
            if share not in (None, "") and float(share) < 1:
                # Part of the top grade: fewer rolls at it.
                item["rolls"] = {str(item["grade"]): max(1, round(item["grade"] * float(share)))}
            items.append(item)
    return items


def read_import(text):
    """Anything a commander might paste: ([(game, name, items)], build) where build is a
    journal Loadout for the ship builder, or None. Accepts our VCMAT codes, materials-helper
    links (edomh://...), EDSY and Coriolis wishlists, SLEF, a journal Loadout, and EDSY or
    Coriolis build links."""
    text = str(text or "").strip()
    if not text or len(text) > 400_000:
        return [], None
    code = read_share_code(text)
    if code:
        data = code.get("data") or {}
        if code.get("kind") == "wishlist":
            return [("horizons" if data.get("game") == "horizons" else "odyssey", data.get("name") or "Imported", data.get("items") or [])], None
        return [], None
    if text.lower().startswith("edomh://"):
        body = text[8:]
        kind, _, data = body.partition("/?")
        payload = _decode_blob(data)
        return _from_payload(payload, kind.lower())
    for marker in ("/#/I=", "#/I=", "import?data=", "?data="):
        if marker in text:
            return _from_payload(_decode_blob(text.split(marker, 1)[1].split("&", 1)[0]), "")
    return _from_payload(_decode_blob(text), "")


def _from_payload(payload, kind):
    if isinstance(payload, list):
        # SLEF: [{"header": ..., "data": <Loadout>}]
        first = payload[0] if payload and isinstance(payload[0], dict) else {}
        payload = first.get("data") if isinstance(first.get("data"), dict) else first
    if not isinstance(payload, dict):
        return [], None
    if isinstance(payload.get("Modules"), list):
        name = payload.get("ShipName") or str(payload.get("Ship") or "Imported ship").title()
        return [("horizons", name[:40], _loadout_items(payload))], payload
    rows = payload.get("items") or payload.get("Items")
    if isinstance(rows, list):
        name = str(payload.get("name") or payload.get("Name") or kind.upper() or "Imported")[:40]
        if kind in ("wishlist",) or any(isinstance(row, dict) and row.get("recipeName") for row in rows):
            return [], None
        return [("horizons", name, _wishlist_items(rows))], None
    return [], None

# -- the journal moves wishlists on ----------------------------------------------

CRAFT_SEEN = 400


def _seen(state, key):
    """True the second time the same journal event comes round (a restart reads the journal back)."""
    seen = state.setdefault("crafted_seen", [])
    if key in seen:
        return True
    seen.append(key)
    del seen[:-CRAFT_SEEN]
    return False


def _lists(state, game):
    """Every wishlist of a game, the one picked first."""
    lists = ((state.get("wishlists") or {}).get(game) or {})
    rows = list(lists.get("lists") or ())
    return sorted(rows, key=lambda row: row["id"] != lists.get("selected"))


_SPLIT_KINDS = {"Seeker Missile Rack": ("Missile Rack",)}

# -- figures learned from your own engineering (5.8.4) -------------------------
# Blueprints newer than the ship data have no published figures. Every roll
# (EngineerCraft) and every engineered module in a Loadout says what each stat
# became against the stock module, at its grade and roll quality; kept here per
# blueprint and grade, they give the builder each stat's ratio from worst to
# best roll. A module with an experimental is left out: its figures mix both.
_LEARN_CAP = 24


def note_engineering_figures(state, blueprint, grade, quality, modifiers):
    """One reading of a blueprint at a grade; True when it was new."""
    blueprint, grade = str(blueprint or "").strip().lower(), _int(grade)
    try:
        quality = float(quality)
    except (TypeError, ValueError):
        return False
    if not blueprint or not 1 <= grade <= 5 or not 0 <= quality <= 1:
        return False
    ratios = {}
    for row in modifiers or ():
        try:
            value, original = float(row.get("Value")), float(row.get("OriginalValue"))
        except (TypeError, ValueError, AttributeError):
            continue
        label = str(row.get("Label") or "")
        if label and original:
            ratios[label] = round(value / original, 6)
    if not ratios:
        return False
    book = state.setdefault("learned_figures", {}).setdefault(blueprint, {}).setdefault(str(grade), [])
    reading = {"q": round(quality, 4), "r": ratios}
    if reading in book:
        return False
    book.append(reading)
    del book[:-_LEARN_CAP]
    return True


def note_loadout_figures(state, modules):
    """Every engineered module in a Loadout without an experimental; True when any was new."""
    learned = False
    for row in modules or ():
        eng = row.get("Engineering") if isinstance(row, dict) else None
        if isinstance(eng, dict) and not eng.get("ExperimentalEffect"):
            learned = note_engineering_figures(state, eng.get("BlueprintName"), eng.get("Level"), eng.get("Quality"),
                                               eng.get("Modifiers")) or learned
    return learned


def note_craft_figures(state, raw):
    """A roll at an engineer, unless the module carries an experimental (by the last Loadout, kept current here)."""
    slot, blueprint = str(raw.get("Slot") or ""), str(raw.get("BlueprintName") or "")
    modules = (state.get("ship_loadout") or {}).get("Modules") or []
    fitted = next((row for row in modules if str(row.get("Slot") or "").lower() == slot.lower()), None)
    eng = fitted.setdefault("Engineering", {}) if isinstance(fitted, dict) else {}
    if str(eng.get("BlueprintName") or "").lower() != blueprint.lower():
        # Another blueprint on that module takes its experimental off.
        eng.pop("ExperimentalEffect", None)
    eng.update({"BlueprintName": blueprint, "Level": raw.get("Level"), "Quality": raw.get("Quality")})
    if raw.get("ApplyExperimentalEffect"):
        eng["ExperimentalEffect"] = raw["ApplyExperimentalEffect"]
        return False
    if not isinstance(fitted, dict):
        # No Loadout seen for this ship yet: whether it carries an experimental isn't known.
        return False
    if eng.get("ExperimentalEffect"):
        return False
    return note_engineering_figures(state, blueprint, raw.get("Level"), raw.get("Quality"), raw.get("Modifiers"))


# -- hulls learned from your journal (5.8.4) ------------------------------------
# A ship type the builder's tables don't have yet still arrives in every Loadout:
# its slots, its modules and the whole ship's unladen mass. The latest Loadout of
# each type you fly is kept, with its name from the shipyard, so the builder can
# offer it as a hull of its own the day it comes out.
_SHIPYARD_NAMES = ("ShipyardBuy", "ShipyardNew", "ShipyardSwap", "ShipyardTransfer", "SellShipOnRebuy")


def note_hull(state, raw):
    """A Loadout's ship type: its slots, modules and masses; True when it changed."""
    symbol = str(raw.get("Ship") or "").strip().lower()
    rows = [row for row in raw.get("Modules") or () if isinstance(row, dict) and row.get("Slot")]
    if not symbol or not rows:
        return False
    modules = []
    for row in rows:
        module = {"Slot": str(row["Slot"]), "Item": str(row.get("Item") or "").lower()}
        eng = row.get("Engineering") if isinstance(row.get("Engineering"), dict) else {}
        for mod in eng.get("Modifiers") or ():
            # Engineering that changes a module's mass changes the ship's: kept to work the hull's own out.
            try:
                if mod.get("Label") == "Mass" and float(mod.get("OriginalValue")):
                    module["mass_ratio"] = round(float(mod["Value"]) / float(mod["OriginalValue"]), 6)
            except (TypeError, ValueError, AttributeError):
                pass
        modules.append(module)
    fuel = raw.get("FuelCapacity") if isinstance(raw.get("FuelCapacity"), dict) else {}
    hull = {"modules": modules, "unladen": raw.get("UnladenMass"), "reserve": fuel.get("Reserve"), "at": raw.get("timestamp") or ""}
    hulls = state.setdefault("seen_hulls", {})
    old = hulls.get(symbol)
    if old == hull or (old and str(old.get("at") or "") > str(hull["at"])):
        return False
    hulls[symbol] = hull
    return True


def note_hull_name(state, raw):
    """A ship type's own name from the shipyard (ShipType_Localised); True when new."""
    symbol = str(raw.get("ShipType") or raw.get("Ship") or "").strip().lower()
    name = str(raw.get("ShipType_Localised") or raw.get("Ship_Localised") or "").strip()
    if not symbol or not name or name.lower() == symbol:
        return False
    names = state.setdefault("ship_names", {})
    if names.get(symbol) == name:
        return False
    names[symbol] = name[:60]
    return True


# -- your fleet (5.8.4) ------------------------------------------------------------
# Every ship you own, by the game's ShipID, as its latest Loadout: so the builder can
# open any of them, not only the one you're in. A ship sold, or missing from the
# shipyard's StoredShips list, leaves it.
FLEET_EVENTS = ("Loadout", "SetUserShipName", "StoredShips", "ShipyardSell", "SellShipOnRebuy", "ShipyardBuy", "ShipyardSwap")
_LOADOUT_KEEP = ("Ship", "ShipName", "ShipIdent", "ShipID", "HullValue", "ModulesValue", "UnladenMass", "CargoCapacity",
                 "MaxJumpRange", "FuelCapacity", "timestamp")


def compact_loadout(raw):
    """A Loadout as the page keeps it: the ship, each module and its engineering."""
    modules = []
    for row in raw.get("Modules") or ():
        if not isinstance(row, dict):
            continue
        module = {key: row.get(key) for key in ("Slot", "Item", "Priority", "On", "Value") if key in row}
        if isinstance(row.get("Engineering"), dict):
            eng = row["Engineering"]
            module["Engineering"] = {key: eng.get(key) for key in ("BlueprintName", "Level", "Quality", "ExperimentalEffect",
                                                                   "Engineer", "Modifiers") if key in eng}
        modules.append(module)
    return {**{key: raw.get(key) for key in _LOADOUT_KEEP if key in raw}, "Modules": modules}


def _fleet_gone(state, key, at):
    fleet = state.get("fleet") or {}
    gone = state.setdefault("_fleet_gone", {})
    gone[key] = max(str(gone.get(key) or ""), at)
    if key in fleet and str(fleet[key].get("timestamp") or "") <= at:
        del fleet[key]
        return True
    return False


def note_fleet(state, ev, raw):
    """One of FLEET_EVENTS into the fleet; True when it changed (and its revision moves on, for the save)."""
    changed = _note_fleet(state, ev, raw)
    if changed:
        state["_fleet_rev"] = int(state.get("_fleet_rev") or 0) + 1
    return changed


def _note_fleet(state, ev, raw):
    fleet = state.setdefault("fleet", {})
    at = str(raw.get("timestamp") or "")
    if ev == "Loadout":
        if raw.get("ShipID") is None or not raw.get("Ship"):
            return False
        key, loadout = str(raw["ShipID"]), compact_loadout(raw)
        old = fleet.get(key)
        if old == loadout or (old and str(old.get("timestamp") or "") > at):
            return False
        fleet[key] = loadout
        return True
    if ev == "SetUserShipName":
        row = fleet.get(str(raw.get("ShipID")))
        if not row:
            return False
        name, ident = raw.get("UserShipName"), raw.get("UserShipId")
        if (row.get("ShipName"), row.get("ShipIdent")) == (name, ident):
            return False
        row["ShipName"], row["ShipIdent"] = name, ident
        return True
    if ev == "StoredShips":
        owned = {str(row.get("ShipID")) for part in ("ShipsHere", "ShipsRemote") for row in raw.get(part) or () if isinstance(row, dict)}
        flying = str((state.get("ship_loadout") or {}).get("ShipID"))
        changed = False
        for key in [key for key in fleet if key not in owned and key != flying]:
            changed = _fleet_gone(state, key, at) or changed
        return changed
    sold = raw.get("SellShipID", raw.get("SellShipId"))
    return _fleet_gone(state, str(sold), at) if sold is not None else False


def merge_fleet(state, fleet, gone):
    """A history scan's fleet into the commander's own: the newer Loadout of each ship wins."""
    mine = state.setdefault("fleet", {})
    for key, at in (gone or {}).items():
        if key in mine and str(mine[key].get("timestamp") or "") <= at:
            del mine[key]
    for key, loadout in (fleet or {}).items():
        if key not in mine or str(mine[key].get("timestamp") or "") < str(loadout.get("timestamp") or ""):
            mine[key] = loadout
    state["_fleet_rev"] = int(state.get("_fleet_rev") or 0) + 1


def fleet_list(state):
    """The ships for the page, the one you're in first, then the latest flown. Just their
    names here: a ship's whole Loadout comes from /api/data/materials-ship when it's opened."""
    flying = str((state.get("ship_loadout") or {}).get("ShipID"))
    rows = sorted((state.get("fleet") or {}).items(), key=lambda kv: str(kv[1].get("timestamp") or ""), reverse=True)
    rows = [kv for kv in rows if kv[0] == flying] + [kv for kv in rows if kv[0] != flying]
    return [{"id": key, "ship": str(row.get("Ship") or "").lower(), "name": row.get("ShipName") or "", "ident": row.get("ShipIdent") or "",
             "at": row.get("timestamp") or "", "now": key == flying} for key, row in rows]


# -- technology brokers you've used (5.8.5) ------------------------------------------
# Spansh doesn't know every broker's kind (colony starports, rescue megaships). Each unlock you
# make writes TechnologyBroker with its BrokerType, at the station you're docked at: that station's
# broker is known from then on. {MarketID: {"kind", "station", "system", "at"}}
def docked_station(raw):
    """The station a Docked (or docked Location) event puts you at, or None."""
    if raw.get("event") == "Location" and not raw.get("Docked"):
        return None
    if not raw.get("MarketID") or not raw.get("StationName"):
        return None
    return {"market_id": raw["MarketID"], "station": str(raw["StationName"]), "system": str(raw.get("StarSystem") or "")}


def note_broker(state, raw, station=None):
    """A TechnologyBroker unlock: the broker's kind at that station; True when it's new."""
    kind = str(raw.get("BrokerType") or "").strip().title()
    market = raw.get("MarketID") or (station or {}).get("market_id")
    if not kind or not market:
        return False
    here = station if station and str(station.get("market_id")) == str(market) else {}
    brokers = state.setdefault("brokers", {})
    old = brokers.get(str(market)) or {}
    row = {**old, "kind": kind, "at": str(raw.get("timestamp") or old.get("at") or ""),
           **({"station": here["station"], "system": here["system"]} if here else {})}
    if row == old:
        return False
    brokers[str(market)] = row
    return True


def broker_kind(state, market_id):
    return ((state.get("brokers") or {}).get(str(market_id)) or {}).get("kind", "") if market_id else ""


def scan_journal_history(paths, fid=""):
    """Every Loadout, roll and shipyard name in these journals, oldest first: a state of its own to merge.
    The fleet is only the commander with this FID's (the folder can hold others' journals)."""
    import json
    scanned = {}
    wanted = str(fid or "").strip().upper()
    markers = ('"Loadout"', '"EngineerCraft"', '"Commander"', '"LoadGame"', '"TechnologyBroker"', '"Docked"', '"Location"') + tuple(
        f'"{event}"' for event in set(_SHIPYARD_NAMES) | set(FLEET_EVENTS))
    station = None
    for path in paths:
        mine = not wanted
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not any(marker in line for marker in markers):
                        continue
                    try:
                        raw = json.loads(line)
                    except ValueError:
                        continue
                    event = raw.get("event")
                    if event in ("Commander", "LoadGame") and raw.get("FID") and wanted:
                        mine = str(raw["FID"]).strip().upper() == wanted
                    if event == "Loadout":
                        scanned["ship_loadout"] = {"ShipID": raw.get("ShipID"),
                                                   "Modules": [dict(row) for row in raw.get("Modules") or () if isinstance(row, dict)]}
                        note_loadout_figures(scanned, raw.get("Modules"))
                        note_hull(scanned, raw)
                    elif event == "EngineerCraft":
                        note_craft_figures(scanned, raw)
                    if event in _SHIPYARD_NAMES:
                        note_hull_name(scanned, raw)
                    if event in FLEET_EVENTS and mine:
                        note_fleet(scanned, event, raw)
                    if event in ("Docked", "Location"):
                        station = docked_station(raw)
                    elif event == "TechnologyBroker":
                        note_broker(scanned, raw, station)
        except OSError:
            continue
    return {key: scanned.get(key) or {} for key in ("learned_figures", "seen_hulls", "ship_names", "fleet", "_fleet_gone", "brokers")}


def scan_journal_figures(paths):
    return scan_journal_history(paths)["learned_figures"]


def merge_journal_history(state, scanned):
    """A history scan into the commander's own: newer live readings win."""
    merge_learned_figures(state, scanned.get("learned_figures"))
    hulls = state.setdefault("seen_hulls", {})
    for symbol, hull in (scanned.get("seen_hulls") or {}).items():
        if symbol not in hulls or str(hulls[symbol].get("at") or "") < str(hull.get("at") or ""):
            hulls[symbol] = hull
    names = state.setdefault("ship_names", {})
    for symbol, name in (scanned.get("ship_names") or {}).items():
        names.setdefault(symbol, name)
    merge_fleet(state, scanned.get("fleet"), scanned.get("_fleet_gone"))
    brokers = state.setdefault("brokers", {})
    for market, row in (scanned.get("brokers") or {}).items():
        if market not in brokers or str(brokers[market].get("at") or "") < str(row.get("at") or ""):
            brokers[market] = {**brokers.get(market, {}), **row}


def merge_learned_figures(state, learned):
    """Readings from a journal scan into the commander's own; True when any was new."""
    added = False
    for blueprint, grades in (learned or {}).items():
        for grade, readings in grades.items():
            book = state.setdefault("learned_figures", {}).setdefault(blueprint, {}).setdefault(grade, [])
            for reading in readings:
                if reading not in book:
                    book.append(reading)
                    added = True
            del book[:-_LEARN_CAP]
    return added


def learned_figures(state):
    """{blueprint: {grade: {"fields": {label: [ratio at the worst roll, at the best]}, "rolls": n}}}"""
    out = {}
    for blueprint, grades in (state.get("learned_figures") or {}).items():
        for grade, readings in grades.items():
            fields = {}
            for label in sorted({label for reading in readings for label in reading["r"]}):
                points = [(reading["q"], reading["r"][label]) for reading in readings if label in reading["r"]]
                qualities = [q for q, _ in points]
                mean_q = sum(qualities) / len(points)
                spread = sum((q - mean_q) ** 2 for q in qualities)
                mean_r = sum(r for _, r in points) / len(points)
                if spread > 1e-6:
                    # A straight line through the readings: worst roll at quality 0, best at 1.
                    slope = sum((q - mean_q) * (r - mean_r) for q, r in points) / spread
                    low, high = mean_r - slope * mean_q, mean_r + slope * (1 - mean_q)
                else:
                    low = high = mean_r
                fields[label] = [round(low, 5), round(high, 5)]
            out.setdefault(blueprint, {})[grade] = {"fields": fields, "rolls": len(readings)}
    return out


def note_craft(state, raw):
    """An EngineerCraft: one roll at its grade off the matching ship wishlist item, and
    an applied experimental off the list. What changed, as lines for the event feed."""
    blueprint, module_symbol = raw.get("BlueprintName"), raw.get("Module")
    level = _int(raw.get("Level"))
    key = f"{raw.get('timestamp')}|{raw.get('Slot')}|{blueprint}|{level}|{raw.get('ApplyExperimentalEffect') or ''}"
    if _seen(state, key):
        return []
    said = []
    effect = str(raw.get("ApplyExperimentalEffect") or "").lower()
    # Applying an experimental isn't a roll of the blueprint.
    found = blueprint_for(blueprint, module_symbol) if blueprint and level and not effect else None
    slot = str(raw.get("Slot") or "").lower()
    for wish in _lists(state, "horizons"):
        items = wish.get("items") or []
        if found:
            # Goals saved before seekers had recipes of their own sit under Missile Rack.
            kinds = {found[0], *_SPLIT_KINDS.get(found[0], ())}
            matches = [item for item in items if item.get("type") == "blueprint"
                       and item.get("module") in kinds and item.get("name") == found[1]
                       and _int(item.get("from")) < level <= _int(item.get("grade"), 5) and item.get("visible", True)]
            matches.sort(key=lambda item: (item.get("module"), item.get("name")) != found)
            matches.sort(key=lambda item: str(item.get("slot") or "").lower() != slot)
            if matches:
                item = matches[0]
                done = item.setdefault("done", {})
                done[str(level)] = _int(done.get(str(level))) + 1
                total = rolls_at(item, level) * max(1, _int(item.get("qty"), 1))
                label = item_label("horizons", item)
                rolled = done[str(level)]
                # Rolling at a grade puts every grade under it behind you.
                if level > _int(item.get("from")) + 1:
                    item["from"] = level - 1
                if rolled >= total:
                    item["from"] = level
                for grade in list(done):
                    if _int(grade) <= _int(item.get("from")):
                        done.pop(grade)
                if _int(item.get("from")) >= _int(item.get("grade"), 5):
                    wish["items"] = [row for row in items if row is not item]
                    said.append(f"{label} done: off {wish['name']}")
                elif rolled >= total:
                    said.append(f"{label}: G{level} done")
                else:
                    said.append(f"{label}: G{level} roll {rolled} of {total}")
                found = None
        if effect:
            hit = next((item for item in wish.get("items") or [] if item.get("type") == "experimental" and item.get("fdname") == effect), None)
            if hit:
                wish["items"] = [row for row in wish["items"] if row is not hit]
                said.append(f"{item_label('horizons', hit)} applied: off {wish['name']}")
                effect = ""
    return said


def note_upgrade(state, raw):
    """UpgradeSuit / UpgradeWeapon: the suit or weapon's grade upgrade moves on."""
    symbol = str(raw.get("Name") or "").lower()
    family = suit_family(symbol)[0] if "suit" in symbol else weapon_family(symbol)
    level = _int(raw.get("Class"))
    key = f"{raw.get('timestamp')}|{raw.get('SuitID') or raw.get('SuitModuleID') or ''}|{symbol}|{level}"
    if not level or _seen(state, key):
        return []
    for wish in _lists(state, "odyssey"):
        for item in wish.get("items") or []:
            if item.get("type") == "upgrade" and item.get("target") == family and _int(item.get("from"), 1) < level <= _int(item.get("grade"), 5):
                label = item_label("odyssey", item)
                item["from"] = level
                if level >= _int(item.get("grade"), 5):
                    wish["items"] = [row for row in wish["items"] if row is not item]
                    return [f"{label} done: off {wish['name']}"]
                return [f"{label}: now G{level}"]
    return []


# -- pinned blueprints ----------------------------------------------------------

PIN_LIMIT = 120


def engineer_grade(module, name, engineer):
    """The best grade an engineer does a blueprint to (0 when they don't)."""
    entry = ship_blueprints().get(module, {}).get(name) or {}
    return max((grade for grade, recipe in entry.get("grades", {}).items() if engineer in recipe["engineers"]), default=0)


def pin_operation(state, operation, payload):
    pins = state.setdefault("pins", [])
    if operation == "pin_add":
        module, name, engineer = _text(payload.get("module"), 60), _text(payload.get("name"), 80), _text(payload.get("engineer"), 60)
        grade = engineer_grade(module, name, engineer)
        if not grade or len(pins) >= PIN_LIMIT or any(p["module"] == module and p["name"] == name and p["engineer"] == engineer for p in pins):
            return False
        pins.append({"id": _new_id(), "module": module, "name": name, "engineer": engineer, "grade": grade})
        return True
    if operation == "pin_remove":
        before = len(pins)
        state["pins"] = [p for p in pins if p["id"] != payload.get("pin_id")]
        return len(state["pins"]) != before
    if operation == "pin_clear":
        state["pins"] = []
        return bool(pins)
    return False


def import_pins(state, rows):
    added = 0
    for row in rows or ():
        if isinstance(row, dict) and pin_operation(state, "pin_add", row):
            added += 1
    return added

# -- the plan: what to do next -------------------------------------------------

def _engineer_for(names, here, progress, prefer=""):
    """Of the engineers who can do it: the one you pinned, else unlocked ones first, nearest first."""
    table = engineers()
    if prefer in names:
        return prefer
    def rank(name):
        info = table.get(name) or {}
        unlocked = (progress.get(name) or {}).get("progress") == "Unlocked"
        far = math.dist(here, (info["x"], info["y"], info["z"])) if here and "x" in info else 0.0
        return (not unlocked, far)
    return min(names, key=rank) if names else ""


def _stop(name, here, kind, title, detail, items, why=""):
    info = engineers().get(name) or {}
    far = round(math.dist(here, (info["x"], info["y"], info["z"])), 1) if here and "x" in info else None
    return {"kind": kind, "title": title, "detail": detail, "why": why, "system": info.get("system", ""),
            "engineer": name, "ly": far, "items": items}


def next_steps(state, game, here=None, nearest=None, hge=None):
    """What to do next for a game's selected wishlist (and, for ships, your pins):
    ready work grouped by the engineer to take it to, trader swaps, what to collect
    and where, the bartender. Worked out afresh from what you hold, so a step goes
    as soon as the journal sees it done."""
    chosen = summary(state, game)
    if not chosen:
        return []
    have = odyssey_have(state) if game == "odyssey" else horizons_have(state)
    progress = state.get("engineers") or {}
    steps = []
    if game == "horizons":
        pins = {(pin["module"], pin["name"]): pin["engineer"] for pin in state.get("pins") or ()}
        by_engineer = {}
        for item in chosen["items"]:
            if not item.get("visible", True):
                continue
            if item.get("type") == "blueprint":
                grade = _int(item.get("from")) + 1
                entry = ship_blueprints().get(item.get("module"), {}).get(item.get("name")) or {}
                recipe = (entry.get("grades") or {}).get(grade)
                if not recipe or grade > _int(item.get("grade"), 5):
                    continue
                if all(have.get(row["symbol"], 0) >= row["count"] for row in recipe["ingredients"]):
                    left = rolls_at(item, grade) * max(1, _int(item.get("qty"), 1)) - _int((item.get("done") or {}).get(str(grade)))
                    rolls = sum(1 for times in range(1, max(0, left) + 1)
                                if all(have.get(row["symbol"], 0) >= row["count"] * times for row in recipe["ingredients"]))
                    if not rolls:
                        continue
                    name = _engineer_for(recipe["engineers"], here, progress, pins.get((item["module"], item["name"]), ""))
                    by_engineer.setdefault(name, []).append(f"{item['module']}: {item['name']} G{grade} ×{rolls}")
            elif item.get("type") == "experimental" and item["ready"]:
                by_engineer.setdefault("", []).append(item["label"])
        for name, items in by_engineer.items():
            if name:
                steps.append(_stop(name, here, "engineer", f"Take your rolls to {name}", f"{len(items)} ready to make now", items,
                                   "Everything for the next roll is in your hold."))
            else:
                steps.append({"kind": "engineer", "title": "Apply your experimentals", "detail": "At any engineer who works that module",
                              "why": "Everything for them is in your hold.", "items": items, "system": "", "ly": None})
        trades = chosen.get("trades") or []
        by_kind = {}
        for trade in trades:
            target = next((row for row in MATERIALS.values() if row["name"] == trade["for"]), None)
            by_kind.setdefault((target or {}).get("category", "raw"), []).append(trade)
        for kind, rows in by_kind.items():
            near = ((nearest or {}).get(kind) or {}).get("rows") or []
            steps.append({"kind": "trade", "title": f"Trade at {'an' if kind[0] in 'aeiou' else 'a'} {kind} material trader",
                          "detail": f"Nearest: {near[0]['station']}, {near[0]['system']} · {near[0]['distance']} ly" if near else "",
                          "why": "Swaps from what the wishlist doesn't need cover these.", "trader": kind,
                          "items": [f"{row['spend']} {row['from']} → {row['covers']} {row['for']}" for row in rows],
                          "system": near[0]["system"] if near else "", "ly": near[0]["distance"] if near else None})
        covered = {}
        for trade in trades:
            covered[trade["for"]] = covered.get(trade["for"], 0) + trade["covers"]
        short = [row for row in chosen["materials"] if row["missing"] - covered.get(row["name"], 0) > 0]
        hge_states = (hge or {}).get("by_state") or {}
        groups = {}
        for row in short:
            info = MATERIALS.get(row["symbol"])
            if info is None:
                key, title = "other", "Collect"
            elif info["category"] == "manufactured" and (info["grade"] or 0) >= 4 and info["family"] not in ("guardian", "thargoid"):
                key, title = "hge", "Work High Grade Emissions"
            else:
                key, title = info["category"], {"raw": "Collect raw materials", "manufactured": "Collect manufactured materials",
                                                "encoded": "Scan for encoded materials"}.get(info["category"], "Collect")
            group = groups.setdefault(key, {"title": title, "items": [], "hints": []})
            group["items"].append(f"{row['name']} ×{row['missing'] - covered.get(row['name'], 0)}")
            hint = material_source_hint(row["symbol"])
            if key == "hge":
                states = sorted((name for name, tally in hge_states.items() if row["name"] in tally), key=lambda name: -hge_states[name][row["name"]])
                hint = f"Your HGEs in {', '.join(states[:2])} gave you {row['name']}." if states else hint
            if hint not in group["hints"]:
                group["hints"].append(hint)
        for key, group in groups.items():
            steps.append({"kind": "collect", "title": group["title"], "detail": f"{len(group['items'])} still short",
                          "why": " ".join(group["hints"][:2]), "items": group["items"], "system": "", "ly": None, "source": key})
        return steps
    # On foot.
    upgrades, by_engineer = [], {}
    for item in chosen["items"]:
        if not item.get("visible", True) or not item["ready"]:
            continue
        if item.get("type") == "upgrade":
            upgrades.append(item["label"])
        elif item.get("type") == "mod":
            model = equipment(item.get("target")) or {}
            recipe = mod_recipe(model.get("kind", ""), item.get("mod"), model.get("maker", "")) or {}
            name = _engineer_for(recipe.get("engineers") or [], here, progress)
            by_engineer.setdefault(name, []).append(item["label"])
    if upgrades:
        steps.append({"kind": "engineer", "title": "Upgrade at Pioneer Supplies", "detail": f"{len(upgrades)} ready",
                      "why": "Grade upgrades are made at any Pioneer Supplies.", "items": upgrades, "system": "", "ly": None})
    for name, items in by_engineer.items():
        steps.append(_stop(name, here, "engineer", f"Take your mods to {name}", f"{len(items)} ready to fit", items,
                           "Everything for them is in your locker."))
    short = [row for row in chosen["materials"] if row["missing"] > 0]
    spare = sum(max(0, count - next((row["need"] for row in chosen["materials"] if row["symbol"] == symbol), 0)) * (R.MICRORESOURCES.get(symbol) or {}).get("barter_value", 0)
                for symbol, count in have.items() if not _used(state, symbol))
    buyable = [row for row in short if (R.MICRORESOURCES.get(row["symbol"]) or {}).get("barter_cost")]
    cost = sum(row["missing"] * R.MICRORESOURCES[row["symbol"]]["barter_cost"] for row in buyable)
    if buyable and spare:
        steps.append({"kind": "bartender", "title": "Swap at a bartender",
                      "detail": f"Your unused items fetch about {spare:,} pts; what's short costs about {cost:,}",
                      "why": "Bartenders in station concourses take goods and data and sell what you're short of.",
                      "items": [f"{row['name']} ×{row['missing']}" for row in buyable[:8]], "system": "", "ly": None})
    # The fewest kinds of building that cover what's short: take the one with the most, then the next.
    left = {row["symbol"]: row for row in short}
    offers = {}
    for symbol in left:
        for code in (R.MICRORESOURCES.get(symbol) or {}).get("buildings") or ():
            offers.setdefault(code, set()).add(symbol)
    for _ in range(4):
        if not left or not offers:
            break
        code = max(offers, key=lambda c: (len(offers[c] & left.keys()), c))
        found = offers.pop(code) & left.keys()
        if not found:
            break
        rows = [left.pop(symbol) for symbol in sorted(found, key=lambda sym: left[sym]["name"])]
        kinds = {row["kind"] for row in rows}
        what = "Search" if len(kinds) > 1 else {"data": "Download data in", "item": "Pick up goods in", "component": "Pick up assets in"}.get(kinds.pop(), "Search")
        steps.append({"kind": "collect", "title": f"{what} {BUILDINGS.get(code, code.lower())}", "detail": f"{len(rows)} of what's short",
                      "why": "Settlement buildings where these turn up; more of what you need in one kind of building first.",
                      "items": [f"{row['name']} ×{row['missing']}" for row in rows], "system": "", "ly": None, "source": code})
    if left:
        rows = list(left.values())
        origins = sorted({origin for row in rows for origin in (R.MICRORESOURCES.get(row["symbol"]) or {}).get("origin") or ()})
        steps.append({"kind": "collect", "title": "Collect the rest", "detail": f"{len(rows)} more",
                      "why": f"Found at {', '.join(origins[:3]).lower()}." if origins else "Mission rewards and settlements.",
                      "items": [f"{row['name']} ×{row['missing']}" for row in rows], "system": "", "ly": None})
    return steps


# Settlement building codes as the game's signs name them.
BUILDINGS = {"RES": "residential buildings", "CMD": "command buildings", "HAB": "habitation buildings",
             "AGRI": "agricultural buildings", "IND": "industrial buildings", "EXT": "extraction buildings",
             "STO": "storage buildings", "MED": "medical buildings", "PWR": "power buildings", "LAB": "laboratories",
             "PROC": "processing buildings", "SEC": "security buildings", "DORM": "dormitories", "OPR": "operations buildings",
             "BAR": "bars", "CBN": "cabins"}


def _used(state, symbol):
    mark = (state.get("relevance") or {}).get(symbol)
    if mark:
        return mark == "used"
    return any(use["game"] == "odyssey" for use in uses().get(symbol, ()))


__all__ = [name for name in dir() if not name.startswith("_")]
