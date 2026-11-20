"""Profile-local persistence helpers for field-tool state."""

from __future__ import annotations

from datetime import datetime
import json
import os
import shutil

from voidcompass.engineering.engineering_data import material_info


def get_material_category(key: str) -> str:
    """Return the Frontier inventory category for an internal material name."""
    return material_info(key).get("category", "manufactured")


# Saved ship builds (5.8.4): one file each, named after the build, in a folder beside
# engineer_materials.json. A build file dropped in there loads at the next start.
SHIP_BUILDS_DIR = "ship_builds"
_UNSAFE = set('<>:"/\\|?*')
_written_builds = {}


def ship_builds_folder(materials_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(materials_path)), SHIP_BUILDS_DIR) if materials_path else ""


def _build_file_name(name: str) -> str:
    text = "".join("_" if ch in _UNSAFE or ord(ch) < 32 else ch for ch in str(name or "Build")).strip(" .")
    return (text or "Build")[:60]


def load_ship_builds(materials_path: str):
    """The builds in the profile's ship_builds folder, or None when there's no folder yet."""
    folder = ship_builds_folder(materials_path)
    if not folder or not os.path.isdir(folder):
        return None
    builds = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                build = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(build, dict) or not build.get("ship"):
            continue
        build.setdefault("name", name[:-5])
        build.setdefault("id", os.urandom(5).hex())
        builds.append(build)
        _written_builds[path] = json.dumps(build, sort_keys=True)
    seen, unique = set(), []
    for build in builds:
        if build["id"] not in seen:
            seen.add(build["id"])
            unique.append(build)
    return sorted(unique, key=lambda row: float(row.get("updated") or 0))


def save_ship_builds(materials_path: str, builds) -> None:
    """Keep the folder to the builds: one file each, renamed and removed with them."""
    folder = ship_builds_folder(materials_path)
    builds = [row for row in builds or () if isinstance(row, dict)]
    if not folder or (not builds and not os.path.isdir(folder)):
        return
    from voidcompass.core.persistence_queue import persistence_queue
    os.makedirs(folder, exist_ok=True)
    wanted, used = {}, set()
    for build in sorted(builds, key=lambda row: (float(row.get("updated") or 0), str(row.get("id")))):
        stem = _build_file_name(build.get("name"))
        name, count = stem, 2
        while name.lower() in used:
            name, count = f"{stem} ({count})", count + 1
        used.add(name.lower())
        wanted[os.path.join(folder, f"{name}.json")] = build
    for path, build in wanted.items():
        text = json.dumps(build, sort_keys=True)
        if _written_builds.get(path) != text or not os.path.exists(path):
            persistence_queue().submit_json(path, build, indent=2, delay_s=0.35)
            _written_builds[path] = text
    # Only files this app wrote or read as builds go; anything else in there is left alone.
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if name.lower().endswith(".json") and path not in wanted and path in _written_builds:
            try:
                os.remove(path)
            except OSError:
                pass
            _written_builds.pop(path, None)


# Every ship you own as its latest Loadout (5.8.4), in a file of its own beside
# engineer_materials.json: it's written when a ship changes, not with every material.
SHIP_FLEET_FILE = "ship_fleet.json"
_written_fleet = {}


def ship_fleet_path(materials_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(materials_path)), SHIP_FLEET_FILE) if materials_path else ""


def load_ship_fleet(materials_path: str) -> dict:
    path = ship_fleet_path(materials_path)
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            ships = json.load(handle).get("ships")
    except (OSError, ValueError, AttributeError):
        return {}
    ships = {str(key): row for key, row in (ships or {}).items() if isinstance(row, dict)} if isinstance(ships, dict) else {}
    _written_fleet[path] = json.dumps(ships, sort_keys=True)
    return ships


def save_ship_fleet(materials_path: str, fleet, revision=None) -> None:
    """Written only when it changed: by its revision (note_fleet counts them), or by its text."""
    path = ship_fleet_path(materials_path)
    if not path or (not fleet and not os.path.exists(path)):
        return
    if revision is not None and _written_fleet.get(path) == ("rev", revision):
        return
    ships = dict(fleet or {})
    text = json.dumps(ships, sort_keys=True)
    if _written_fleet.get(path) != text:
        from voidcompass.core.persistence_queue import persistence_queue
        persistence_queue().submit_json(path, {"ships": ships}, indent=1, delay_s=0.35)
    _written_fleet[path] = ("rev", revision) if revision is not None else text


def load_engineer_materials(path: str) -> dict:
    """Load a commander's engineering inventory and preserve corrupt input."""
    empty = {
        "raw": {}, "manufactured": {}, "encoded": {}, "engineers": {},
        "pinned_blueprints": [], "odyssey_goals": [], "ship_locker": {},
        # Retained for read-only compatibility with pre-Build-Planner profiles.
        "engineering_builds": [], "engineering_follow_current": True,
        "build_planner_builds": [], "build_planner_selected": "live", "build_planner_compare": "",
        "last_updated": None,
    }
    if not path or not os.path.exists(path):
        return {**empty, "fleet": load_ship_fleet(path)}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for category in ("raw", "manufactured", "encoded"):
            data.setdefault(category, {})
        data.setdefault("engineers", {})
        data.setdefault("pinned_blueprints", [])
        data.setdefault("odyssey_goals", [])
        data.setdefault("ship_locker", {})
        data.setdefault("engineering_builds", [])
        data.setdefault("engineering_follow_current", True)
        data.setdefault("build_planner_builds", [])
        data.setdefault("build_planner_selected", "live")
        data.setdefault("build_planner_compare", "")
        # Builds live in their own files; one from before 5.8.4 keeps its list until the next save moves it.
        builds = load_ship_builds(path)
        if builds is not None:
            data["ship_builds"] = builds
        data["fleet"] = load_ship_fleet(path)
        return data
    except Exception as exc:
        backup = None
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = f"{path}.corrupt-{stamp}"
            shutil.copy2(path, backup)
        except Exception:
            backup = None
        # Builds are files of their own: they load even when this file doesn't, so a save can't drop them.
        try:
            builds = load_ship_builds(path)
        except Exception:
            builds = None
        return {
            **empty,
            **({"ship_builds": builds} if builds is not None else {}),
            "fleet": load_ship_fleet(path),
            "_load_warning": f"Could not read engineering data: {exc}",
            "_corrupt_backup": backup,
        }


def load_colonisation_data(path: str) -> dict:
    """Load tracked construction projects keyed by integer MarketID."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return {int(key): value for key, value in json.load(handle).items()}
    except Exception:
        return {}


def save_colonisation_data(projects: dict, path: str) -> None:
    """Persist construction projects for the active commander."""
    if not path:
        return
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({str(key): value for key, value in projects.items()}, handle, indent=2)
    except Exception:
        pass
