"""FOLLOW ME on the deck's Galactic Atlas (5.7.4)."""
import unittest

from tests import test_galactic_atlas as atlas
from voidcompass.exploration.expedition_map_view import ExpeditionMapView


class FollowViewStateTests(unittest.TestCase):
    def test_follow_is_saved_only_when_switched_on(self):
        view = ExpeditionMapView.__new__(ExpeditionMapView)
        view.config = {}
        self.assertFalse(view._normalise_view_state({})["follow"])
        self.assertTrue(view._normalise_view_state({"follow": True})["follow"])
        self.assertFalse(view._normalise_view_state({"follow": "yes"})["follow"])


class FollowMeBrowserTests(unittest.TestCase):
    setUpClass = classmethod(atlas.AtlasBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(atlas.AtlasBrowserTests.tearDownClass.__func__)
    snapshot = atlas.AtlasBrowserTests.snapshot
    open = atlas.AtlasBrowserTests.open

    def here_on_screen(self, page, position):
        return page.evaluate("(pos) => window.voidcompassAtlas.project(pos)", position)

    def test_follow_me_centres_follows_arrivals_and_stops_when_panned(self):
        page, commands = self.open()
        button = page.locator("#follow-me")
        self.assertEqual(button.get_attribute("aria-pressed"), "false")
        # Its hover description says what it does.
        button.hover()
        page.wait_for_selector("#tooltip:not([hidden])")
        tip = page.locator("#tooltip").inner_text()
        self.assertIn("FOLLOW ME", tip)
        self.assertIn("YOU ARE HERE", tip)
        self.assertIn("centred", tip)
        button.click()
        page.wait_for_function("window.voidcompassAtlas.state().follow === true")
        self.assertEqual(button.get_attribute("aria-pressed"), "true")
        colonia = [-9530.5, -910.3, 19808.1]
        page.wait_for_timeout(300)
        anchor = self.here_on_screen(page, colonia)
        # A jump arrives: the map follows to the new position, same place on screen.
        snapshot = self.snapshot()
        moved = [-9300.0, -900.0, 20500.0]
        snapshot["route"].append({"system": "Next Stop", "pos": moved, "timestamp": "2026-09-10T10:00:00Z", "jump_dist": 700, "star_class": "K"})
        snapshot["current"] = {"system": "Next Stop", "position": moved, "region": {"id": 9, "name": "Inner Scutum-Centaurus Arm"}}
        self._publish(page, snapshot)
        page.wait_for_function(f"(() => {{ const p = window.voidcompassAtlas.project({moved}); return p && Math.hypot(p.x - {anchor['x']}, p.y - {anchor['y']}) < 6; }})()",
                               timeout=15000)
        # The choice is saved with the view.
        for _ in range(30):
            saves = [command for command in commands if command.get("action") == "save_view"]
            if saves and saves[-1]["state"].get("follow") is True:
                break
            page.wait_for_timeout(200)
        self.assertTrue(saves[-1]["state"]["follow"])
        # Panning the map hands control back.
        box = page.locator("#viewport canvas").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2 + 160, box["y"] + box["height"] / 2 + 30, steps=6)
        page.mouse.up()
        page.wait_for_function("window.voidcompassAtlas.state().follow === false")
        self.assertEqual(button.get_attribute("aria-pressed"), "false")

    def _publish(self, page, snapshot):
        # The fixture's server is the only one this page talks to; republish through it.
        server = self._server
        server.publish(snapshot)

    def setUp(self):
        original = atlas.GalacticMapServer

        test = self

        class Recording(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                test._server = self

        atlas.GalacticMapServer = Recording
        self.addCleanup(setattr, atlas, "GalacticMapServer", original)


if __name__ == "__main__":
    unittest.main()
