"""The rebuilt Galactic Atlas: Elite's 42 Codex regions and where you have been.

The atlas draws region borders straight from the same raster the app names a
position's region with, so the browser and Python must agree about it; its
labels sit inside their regions; the commander's camera and map marks come
back to Python; and the page runs in a real browser without errors.
"""

import json
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from voidcompass.exploration.expedition_map_view import (
    MAP_ORIENTATION, ExpeditionMapView, galactic_region_payload,
)
from voidcompass.exploration.galactic_map_server import GalacticMapServer
from voidcompass.exploration.galactic_regions import find_region, region_labels, region_raster

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "galactic_map"


def decode(payload):
    """What regions.js does: runs back into one id per raster cell."""
    size = payload["size"]
    ids = bytearray(size * size)
    for z, row in enumerate(payload["rows"]):
        x = 0
        for index in range(0, len(row), 2):
            length, region = row[index], row[index + 1]
            ids[z * size + x:z * size + x + length] = bytes([region]) * length
            x += length
    return ids


class RegionDataTests(unittest.TestCase):
    def test_the_raster_the_atlas_draws_names_regions_as_python_does(self):
        payload = region_raster()
        ids = decode(payload)
        size, scale, x0, z0 = payload["size"], payload["scale"], payload["x0"], payload["z0"]
        for x, z in ((0, 0), (25.2, 25900), (-9530.5, 19808.1), (-1111.6, 65269.8), (30000, 40000), (-40000, 10000)):
            px, pz = int((x - x0) / scale), int((z - z0) / scale)
            expected = find_region(x, 0, z)
            self.assertEqual(ids[pz * size + px], expected[0] if expected else 0, (x, z))
        self.assertEqual(len(payload["names"]), 42)
        self.assertEqual(find_region(0, 0, 0)[1], "Inner Orion Spur")

    def test_every_label_sits_inside_its_own_region(self):
        labels = region_labels()
        self.assertEqual(len(labels), 42)
        for label in labels:
            x, _y, z = label["position"]
            self.assertEqual(find_region(x, 0, z)[0], label["id"], label["name"])
            self.assertGreater(label["cells"], 0)

    def test_the_region_payload_is_compact_and_complete(self):
        payload = galactic_region_payload()
        self.assertEqual(payload["schema"], 2)
        self.assertEqual(len(payload["rows"]), 2048)
        self.assertEqual({row["id"] for row in payload["labels"]}, set(range(1, 43)))
        self.assertLess(len(json.dumps(payload)), 400_000)


class ViewStateTests(unittest.TestCase):
    def normalise(self, state):
        view = ExpeditionMapView.__new__(ExpeditionMapView)
        view.config = {}
        return view._normalise_view_state(state)

    def test_the_camera_is_kept_within_its_limits(self):
        state = self.normalise({"orientation": MAP_ORIENTATION, "camera": {
            "target": [100, 0, 2000], "distance": 5, "heading": 370, "tilt": 99}})
        self.assertEqual(state["camera"], {"target": [100.0, 0.0, 2000.0], "distance": 20.0, "heading": 10.0, "tilt": 72.0})
        self.assertTrue(state["labels"])

    def test_a_camera_saved_by_the_old_atlas_is_dropped_not_misread(self):
        old = {"orientation": "galactic-north-up-east-right-v2", "camera": {"position": [1, 2, 3], "target": [0, 0, 0]}}
        self.assertIsNone(self.normalise(old)["camera"])
        self.assertIsNone(self.normalise({"orientation": MAP_ORIENTATION, "camera": {"target": [0, 0, 0], "distance": "far"}})["camera"])


class ServerTests(unittest.TestCase):
    def test_it_serves_the_atlas_modules_and_nothing_retired(self):
        server = GalacticMapServer(STATIC, ROOT / "assets" / "images" / "Galaxy" / "voidcompass-galactic-atlas.png",
                                   regions_provider=galactic_region_payload)
        self.addCleanup(server.stop)
        for name in ("app.js", "regions.js", "camera.js", "scene.js", "styles.css", "vendor/three.module.min.js"):
            with urlopen(f"{server.origin}/{name}") as response:
                self.assertEqual(response.status, 200, name)
        self.assertFalse((STATIC / "vendor" / "OrbitControls.js").exists())
        with self.assertRaises(HTTPError) as refused:
            urlopen(f"{server.origin}/vendor/OrbitControls.js")
        refused.exception.close()
        self.assertEqual(refused.exception.code, 404)


class AtlasBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(
                headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def snapshot(self):
        route = [
            {"system": "Sol", "pos": [0, 0, 0], "timestamp": "2026-09-01T10:00:00Z", "jump_dist": 0, "star_class": "G", "fss_complete": True},
            {"system": "Merope", "pos": [-78.6, -149.6, -340.5], "timestamp": "2026-09-02T10:00:00Z", "jump_dist": 380, "star_class": "B"},
            {"system": "Eagle Sector IR-W d1-117", "pos": [-2046.1, 104.1, 6699.2], "timestamp": "2026-09-05T10:00:00Z", "jump_dist": 7000, "star_class": "O"},
            {"system": "Colonia", "pos": [-9530.5, -910.3, 19808.1], "timestamp": "2026-09-09T10:00:00Z", "jump_dist": 15700, "star_class": "F"},
        ]
        return {
            "schema": 1, "theme": {"bg": "#070b10", "accent": "#00d1ff", "orange": "#ff8a3d", "text": "#dcebf3"},
            "profile": {"commander": "Test"}, "reduced_motion": True, "view_state": {"layers": {}},
            "current": {"system": "Colonia", "position": [-9530.5, -910.3, 19808.1], "region": {"id": 9, "name": "Inner Scutum-Centaurus Arm"}},
            "route": route, "planned": [{"system": "Far Away", "pos": [-9800, -900, 20300], "visited": False}],
            "markers": [{"layer": "Biology", "kind": "System", "system": "Merope", "subject": "Biological survey", "detail": "3 signals",
                         "position": [-78.6, -149.6, -340.5]}],
            "annotations": [], "route_context": {}, "session": {"started_epoch": 0}, "summary": {},
        }

    def open(self):
        commands = []
        server = GalacticMapServer(STATIC, ROOT / "assets" / "images" / "Galaxy" / "voidcompass-galactic-atlas.png",
                                   command_callback=lambda payload: commands.append(payload) or True,
                                   regions_provider=galactic_region_payload)
        self.addCleanup(server.stop)
        server.publish(self.snapshot())
        context = self.browser.new_context(viewport={"width": 1400, "height": 900}, bypass_csp=True)
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: message.type == "error" and errors.append(message.text))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        page.goto(server.url)
        page.wait_for_function("window.voidcompassAtlas", timeout=30000)
        return page, commands

    def test_it_charts_regions_history_and_keeps_the_commanders_view(self):
        page, commands = self.open()
        # The browser names regions exactly as Python does.
        self.assertEqual(page.evaluate("window.voidcompassAtlas.regionAt(0, 0)"), find_region(0, 0, 0)[0])
        state = page.evaluate("window.voidcompassAtlas.state()")
        self.assertEqual((state["systems"], state["regionsVisited"], state["currentRegion"]), (4, 2, 9))
        self.assertIn("here", state["labels"])
        self.assertEqual(page.locator("#stat-regions").inner_text(), "2 / 42")
        # A region from the list is selected and described.
        page.locator('[data-tab="regions"]').click()
        page.locator('[data-region="18"]').click()
        page.wait_for_function("window.voidcompassAtlas.state().selection?.id === 18")
        self.assertEqual(page.locator("#inspect-title").inner_text(), "Inner Orion Spur")
        # Dragging the map saves the commander's view.
        box = page.locator("#viewport canvas").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2 + 120, box["y"] + box["height"] / 2 + 40, steps=6)
        page.mouse.up()
        # Saved a moment after the map settles (software WebGL is slow under a
        # full test run, so allow a few seconds).
        for _ in range(30):
            saves = [command for command in commands if command.get("action") == "save_view"]
            if saves:
                break
            page.wait_for_timeout(200)
        self.assertTrue(saves)
        self.assertEqual(saves[-1]["state"]["orientation"], MAP_ORIENTATION)
        self.assertEqual(set(saves[-1]["state"]["camera"]), {"target", "distance", "heading", "tilt"})

    def test_a_map_mark_goes_back_to_python(self):
        page, commands = self.open()
        box = page.locator("#viewport canvas").bounding_box()
        page.mouse.click(box["x"] + box["width"] * .6, box["y"] + box["height"] * .45, button="right")
        page.locator('[data-menu="mark"]').click()
        page.locator("#mark-title").fill("Nebula to survey")
        page.locator("#mark-category").select_option("Survey Target")
        page.locator("#mark-form button.primary").click()
        page.wait_for_timeout(300)
        marks = [command for command in commands if command.get("action") == "annotation_upsert"]
        self.assertEqual(len(marks), 1)
        self.assertEqual((marks[0]["annotation"]["title"], marks[0]["annotation"]["category"]), ("Nebula to survey", "Survey Target"))
        self.assertEqual(len(marks[0]["annotation"]["position"]), 3)


if __name__ == "__main__":
    unittest.main()
