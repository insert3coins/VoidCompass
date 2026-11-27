"""Settings › Helm (5.8.6) for MainDashboard:
its status and operations, and the silent daily backup of Elite's control files.

Helm asks for a small status while it's on screen (/api/data/helm-status:
what's set up, what's waiting for APPLY, the check, the backups, the crew's
keys); the big tables (every control of a binds file) come from
/api/data/helm-file when its revision changes. Controller presses are
learnt here, not in the page (WebView2 only sees a pad while its window has focus)."""
from __future__ import annotations

import logging
import threading
import time

from voidcompass.helm import assign as bf_assign
from voidcompass.helm import binds as bf
from voidcompass.helm import catalog, rules
from voidcompass.helm import devices as dv
from voidcompass.helm import settings as hs
from voidcompass.helm.store import CLOSE_CONTROLS, DAILY_DAYS, MAPPINGS_KEY, Install, Store, is_binds_name, map_key
from voidcompass.core import controller_input, elite_binds, elite_keys
from voidcompass.core.platform_support import application_dir, open_path

INSTALLS_TTL_S = 60.0
CAPTURE_S = 8.0
NOTICE_S = 90.0
PAD_TOKENS = {"A": "GamePad_FaceDown", "B": "GamePad_FaceRight", "X": "GamePad_FaceLeft", "Y": "GamePad_FaceUp",
              "LB": "GamePad_LBumper", "RB": "GamePad_RBumper", "LS": "GamePad_LThumb", "RS": "GamePad_RThumb",
              "Back": "GamePad_Back", "Start": "GamePad_Start", "Up": "GamePad_DPadUp", "Down": "GamePad_DPadDown",
              "Left": "GamePad_DPadLeft", "Right": "GamePad_DPadRight", "LT": "Pos_GamePad_LTrigger",
              "RT": "Pos_GamePad_RTrigger"}
MOUSE_INPUTS = [("Mouse_1", "Left click"), ("Mouse_2", "Right click"), ("Mouse_3", "Middle click"),
                ("Mouse_4", "Mouse 4"), ("Mouse_5", "Mouse 5"), ("Pos_Mouse_ZAxis", "Wheel up"),
                ("Neg_Mouse_ZAxis", "Wheel down")]
AXES = ["XAxis", "YAxis", "ZAxis", "RXAxis", "RYAxis", "RZAxis", "UAxis", "VAxis"]
SKIPPED = {
    "factory": "is in a built-in preset, which can't be changed: make an editable copy first",
}


def _text(value, limit=200):
    return str(value or "").strip()[:limit]


class DashboardHelmMixin:
    # -- the store ----------------------------------------------------------------------
    def _helm(self):
        store = getattr(self, "_helm_store", None)
        if store is None:
            from voidcompass.core.version import APP_VERSION
            store = self._helm_store = Store(application_dir() / "helm", elite_binds.bindings_folder(),
                                                  self._helm_installs, app_version=APP_VERSION)
        return store

    def _helm_installs(self):
        """Every install of the game found (cached a minute: the running-game probe walks processes)."""
        cached = getattr(self, "_helm_installs_cache", None)
        now = time.monotonic()
        if cached and now - cached[0] < INSTALLS_TTL_S:
            return cached[1]
        chosen = str(self.config.get("elite_game_folder") or "")
        folders = elite_binds.control_scheme_folders(True, None, chosen)
        running = elite_binds.running_game_folder() if not folders else None
        if running is not None:
            folders = elite_binds.control_scheme_folders(True, None, chosen, running)
        installs = [Install(folder) for folder in folders if "odyssey" in str(folder).casefold()
                    or "products" not in str(folder).casefold()]
        self._helm_installs_cache = (now, installs)
        return installs

    def _helm_retention(self):
        days = int(self.config.get("helm_daily_days") or 30)
        keep = int(self.config.get("helm_before_keep") or 100)
        return (days if days in DAILY_DAYS else 30), max(10, min(1000, keep))

    def _helm_start(self):
        """At start: the day's silent backup of every control file, off the UI thread."""
        if getattr(self, "_helm_started", False):
            return
        self._helm_started = True

        def work():
            try:
                path = self._helm().daily_backup(*self._helm_retention())
                if path:
                    logging.info("Helm: daily backup of Elite's control files: %s", path.name)
            except Exception as exc:
                # Tried again at the next start (the same day too).
                logging.warning("Helm's daily backup failed: %s", exc)

        threading.Thread(target=work, name="helm-daily", daemon=True).start()

    def _helm_notice(self, text, severity="info", report=None):
        self._helm_note = {"text": text, "severity": severity, "at": time.time(), "report": report or {}}
        self._schedule_html_dashboard_publish(immediate=True)

    def _helm_changed(self):
        """The game's files were written: the reader and its caches look again."""
        try:
            self._elite_binds().refresh(force=True)
        except Exception:
            logging.debug("Elite's bindings couldn't be re-read", exc_info=True)

    # -- names -------------------------------------------------------------------------
    def _helm_device_labels(self):
        """{device as a binds file writes it: what to call it}: your device names as they are,
        a raw id by the connected controller's own name."""
        store = self._helm()
        labels = {"Keyboard": "Keyboard", "Mouse": "Mouse", "GamePad": "Pad"}
        hub_names = {}
        try:
            hub_names = self._controller_hub().names()
        except Exception:
            pass
        for row in dv.parse_mappings(store.device_files().get(MAPPINGS_KEY) or dv.stock_mappings()):
            labels.setdefault(row["name"], row["name"])
        for ident, name in hub_names.items():
            labels[dv.hex_id(ident)] = name
        return labels

    def _helm_button_labels(self):
        """{(device, token) casefolded: label} from every .buttonMap in the set."""
        out = {}
        for key, data in self._helm().device_files().items():
            if key.endswith(".buttonMap"):
                device = key.rsplit("/", 1)[-1][:-len(".buttonMap")].casefold()
                for token, label in dv.parse_button_map(data).items():
                    if label:
                        out[(device, token.casefold())] = label
        return out

    # -- your controllers: names, labels, ids ------------------------------------------
    def _helm_hub_devices(self):
        try:
            hub = self._controller_hub()
            hub.watch(20)
            hub.refresh()
            if not hub.devices:
                # The hub's own thread may be mid-look (it marks the time first): look now.
                hub.refresh(force=True)
            return list(hub.devices)
        except Exception:
            logging.debug("Controllers couldn't be read for Helm", exc_info=True)
            return []

    def _helm_devices_view(self):
        """Every controller: connected ones by the name the game gives them (or none yet),
        and your named ones that aren't plugged in."""
        store = self._helm()
        files = store.device_files()
        mappings_bytes = files.get(MAPPINGS_KEY) or dv.stock_mappings()
        mappings = dv.parse_mappings(mappings_bytes)
        stock = {dv.fold(name) for name in dv.frontier_names()}
        hub = self._helm_hub_devices()
        taken = [row["name"] for row in mappings] + list(dv.frontier_names())
        maps = {key.rsplit("/", 1)[-1][:-len(".buttonMap")].casefold(): len(dv.parse_button_map(data))
                for key, data in files.items() if key.endswith(".buttonMap")}
        rows, seen = [], set()
        for device in hub:
            if device.get("kind") != "joystick":
                continue
            ident = str(device.get("ident") or "")
            name = dv.resolve(mappings, ident)
            by_id = store.references(dv.by_ident(ident))
            suggest = ""
            if not name:
                suggest = dv.default_name(device.get("name"), taken)
                taken.append(suggest)
            rows.append({"connected": True, "ident": ident, "reported": device.get("name") or "", "name": name,
                         "builtin": bool(name) and dv.fold(name) in stock, "buttons": device.get("buttons") or 0,
                         "axes": device.get("axes") or 0, "hats": device.get("hats") or 0,
                         "labels": maps.get(name.casefold(), 0) if name else 0,
                         "refs": (store.references(dv.by_name(name)) if name else 0) + by_id, "by_id": by_id,
                         "suggest": suggest})
            if name:
                seen.add(name.casefold())
        # Xbox-style pads: listed like the rest; the game knows every one as GamePad already.
        pad_refs = None
        for device in hub:
            if device.get("kind") != "pad":
                continue
            if pad_refs is None:
                pad_refs = store.references(dv.by_name("GamePad"))
            rows.append({"connected": True, "ident": str(device.get("ident") or ""), "reported": device.get("name") or "",
                         "name": "GamePad", "builtin": True, "pad": True, "buttons": device.get("buttons") or 0,
                         "labels": 0, "refs": pad_refs, "by_id": 0, "suggest": ""})
        for entry in dv.user_entries(mappings_bytes):
            if entry["name"].casefold() in seen:
                continue
            rows.append({"connected": False, "ident": (entry["ids"] or [""])[0], "reported": "", "name": entry["name"],
                         "builtin": False, "labels": maps.get(entry["name"].casefold(), 0),
                         "refs": store.references(dv.by_name(entry["name"])), "by_id": 0, "suggest": ""})
        unnamed = [row for row in rows if row["connected"] and not row["name"]]
        return {"rows": rows, "pads": sum(1 for device in hub if device.get("kind") == "pad"),
                "unnamed": len(unnamed), "adopted": store.devices_adopted()}

    def _helm_device_detail(self, name):
        """/api/data/helm-device: one device for its editor (labels by input)."""
        store = self._helm()
        files = store.device_files()
        mappings = dv.parse_mappings(files.get(MAPPINGS_KEY) or dv.stock_mappings())
        entry = next((row for row in mappings if row["name"].casefold() == str(name).casefold()), None)
        if entry is None:
            return {"error": "not found"}
        key = next((k for k in files if k.casefold() == map_key(entry["name"]).casefold()), None)
        labels = dv.parse_button_map(files.get(key)) if key else {}
        hub = next((row for row in self._helm_hub_devices() if row.get("ident") in entry["ids"]), None)
        tokens = dict(dv.default_labels(hub.get("buttons"), hub.get("axes"), hub.get("hats"))) if hub else {}
        for token in labels:
            tokens.setdefault(token, "")
        if not tokens:
            tokens = dv.default_labels(32, 1, 1)
        unnamed = [row for row in self._helm_devices_view()["rows"] if row["connected"] and not row["name"]]
        return {"name": entry["name"], "ids": entry["ids"], "builtin": dv.fold(entry["name"]) in {dv.fold(n) for n in dv.frontier_names()},
                "connected": hub is not None, "reported": (hub or {}).get("name", ""),
                "inputs": [{"token": token, "label": labels.get(token, ""), "default": default}
                           for token, default in tokens.items()],
                "refs": store.references(dv.by_name(entry["name"])),
                "candidates": [{"ident": row["ident"], "reported": row["reported"]} for row in unnamed]}

    def _helm_devices_ready(self, store):
        """Device edits need the installs' device files as one set first."""
        if store.devices_adopted():
            return True
        if store.install_differences():
            self._helm_notice("Your game installs have different device files: choose whose to keep first "
                              "(the banner above).", "warn")
            return False
        ok, message = store.adopt_devices()
        if not ok:
            self._helm_notice(message, "warn")
        return ok

    def _helm_device_op(self, store, operation, payload):
        files = store.device_files()
        mappings = files.get(MAPPINGS_KEY) or dv.stock_mappings()
        entries = dv.parse_mappings(mappings)
        names = [row["name"] for row in entries] + list(dv.frontier_names())
        hub = {row.get("ident"): row for row in self._helm_hub_devices() if row.get("kind") == "joystick"}
        if operation == "name_devices":
            changes, moved, done = {}, 0, []
            for item in payload.get("devices") or []:
                ident, name = _text(item.get("ident"), 9).upper(), _text(item.get("name"), 50)
                problem = dv.name_problem(name, names)
                if problem or ident not in hub or dv.resolve(dv.parse_mappings(mappings), ident):
                    if problem:
                        self._helm_notice(f"{name or 'That name'}: {problem}", "warn")
                        return False
                    continue
                vid, pid = ident.split(":")
                mappings = dv.insert_entry(mappings, name, vid, pid)
                names.append(name)
                key = map_key(name)
                if not any(k.casefold() == key.casefold() for k in files):
                    device = hub[ident]
                    changes[key] = dv.build_button_map(dv.default_labels(device.get("buttons"), device.get("axes"), device.get("hats")))
                done.append((ident, name))
            if not done:
                self._helm_notice("Nothing to name: every connected controller has a name.", "info")
                return True
            changes[MAPPINGS_KEY] = mappings
            store.change_device_files(changes)
            for ident, name in done:
                moved += store.rewrite_references(dv.by_ident(ident), name)
            words = ", ".join(name for _ident, name in done)
            self._helm_notice(f"Named {words}." + (f" {moved} binding{'s' if moved != 1 else ''} will move to "
                                                    f"{'its' if len(done) == 1 else 'their'} name" if moved else "")
                              + ". APPLY writes it to every install.", "success")
            return True
        name = _text(payload.get("name"), 50)
        entry = next((row for row in entries if row["name"].casefold() == name.casefold()), None)
        if entry is None:
            self._helm_notice(f"{name} isn't in your device list.", "warn")
            return False
        builtin = dv.fold(entry["name"]) in {dv.fold(n) for n in dv.frontier_names()}
        old_key = next((k for k in files if k.casefold() == map_key(entry["name"]).casefold()), map_key(entry["name"]))
        if operation == "device_labels":
            labels = {str(k)[:40]: _text(v, 40) for k, v in (payload.get("labels") or {}).items()}
            store.change_device_files({old_key: dv.build_button_map(labels) if any(labels.values()) else None})
            self._helm_notice(f"{entry['name']}'s labels changed: APPLY writes them.", "info")
            return True
        if operation == "reset_labels":
            device = next((row for ident, row in hub.items() if ident in entry["ids"]), None)
            labels = dv.default_labels(device.get("buttons"), device.get("axes"), device.get("hats")) if device \
                else {token: dv.default_labels(64, 1, 4).get(token, token) for token in dv.parse_button_map(files.get(old_key))}
            store.change_device_files({old_key: dv.build_button_map(labels)})
            self._helm_notice(f"{entry['name']}'s labels are back to Button 1, Button 2…: APPLY writes them.", "info")
            return True
        if builtin:
            self._helm_notice(f"{entry['name']} is one of the game's own names: only its labels can change.", "warn")
            return False
        if operation == "rename_device":
            new = _text(payload.get("new"), 50)
            problem = dv.name_problem(new, [n for n in names if n.casefold() != entry["name"].casefold()])
            if problem:
                self._helm_notice(f"{new}: {problem}", "warn")
                return False
            changes = {MAPPINGS_KEY: dv.rename_entry(mappings, entry["name"], new)}
            if old_key in files:
                changes[old_key] = None
                changes[map_key(new)] = files[old_key]
            store.change_device_files(changes)
            moved = store.rewrite_references(dv.by_name(entry["name"]), new)
            self._helm_notice(f"{entry['name']} is now {new}; {moved} binding{'s follow' if moved != 1 else ' follows'}. "
                              "APPLY writes it everywhere.", "success")
            return True
        if operation == "retarget_device":
            ident = _text(payload.get("ident"), 9).upper()
            if ident not in hub:
                self._helm_notice("That controller isn't connected.", "warn")
                return False
            vid, pid = ident.split(":")
            store.change_device_files({MAPPINGS_KEY: dv.retarget_entry(mappings, entry["name"], vid, pid)})
            moved = store.rewrite_references(dv.by_ident(ident), entry["name"])
            self._helm_notice(f"{entry['name']} is now the controller {ident}: its bindings keep working"
                              + (f", and {moved} made on its new id move to its name" if moved else "") + ". APPLY writes it.",
                              "success")
            return True
        if operation == "clear_device":
            first = (entry["ids"] or [""])[0]
            changes = {MAPPINGS_KEY: dv.remove_entry(mappings, entry["name"])}
            if old_key in files:
                changes[old_key] = None
            store.change_device_files(changes)
            moved = store.rewrite_references(dv.by_name(entry["name"]), dv.hex_id(first)) if first else 0
            self._helm_notice(f"{entry['name']} is no longer named; {moved} binding{'s go' if moved != 1 else ' goes'} back to "
                              "its id. APPLY writes it.", "info")
            return True
        return False

    # -- the crew ----------------------------------------------------------------------
    def _helm_crew(self, files=None):
        """The actions the crew presses, where each is and the key it has (in the set with your edits)."""
        store = self._helm()
        files = store.current() if files is None else files
        try:
            wanted = self._ship_wanted_actions()
        except Exception:
            logging.debug("The crew's actions couldn't be listed", exc_info=True)
            wanted = {}
        sections = {row["section"]: row for row in store.sections(files)}
        parsed = {}
        rows = []
        for action, says in sorted(wanted.items(), key=lambda item: catalog.lookup(item[0]).order):
            section = elite_binds.group_of(action)
            where = sections.get(section) or {}
            row = {"action": action, "name": catalog.lookup(action).name, "label": catalog.label(action),
                   "section": section, "preset": where.get("preset", ""), "kind": where.get("kind", "missing"),
                   "file": where.get("file", ""), "says": says[:4], "key": "", "state": "missing"}
            data = None
            if where.get("kind") == "user":
                data = files.get(where["file"])
            elif where.get("kind") == "factory":
                data = store.read_binds(where["file"])
            if data is not None:
                cache_key = where["file"]
                if cache_key not in parsed:
                    try:
                        parsed[cache_key] = bf.parse(data)
                    except ValueError:
                        parsed[cache_key] = None
                binds = parsed[cache_key]
                if binds is not None:
                    slot = next((s for s in binds.slots(action) if s.keyboard_usable(binds.layout)), None)
                    if slot is not None:
                        odd = elite_keys.pressable(slot.key, [k for _d, k in slot.modifiers])
                        row["key"] = rules.slot_label(slot)
                        row["state"] = "odd" if odd else "ready"
                    elif action not in binds.buttons:
                        row["state"] = "absent"
                    elif any(s.assigned() for s in binds.slots(action)):
                        row["state"] = "device"
                        row["device"] = " / ".join(rules.slot_label(s) for s in binds.slots(action) if s.assigned())
            rows.append(row)
        return rows

    def _helm_crew_assign(self, actions=None):
        """ASSIGN MISSING KEYS: safe free keys for the crew's actions, as edits (APPLY writes them)."""
        store = self._helm()
        files = store.current()
        crew = [row for row in self._helm_crew(files) if row["state"] in ("missing", "device")
                and (actions is None or row["action"] in actions)]
        if not crew:
            return {"ok": True, "assigned": [], "skipped": [], "text": "Every key the crew needs is there."}
        by_file, skipped = {}, []
        for row in crew:
            if row["kind"] == "user":
                by_file.setdefault(row["file"], []).append(row["action"])
            else:
                skipped.append({"action": row["action"], "reason": "factory" if row["kind"] == "factory" else "absent",
                                "preset": row["preset"]})
        active = {row["file"] for row in store.sections(files) if row["kind"] == "user"}

        def usable(key, modifier):
            return not elite_keys.pressable(key, [modifier] if modifier else [])

        assigned = []
        for name, wanted in by_file.items():
            try:
                binds = bf.parse(files[name])
            except (KeyError, ValueError):
                skipped += [{"action": action, "reason": "unreadable"} for action in wanted]
                continue
            others = set()
            for other in active - {name}:
                try:
                    others |= bf_assign.taken_chords(bf.parse(files[other]))
                except (KeyError, ValueError):
                    pass
            plan = bf_assign.plan(binds, wanted, others, usable)
            for edit in plan["edits"]:
                modifiers = [(bf.KEYBOARD, edit["modifier"])] if edit["modifier"] else []
                result = store.change_binds(name, lambda data, e=edit, m=modifiers: bf.assign_slot(
                    data, e["action"], e["position"], bf.KEYBOARD, e["key"], m))
                if result == bf.SAVED:
                    assigned.append({**edit, "file": name, "label": catalog.label(edit["action"]),
                                     "chord": " + ".join(rules.key_name(k) for k in (edit["modifier"], edit["key"]) if k)})
                else:
                    skipped.append({"action": edit["action"], "reason": result})
            skipped += plan["skipped"]
        for row in skipped:
            row["label"] = catalog.label(row["action"])
            row["why"] = SKIPPED.get(row["reason"]) or bf_assign.SKIP_REASONS.get(row["reason"]) or row["reason"]
        text = (f"{len(assigned)} key{'s' if len(assigned) != 1 else ''} assigned: check them on CREW KEYS, then APPLY."
                if assigned else "No key could be assigned.")
        return {"ok": bool(assigned), "assigned": assigned, "skipped": skipped, "text": text}

    # -- the page ----------------------------------------------------------------------
    def _helm_live_stamp(self, store):
        """The bindings folder's files and their times: a change outside sends the page through the check."""
        if not store.folder_found():
            return ()
        try:
            return tuple(sorted((path.name, path.stat().st_mtime_ns) for path in store.folder.iterdir()
                                if path.is_file() and (path.suffix.casefold() in (".binds", ".start"))))
        except OSError:
            return ()

    def _helm_game_running(self):
        """Is Elite running? Asked every few seconds at most (it walks the processes)."""
        seen = getattr(self, "_helm_running_seen", None)
        now = time.monotonic()
        if seen is None or now - seen[0] > 5:
            seen = self._helm_running_seen = (now, bool(elite_binds.game_running()))
        return seen[1]

    def _html_helm_workspace(self):
        """/api/data/helm-status: asked only while Settings › Helm is on screen."""
        store = self._helm()
        stamp = self._helm_live_stamp(store)
        if store.set_up() and stamp != getattr(self, "_helm_checked_stamp", None):
            # The first look this session, and after the game changed a file: check by value.
            self._helm_checked_stamp = stamp
            try:
                self._helm_check = store.check()
            except Exception as exc:
                logging.warning("Helm's check failed: %s", exc)
                self._helm_check = {"changed": False, "files": [], "error": str(exc)}
        files = store.current()
        note = getattr(self, "_helm_note", None)
        if note and time.time() - note["at"] > NOTICE_S:
            note = self._helm_note = None
        days, keep = self._helm_retention()
        sections = store.sections(files)
        capture = dict(getattr(self, "_helm_capturing", None) or {})
        return {
            "revision": store.revision,
            "set_up": store.set_up(),
            "folder": str(store.folder or ""),
            "folder_found": store.folder_found(),
            "installs": [install.as_dict() for install in store.installs()],
            "sections": sections,
            "files": store.user_binds_files(files),
            "factories": sorted(store.factory_files(), key=str.casefold),
            "pending": store.pending(),
            "check": getattr(self, "_helm_check", None) if store.set_up() else None,
            "backups": store.backups()[:200],
            "backups_folder": str(store.backups_dir),
            "retention": {"daily_days": days, "before_keep": keep, "choices": list(DAILY_DAYS)},
            "crew": self._helm_crew(files),
            "notice": note,
            "capture": capture,
            "close_controls": CLOSE_CONTROLS,
            # Void Compass's own shortcuts live here too (they were Settings › Hotkeys).
            "shortcuts": self._html_shortcuts(),
            "devices": self._helm_devices_view() if store.set_up() else None,
            "game_running": self._helm_game_running(),
        }

    def _helm_file_rows(self, name):
        """/api/data/helm-file: every control of one binds file (yours, or a built-in one to look at)."""
        store = self._helm()
        files = store.current()
        own = next((key for key in files if key.casefold() == str(name).casefold()), None)
        data = files[own] if own else store.read_binds(name)
        if data is None:
            return {"error": "not found", "file": name}
        try:
            binds = bf.parse(data)
        except ValueError as exc:
            return {"error": f"This file can't be read: {exc}", "file": name}
        labels = self._helm_device_labels()
        device_label = labels.get
        button_labels = self._helm_button_labels()
        tags = sorted(set(binds.buttons) | set(binds.axes),
                      key=lambda tag: (catalog.lookup(tag).order, tag.casefold()))
        rows = []
        for tag in tags:
            control = catalog.lookup(tag)
            row = {"tag": tag, "section": catalog.section_of(tag), "group": control.group or "",
                   "name": control.name, "order": control.order}
            if tag in binds.buttons:
                row["kind"] = "button"
                row["slots"] = [{**slot.as_dict(), "label": rules.slot_label(slot, device_label, button_labels),
                                 "assigned": slot.assigned(), "keyboard": slot.keyboard_usable(binds.layout)}
                                if slot else None for slot in (binds.buttons[tag].get(bf.PRIMARY),
                                                               binds.buttons[tag].get(bf.SECONDARY))]
            else:
                axis = binds.axes[tag]
                row["kind"] = "axis"
                row["axis"] = {**axis.as_dict(), "label": rules.input_label(axis.device, axis.key,
                                                                             device_label(axis.device), button_labels)
                               if axis.bound() else ""}
            rows.append(row)
        sections = [row["section"] for row in store.sections(files) if row["file"] in (own, name)
                    or row["file"].casefold() == str(name).casefold()]
        try:
            wanted = self._ship_wanted_actions()
        except Exception:
            wanted = {}
        settings = [{"tag": tag, "value": value["value"], "editable": value["editable"],
                     "name": catalog.lookup(tag).name, "group": catalog.lookup(tag).group or ""}
                    for tag, value in sorted(binds.settings.items())]

        def order(tag):
            return catalog.lookup(tag).order, tag.casefold()
        toggles = [{"tag": tag, "name": catalog.lookup(tag).name, "group": catalog.lookup(tag).group or "Other",
                    "section": catalog.section_of(tag), "on": binds.settings[tag]["value"] == "1",
                    "editable": binds.settings[tag]["editable"]}
                   for tag in sorted(set(binds.settings) & hs.TOGGLES, key=order)]
        numbers = [{"tag": tag, "name": catalog.lookup(tag).name, "group": catalog.lookup(tag).group or "Other",
                    "value": hs.shown(binds.settings[tag]["value"]), "editable": binds.settings[tag]["editable"],
                    "range": list(hs.NUMBERS[tag]) if hs.NUMBERS[tag] else None}
                   for tag in sorted(set(binds.settings) & set(hs.NUMBERS), key=order)]
        throttles = [{"axis": axis, "name": catalog.lookup(axis).name, "setting": setting,
                      "reading": hs.throttle_reading(axis, binds.settings[setting]["value"]),
                      "editable": binds.settings[setting]["editable"], "forward": forward}
                     for axis, (setting, forward, _also) in hs.THROTTLE.items() if setting in binds.settings]
        deadzones = [{"tag": tag, "name": catalog.lookup(tag).name, "group": catalog.lookup(tag).group or "",
                      "section": catalog.section_of(tag), "deadzone": round(axis.deadzone, 3), "bound": axis.bound(),
                      "editable": axis.editable, "device": axis.device, "key": axis.key, "inverted": axis.inverted,
                      "label": rules.input_label(axis.device, axis.key, device_label(axis.device), button_labels) if axis.bound() else ""}
                     for tag, axis in sorted(binds.axes.items(), key=lambda item: order(item[0])) if axis.bound()]
        return {
            "file": own or name, "editable": bool(own) and is_binds_name(own), "preset_name": binds.preset_name,
            "layout": binds.layout, "azerty": bf.is_azerty(binds.layout), "sections_using": sections,
            "rows": rows, "settings": settings, "toggles": toggles, "numbers": numbers, "throttles": throttles,
            "deadzones": deadzones, "conflicts": rules.scan(binds), "reserved": rules.reserved(binds),
            "invalid": rules.layout_invalid(binds), "twins": rules.twins(binds),
            "crew": sorted(wanted), "devices": labels,
            "inputs": {"mouse": MOUSE_INPUTS, "axes": AXES, "keys": bf_assign.ASSIGNABLE_KEYS,
                       "pad": [[name, token] for name, token in PAD_TOKENS.items()]},
            "revision": store.revision,
        }

    def _helm_data(self, name, query):
        if name == "helm-status":
            return self._html_helm_workspace()
        if name == "helm-file":
            return self._helm_file_rows(_text(query.get("name"), 200))
        if name == "helm-holder":
            return self._helm_holder(query)
        if name == "helm-capture":
            return dict(getattr(self, "_helm_capturing", None) or {})
        if name == "helm-live":
            # DEVICES' button tester: what's held and where every axis is, polled while it's open.
            hub = self._controller_hub()
            hub.watch(20)
            return hub.live()
        if name == "helm-diff":
            return {"rows": self._helm().diff_rows(_text(query.get("name"), 200))}
        if name == "helm-device":
            return self._helm_device_detail(_text(query.get("name"), 60))
        return None

    def _helm_holder(self, query):
        """Which other control already takes an input the capture dialog is about to set."""
        store = self._helm()
        data = store.read_binds(_text(query.get("file"), 200))
        if data is None:
            return {"holder": None}
        try:
            binds = bf.parse(data)
        except ValueError:
            return {"holder": None}
        modifiers = []
        for part in _text(query.get("mods"), 400).split(","):
            device, _, key = part.partition("|")
            if device and key:
                modifiers.append((device, key))
        action = _text(query.get("action"), 120)
        holder = rules.holder_of(binds, action, _text(query.get("device"), 120), _text(query.get("key"), 120),
                                 modifiers, query.get("hold") in ("1", "true"))
        reserved = ""
        if _text(query.get("device"), 20) == bf.KEYBOARD and action != rules.GAME_MENU:
            reserved = rules.reserved_reason(_text(query.get("key"), 120), [k for _d, k in modifiers],
                                             rules.game_menu_keys(binds))
        return {"holder": holder, "holder_label": catalog.label(holder) if holder else "", "reserved": reserved}

    # -- capturing a controller press ---------------------------------------------------
    def _helm_spec_input(self, spec):
        """A learnt controller spec as the binds file writes it: (device, key, modifiers) or None."""
        pair = controller_input.split(spec)
        if pair is None:
            return None
        mappings = dv.parse_mappings(self._helm().device_files().get(MAPPINGS_KEY) or dv.stock_mappings())
        by_id = {}
        for row in mappings:  # the first entry claiming an id is the one the game uses
            for ident in row["ids"]:
                by_id.setdefault(ident, row["name"])

        def one(part):
            parsed = controller_input.parse(part)
            if parsed is None:
                return None
            if parsed[0] == "pad":
                return "GamePad", PAD_TOKENS[parsed[1]]
            device = by_id.get(parsed[1]) or parsed[1].replace(":", "")
            if parsed[0] == "joy":
                return device, f"Joy_{parsed[2]}"
            return device, f"Joy_POV1{parsed[2]}"
        held, pressed = pair
        main = one(pressed)
        if main is None:
            return None
        modifiers = [one(held)] if held else []
        if any(modifier is None for modifier in modifiers):
            return None
        return main[0], main[1], modifiers

    def _helm_capture_start(self, token):
        hub = self._controller_hub()
        hub.cancel_learning()
        self._helm_capturing = {"token": token, "status": "listening", "at": time.time()}
        self._schedule_html_dashboard_publish(immediate=True)

        def work():
            spec = hub.learn(CAPTURE_S)
            current = getattr(self, "_helm_capturing", None) or {}
            if current.get("token") != token:
                return
            found = self._helm_spec_input(spec) if spec else None
            if found is None:
                self._helm_capturing = {"token": token, "status": "none", "at": time.time()}
            else:
                device, key, modifiers = found
                labels = self._helm_device_labels()
                label = " + ".join(rules.input_label(d, k, labels.get(d)) for d, k in [*modifiers, (device, key)])
                self._helm_capturing = {"token": token, "status": "done", "at": time.time(), "device": device,
                                             "key": key, "modifiers": [list(m) for m in modifiers], "label": label}
            self._ui_post(self._schedule_html_dashboard_publish, immediate=True, key="helm-capture")

        threading.Thread(target=work, name="helm-capture", daemon=True).start()
        return True

    # -- operations ----------------------------------------------------------------------
    def _html_helm_operation(self, operation, payload):
        store = self._helm()
        if operation == "setup":
            ok, message = store.setup()
            self._helm_check = store.check() if ok else None
            self._helm_notice(message, "success" if ok else "warn")
            return ok
        if operation in ("assign", "clear"):
            return self._helm_assign(store, operation, payload)
        if operation == "axis":
            name, tag = _text(payload.get("file"), 200), _text(payload.get("tag"), 120)
            device, key = _text(payload.get("device"), 120), _text(payload.get("key"), 120)
            try:
                zone = float(payload.get("deadzone") or 0)
            except (TypeError, ValueError):
                zone = 0.0
            result = store.change_binds(name, lambda data: bf.assign_axis(
                data, tag, device, key, bool(payload.get("inverted")), zone))
            return self._helm_result(result, catalog.label(tag))
        if operation == "setting":
            name, tag = _text(payload.get("file"), 200), _text(payload.get("tag"), 120)
            value = _text(payload.get("value"), 60)
            if tag in hs.TOGGLES:
                value = "1" if value in ("1", "true", "on") else "0"
            elif tag in hs.NUMBERS:
                value, why = hs.judge(tag, value)
                if value is None:
                    self._helm_notice(f"{catalog.lookup(tag).name}: {why}", "warn")
                    return False
            result = store.change_binds(name, lambda data: bf.assign_setting(data, tag, value))
            return self._helm_result(result, catalog.lookup(tag).name)
        if operation == "presets":
            lines = [_text(line, 60) for line in payload.get("lines") or []]
            ok = store.set_presets(lines)
            if ok:
                self._helm_notice("Presets changed: APPLY writes them.", "info")
            return ok
        if operation == "copy_factory":
            sections = [s for s in payload.get("sections") or [] if s in catalog.SECTIONS] or list(catalog.SECTIONS)
            ok, message = store.copy_factory(_text(payload.get("factory"), 80), _text(payload.get("name"), 40), sections)
            self._helm_notice(message + (" APPLY writes it." if ok else ""), "success" if ok else "warn")
            return ok
        if operation == "crew_assign":
            actions = payload.get("actions")
            report = self._helm_crew_assign(set(actions) if isinstance(actions, list) else None)
            self._helm_notice(report["text"], "success" if report["ok"] else "warn", report)
            return True
        if operation == "discard":
            store.discard()
            self._helm_notice("Your edits were discarded.", "info")
            return True
        if operation == "apply":
            report = store.apply()
            if report.get("check"):
                self._helm_check = store.check()
            return self._helm_report(report, "Applied. Your files were backed up first.")
        if operation == "check":
            self._helm_check = store.check()
            self._helm_checked_stamp = self._helm_live_stamp(store)
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "keep_mine":
            report = store.keep_mine()
            self._helm_check = store.check()
            return self._helm_report(report, "Your working copy is back in the game's files.")
        if operation in ("name_devices", "device_labels", "reset_labels", "rename_device", "retarget_device", "clear_device"):
            if not store.set_up():
                self._helm_notice("Set Helm up first (the banner above).", "warn")
                return False
            if not self._helm_devices_ready(store):
                return False
            return self._helm_device_op(store, operation, payload)
        if operation == "adopt_devices":
            picks = {str(k)[:200]: _text(v, 60) for k, v in (payload.get("picks") or {}).items()}
            ok, message = store.adopt_devices(picks=picks, base=_text(payload.get("base"), 60) or None)
            self._helm_check = store.check()
            self._helm_notice(message, "success" if ok else "warn")
            return ok
        if operation == "merge_file":
            picks = {str(k)[:120]: _text(v, 8) for k, v in (payload.get("picks") or {}).items()}
            report = store.merge_file(_text(payload.get("file"), 200), picks)
            self._helm_check = store.check()
            return self._helm_report(report, "Merged: what you chose from each side is in both.")
        if operation == "merge_install":
            picks = {str(k)[:200]: _text(v, 8) for k, v in (payload.get("picks") or {}).items()}
            report = store.merge_install(_text(payload.get("install"), 60), picks)
            self._helm_check = store.check()
            return self._helm_report(report, "Merged: every install now has the same device files.")
        if operation == "throttle":
            name, axis = _text(payload.get("file"), 200), _text(payload.get("axis"), 40)
            if axis not in hs.THROTTLE:
                return False
            setting, forward, _also = hs.THROTTLE[axis]
            value = forward if payload.get("forward") else ""
            result = store.change_binds(name, lambda data: bf.assign_setting(data, setting, value))
            return self._helm_result(result, catalog.lookup(axis).name + " range")
        if operation == "take_games":
            report = store.take_games(_text(payload.get("install"), 60) or None)
            self._helm_check = store.check()
            return self._helm_report(report, "The game's files are now Helm's working copy.")
        if operation == "backup_now":
            try:
                path = store.backup("user", _text(payload.get("note"), 80))
            except OSError as exc:
                self._helm_notice(f"The backup couldn't be made: {exc}", "warn")
                return False
            self._helm_notice(f"Backed up: {path.name}.", "success")
            return True
        if operation == "restore":
            report = store.restore(_text(payload.get("id"), 120))
            self._helm_check = store.check()
            return self._helm_report(report, "Restored. What was there is backed up too.")
        if operation == "delete_backup":
            ok = store.delete_backup(_text(payload.get("id"), 120))
            self._helm_notice("Backup deleted." if ok else "Only your own backups can be deleted.",
                                   "info" if ok else "warn")
            return ok
        if operation == "open_folder":
            target = {"backups": store.backups_dir, "bindings": store.folder,
                      "working": store.working_dir}.get(_text(payload.get("which"), 20))
            if target is None:
                return False
            if target == store.backups_dir:
                target.mkdir(parents=True, exist_ok=True)
            return bool(open_path(target))
        if operation == "retention":
            days = int(payload.get("daily_days") or 30)
            keep = int(payload.get("before_keep") or 100)
            self.config["helm_daily_days"] = days if days in DAILY_DAYS else 30
            self.config["helm_before_keep"] = max(10, min(1000, keep))
            self._persist_config()
            store.prune(*self._helm_retention())
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "capture":
            return self._helm_capture_start(_text(payload.get("token"), 40) or str(time.time()))
        if operation == "capture_cancel":
            self._helm_capturing = None
            self._controller_hub().cancel_learning()
            return True
        return False

    def _helm_assign(self, store, operation, payload):
        name, tag = _text(payload.get("file"), 200), _text(payload.get("tag"), 120)
        position = bf.SECONDARY if payload.get("position") == bf.SECONDARY else bf.PRIMARY
        if operation == "clear":
            result = store.change_binds(name, lambda data: bf.clear_slot(data, tag, position))
            return self._helm_result(result, catalog.label(tag), cleared=True)
        device, key = _text(payload.get("device"), 120), _text(payload.get("key"), 120)
        modifiers = []
        for item in payload.get("modifiers") or []:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                modifiers.append((_text(item[0], 120), _text(item[1], 120)))
        result = store.change_binds(name, lambda data: bf.assign_slot(
            data, tag, position, device, key, modifiers, bool(payload.get("hold"))))
        return self._helm_result(result, catalog.label(tag))

    def _helm_result(self, result, label, cleared=False):
        texts = {
            bf.SAVED: (f"{label}: cleared." if cleared else f"{label}: set.") + " APPLY writes it.",
            bf.NO_CHANGE: f"{label}: no change.",
            bf.UNKNOWN_KEY: f"{label}: that input can't go in this slot.",
            bf.NOT_FOUND: f"{label} isn't in this file.",
            bf.UNSUPPORTED: f"{label} is written in a way Helm won't rewrite, so it was left alone.",
        }
        ok = result in (bf.SAVED, bf.NO_CHANGE)
        self._helm_notice(texts.get(result, str(result)), "info" if ok else "warn", {"result": result})
        return ok

    def _helm_report(self, report, success):
        if report.get("refused"):
            self._helm_notice(report["refused"], "warn", report)
            return False
        failed = report.get("failed") or []
        written = list(report.get("written") or []) + [f"{row['install']}: {item}" for row in report.get("installs") or []
                                                        for item in row.get("written") or []]
        installs = [row for row in report.get("installs") or [] if row.get("state") in ("failed", "unreachable")]
        if failed or installs:
            names = ", ".join(row["file"] for row in failed) or ", ".join(row["install"] for row in installs)
            text = (f"Updated {len(written)} of {len(written) + len(failed)} file(s): {names} couldn't be written. "
                    "The next check offers to put it right.")
            self._helm_notice(text, "warn", report)
        else:
            text = success if written else success.replace("Applied.", "Nothing needed writing.")
            self._helm_notice(text + (f" Backup: {report['backup']}." if report.get("backup") else ""),
                                   "success", report)
        self._helm_checked_stamp = self._helm_live_stamp(self._helm())
        self._helm_changed()
        return not failed
