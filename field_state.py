"""Profile-local persistence helpers for field-tool state."""

from __future__ import annotations

from datetime import datetime
import json
import os
import shutil

from engineering_data import material_info


def get_material_category(key: str) -> str:
    """Return the Frontier inventory category for an internal material name."""
    return material_info(key).get("category", "manufactured")


def load_engineer_materials(path: str) -> dict:
    """Load a commander's engineering inventory and preserve corrupt input."""
    empty = {
        "raw": {}, "manufactured": {}, "encoded": {}, "engineers": {},
        "pinned_blueprints": [], "odyssey_goals": [], "ship_locker": {},
        "last_updated": None,
    }
    if not path or not os.path.exists(path):
        return empty
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for category in ("raw", "manufactured", "encoded"):
            data.setdefault(category, {})
        data.setdefault("engineers", {})
        data.setdefault("pinned_blueprints", [])
        data.setdefault("odyssey_goals", [])
        data.setdefault("ship_locker", {})
        return data
    except Exception as exc:
        backup = None
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = f"{path}.corrupt-{stamp}"
            shutil.copy2(path, backup)
        except Exception:
            backup = None
        return {
            **empty,
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
