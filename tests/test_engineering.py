import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engineering_data import (  # noqa: E402
    MATERIALS,
    convertible,
    material_info,
    plan,
    requirements,
)
from dashboard import MainDashboard  # noqa: E402


def test_canonical_material_grades():
    assert material_info("cadmium")["grade"] == 3
    assert material_info("legacyfirmware")["grade"] == 1
    assert material_info("chemicalstorageunits")["grade"] == 1
    assert material_info("compactemissionsdata")["grade"] == 5
    assert material_info("guardian_powercell")["category"] == "manufactured"
    assert len(MATERIALS) >= 120


def test_blueprint_requirements_and_inventory_plan():
    need = requirements("FSD Increased Range", 5)
    assert need["disruptedwakeechoes"] == 4
    assert need["chemicalprocessors"] == 5
    assert need["dataminedwake"] == 5
    empty = plan("FSD Increased Range", 5, {})
    assert not empty["craftable"]
    full = plan("FSD Increased Range", 5, need)
    assert full["craftable"]


def test_material_trader_conversion_math():
    assert convertible(2, 5, 3) == 18
    assert convertible(35, 1, 3) == 0
    assert convertible(36, 1, 3) == 1


def test_latest_real_journal_materials_are_catalogued():
    journal_dir = pathlib.Path.home() / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
    if not journal_dir.exists():
        return
    latest = None
    for path in sorted(journal_dir.glob("Journal*.log"), reverse=True):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "Materials":
                latest = event
        if latest:
            break
    if not latest:
        return
    missing = []
    for category in ("Raw", "Manufactured", "Encoded"):
        missing.extend(item["Name"] for item in latest.get(category, [])
                       if item["Name"].lower() not in MATERIALS)
    assert not missing, missing


def test_dashboard_engineering_journal_integration():
    class ImmediateRoot:
        @staticmethod
        def after(_delay, callback):
            callback()

    class Toast:
        def __init__(self):
            self.rows = []

        def push(self, *args, **kwargs):
            self.rows.append((args, kwargs))

    class Voice:
        def __init__(self):
            self.rows = []

        def say(self, text, **kwargs):
            self.rows.append((text, kwargs))
            return True

    app = MainDashboard.__new__(MainDashboard)
    app.root = ImmediateRoot()
    app.engineer_window = None
    app.toast_hud = Toast()
    app.voice_callouts = Voice()
    app._save_engineer_materials = lambda _state: None
    app.engineer_materials = {
        "raw": {}, "manufactured": {},
        "encoded": {"disruptedwakeechoes": {"name": "Atypical Disrupted Wake Echoes", "count": 1}},
        "engineers": {}, "ship_locker": {},
        "pinned_blueprints": [{"name": "FSD Increased Range", "grade": 1}],
    }
    app._process_engineer_progress({
        "Engineers": [{"Engineer": "Felicity Farseer", "Progress": "Unlocked", "Rank": 5}]
    })
    assert app.engineer_materials["engineers"]["Felicity Farseer"]["rank"] == 5
    app._process_material_change("MaterialCollected", {
        "Category": "Encoded", "Name": "disruptedwakeechoes",
        "Name_Localised": "Atypical Disrupted Wake Echoes", "Count": 1,
    })
    assert len(app.toast_hud.rows) == 1
    assert any("Materials complete" in row[0] for row in app.voice_callouts.rows)
    app._apply_ship_locker({
        "Items": [{"Name": "test_item", "Count": 2}, {"Name": "test_item", "Count": 3}],
        "Components": [], "Data": [], "Consumables": [],
    })
    assert app.engineer_materials["ship_locker"]["items"][0]["count"] == 5


if __name__ == "__main__":
    test_canonical_material_grades()
    test_blueprint_requirements_and_inventory_plan()
    test_material_trader_conversion_math()
    test_latest_real_journal_materials_are_catalogued()
    test_dashboard_engineering_journal_integration()
    print("ALL ENGINEERING TESTS PASSED")
