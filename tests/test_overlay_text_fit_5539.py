"""Prospector, Cargo, Planet Materials, Station Link, the Rig Tracker, the Rhino Map (5.5.18), Expedition (5.6.1) and Hatchling (5.6.3) at large text (5.5.3.9): the page's columns grow with
the text size as the window does, so nothing is cut off at 150% or 200%."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

from voidcompass.overlays.cargo_hud import build_cargo_model
from voidcompass.core import hatchling
from voidcompass.overlays.expedition_hud import build_expedition_model
from voidcompass.overlays.hatchling_hud import build_hatchling_model
from voidcompass.overlays.planet_materials_hud import build_planet_materials_model
from voidcompass.overlays.prospector_hud import build_prospector_model
from voidcompass.overlays.rig_tracker import build_rig_model, hold_row
from voidcompass.overlays.station_info_hud import build_station_model

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderIt = options.render; window.measure = options.contentHeight; return {rerender() {}}; }};")
THEME = {"bg": "#070b10", "panel": "#0d141c", "accent": "#00d1ff", "orange": "#ff7a18", "text": "#dce8ef",
         "green": "#4ee59b", "yellow": "#ffd166", "red": "#ff6075", "muted": "#85939d", "dim": "#52616c"}

PROSPECTED = {"event": "ProspectedAsteroid", "Content": "$AsteroidMaterialContent_High;", "MotherlodeMaterial": "Painite",
              "Remaining": 100.0, "Materials": [
                  {"Name": "platinum", "Name_Localised": "Platinum", "Proportion": 31.2},
                  {"Name": "praseodymium", "Name_Localised": "Praseodymium", "Proportion": 9.9},
                  {"Name": "lowtemperaturediamond", "Name_Localised": "Low Temperature Diamonds", "Proportion": 6.1}]}
HOLD = [{"Name": "lowtemperaturediamond", "Name_Localised": "Low Temperature Diamonds", "Count": 212},
        {"Name": "hydrogenfuel", "Name_Localised": "Hydrogen Fuel", "Count": 12, "Stolen": 2}]

BODY = "Synuefe XX-A d1-58 AB 3 a"
WORKSPACE = {"system": "Synuefe XX-A d1-58", "body": BODY, "on_planet": True,
             "bodies": [{"body": BODY, "short_name": "AB 3 a", "class": "High metal content world",
                         "volcanism": "Minor metallic magma volcanism", "gravity": 0.31, "temperature": 182, "landable": True,
                         "mining_locations": 4, "ground_label": "Metallic rocky ground", "ground_sample": 3,
                         "materials": [{"name": "Ruthenium", "percent": 1.9, "rare": True}, {"name": "Iron", "percent": 21.4}],
                         "best_materials": [{"material": "Low Temperature Diamonds", "pct": 42.0, "median": 12}]}],
             "sites": [{"id": 1, "system": "Synuefe XX-A d1-58", "body": BODY, "name": "Ridge seam", "density": "Medium",
                        "amount": "Medium", "materials": "Painite", "latitude": 10.1, "longitude": -44.0}],
             "navigation_target": {}}

DOCKED = SimpleNamespace(
    current_station_name="Shinrarta Dezhra Jameson Memorial", current_sys="Shinrarta Dezhra", current_station_type="Orbis",
    current_station_dist_ls=346.2, current_station_landing_pads={"Small": 17, "Medium": 18, "Large": 9},
    current_station_services=["dock", "commodities", "exploration", "rearm", "refuel", "repair", "outfitting", "shipyard",
                              "searchrescue", "vistagenomics", "engineer", "materialtrader", "techBroker"],
    current_station_economies=[{"Name_Localised": "High Tech", "Proportion": 0.8}, {"Name_Localised": "Industrial", "Proportion": 0.2}],
    current_station_economy="High Tech", current_station_faction={"Name": "The Pilots Federation", "FactionState": "Boom"},
    current_station_government="Democracy", current_station_allegiance="Independent", current_station_state="Boom",
    current_station_market_id=128666762, companion_state=None, carrier_tracker=None)

# Five rigs out on a long-named body (5.5.10).
RIGS = {slot: {"lat": 11.9 + slot * .01, "lon": -45.1 - (slot % 2) * .02, "at": 1_700_000_000 + slot * 600}
        for slot in (1, 2, 3, 4, 5)}
RIG_MODEL = build_rig_model(RIGS, 11.9, -45.1, 212, 2400000, BODY, now=1_700_100_000,
                            holds=[hold_row("RHINO", 23, 72), hold_row("SHIP", 238, 256)])

# The Rhino Map (5.5.18): two rigs, one too close, the ship far off, mining
# sites: its strip's warnings wrap rather than being cut.
def _rhino_model():
    from voidcompass.overlays.surface_map import build_surface_map
    radius = 2400000.0
    plane = lambda point: [round(point[1] * 41888, 1), round(point[0] * 41888, 1)]
    rigs = {1: {"lat": 0.0012, "lon": 0.0, "at": 1_700_000_000}, 2: {"lat": 0.0003, "lon": 0.0004, "at": 1_700_000_300}}
    rig_model = build_rig_model(rigs, 0.0, 0.0, 30, radius, BODY, now=1_700_000_400, in_rhino=True)
    plane_map = {"body": BODY, "you": {"at": [0.0, 0.0], "heading": 30}, "ship": {"at": [0.0, -2500.0]}, "trail": [[0, -40], [0, 0]]}
    model = build_surface_map(plane_map, plane, rig_model=rig_model, rig_points={slot: (rig["lat"], rig["lon"]) for slot, rig in rigs.items()},
                              signals=4, vehicle="RHINO")
    return {**model, "size": 240}


# The Expedition overlay (5.6.1) on a busy trip: long names, a surface
# compass, every warning. The Nav HUD's coverage test uses it too.
def _pet():
    """A long-named, hungry, frightened larva with a fresh log line."""
    state = hatchling.new_state()
    hatchling.act(state, "hatch", {"species": "larva", "name": "Thrummington-Vex"}, 0.0)
    state["pet"]["needs"].update(hunger=20.0, mood=30.0)
    hatchling.observe(state, {"event": "ShieldState", "ShieldsUp": False}, 7200.0)
    return hatchling.view(state, 7200.0), 7210.0


EXPEDITION_SAMPLE = (
    {"name": "Distant Worlds 3: The Long Way Round to Beagle Point", "ironman": True},
    {"progress": {"share": .42, "done_ly": 27_500.4, "to_go_ly": 37_779.6,
                  "next": {"system": "Eol Prou LW-L c8-306", "body": "Eol Prou LW-L c8-306 4 a", "kind": "stop",
                           "note": "The Crystal Arches by the Canyon Wall",
                           "fuel_runs": [{"jumps": 6, "from": "Shinrarta Dezhra Jameson Memorial"}]}},
     "surface": {"title": "The Crystal Arches by the Canyon Wall", "body": "Eol Prou LW-L c8-306 4 a", "here": True, "on_body": True,
                 "lat": -23.4512, "lon": 114.0821, "altitude_m": 1250.0,
                 "target": {"distance_m": 17453.3, "bearing": 92, "turn": -35, "arrived": False}},
     "risk": {"value": 1_234_567_890, "over": True, "hull": 64.0}, "streak": {"jumps": 1287}, "eta": {"hours": 61.2},
     "supplies": {"low": ["Limpets", "FSD injections", "AFMU ammo"]}},
)

# (page, model key, model, design width, min height, max height)
OVERLAYS = (
    ("prospector", "prospector", build_prospector_model(PROSPECTED, {"Platinum": 12}), 400, 180, 560),
    ("cargo", "cargo", build_cargo_model(HOLD, 320, "Ship", "Mandalay"), 410, 190, 760),
    ("planet-materials-overlay", "planet_materials",
     build_planet_materials_model(WORKSPACE, latitude=11.9, longitude=-45.1, heading=212, radius_m=2400000, vehicle_name="Rhino"),
     440, 190, 680),
    ("station", "station", build_station_model(DOCKED), 520, 330, 720),
    ("rig_tracker", "rigs", RIG_MODEL, 420, 130, 420),
    ("rhino_map", "rhino", _rhino_model(), 240, 280, 360),
    ("expedition", "expedition", build_expedition_model(*EXPEDITION_SAMPLE), 380, 120, 640),
    ("hatchling", "hatchling", build_hatchling_model(*_pet()), 250, 110, 260),
)


class LargeTextFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_nothing_cut_off_at_large_text(self):
        for name, key, model, width, low, high in OVERLAYS:
            for scale in (1.0, 1.5, 2.0):
                with self.subTest(overlay=name, scale=scale):
                    page = self.browser.new_page(viewport={"width": round(width * scale), "height": 1600})
                    self.addCleanup(page.close)

                    def serve(route):
                        file = WEB / urlsplit(route.request.url).path.lstrip("/")
                        if not file.is_file():
                            route.fulfill(status=404, body="")
                        elif file.name == "overlay-client.js":
                            route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
                        else:
                            route.fulfill(path=str(file))
                    page.route("http://fit.test/**", serve)
                    page.goto(f"http://fit.test/{name}/index.html?token=t&overlay={name}")
                    page.wait_for_function("Boolean(window.renderIt)")
                    page.evaluate(f"([m, t, s]) => renderIt({{theme: t, effects: {{text_scale: s}}, {key}: m}})", [model, THEME, scale])
                    measured = page.evaluate("measure()")
                    # The window the app gives it: design size times the text size.
                    page.set_viewport_size({"width": round(width * scale),
                                            "height": max(round(low * scale), min(round(high * scale), measured))})
                    cut = page.evaluate("""() => [...document.querySelectorAll('body strong, body span, body b, body small')]
                      .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1)
                      .map(el => el.textContent.trim()).filter(Boolean)""")
                    self.assertEqual(cut, [], "no text cut short")
                    wide = page.evaluate("document.documentElement.scrollWidth")
                    self.assertLessEqual(wide, round(width * scale) + 1, "nothing past the window's edge")

    def test_fits_a_window_drawn_at_another_scale(self):
        """Windows draws the page at another scale than the window was sized
        for: the page fits itself to the window, and every row still shows."""
        for name, key, model, width, low, high in OVERLAYS:
            for drawn in (1.25, 1.5):
                with self.subTest(overlay=name, drawn=drawn):
                    page = self.browser.new_page(viewport={"width": round(width / drawn), "height": 1600})
                    self.addCleanup(page.close)

                    def serve(route):
                        file = WEB / urlsplit(route.request.url).path.lstrip("/")
                        if not file.is_file():
                            route.fulfill(status=404, body="")
                        elif file.name == "overlay-client.js":
                            route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
                        else:
                            route.fulfill(path=str(file))
                    page.route("http://fit.test/**", serve)
                    page.goto(f"http://fit.test/{name}/index.html?token=t&overlay={name}")
                    page.wait_for_function("Boolean(window.renderIt)")
                    page.evaluate(f"([m, t]) => renderIt({{theme: t, effects: {{text_scale: 1}}, {key}: m}})", [model, THEME])
                    measured = page.evaluate("measure()")
                    # The app's window, in the page's own (larger) pixels.
                    page.set_viewport_size({"width": round(width / drawn), "height": round(max(low, min(high, measured)) / drawn)})
                    page.wait_for_timeout(50)
                    cut = page.evaluate("""() => [...document.querySelectorAll('body strong, body span, body b, body small')]
                      .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1)
                      .map(el => el.textContent.trim()).filter(Boolean)""")
                    self.assertEqual(cut, [], "no text cut short")
                    below = page.evaluate("""() => [...document.querySelectorAll('body *')]
                      .filter(el => el.getClientRects().length && el.getBoundingClientRect().bottom > innerHeight + 2)
                      .map(el => el.tagName + '.' + el.className)""")
                    self.assertEqual(below, [], "every row inside the window")


if __name__ == "__main__":
    unittest.main()
