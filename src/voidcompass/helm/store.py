"""Where Helm keeps your control files safe, and the one way it writes them.

The files it looks after ("the set"):
- the bindings folder (%LOCALAPPDATA%\\Frontier Developments\\Elite Dangerous\\
  Options\\Bindings): StartPreset.N.start and every <name>.<major>.<minor>.binds;
- each game install's Products\\elite-dangerous-odyssey-64\\ControlSchemes:
  DeviceMappings.xml and DeviceButtonMaps\\*.buttonMap.

The working copy, in Void Compass's own folder, is what Helm last wrote:
the source of truth once it's set up. Edits stay in memory until APPLY, which
checks nothing changed outside, backs everything up, saves the working copy and
writes the files that differ. Every backup is a zip of the live files, in
Void Compass's folder (never the game's, where an update could delete it):
daily (the first start each day), before changes (every write), yours (BACK UP
NOW) and first setup (kept forever). Nothing reaches the game's files unless
you press APPLY, RESTORE or KEEP MINE."""
from __future__ import annotations

from datetime import datetime
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import threading
import time
import xml.etree.ElementTree as ET
import zipfile

from voidcompass.helm import binds as bf
from voidcompass.helm import catalog
from voidcompass.helm import devices as dv

PRESET_FILE = "StartPreset.4.start"
SECTIONS = catalog.SECTIONS
DAILY, BEFORE, USER, FIRST = "daily", "before", "user", "first"
KINDS = (DAILY, BEFORE, USER, FIRST)
KIND_LABELS = {DAILY: "Daily", BEFORE: "Before a change", USER: "Yours", FIRST: "First setup"}
DAILY_DAYS = (30, 60, 90, 180)
_BINDS_NAME = re.compile(r"(.+)\.(\d+)\.(\d+)\.binds", re.I)
_PRESET_NAME = re.compile(r"StartPreset\.(\d+)\.start", re.I)
_NAME_RULE = re.compile(r"[A-Za-z][A-Za-z0-9 _-]{0,39}")
_TMP = ".voidcompass-tmp"
CLOSE_CONTROLS = ("Close the game's Options › Controls screen before applying: the game writes its own copy back "
                  "when you apply there, and changes made in both at once can be lost.")


def is_binds_name(name):
    return bool(_BINDS_NAME.fullmatch(name or ""))


def binds_name_parts(name):
    match = _BINDS_NAME.fullmatch(name or "")
    return (match.group(1), int(match.group(2)), int(match.group(3))) if match else None


DEVICES = "ControlSchemes/"
MAPPINGS_KEY = DEVICES + dv.MAPPINGS


def is_device_key(key):
    """A device file in a set: "ControlSchemes/DeviceMappings.xml", "ControlSchemes/DeviceButtonMaps/X.buttonMap"."""
    return str(key).startswith(DEVICES)


def map_key(name):
    return f"{DEVICES}{dv.MAPS_DIR}/{name}.buttonMap"


def bindings_of(files):
    return {key: value for key, value in files.items() if not is_device_key(key)}


def devices_of(files):
    return {key: value for key, value in files.items() if is_device_key(key)}


def same_devices(a, b):
    """Two device sets hold the same values (layout and line endings aside)."""
    folded_a = {key.casefold(): value for key, value in a.items()}
    folded_b = {key.casefold(): value for key, value in b.items()}
    return folded_a.keys() == folded_b.keys() and all(
        bf.canonical(folded_a[key]) == bf.canonical(folded_b[key]) for key in folded_a)


def is_preset_name(name):
    return bool(_PRESET_NAME.fullmatch(name or ""))


def managed_name(name):
    return is_binds_name(name) or is_preset_name(name)


def fold_name(name):
    """Two preset names the game could mix up: case, - and _ don't count."""
    return str(name).casefold().replace("-", "_").replace(" ", "_")


def same_name(a, b):
    """The game reads file names the Windows way: case doesn't count."""
    return str(a).casefold() == str(b).casefold()


class Install:
    """One copy of the game: its ControlSchemes folder."""

    def __init__(self, schemes, label=""):
        self.schemes = Path(schemes)
        self.label = label or install_label(self.schemes)

    @property
    def key(self):
        return str(self.schemes).casefold()

    def reachable(self):
        return self.schemes.is_dir()

    def as_dict(self):
        return {"label": self.label, "path": str(self.schemes), "reachable": self.reachable()}


def install_label(schemes):
    text = str(schemes).casefold()
    if "steamapps" in text:
        return "Steam"
    if "epic" in text:
        return "Epic"
    if "frontier" in text:
        return "Frontier"
    return "Game folder"


def read_device_files(install):
    """{"DeviceMappings.xml": bytes, "DeviceButtonMaps/X.buttonMap": bytes} of one install
    (a backup's layout; device_set() is the same with the working copy's prefix)."""
    files = {}
    try:
        files["DeviceMappings.xml"] = (install.schemes / "DeviceMappings.xml").read_bytes()
    except OSError:
        pass
    maps = install.schemes / "DeviceButtonMaps"
    try:
        for path in sorted(maps.iterdir()):
            if path.is_file() and path.suffix.casefold() == ".buttonmap":
                files[f"DeviceButtonMaps/{path.name}"] = path.read_bytes()
    except OSError:
        pass
    return files


def device_names(installs):
    """DeviceMappings.xml: {name as written: {"VVVV:PPPP", ...}}, from the first install that has one."""
    for install in installs:
        try:
            root = ET.parse(install.schemes / "DeviceMappings.xml").getroot()
        except (OSError, ET.ParseError):
            continue
        found = {}
        for device in root:
            ids = set()
            for node in [device, *device.findall("Alternative")]:
                vid, pid = (node.findtext("VID") or "").strip(), (node.findtext("PID") or "").strip()
                if vid and pid:
                    ids.add(f"{vid.upper().zfill(4)}:{pid.upper().zfill(4)}")
            if ids:
                found[device.tag] = ids
        return found
    return {}


def device_set(install):
    """An install's device files as the working copy keys them."""
    return {DEVICES + name: data for name, data in read_device_files(install).items()}


def device_items(sets):
    """What differs between device sets ({label: set}): [{item, kind, name, values: {label: summary}}]
    One item per DeviceMappings entry and per .buttonMap."""
    entries = {}
    for label, files in sets.items():
        mappings = files.get(MAPPINGS_KEY)
        text = ""
        if mappings:
            try:
                text = bf._text(mappings)[0]
            except UnicodeDecodeError:
                text = ""
        for row in dv.parse_mappings(mappings):
            spans = bf._spans(text, row["name"]) if text else []
            form = " ".join(text[spans[0][0]:spans[0][1]].split()) if spans else ""
            entries.setdefault(row["name"], {})[label] = (form, ", ".join(row["ids"][:3]) + (" …" if len(row["ids"]) > 3 else ""))
    labels = list(sets)
    out = []
    for name, seen in sorted(entries.items(), key=lambda item: item[0].casefold()):
        forms = {label: seen.get(label, (None, ""))[0] for label in labels}
        if len(set(forms.values())) > 1:
            out.append({"item": f"device:{name}", "kind": "device", "name": name,
                        "values": {label: (seen[label][1] if label in seen else "not there") for label in labels}})
    maps = sorted({key for files in sets.values() for key in files if key.endswith(".buttonMap")}, key=str.casefold)
    for key in maps:
        values = {label: files.get(key) for label, files in sets.items()}
        forms = {label: (bf.canonical(value) if value else None) for label, value in values.items()}
        if len({repr(form) for form in forms.values()}) > 1:
            name = key.rsplit("/", 1)[-1][:-len(".buttonMap")]
            out.append({"item": f"map:{key}", "kind": "labels", "name": name,
                        "values": {label: (f"{len(dv.parse_button_map(value))} labels" if value else "not there")
                                   for label, value in values.items()}})
    return out


def merge_devices(base, sources, picks):
    """``base`` (a device set) with each picked item taken from ``sources[picks[item]]``."""
    merged = dict(base)
    for item, label in picks.items():
        source = sources.get(label)
        if source is None:
            continue
        if item.startswith("device:"):
            name = item[len("device:"):]
            mine = merged.get(MAPPINGS_KEY) or dv.stock_mappings()
            theirs = source.get(MAPPINGS_KEY) or dv.stock_mappings()
            merged[MAPPINGS_KEY] = bf.copy_element(mine, theirs, name)
        elif item.startswith("map:"):
            key = item[len("map:"):]
            if source.get(key) is None:
                merged.pop(key, None)
            else:
                merged[key] = source[key]
    return merged


def preset_lines(data):
    """The four lines (General, Ship, SRV, On foot) of a preset file; one line counts for all four."""
    if data is None:
        return []
    text = data.decode("utf-8-sig", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    return (lines + [lines[-1]] * 4)[:4]


def preset_bytes(lines, before=None):
    """Four lines as the game writes them (keeping the old file's line ending and BOM)."""
    newline, bom = "\r\n", b""
    if isinstance(before, (bytes, bytearray)):
        newline = "\r\n" if b"\r\n" in before else "\n" if b"\n" in before else "\r\n"
        bom = b"\xef\xbb\xbf" if before.startswith(b"\xef\xbb\xbf") else b""
    trailing = newline if not isinstance(before, (bytes, bytearray)) or before.rstrip(b"\r\n") != before else ""
    return bom + (newline.join(lines) + trailing).encode("utf-8")


def preset_file_of(files):
    """The preset file the game reads: the highest StartPreset.N.start in the set."""
    found = [(int(_PRESET_NAME.fullmatch(name).group(1)), name) for name in files if is_preset_name(name)]
    return max(found)[1] if found else None


class Store:
    def __init__(self, root, bindings_folder, installs=lambda: [], clock=time.time, app_version=""):
        self.root = Path(root)
        self.folder = Path(bindings_folder) if bindings_folder else None
        self._installs = installs
        self.clock = clock
        self.app_version = app_version
        self.edits = {}          # name -> bytes (changed) or None (removed)
        self.lock = threading.RLock()
        self._factory_cache = {}
        self._working_cache = None
        self._backups_cache = None
        self._factories_cache = None
        self.revision = 0

    # -- places ------------------------------------------------------------------------
    @property
    def working_dir(self):
        return self.root / "working"

    @property
    def backups_dir(self):
        return self.root / "backups"

    def installs(self):
        try:
            found = list(self._installs() or ())
        except Exception:
            logging.debug("Helm couldn't list the game's installs", exc_info=True)
            found = []
        seen, out = set(), []
        for install in found:
            install = install if isinstance(install, Install) else Install(install)
            if install.key not in seen:
                seen.add(install.key)
                out.append(install)
        return out

    def folder_found(self):
        return self.folder is not None and self.folder.is_dir()

    def _state_path(self):
        return self.root / "state.json"

    def state(self):
        try:
            return json.loads(self._state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, **changes):
        state = self.state()
        state.update(changes)
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, self._state_path())

    # -- reading -----------------------------------------------------------------------
    def live(self):
        """The set as the game has it now: {name: bytes}."""
        files = {}
        if not self.folder_found():
            return files
        for path in self.folder.iterdir():
            if path.is_file() and managed_name(path.name):
                try:
                    files[path.name] = path.read_bytes()
                except OSError as exc:
                    logging.warning("Helm couldn't read %s: %s", path, exc)
        return files

    def set_up(self):
        self._finish_swap()
        return self.working_dir.is_dir()

    def working(self):
        """What Helm last wrote (None before setup)."""
        if self._working_cache is not None:
            return dict(self._working_cache)
        if not self.set_up():
            return None
        files = {}
        for path in self.working_dir.iterdir():
            if path.is_file() and managed_name(path.name):
                files[path.name] = path.read_bytes()
        schemes = self.working_dir / "ControlSchemes"
        if schemes.is_dir():
            for path in schemes.rglob("*"):
                if path.is_file():
                    files[DEVICES + path.relative_to(schemes).as_posix()] = path.read_bytes()
        self._working_cache = files
        return dict(files)

    def current(self):
        """The working copy with the edits on top (the live set before setup)."""
        with self.lock:
            files = self.working()
            if files is None:
                files = self.live()
            for name, data in self.edits.items():
                for existing in [key for key in files if same_name(key, name)]:
                    files.pop(existing)
                if data is not None:
                    files[name] = data
            return files

    def pending(self):
        """The names an APPLY would change."""
        with self.lock:
            base = self.working()
            if base is None:
                base = self.live()
            changed = []
            for name, data in self.edits.items():
                before = next((value for key, value in base.items() if same_name(key, name)), None)
                if data != before:
                    changed.append(name)
            return sorted(changed, key=str.casefold)

    # -- presets and their files -------------------------------------------------------
    def presets(self, files=None):
        files = self.current() if files is None else files
        name = preset_file_of(files)
        return preset_lines(files.get(name)) if name else []

    def user_file(self, preset, files=None):
        """The binds file of yours a preset name means: its highest version in the set."""
        files = self.current() if files is None else files
        found = []
        for name in files:
            parts = binds_name_parts(name)
            if parts and same_name(parts[0], preset):
                found.append(((parts[1], parts[2]), name))
        return max(found)[1] if found else None

    def factory_files(self):
        """{preset name: Path} of the game's own binds files (the first install that has each)."""
        cached = self._factories_cache
        if cached is not None and time.monotonic() - cached[0] < 30:
            return dict(cached[1])
        found = {}
        for install in self.installs():
            try:
                for path in sorted(install.schemes.glob("*.binds")):
                    found.setdefault(path.stem, path)
            except OSError:
                continue
        self._factories_cache = (time.monotonic(), found)
        return dict(found)

    def resolve(self, preset, files=None):
        """("user", file name) | ("factory", Path) | (None, None)."""
        mine = self.user_file(preset, files)
        if mine:
            return "user", mine
        for name, path in self.factory_files().items():
            if same_name(name, preset):
                return "factory", path
        return None, None

    def read_binds(self, name, files=None):
        """A binds file's bytes: one of yours by file name, or a factory one by preset name."""
        files = self.current() if files is None else files
        for key, data in files.items():
            if same_name(key, name):
                return data
        for preset, path in self.factory_files().items():
            if same_name(preset, name) or same_name(path.name, name):
                try:
                    return path.read_bytes()
                except OSError:
                    return None
        return None

    def sections(self, files=None):
        """Each section's preset and the file it reads: [{section, preset, kind, file}]."""
        files = self.current() if files is None else files
        out = []
        for section, preset in zip(SECTIONS, self.presets(files)):
            kind, where = self.resolve(preset, files)
            out.append({"section": section, "preset": preset, "kind": kind or "missing",
                        "file": where if kind == "user" else (where.name if kind == "factory" else "")})
        return out

    def user_binds_files(self, files=None):
        files = self.current() if files is None else files
        return sorted((name for name in files if is_binds_name(name)), key=str.casefold)

    # -- edits -------------------------------------------------------------------------
    def _bump(self):
        self.revision += 1

    def change_binds(self, name, change):
        """Apply ``change(bytes) -> (result, bytes)`` to one of your binds files. -> result."""
        with self.lock:
            files = self.current()
            key = next((k for k in files if same_name(k, name)), None)
            if key is None or not is_binds_name(key):
                return bf.NOT_FOUND
            result, data = change(files[key])
            if result == bf.SAVED:
                self.edits[key] = data
                self._settle(key)
                self._bump()
            return result

    def _settle(self, name):
        """An edit back to what the working copy holds is no edit."""
        base = self.working()
        if base is None:
            base = self.live()
        before = next((value for key, value in base.items() if same_name(key, name)), None)
        if self.edits.get(name) == before:
            self.edits.pop(name, None)

    def set_presets(self, lines):
        lines = [str(line).strip() for line in lines]
        if len(lines) != 4 or not all(lines):
            return False
        with self.lock:
            files = self.current()
            name = preset_file_of(files) or PRESET_FILE
            if preset_lines(files.get(name)) == lines:
                return True
            self.edits[name] = preset_bytes(lines, files.get(name))
            self._settle(name)
            self._bump()
            return True

    def taken_names(self, files=None):
        files = self.current() if files is None else files
        names = {binds_name_parts(name)[0].casefold() for name in files if is_binds_name(name)}
        return names | {name.casefold() for name in self.factory_files()}

    def copy_factory(self, factory, new_name, sections=SECTIONS):
        """An editable copy of one of the game's presets, under a name of yours,
        and the chosen sections pointed at it (edits not applied). -> (ok, message)."""
        new_name = str(new_name or "").strip()
        if not _NAME_RULE.fullmatch(new_name):
            return False, "Use letters, digits, spaces, - or _ (starting with a letter, up to 40)."
        with self.lock:
            files = self.current()
            if fold_name(new_name) in {fold_name(name) for name in self.taken_names(files)}:
                return False, f"{new_name} is taken: pick another name."
            path = self.factory_files().get(factory) or next(
                (p for n, p in self.factory_files().items() if same_name(n, factory)), None)
            if path is None:
                return False, f"The game's {factory} preset wasn't found in any install."
            try:
                data = path.read_bytes()
                copy = bf.with_preset_name(data, new_name)
            except (OSError, ValueError) as exc:
                return False, f"Couldn't copy {factory}: {exc}"
            version = bf.root_version(data) or ("4", "2")
            file_name = f"{new_name}.{version[0]}.{version[1]}.binds"
            self.edits[file_name] = copy
            lines = self.presets(files) or [factory] * 4
            lines = [new_name if section in sections else line for section, line in zip(SECTIONS, lines)]
            name = preset_file_of(files) or PRESET_FILE
            self.edits[name] = preset_bytes(lines, files.get(name))
            self._settle(name)
            self._bump()
            return True, f"{file_name} made from {factory}."

    def discard(self):
        with self.lock:
            self.edits.clear()
            self._bump()

    # -- backups -----------------------------------------------------------------------
    def _stamp(self):
        return datetime.fromtimestamp(self.clock()).strftime("%Y-%m-%d_%H%M%S")

    def backup(self, kind, note=""):
        """A zip of every live file (and each install's device files). -> its path. Raises OSError."""
        if kind not in KINDS:
            raise ValueError(kind)
        installs = [install for install in self.installs() if install.reachable()]
        live = self.live()
        manifest = {"kind": kind, "note": note, "created": self.clock(), "app": self.app_version,
                    "bindings_folder": str(self.folder or ""),
                    "installs": [{"index": i, **install.as_dict()} for i, install in enumerate(installs)]}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for name, data in sorted(live.items()):
                archive.writestr(f"Bindings/{name}", data)
            for index, install in enumerate(installs):
                for name, data in read_device_files(install).items():
                    archive.writestr(f"Installs/{index}/{name}", data)
        return self._save_zip(kind, buffer.getvalue())

    def backup_working(self, note="working copy"):
        """The working copy, zipped the same way, before something replaces it."""
        files = self.working() or {}
        buffer = io.BytesIO()
        manifest = {"kind": BEFORE, "note": note, "created": self.clock(), "app": self.app_version,
                    "bindings_folder": str(self.folder or ""), "installs": [], "working": True}
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for name, data in sorted(files.items()):
                archive.writestr(f"Bindings/{name}", data)
        return self._save_zip(BEFORE, buffer.getvalue())

    def _save_zip(self, kind, data):
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = self._stamp()
        path = self.backups_dir / f"{stamp}_{kind}.zip"
        count = 1
        while path.exists():
            count += 1
            path = self.backups_dir / f"{stamp}-{count}_{kind}.zip"
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        self._bump()
        return path

    def backups(self):
        """Newest first: [{id, kind, label, created, size, note, files, working}]."""
        try:
            paths = list(self.backups_dir.glob("*.zip"))
        except OSError:
            paths = []
        key = tuple(sorted(path.name for path in paths))
        if self._backups_cache is not None and self._backups_cache[0] == key:
            return [dict(row) for row in self._backups_cache[1]]
        rows = []
        for path in paths:
            match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}_\d{6})(?:-\d+)?_(\w+)\.zip", path.name)
            if not match or match.group(2) not in KINDS:
                continue
            note, working, files = "", False, 0
            try:
                with zipfile.ZipFile(path) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    note, working = str(manifest.get("note") or ""), bool(manifest.get("working"))
                    files = sum(1 for item in archive.namelist() if item != "manifest.json")
            except (OSError, KeyError, ValueError, zipfile.BadZipFile):
                note = "unreadable"
            try:
                created = datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S").timestamp()
                size = path.stat().st_size
            except (OSError, ValueError):
                continue
            rows.append({"id": path.name, "kind": match.group(2), "label": KIND_LABELS[match.group(2)],
                         "created": created, "size": size, "note": note, "files": files, "working": working})
        rows.sort(key=lambda row: (row["created"], row["id"]), reverse=True)
        self._backups_cache = (key, rows)
        return [dict(row) for row in rows]

    def _backup_path(self, backup_id):
        name = Path(str(backup_id or "")).name
        path = self.backups_dir / name
        return path if name.endswith(".zip") and path.is_file() else None

    def delete_backup(self, backup_id):
        """Only yours can be deleted by hand; the rest go by their own rule."""
        path = self._backup_path(backup_id)
        if path is None or not path.name.endswith(f"_{USER}.zip"):
            return False
        path.unlink()
        self._bump()
        return True

    def prune(self, daily_days=30, before_keep=100):
        now = self.clock()
        before = [row for row in self.backups() if row["kind"] == BEFORE]
        for row in self.backups():
            if row["kind"] == DAILY and now - row["created"] > daily_days * 86400:
                self._remove_backup(row["id"])
        for row in before[max(10, int(before_keep)):]:
            self._remove_backup(row["id"])

    def _remove_backup(self, backup_id):
        path = self._backup_path(backup_id)
        if path is not None:
            try:
                path.unlink()
            except OSError as exc:
                logging.warning("Helm couldn't remove the old backup %s: %s", path, exc)

    def daily_backup(self, daily_days=30, before_keep=100):
        """The first start each day: a silent backup. -> its path or None (already today, or nothing to keep)."""
        today = datetime.fromtimestamp(self.clock()).strftime("%Y-%m-%d")
        if any(row["kind"] == DAILY and row["id"].startswith(today) for row in self.backups()):
            return None
        if not self.folder_found():
            return None
        path = self.backup(DAILY)
        self.prune(daily_days, before_keep)
        return path

    # -- the working copy --------------------------------------------------------------
    def _finish_swap(self):
        """Finish a working-copy write that was stopped after it was marked complete."""
        new, old = self.root / "working.new", self.root / "working.old"
        if new.is_dir() and (new / ".complete").exists():
            if self.working_dir.is_dir():
                if old.exists():
                    shutil.rmtree(old, ignore_errors=True)
                os.replace(self.working_dir, old)
            os.replace(new, self.working_dir)
        elif new.exists():
            shutil.rmtree(new, ignore_errors=True)
        if old.exists():
            shutil.rmtree(old, ignore_errors=True)

    def _save_working(self, files):
        """Write the set as the working copy in one step: beside it, marked, swapped in."""
        self._working_cache = None
        new = self.root / "working.new"
        if new.exists():
            shutil.rmtree(new)
        new.mkdir(parents=True)
        for name, data in files.items():
            target = new / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (new / ".complete").write_text("", encoding="utf-8")
        self._finish_swap()
        try:
            (self.working_dir / ".complete").unlink()
        except OSError:
            pass
        self._working_cache = None

    def install_sets(self):
        """{install label: its device set} for every reachable install (labels made unique)."""
        out = {}
        for install in self.installs():
            if install.reachable():
                label = install.label
                count = 2
                while label in out:
                    label = f"{install.label} {count}"
                    count += 1
                out[label] = device_set(install)
        return out

    def install_differences(self):
        """What differs between the installs' device files (nothing with one install)."""
        sets = self.install_sets()
        return device_items(sets) if len(sets) > 1 else []

    def devices_adopted(self):
        return bool(self.state().get("devices_at"))

    def adopt_devices(self, picks=None, base=None):
        """The installs' device files become the working copy's one set. When they
        differ, ``picks`` ({item: install label}) says whose each item is; ``base``
        whose the rest is. -> (ok, message)."""
        with self.lock:
            if not self.set_up():
                return False, "Helm isn't set up yet."
            sets = self.install_sets()
            if not sets:
                self._save_state(devices_at=self.clock())
                return True, "No game install was found, so there are no device files to keep yet."
            labels = list(sets)
            base_label = base if base in sets else labels[0]
            differences = device_items(sets) if len(sets) > 1 else []
            if differences and picks is None and base is None:
                return False, "Your game installs' device files differ: choose whose to keep."
            merged = merge_devices(sets[base_label], sets, picks or {})
            try:
                if differences:
                    self.backup(BEFORE, "before the installs' device files were made one set")
                working = self.working() or {}
                self._save_working({**bindings_of(working), **merged})
                self._save_state(devices_at=self.clock())
            except OSError as exc:
                return False, f"Helm couldn't keep the device files: {exc}"
            if differences:
                # What you chose goes to every install now: they must agree for the game.
                extra = sorted({key for theirs in sets.values() for key in theirs if key not in merged})
                self._write_devices(merged, extra)
            self._bump()
            return True, "Your device files are in Helm's working copy." + (
                " Every install now has the same set." if differences else "")

    def setup(self):
        """First setup: a backup kept forever, then the working copy from the live files. -> (ok, message)."""
        with self.lock:
            if not self.folder_found():
                return False, ("Elite's bindings folder isn't there yet: the game makes it once you've played "
                               "through the start. Nothing was changed.")
            try:
                self.backup(FIRST, "your files before Helm wrote anything")
                self._save_working(self.live())
                self._save_state(set_up_at=self.clock())
            except OSError as exc:
                return False, f"Helm couldn't make its working copy: {exc}"
            self._bump()
            if not self.install_differences():
                self.adopt_devices()
            return True, "Your control files are backed up and Helm's working copy is made."

    # -- writing the game's files --------------------------------------------------------
    def _write_live(self, name, data):
        """One file into the bindings folder; a read-only file stays read-only."""
        path = self._live_path(name)
        read_only = path.exists() and not os.access(path, os.W_OK)
        if read_only:
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        tmp = self.folder / (name + _TMP)
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            if read_only:
                os.chmod(path, stat.S_IREAD)

    def _live_path(self, name):
        """The live file of that name, matched ignoring case (so we never leave two)."""
        try:
            for path in self.folder.iterdir():
                if same_name(path.name, name):
                    if path.name != name:
                        os.replace(path, self.folder / name)
                    return self.folder / name
        except OSError:
            pass
        return self.folder / name

    def _remove_live(self, name):
        path = self._live_path(name)
        if path.exists():
            if not os.access(path, os.W_OK):
                os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            path.unlink()

    def _write_set(self, files, remove=()):
        """Write the set to the bindings folder (same bytes skipped). -> report."""
        written, same, failed = [], [], []
        live = self.live()
        binds_failed = False
        # The binds files first: a preset file must never name a file that isn't there.
        order = sorted(files, key=lambda name: (is_preset_name(name), name.casefold()))
        for name in order:
            data = files[name]
            if is_preset_name(name) and binds_failed:
                failed.append({"file": name, "error": "held back: a binds file it names couldn't be written"})
                continue
            before = next((value for key, value in live.items() if same_name(key, name)), None)
            if before == data:
                same.append(name)
                continue
            try:
                self._write_live(name, data)
                written.append(name)
            except OSError as exc:
                failed.append({"file": name, "error": str(exc)})
                binds_failed = binds_failed or is_binds_name(name)
        for name in remove:
            if binds_failed:
                break
            try:
                self._remove_live(name)
                written.append(f"{name} (removed)")
            except OSError as exc:
                failed.append({"file": name, "error": str(exc)})
        return {"written": written, "same": same, "failed": failed}

    def _write_devices(self, files, removed=()):
        """The working copy's device set into every reachable install (same bytes skipped,
        a read-only file kept read-only). -> [{install, written, failed}]."""
        rows = []
        for install in self.installs():
            if not install.reachable():
                rows.append({"install": install.label, "path": str(install.schemes), "state": "unreachable",
                             "written": [], "failed": []})
                continue
            written, failed = [], []
            for key, data in sorted(files.items()):
                target = install.schemes / key[len(DEVICES):]
                try:
                    if target.exists() and target.read_bytes() == data:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    read_only = target.exists() and not os.access(target, os.W_OK)
                    if read_only:
                        os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
                    tmp = target.with_name(target.name + _TMP)
                    tmp.write_bytes(data)
                    os.replace(tmp, target)
                    if read_only:
                        os.chmod(target, stat.S_IREAD)
                    written.append(key[len(DEVICES):])
                except OSError as exc:
                    failed.append({"file": key[len(DEVICES):], "error": str(exc)})
            for key in removed:
                target = install.schemes / key[len(DEVICES):]
                try:
                    if target.exists():
                        if not os.access(target, os.W_OK):
                            os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
                        target.unlink()
                        written.append(f"{key[len(DEVICES):]} (removed)")
                except OSError as exc:
                    failed.append({"file": key[len(DEVICES):], "error": str(exc)})
            rows.append({"install": install.label, "path": str(install.schemes),
                         "state": "failed" if failed else "written" if written else "same",
                         "written": written, "failed": failed})
        return rows

    def preset_problems(self, files):
        """Sections whose preset names no file: APPLY refuses rather than let the game load something else."""
        lines = self.presets(files)
        if not lines:
            return []
        return [catalog.SECTION_LABELS[section] for section, line in zip(SECTIONS, lines)
                if self.resolve(line, files)[0] is None]

    def apply(self):
        """APPLY: check, back up, save the working copy, write what differs. -> report dict."""
        with self.lock:
            if not self.folder_found():
                return {"ok": False, "refused": "Elite's bindings folder wasn't found, so nothing was written."}
            if not self.set_up():
                ok, message = self.setup()
                if not ok:
                    return {"ok": False, "refused": message}
            check = self.check()
            if check["changed"]:
                return {"ok": False, "check": True,
                        "refused": "Your control files changed outside Helm: settle that first (nothing was written)."}
            files = self.current()
            problems = self.preset_problems(files)
            if problems:
                return {"ok": False, "refused": f"{', '.join(problems)}: the preset names a binds file that isn't "
                                                f"there, so the game would quietly load another. Nothing was written."}
            working = self.working() or {}
            removed = [name for name in working if not any(same_name(name, key) for key in files)]
            try:
                backup = self.backup(BEFORE, "before APPLY")
            except OSError as exc:
                return {"ok": False, "refused": f"The backup couldn't be made ({exc}), so nothing was written."}
            try:
                self._save_working(files)
            except OSError as exc:
                return {"ok": False, "refused": f"The working copy couldn't be saved ({exc}), so nothing was written."}
            report = self._write_set(bindings_of(files), [name for name in removed if not is_device_key(name)])
            report["installs"] = self._write_devices(devices_of(files), [name for name in removed if is_device_key(name)])
            report["failed"] += [{"file": f"{row['install']}: {item['file']}", "error": item["error"]}
                                 for row in report["installs"] for item in row["failed"]]
            self.edits.clear()
            self._save_state(last_apply=self.clock())
            self._bump()
            report.update(ok=not report["failed"], backup=backup.name)
            return report

    # -- the check -----------------------------------------------------------------------
    def _factory_canonicals(self):
        out = []
        for preset, path in self.factory_files().items():
            try:
                stamp = path.stat().st_mtime_ns
            except OSError:
                continue
            cached = self._factory_cache.get(str(path))
            if cached is None or cached[0] != stamp:
                try:
                    cached = (stamp, bf.canonical(path.read_bytes(), ignore_preset_name=True))
                except OSError:
                    continue
                self._factory_cache[str(path)] = cached
            out.append((preset, cached[1]))
        return out

    def reset_to(self, data):
        """The factory preset a binds file is, value for value (its name aside), or ""."""
        form = bf.canonical(data, ignore_preset_name=True)
        return next((preset for preset, canonical in self._factory_canonicals() if canonical == form), "")

    def check(self):
        """The live files against the working copy, by value. -> {changed, set_up, files: [...]}."""
        with self.lock:
            working = self.working()
            if working is None:
                return {"changed": False, "set_up": False, "files": []}
            if not self.devices_adopted() and not self.install_differences():
                # Set up before the device files joined in: the installs agree, so take them.
                self.adopt_devices()
                working = self.working() or {}
            live = self.live()
            rows = []
            names = {name.casefold(): name for name in [*working, *live]}
            for folded, name in sorted(names.items()):
                mine = next((v for k, v in working.items() if k.casefold() == folded), None)
                game = next((v for k, v in live.items() if k.casefold() == folded), None)
                if mine is not None and game is not None:
                    if is_preset_name(name):
                        if preset_lines(mine) == preset_lines(game):
                            continue
                        rows.append({"file": name, "state": "changed", "preset": True,
                                     "mine": preset_lines(mine), "game": preset_lines(game)})
                        continue
                    if bf.values_equal(mine, game):
                        continue
                    rows.append({"file": name, "state": "changed", "detail": diff_summary(mine, game),
                                 "reset": self.reset_to(game)})
                elif mine is not None:
                    rows.append({"file": name, "state": "gone", "detail": {}})
                else:
                    rows.append({"file": name, "state": "new", "detail": {}})
            rows = [row for row in rows if not is_device_key(row["file"])]
            installs = []
            if self.devices_adopted():
                mine = devices_of(working)
                stock = bf.canonical(dv.stock_mappings())
                for label, theirs in self.install_sets().items():
                    if same_devices(mine, theirs):
                        continue
                    items = device_items({"mine": mine, "game": theirs})
                    reset = bool(theirs.get(MAPPINGS_KEY)) and bf.canonical(theirs[MAPPINGS_KEY]) == stock \
                        and bf.canonical(mine.get(MAPPINGS_KEY) or b"") != stock
                    installs.append({"install": label, "items": items, "reset": reset or not theirs.get(MAPPINGS_KEY)})
            return {"changed": bool(rows or installs), "set_up": True, "files": rows, "installs": installs,
                    "reconcile": [] if self.devices_adopted() else self.install_differences()}

    def keep_mine(self):
        """The check's KEEP MINE: the working copy back over the game's files."""
        with self.lock:
            working = self.working()
            if working is None or not self.folder_found():
                return {"ok": False, "refused": "Nothing to put back."}
            live = self.live()
            extra = [name for name in live if not any(same_name(name, key) for key in working)]
            try:
                backup = self.backup(BEFORE, "before KEEP MINE")
            except OSError as exc:
                return {"ok": False, "refused": f"The backup couldn't be made ({exc}), so nothing was written."}
            report = self._write_set(bindings_of(working), extra)
            if self.devices_adopted():
                mine = devices_of(working)
                extra_maps = sorted({key for theirs in self.install_sets().values() for key in theirs
                                     if key not in mine and key != MAPPINGS_KEY})
                report["installs"] = self._write_devices(mine, extra_maps)
                report["failed"] += [{"file": f"{row['install']}: {item['file']}", "error": item["error"]}
                                     for row in report["installs"] for item in row["failed"]]
            self._bump()
            report.update(ok=not report["failed"], backup=backup.name)
            return report

    def take_games(self, install=None):
        """The check's TAKE THE GAME'S: the live files become the working copy (which is backed up first);
        the device files from ``install`` (a label) when one is named."""
        with self.lock:
            if not self.set_up():
                return {"ok": False, "refused": "Helm isn't set up yet."}
            try:
                backup = self.backup_working("working copy, before the game's files replaced it")
                devices = devices_of(self.working() or {})
                if install and install in self.install_sets():
                    devices = self.install_sets()[install]
                self._save_working({**self.live(), **devices})
            except OSError as exc:
                return {"ok": False, "refused": f"Couldn't take the game's files ({exc})."}
            self.edits.clear()
            self._bump()
            return {"ok": True, "backup": backup.name, "written": [], "failed": []}

    # -- merging, item by item ------------------------------------------------------------
    def diff_rows(self, name):
        """A binds file's controls where the working copy and the game's differ:
        [{tag, label, mine, game}]. The preset file: its four lines."""
        working, live = self.working() or {}, self.live()
        mine = next((v for k, v in working.items() if same_name(k, name)), None)
        game = next((v for k, v in live.items() if same_name(k, name)), None)
        if mine is None or game is None:
            return []
        if is_preset_name(name):
            a, b = preset_lines(mine), preset_lines(game)
            return [{"tag": section, "label": catalog.SECTION_LABELS[section], "mine": x, "game": y}
                    for section, x, y in zip(SECTIONS, a, b) if x != y]
        try:
            pa, pb = bf.parse(mine), bf.parse(game)
        except ValueError:
            return []
        forms_a, forms_b = _forms(pa), _forms(pb)
        rows = []
        for tag in sorted(set(forms_a) | set(forms_b), key=lambda t: (catalog.lookup(t).order, t.casefold())):
            if forms_a.get(tag) != forms_b.get(tag):
                rows.append({"tag": tag, "label": catalog.label(tag), "mine": bf.element_summary(pa, tag),
                             "game": bf.element_summary(pb, tag)})
        return rows

    def merge_file(self, name, picks):
        """The check's MERGE for one bindings-folder file: each control from the side picked
        (``picks`` {tag: "game"}; the rest stay yours). The result goes to both. -> report."""
        with self.lock:
            working, live = self.working() or {}, self.live()
            key = next((k for k in working if same_name(k, name)), None)
            game = next((v for k, v in live.items() if same_name(k, name)), None)
            if key is None or game is None:
                return {"ok": False, "refused": "That file isn't on both sides any more: CHECK AGAIN."}
            merged = working[key]
            if is_preset_name(name):
                lines = preset_lines(merged)
                theirs = preset_lines(game)
                lines = [theirs[i] if picks.get(section) == "game" else lines[i] for i, section in enumerate(SECTIONS)]
                merged = preset_bytes(lines, merged)
            else:
                for tag, side in picks.items():
                    if side == "game":
                        merged = bf.copy_element(merged, game, tag)
            try:
                backup = self.backup(BEFORE, f"before merging {name}")
                self._save_working({**working, key: merged})
            except OSError as exc:
                return {"ok": False, "refused": f"Couldn't merge ({exc})."}
            report = self._write_set({key: merged})
            self._bump()
            report.update(ok=not report["failed"], backup=backup.name)
            return report

    def merge_install(self, install, picks):
        """The check's MERGE for one install's device files: ``picks`` {item: "game"} take
        that install's; the rest stay yours. The result goes to every install."""
        with self.lock:
            sets = self.install_sets()
            if install not in sets:
                return {"ok": False, "refused": "That install isn't there any more."}
            working = self.working() or {}
            merged = merge_devices(devices_of(working), {"game": sets[install]},
                                   {item: "game" for item, side in picks.items() if side == "game"})
            removed = [key for key in devices_of(working) if key not in merged]
            try:
                backup = self.backup(BEFORE, f"before merging {install}'s device files")
                self._save_working({**bindings_of(working), **merged})
            except OSError as exc:
                return {"ok": False, "refused": f"Couldn't merge ({exc})."}
            rows = self._write_devices(merged, removed)
            self._bump()
            failed = [{"file": f"{row['install']}: {item['file']}", "error": item["error"]} for row in rows for item in row["failed"]]
            return {"ok": not failed, "written": [f"{row['install']}: {', '.join(row['written'])}" for row in rows if row["written"]],
                    "failed": failed, "installs": rows, "backup": backup.name}

    # -- device files: names, labels, ids --------------------------------------------------
    def device_files(self, files=None):
        """The device set edits work on: the working copy's (with edits), else the first install's."""
        files = self.current() if files is None else files
        found = devices_of(files)
        if found:
            return found
        sets = self.install_sets()
        return next(iter(sets.values()), {}) if sets else {}

    def change_device_files(self, changes):
        """Edits not applied: {key: bytes or None (removed)} on the device set."""
        with self.lock:
            base = self.device_files()
            for key, data in changes.items():
                if not is_device_key(key):
                    continue
                if base.get(key) == data:
                    continue
                self.edits[key] = data
                self._settle(key)
            self._bump()

    def rewrite_references(self, matches, new):
        """Every binds file of yours: references ``matches`` moved to ``new``, as edits. -> how many."""
        moved = 0
        for name in self.user_binds_files():
            count = [0]

            def change(data):
                result, count[0] = dv.rewrite_references(data, matches, new)
                return (bf.SAVED if count[0] else bf.NO_CHANGE), result
            if self.change_binds(name, change) == bf.SAVED:
                moved += count[0]
        return moved

    def references(self, matches):
        """How many slots in your binds files name a device."""
        files = self.current()
        return sum(dv.count_references(files[name], matches) for name in self.user_binds_files(files))

    # -- restore -------------------------------------------------------------------------
    def backup_contents(self, backup_id):
        path = self._backup_path(backup_id)
        if path is None:
            return None
        try:
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                bindings = {item[len("Bindings/"):]: archive.read(item) for item in archive.namelist()
                            if item.startswith("Bindings/") and managed_name(item[len("Bindings/"):])}
                devices = {}
                for item in archive.namelist():
                    match = re.fullmatch(r"Installs/(\d+)/(.+)", item)
                    if match:
                        devices.setdefault(int(match.group(1)), {})[match.group(2)] = archive.read(item)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            return None
        return {"manifest": manifest, "bindings": bindings, "devices": devices}

    def restore(self, backup_id):
        """RESTORE: back up what's there, put the whole backup back, make it the working copy."""
        with self.lock:
            contents = self.backup_contents(backup_id)
            if contents is None:
                return {"ok": False, "refused": "That backup can't be read."}
            if not self.folder_found():
                return {"ok": False, "refused": "Elite's bindings folder isn't there, so nothing was restored."}
            bindings = contents["bindings"]
            if not any(is_binds_name(name) for name in bindings) and not any(is_preset_name(n) for n in bindings):
                return {"ok": False, "refused": "That backup holds no binds or preset file."}
            try:
                backup = self.backup(BEFORE, "before RESTORE")
            except OSError as exc:
                return {"ok": False, "refused": f"The backup couldn't be made ({exc}), so nothing was restored."}
            live = self.live()
            extra = [name for name in live if not any(same_name(name, key) for key in bindings)]
            report = self._write_set(bindings, extra)
            report["installs"] = self._restore_devices(contents)
            if not report["failed"]:
                try:
                    held = next(iter(contents["devices"].values()), {}) if contents["devices"] else {}
                    devices = {DEVICES + name: data for name, data in held.items()}
                    self._save_working({**bindings, **devices})
                    if devices:
                        self._save_state(devices_at=self.clock())
                    self._save_state(set_up_at=self.state().get("set_up_at") or self.clock())
                except OSError as exc:
                    report["failed"].append({"file": "working copy", "error": str(exc)})
            self.edits.clear()
            self._bump()
            report.update(ok=not report["failed"], backup=backup.name)
            return report

    def _restore_devices(self, contents):
        """Each install's own device files back, matched by its folder; ones the backup doesn't hold are left."""
        rows = []
        saved = {str(row.get("path", "")).casefold(): row.get("index") for row in contents["manifest"].get("installs", [])}
        for install in self.installs():
            index = saved.get(install.key)
            files = contents["devices"].get(index) if index is not None else None
            if not files:
                rows.append({"install": install.label, "path": str(install.schemes), "state": "not in backup"})
                continue
            if not install.reachable():
                rows.append({"install": install.label, "path": str(install.schemes), "state": "unreachable"})
                continue
            failed = []
            for name, data in files.items():
                target = install.schemes / Path(name)
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and target.read_bytes() == data:
                        continue
                    read_only = target.exists() and not os.access(target, os.W_OK)
                    if read_only:
                        os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
                    target.write_bytes(data)
                    if read_only:
                        os.chmod(target, stat.S_IREAD)
                except OSError as exc:
                    failed.append(f"{name}: {exc}")
            rows.append({"install": install.label, "path": str(install.schemes),
                         "state": "failed" if failed else "restored", "errors": failed})
        return rows


def _forms(binds):
    out = {}
    for tag, pair in binds.buttons.items():
        out[tag] = tuple((s.device, s.key, frozenset(s.modifiers), s.hold) if s else None
                         for s in (pair.get(bf.PRIMARY), pair.get(bf.SECONDARY)))
    for tag, axis in binds.axes.items():
        out[tag] = (axis.device, axis.key, axis.inverted, round(axis.deadzone, 6))
    for tag, setting in binds.settings.items():
        out[tag] = setting["value"]
    return out


def diff_summary(mine, game):
    """What the game's copy has that the working copy doesn't: {changed, added, removed, labels}."""
    try:
        a, b = bf.parse(mine), bf.parse(game)
    except ValueError:
        return {"changed": 0, "added": 0, "removed": 0, "labels": [], "unreadable": True}

    def forms(binds):
        out = {}
        for tag, pair in binds.buttons.items():
            out[tag] = tuple((s.device, s.key, frozenset(s.modifiers), s.hold) if s else None
                             for s in (pair.get(bf.PRIMARY), pair.get(bf.SECONDARY)))
        for tag, axis in binds.axes.items():
            out[tag] = (axis.device, axis.key, axis.inverted, round(axis.deadzone, 6))
        for tag, setting in binds.settings.items():
            out[tag] = setting["value"]
        return out
    fa, fb = forms(a), forms(b)
    changed = [tag for tag in fa if tag in fb and fa[tag] != fb[tag]]
    added = [tag for tag in fb if tag not in fa]
    removed = [tag for tag in fa if tag not in fb]
    labels = [catalog.label(tag) for tag in (changed + added + removed)[:8]]
    return {"changed": len(changed), "added": len(added), "removed": len(removed), "labels": labels}

