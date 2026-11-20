"""The Materials page (5.8.4): the deck's side. Journal events keep the
commander's engineer_materials up to date; the page gets its state with each
refresh and its fixed tables once, from /api/data/materials-reference and
/materials-ships.json."""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from voidcompass.engineering import materials_page as mp

LOCKER_EVENTS = {"ShipLocker", "Backpack", "BackpackChange", "ShipLockerMaterials"}
SUIT_EVENTS = {"SuitLoadout", "CreateSuitLoadout", "SwitchSuitLoadout", "RenameSuitLoadout", "DeleteSuitLoadout",
               "LoadoutEquipModule", "LoadoutRemoveModule"}
NEAREST = {"raw": ("Raw material trader", "Raw"), "manufactured": ("Manufactured material trader", "Manufactured"),
           "encoded": ("Encoded material trader", "Encoded"), "broker": ("Technology broker", None)}
NEAREST_TTL_S = 600
BUILD_BYTES = 40_000
WANTED_GAP_S = 15
OPTIONS = {"materials_wanted_toast": True, "materials_ready_toast": True, "materials_hide_unused": False,
           "materials_locker_sort": "name", "materials_roll": 100}


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class HtmlMaterialsMixin:

    # -- state ---------------------------------------------------------------
    def _materials_state(self):
        state = getattr(self, "engineer_materials", None)
        if not isinstance(state, dict):
            state = self.engineer_materials = {}
        # The ship's hold as the deck last read it (the SRV's doesn't count at a broker).
        inventory = getattr(self, "current_cargo_inventory", None)
        if isinstance(inventory, list) and str(getattr(self, "current_cargo_vessel", "") or "Ship").lower() == "ship":
            cargo = {}
            for row in inventory:
                if isinstance(row, dict) and row.get("Name", row.get("name")):
                    symbol = str(row.get("Name", row.get("name"))).lower()
                    cargo[symbol] = cargo.get(symbol, 0) + int(row.get("Count", row.get("count", 0)) or 0)
            state["cargo"] = cargo
        return state

    def _materials_changed(self, check=True, quiet=False):
        state = self._materials_state()
        state["last_updated"] = time.time()
        saver = getattr(self, "_save_engineer_materials", None)
        if callable(saver):
            saver(state)
        if check:
            self._materials_ready_check(quiet=quiet)
        refresh = getattr(self, "_refresh_html_workspace", None)
        if callable(refresh):
            refresh()

    def _materials_ready_check(self, quiet=False):
        """A toast when a wishlist item becomes ready to make (live only)."""
        state = self._materials_state()
        ready = set()
        for game in ("odyssey", "horizons"):
            lists = ((state.get("wishlists") or {}).get(game) or {}).get("lists") or ()
            for row in lists:
                summary = mp.summary(state, game, row["id"])
                for item in (summary or {}).get("items") or ():
                    if item["ready"] and item.get("visible", True):
                        ready.add((game, row["name"], item["label"]))
        before = getattr(self, "_materials_ready_seen", None)
        self._materials_ready_seen = ready
        if before is None or quiet or getattr(self, "_startup_restore_active", False) or not self._materials_option("materials_ready_toast"):
            return
        toast = getattr(self, "toast_hud", None)
        for game, name, label in sorted(ready - before)[:3]:
            if toast is not None:
                post = getattr(self, "_ui_post", None)
                push = lambda label=label, name=name: toast.push("WISHLIST READY", f"{label} · {name}", severity="info", duration_s=12)
                post(push) if callable(post) else push()
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("ENGINEERING", f"Ready to make: {label} ({name})", severity="INFO")

    def _materials_option(self, key):
        value = (getattr(self, "config", None) or {}).get(key)
        return OPTIONS[key] if value is None else value

    def _materials_options(self):
        return {key.removeprefix("materials_"): self._materials_option(key) for key in OPTIONS}

    def _materials_wanted(self, game, picked):
        """A toast when you pick up something a wishlist is short of: {symbol: count} picked."""
        if not picked or not self._materials_option("materials_wanted_toast") or getattr(self, "_startup_restore_active", False):
            return
        summary = mp.summary(self._materials_state(), game)
        rows = {row["symbol"]: row for row in (summary or {}).get("materials") or ()}
        last = self.__dict__.setdefault("_materials_wanted_at", {})
        now = time.monotonic()
        for symbol, count in picked.items():
            row = rows.get(symbol)
            if not row or row["missing"] <= 0 or now - last.get(symbol, -1e9) < WANTED_GAP_S:
                continue
            last[symbol] = now
            have = row["have"] + count
            text = f"{row['name']} +{count} · {min(have, row['need'])}/{row['need']} for {summary['name']}"
            toast = getattr(self, "toast_hud", None)
            if toast is not None:
                post = getattr(self, "_ui_post", None)
                push = lambda text=text: toast.push("WANTED", text, severity="info", duration_s=8)
                post(push) if callable(post) else push()

    def _materials_locker(self, where, counts):
        locker = self._materials_state().setdefault("locker", {})
        if locker.get(where) == counts:
            return False
        locker[where] = counts
        locker["seen"] = time.time()
        return True

    def _materials_ship_locker_file(self, data):
        """ShipLocker.json (the watcher hands it over on the UI thread)."""
        if any(key in (data or {}) for key in ("Items", "Components", "Data", "Consumables")):
            if self._materials_locker("shiplocker", mp.locker_from_event(data)):
                self._materials_changed()

    def _materials_backpack_file(self):
        folder = str((getattr(self, "config", None) or {}).get("journal_path") or "")
        path = os.path.join(folder, "Backpack.json") if folder else ""
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None

    def _materials_event(self, ev, raw, startup_replay=False):
        if not isinstance(raw, dict):
            return
        try:
            self._materials_event_now(ev, raw, startup_replay)
        except Exception:
            logging.debug("Materials page skipped %s", ev, exc_info=True)

    def _materials_event_now(self, ev, raw, startup_replay):
        state = self._materials_state()
        changed = False
        if ev in ("FSDJump", "Location", "CarrierJump"):
            self._materials_where = mp.system_factions(raw)
        if ev in ("SupercruiseEntry", "FSDJump", "Shutdown", "Died", "LoadGame"):
            self._materials_hge_open = None
        if ev == "USSDrop" and mp.is_hge(raw):
            visit = mp.note_hge_drop(state, raw, getattr(self, "_materials_where", None))
            self._materials_hge_open = (visit["id"], time.monotonic())
            changed = True
        elif ev == "MaterialCollected":
            opened = getattr(self, "_materials_hge_open", None)
            if opened and time.monotonic() - opened[1] < mp.HGE_OPEN_S:
                visit = next((row for row in reversed(state.get("hge") or ()) if row["id"] == opened[0]), None)
                changed = mp.note_hge_material(visit, raw)
            if not startup_replay:
                symbol = str(raw.get("Name") or "").lower()
                self._materials_wanted("horizons", {symbol: max(1, _int(raw.get("Count"), 1))} if symbol else {})
        elif ev == "CollectItems" and not startup_replay:
            symbol = str(raw.get("Name") or "").lower()
            self._materials_wanted("odyssey", {symbol: max(1, _int(raw.get("Count"), 1))} if symbol else {})
        if ev == "ShipLocker" and any(key in raw for key in ("Items", "Components", "Data")):
            changed = self._materials_locker("shiplocker", mp.locker_from_event(raw))
        elif ev == "Backpack":
            data = raw if any(key in raw for key in ("Items", "Components", "Data")) else self._materials_backpack_file()
            if data:
                changed = self._materials_locker("backpack", mp.locker_from_event(data))
        elif ev == "BackpackChange":
            if not startup_replay:
                # Data downloads (goods and assets are told by CollectItems).
                self._materials_wanted("odyssey", {str(row.get("Name") or "").lower(): _int(row.get("Count"), 1)
                                                   for row in raw.get("Added") or () if str(row.get("Type") or "").lower() == "data"})
            pack = dict((state.get("locker") or {}).get("backpack") or {})
            for sign, key in ((1, "Added"), (-1, "Removed")):
                for row in raw.get(key) or ():
                    symbol = str(row.get("Name") or "").lower()
                    if symbol:
                        pack[symbol] = max(0, pack.get(symbol, 0) + sign * _int(row.get("Count")))
            changed = self._materials_locker("backpack", {k: v for k, v in pack.items() if v})
        elif ev in SUIT_EVENTS:
            changed = mp.note_suit_loadout(state, ev, raw)
        elif ev == "Loadout":
            state["ship_loadout"] = mp.compact_loadout(raw)
            mp.note_loadout_figures(state, state["ship_loadout"]["Modules"])
            mp.note_hull(state, raw)
            mp.note_fleet(state, ev, raw)
            changed = True
        elif ev == "CommunityGoal":
            mp.note_goals(state, raw)
            changed = True
        elif ev in ("EngineerCraft", "UpgradeSuit", "UpgradeWeapon"):
            # Engineering done in the game moves the wishlists on (once per event, restarts included).
            said = mp.note_craft(state, raw) if ev == "EngineerCraft" else mp.note_upgrade(state, raw)
            if ev == "EngineerCraft":
                changed = mp.note_craft_figures(state, raw) or changed
            changed = bool(said) or changed
            feed = getattr(self, "add_event_feed_entry", None)
            if said and callable(feed) and not startup_replay:
                for line in said:
                    feed("ENGINEERING", line, severity="INFO")
        if ev in mp._SHIPYARD_NAMES:
            changed = mp.note_hull_name(state, raw) or changed
        if ev in mp.FLEET_EVENTS and ev != "Loadout":
            changed = mp.note_fleet(state, ev, raw) or changed
        if changed:
            # Read back at startup, readiness is noted without a toast for it.
            self._materials_changed(quiet=startup_replay)

    # -- the page ------------------------------------------------------------
    def _materials_here(self):
        position = self._galaxy_minimap_position() if hasattr(self, "_galaxy_minimap_position") else None
        return {"system": str(getattr(self, "current_sys", "") or ""), "coords": list(position) if position else None}

    _HISTORY_SCAN = 3   # 1: blueprint figures; 2: and the ship types you've flown; 3: and every ship you own

    def _materials_learn_from_history(self, state):
        """Once per commander: read the journal history for blueprint figures and ship types from before 5.8.4."""
        if _int(state.get("history_scan")) >= self._HISTORY_SCAN or getattr(self, "_materials_learn_running", False):
            return
        folder = str((getattr(self, "config", None) or {}).get("journal_path") or "")
        if not folder or not os.path.isdir(folder):
            return
        self._materials_learn_running = True
        from voidcompass.core.journal_files import list_journals

        def done(learned):
            self._materials_learn_running = False
            current = self._materials_state()
            current["history_scan"] = self._HISTORY_SCAN
            mp.merge_journal_history(current, learned)
            self._materials_changed(check=False)

        def work():
            try:
                learned = mp.scan_journal_history(list_journals(folder), getattr(self, "cmdr_fid", "") or "")
            except Exception:
                logging.debug("Materials history scan failed", exc_info=True)
                learned = {}
            post = getattr(self, "_ui_post", None)
            post(done, learned) if callable(post) else done(learned)

        threading.Thread(target=work, name="materials-figures", daemon=True).start()

    def _html_materials_workspace(self):
        state = self._materials_state()
        self._materials_learn_from_history(state)
        here = self._materials_here()
        wishes, routes = {}, {}
        for game in ("odyssey", "horizons"):
            summary = mp.summary(state, game)
            wishes[game] = {**mp.wishlist_index(state, game), "summary": summary}
            routes[game] = mp.engineer_route((summary or {}).get("items") or (), game, here["coords"], state.get("engineers"), state.get("pins"))
        locker = state.get("locker") or {}
        carrier = None
        tracker = getattr(self, "carrier_tracker", None)
        try:
            shown = tracker.display_carrier() if tracker is not None else None
            if shown:
                carrier = {"name": shown.get("name") or shown.get("callsign") or "", "orders": shown.get("trade_orders") or [],
                           "space_cargo": shown.get("space_cargo")}
        except Exception:
            carrier = None
        goals = sorted((state.get("goals") or {}).values(), key=lambda row: (row.get("complete", False), row.get("expiry") or ""))
        return {
            "here": here,
            "odyssey_game": bool(getattr(self, "game_odyssey", True)),
            "have": {"odyssey": mp.odyssey_have(state), "backpack": locker.get("backpack") or {},
                     "shiplocker": locker.get("shiplocker") or {}, "horizons": mp.horizons_have(state)},
            "locker_seen": locker.get("seen"),
            "progress": state.get("engineers") or {},
            "wishlists": wishes, "routes": routes,
            "loadouts": state.get("loadouts") or [], "suit_loadouts": list((state.get("suit_loadouts") or {}).values()),
            "ship_builds": state.get("ship_builds") or [], "ship_loadout": state.get("ship_loadout"),
            "cargo": list(getattr(self, "current_cargo_inventory", None) or [])[:200],
            "cargo_capacity": getattr(self, "cargo_capacity", 0),
            "carrier": carrier, "goals": goals[:40],
            "nearest": getattr(self, "_materials_nearest_cache", None) or {},
            "relevance": state.get("relevance") or {},
            "pins": state.get("pins") or [],
            "hge": mp.hge_summary(state, {row["symbol"]: row["missing"] for row in (wishes["horizons"]["summary"] or {}).get("materials") or ()
                                          if row["missing"]}),
            "imported_build": state.get("imported_build"),
            # What your own rolls showed each blueprint grade does (for blueprints with no published figures).
            "learned_figures": mp.learned_figures(state),
            # The latest Loadout of each ship type you've flown, for hulls the builder's tables don't have yet.
            "seen_hulls": state.get("seen_hulls") or {}, "ship_names": state.get("ship_names") or {},
            # Every ship you own as its latest Loadout, the one you're in first.
            "fleet": mp.fleet_list(state),
            # What to do next, worked out from all of the above (the PLAN tabs).
            "plan": {game: mp.next_steps(state, game, here["coords"], getattr(self, "_materials_nearest_cache", None),
                                         mp.hge_summary(state) if game == "horizons" else None) for game in ("odyssey", "horizons")},
            "options": self._materials_options(),
            "online": bool(self._trading_online()) if hasattr(self, "_trading_online") else False,
        }

    def _materials_data(self, name, query):
        """GET /api/data/materials-reference: the page's fixed tables."""
        if name == "materials-reference":
            return mp.reference()
        if name == "materials-summary":
            game = "horizons" if query.get("game") == "horizons" else "odyssey"
            return mp.summary(self._materials_state(), game, str(query.get("list") or "")[:16])
        if name == "materials-ship":
            # One of your ships, its whole latest Loadout (the one you're in: as engineered since).
            state = self._materials_state()
            ship_id = str(query.get("id") or "")
            now = state.get("ship_loadout") or {}
            if ship_id and str(now.get("ShipID")) == ship_id:
                return now
            return (state.get("fleet") or {}).get(ship_id) or {}
        return None

    def _materials_nearest(self, kind):
        """Spansh's nearest material trader or technology broker, kept for ten minutes."""
        if kind not in NEAREST or not hasattr(self, "_trading_task"):
            return False
        from voidcompass.services import spansh
        here = self._materials_here()
        label, trader = NEAREST[kind]
        cache = self.__dict__.setdefault("_materials_nearest_cache", {})
        cache[kind] = {"label": label, "waiting": True, "rows": (cache.get(kind) or {}).get("rows") or [],
                       "system": here["system"]}

        def work():
            if trader:
                return spansh.material_traders(here["system"], trader, size=5, coords=here["coords"])
            return spansh.service_stations(here["system"], "Technology Broker", size=5, coords=here["coords"])

        def done(result, error):
            cache[kind] = {"label": label, "waiting": False, "rows": [row for row in (result or []) if not row.get("carrier")][:5],
                           "error": str(error or "")[:200], "system": here["system"], "at": time.time()}
            self._refresh_html_workspace()

        post = getattr(self, "_ui_post", None)
        self._trading_task("materials-nearest", work, lambda result, error: post(done, result, error) if callable(post) else done(result, error),
                           cache_key=("materials-nearest", kind, here["system"], int(time.time() // NEAREST_TTL_S)))
        return True

    def _html_materials_operation(self, operation, payload):
        state = self._materials_state()
        game = "horizons" if payload.get("game") == "horizons" else "odyssey"
        if operation.startswith("wish_") and operation not in ("wish_share", "wish_import", "wish_from_design"):
            done = mp.wishlist_operation(state, game, operation, payload)
            if done:
                self._materials_changed()
            return done
        if operation == "wish_share":
            chosen = mp.wishlist(state, game, str(payload.get("list_id") or "")[:16])
            if chosen is None:
                return False
            code = mp.share_code("wishlist", {"game": game, "name": chosen["name"], "items": chosen.get("items") or []})
            return self._html_copy_text(code, "wishlist code")
        if operation == "wish_import":
            data = mp.read_share_code(payload.get("code"))
            if not data or data.get("kind") != "wishlist":
                return False
            body = data.get("data") or {}
            game = "horizons" if body.get("game") == "horizons" else "odyssey"
            if not mp.wishlist_operation(state, game, "wish_new", {"name": body.get("name")}):
                return False
            mp.wishlist_operation(state, game, "wish_add", {"items": body.get("items") or []})
            self._materials_changed()
            return True
        if operation == "wish_from_design":
            design = next((row for row in state.get("loadouts") or () if row.get("id") == payload.get("design_id")), None)
            items = mp.design_wishlist_items(design) if design else []
            done = bool(items) and mp.wishlist_operation(state, "odyssey", "wish_add", {"items": items})
            if done:
                self._materials_changed()
            return done
        if operation == "design_save":
            design = mp.clean_design(payload.get("design"))
            rows = [row for row in state.get("loadouts") or () if row.get("id") != design["id"]]
            if len(rows) >= mp.LOADOUT_LIMIT:
                return False
            rows.append(design)
            state["loadouts"] = rows
            self._materials_changed(check=False)
            return True
        if operation == "design_delete":
            before = len(state.get("loadouts") or ())
            state["loadouts"] = [row for row in state.get("loadouts") or () if row.get("id") != payload.get("design_id")]
            if len(state["loadouts"]) != before:
                self._materials_changed(check=False)
                return True
            return False
        if operation == "build_save":
            build = payload.get("build")
            if not isinstance(build, dict) or len(json.dumps(build)) > BUILD_BYTES:
                return False
            build = {**build, "id": str(build.get("id") or mp._new_id())[:16], "name": str(build.get("name") or "Build")[:40],
                     "updated": time.time()}
            rows = [row for row in state.get("ship_builds") or () if row.get("id") != build["id"]]
            if len(rows) >= mp.BUILD_LIMIT:
                return False
            rows.append(build)
            state["ship_builds"] = rows
            self._materials_changed(check=False)
            return True
        if operation == "build_delete":
            before = len(state.get("ship_builds") or ())
            state["ship_builds"] = [row for row in state.get("ship_builds") or () if row.get("id") != payload.get("build_id")]
            if len(state["ship_builds"]) != before:
                self._materials_changed(check=False)
                return True
            return False
        if operation in ("share_design", "share_build"):
            rows = state.get("loadouts" if operation == "share_design" else "ship_builds") or ()
            row = next((r for r in rows if r.get("id") == payload.get("id")), None)
            if row is None:
                return False
            code = mp.build_code(row) if operation == "share_build" else mp.share_code("design", row)
            return self._html_copy_text(code, "share code")
        if operation == "import_code":
            data = mp.read_share_code(payload.get("code"))
            if not data:
                # A materials-helper link, an EDSY or Coriolis wishlist, SLEF, a Loadout or a build link.
                lists, _ = mp.read_import(payload.get("code"))
                added = False
                for game, name, items in lists:
                    if items and mp.wishlist_operation(state, game, "wish_new", {"name": name}):
                        added = mp.wishlist_operation(state, game, "wish_add", {"items": items}) or added
                if added:
                    self._materials_changed()
                return added
            if data.get("kind") == "pins":
                added = mp.import_pins(state, data.get("data"))
                if added:
                    self._materials_changed(check=False)
                return bool(added)
            if data.get("kind") not in ("design", "build", "wishlist"):
                return False
            if data["kind"] == "wishlist":
                return self._html_materials_operation("wish_import", {"code": payload.get("code")})
            body = dict(data.get("data") or {})
            body["id"] = mp._new_id()
            return self._html_materials_operation("design_save" if data["kind"] == "design" else "build_save",
                                                  {"design": body, "build": body})
        if operation in ("pin_add", "pin_remove", "pin_clear"):
            done = mp.pin_operation(state, operation, payload)
            if done:
                self._materials_changed(check=False)
            return done
        if operation == "share_pins":
            pins = state.get("pins") or []
            return bool(pins) and self._html_copy_text(mp.share_code("pins", [{k: p[k] for k in ("module", "name", "engineer")} for p in pins]), "pins code")
        if operation == "relevance_set":
            done = mp.set_relevance(state, payload.get("symbol"), str(payload.get("value") or "auto"))
            if done:
                self._materials_changed(check=False)
            return done
        if operation == "hge_forget":
            before = len(state.get("hge") or ())
            state["hge"] = [row for row in state.get("hge") or () if row.get("id") != payload.get("visit_id")]
            if len(state["hge"]) != before:
                self._materials_changed(check=False)
                return True
            return False
        if operation == "build_import":
            _, build = mp.read_import(payload.get("code"))
            if not build:
                return False
            state["imported_build"] = {"at": time.time(), "loadout": build}
            self._materials_changed(check=False)
            return True
        if operation == "copy_text":
            text = str(payload.get("text") or "")[:20000]
            return bool(text) and self._html_copy_text(text, str(payload.get("label") or "text")[:40])
        if operation == "nearest":
            return self._materials_nearest(str(payload.get("kind") or ""))
        if operation == "goal_forget":
            goals = state.get("goals") or {}
            if goals.pop(str(payload.get("goal_id") or ""), None) is not None:
                self._materials_changed(check=False)
                return True
            return False
        return False

    # -- the Local API --------------------------------------------------------
    def api_materials(self):
        state = self._materials_state()
        here = self._materials_here()
        out = {"odyssey": {"have": mp.odyssey_have(state)}, "horizons": {"have": mp.horizons_have(state)},
               "engineers": state.get("engineers") or {}}
        for game in ("odyssey", "horizons"):
            summary = mp.summary(state, game)
            out[game]["wishlist"] = summary
            out[game]["route"] = mp.engineer_route((summary or {}).get("items") or (), game, here["coords"], state.get("engineers"), state.get("pins"))
        out["horizons"]["high_grade_emissions"] = mp.hge_summary(state)
        return out


__all__ = ["HtmlMaterialsMixin"]
