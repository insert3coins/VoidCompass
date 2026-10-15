"""5.5.3.7: the Galaxy Minimap overlay.

The Milky Way in a corner of the screen, drawn from the same Codex region
map (and the same regions.js) as the Galactic Atlas, with you on it: the
here and now. The trail of this game session's jumps (from its LoadGame),
the route you've plotted, waypoint by waypoint, Sol and the core; the
region's name and how far from Sol underneath. (The whole journey was on it
at first; the user preferred the session and the route, and the Galactic
Atlas has the rest.)"""

import http.client
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.exploration.travel_history import TravelHistory
from voidcompass.overlays.galaxy_minimap_hud import (
    TRAIL_POINTS, GalaxyMinimapHUD, build_minimap_model, minimap_options, plotted_route, session_trail,
)
from voidcompass.overlays.html_galaxy_minimap_overlay import HtmlGalaxyMinimapBridge, minimap_file
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class FakeRoot:
    def __init__(self):
        self.jobs = {}
        self.serial = 0

    def call_later(self, milliseconds, callback):
        self.serial += 1
        self.jobs[self.serial] = (milliseconds, callback)
        return self.serial

    def cancel(self, token):
        self.jobs.pop(token, None)


def row(index, x, z, system=None):
    return [f"2026-10-11T10:{index // 60:02d}:{index % 60:02d}Z", system or f"Sys {index}", x, 0.0, z, "K", 40.0, ""]


def route(*stops):
    return [{"StarSystem": name, "StarPos": list(pos)} for name, pos in stops]


BEAGLE = ("Beagle Point", (-1111.56, -134.22, 65269.75))


class ModelTests(unittest.TestCase):
    def test_options_stay_within_their_choices(self):
        self.assertEqual(minimap_options({}), {"size": 240, "view": "route", "route": True, "labels": True, "spansh": True,
                                                "capsules": True, "region_text": 0},
                         "Your route by default: the whole galaxy made you and the route hard to see")
        self.assertEqual(minimap_options({"galaxy_minimap_size": 999, "galaxy_minimap_view": "zoom"})["size"], 240)
        self.assertEqual(minimap_options({"galaxy_minimap_view": "LOCAL"})["view"], "local")

    def test_a_long_session_is_thinned_but_keeps_both_ends(self):
        rows = [row(index, index * 100.0, index * 50.0) for index in range(5000)]
        points = session_trail(rows)
        self.assertEqual(len(points), TRAIL_POINTS)
        self.assertEqual((points[0], points[-1]), ([0.0, 0.0], [499900.0, 249950.0]))

    def test_the_route_ahead_from_where_you_are(self):
        plotted = route(("Sol", (0, 0, 0)), ("Alpha Centauri", (3.03, -0.09, 3.16)),
                        ("Colonia", (-9530.5, -910.3, 19808.1)), BEAGLE)
        ahead = plotted_route(plotted, [3.03, -0.09, 3.16], "Alpha Centauri")
        self.assertEqual(ahead["points"][0], [3.0, 3.2], "from where you are, not where it was plotted")
        self.assertEqual((ahead["name"], ahead["jumps"], len(ahead["points"])), ("Beagle Point", 2, 3))
        self.assertAlmostEqual(ahead["distance"], math.dist((3.03, -0.09, 3.16), BEAGLE[1]), 0)
        self.assertIsNone(plotted_route(plotted, BEAGLE[1], "Beagle Point"), "arrived: no route left")
        self.assertIsNone(plotted_route([], None))

    def test_where_you_are_this_session_and_the_route(self):
        rows = [row(index, -index * 30.0, index * 60.0) for index in range(10)]
        model = build_minimap_model(rows, position=[0.0, 0.0, 0.0], system="Sol",
                                    route_entries=route(("Sol", (0, 0, 0)), BEAGLE), regions_visited=3)
        self.assertEqual(model["here"]["system"], "Sol")
        self.assertEqual(model["here"]["region"], "Inner Orion Spur")
        self.assertEqual(len(model["trail"]), 10, "every jump this session")
        self.assertEqual(model["session_jumps"], 9, "the first row is where the session began")
        self.assertEqual(model["route"]["name"], "Beagle Point")
        self.assertNotIn("journey", model, "the whole journey is the Galactic Atlas's")
        off = build_minimap_model(rows, route_entries=route(("Sys 9", (1, 2, 3)), BEAGLE),
                                  options={**minimap_options({}), "route": False})
        self.assertIsNone(off["route"])
        self.assertEqual(off["here"]["system"], "Sys 9", "no ship position: the last arrival")

    def test_the_hud_rebuilds_only_when_something_changed(self):
        hud = GalaxyMinimapHUD(FakeRoot(), {})
        rows = [row(0, 0.0, 0.0, "Sol"), row(1, 3.03, -0.09, "Alpha Centauri"), row(2, -9530.5, 19808.1, "Colonia")]
        self.assertTrue(hud.update(rows[1:], rows, 1, [-9530.5, -910.3, 19808.1], "Colonia"))
        self.assertFalse(hud.update(rows[1:], rows, 1, [-9530.5, -910.3, 19808.1], "Colonia"))
        model = hud._html_render_model
        self.assertEqual(model["here"]["region"], "Inner Scutum-Centaurus Arm", "Colonia, by the Codex map")
        self.assertEqual(model["regions_visited"], 2, "regions over the whole journey")
        self.assertEqual(model["session_jumps"], 1)
        hud.config["galaxy_minimap_view"] = "local"
        hud.apply_settings()
        self.assertEqual(hud._html_render_model["options"]["view"], "local")


class ControlTests(unittest.TestCase):
    """Its own view hotkey, its own text size, region names (5.5.3.7)."""

    def test_the_view_hotkey_goes_round(self):
        from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS
        from voidcompass.overlays.galaxy_minimap_hud import next_view
        self.assertEqual([next_view(view) for view in ("route", "local", "galaxy", "?")], ["local", "galaxy", "route", "route"])
        spec = next(row for row in OVERLAY_HOTKEY_SPECS if row[0] == "galaxy_minimap_view")
        self.assertEqual(spec[1], "overlay_hotkey_galaxy_minimap_view")
        self.assertIn(spec[1], config_module.PROFILE_SETTINGS)

        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        saved, feed = [], []
        deck.config = {}
        deck._persist_config = lambda: saved.append(deck.config["galaxy_minimap_view"])
        deck.add_event_feed_entry = lambda tag, text, severity=None: feed.append(text)
        deck.galaxy_minimap_hud = GalaxyMinimapHUD(FakeRoot(), deck.config)
        self.assertEqual(deck._galaxy_minimap_next_view(), "local")
        self.assertEqual(deck.galaxy_minimap_hud._html_render_model["options"]["view"], "local")
        self.assertEqual(deck._galaxy_minimap_next_view(), "galaxy")
        self.assertEqual(saved, ["local", "galaxy"])
        self.assertEqual(feed[-1], "Galaxy Minimap: Whole galaxy")
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('if action == "galaxy_minimap_view":', dashboard)

    def test_its_own_text_size(self):
        from voidcompass.overlays.galaxy_minimap_hud import minimap_text_scale
        self.assertEqual(minimap_text_scale({"overlay_text_scale_percent": 120}), 1.2, "0 follows all overlays")
        self.assertEqual(minimap_text_scale({"galaxy_minimap_text_scale_percent": 150}), 1.5)
        self.assertEqual(minimap_text_scale({"galaxy_minimap_text_scale_percent": 140}), 1.5, "the nearest on the list")
        bridge = HtmlGalaxyMinimapBridge.__new__(HtmlGalaxyMinimapBridge)
        bridge.config = {"galaxy_minimap_size": 240, "galaxy_minimap_text_scale_percent": 200, "overlay_text_scale_percent": 100}
        self.assertEqual(bridge._dimensions(), (240, 240 + 80), "the strip grows, the map keeps its size")
        self.assertIn("galaxy_minimap_text_scale_percent", config_module.PROFILE_SETTINGS)
        self.assertIn("galaxy_minimap_labels", config_module.PROFILE_SETTINGS)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-studio-setting="galaxy_minimap_text_scale_percent"', html)
        self.assertIn('data-overlay-option="galaxy_minimap_labels"', html)


class SessionTests(unittest.TestCase):
    """The travel history remembers when the game session began."""

    def test_the_session_starts_at_its_loadgame(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            history = TravelHistory(str(Path(folder) / "travel.json"))

            def jump(stamp, name, x):
                return {"event": "FSDJump", "timestamp": stamp, "StarSystem": name, "StarPos": [x, 0, 0], "JumpDist": 10}
            history.observe(jump("2026-10-10T20:00:00Z", "Yesterday A", 1))
            history.observe(jump("2026-10-10T20:10:00Z", "Yesterday B", 2))
            history.observe({"event": "LoadGame", "timestamp": "2026-10-11T19:00:00Z"})
            self.assertEqual([row[1] for row in history.session_rows()], ["Yesterday B"], "where it began")
            history.observe(jump("2026-10-11T19:05:00Z", "Today A", 3))
            self.assertEqual([row[1] for row in history.session_rows()], ["Yesterday B", "Today A"])
            history.flush(wait=True)
            again = TravelHistory(str(Path(folder) / "travel.json"))
            self.assertEqual(again.session_start, "2026-10-11T19:00:00Z", "kept with the history")

    def test_from_the_journals_too(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            journal = Path(folder) / "Journal.2026-10-11T190000.01.log"
            lines = [{"event": "Commander", "timestamp": "2026-10-11T19:00:00Z", "Name": "Cmdr", "FID": "F1"},
                     {"event": "LoadGame", "timestamp": "2026-10-11T19:00:01Z", "Commander": "Cmdr", "FID": "F1"},
                     {"event": "FSDJump", "timestamp": "2026-10-11T19:05:00Z", "StarSystem": "Today A",
                      "StarPos": [1, 0, 0], "JumpDist": 1}]
            journal.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
            history = TravelHistory(str(Path(folder) / "travel.json"))
            history.import_journals(folder, commander="Cmdr", fid="F1")
            history.flush(wait=True)
            self.assertEqual(history.session_start, "2026-10-11T19:00:01Z")


class BridgeTests(unittest.TestCase):
    def test_the_window_is_the_map_and_its_strip(self):
        bridge = HtmlGalaxyMinimapBridge.__new__(HtmlGalaxyMinimapBridge)
        bridge.config = {"galaxy_minimap_size": 320, "overlay_text_scale_percent": 150}
        self.assertEqual(bridge._dimensions(), (320, 320 + 60))

    def test_the_region_map_is_served_once_by_name_and_token(self):
        body, kind = minimap_file("regions")
        raster = json.loads(body)
        self.assertEqual((raster["size"], len(raster["rows"]), len(raster["names"])), (2048, 2048, 42))
        self.assertIn("json", kind)
        self.assertIsNone(minimap_file("anything else"))
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        server.register("galaxy-minimap", "galaxy_minimap", "Minimap")
        server.set_file_provider("galaxy-minimap", minimap_file)
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("GET", f"/api/file?token={server.token}&overlay=galaxy-minimap&name=regions")
        reply = connection.getresponse()
        self.assertEqual(reply.status, 200)
        self.assertEqual(json.loads(reply.read())["size"], 2048)
        connection.request("GET", f"/api/file?token={server.token}&overlay=galaxy-minimap&name=nope")
        reply = connection.getresponse()
        reply.read()
        self.assertEqual(reply.status, 404)
        connection.request("GET", "/api/file?overlay=galaxy-minimap&name=regions")
        reply = connection.getresponse()
        reply.read()
        self.assertEqual(reply.status, 403, "only with the token")


class DashboardTests(unittest.TestCase):
    def test_it_follows_the_session_the_ship_and_the_route(self):
        hud = GalaxyMinimapHUD(FakeRoot(), {})
        import threading
        rows = [row(0, 0.0, 0.0, "Sol")]
        history = SimpleNamespace(lock=threading.RLock(), rows=rows, revision=4, session_rows=lambda: list(rows))

        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.__dict__.update(galaxy_minimap_hud=hud, travel_history=history, current_coords=[0, 0, 0], current_sys="Sol",
                             nav_route_entries=route(("Sol", (0, 0, 0)), ("Colonia", (-9530.5, -910.3, 19808.1))))
        deck._update_galaxy_minimap()
        self.assertEqual(hud._html_render_model["route"]["name"], "Colonia")
        self.assertEqual(hud._html_render_model["here"]["system"], "Sol")
        # 0, 0, 0 anywhere but Sol is "not known yet".
        deck.current_sys = "Achenar"
        self.assertIsNone(deck._galaxy_minimap_position())


class RegistrationTests(unittest.TestCase):
    def test_a_managed_overlay_off_until_turned_on(self):
        spec = OVERLAY_SPEC_BY_ATTR["galaxy_minimap_hud"]
        self.assertEqual((spec.overlay_id, spec.default_enabled, spec.hotkey_key),
                         ("galaxy-minimap", False, "overlay_hotkey_galaxy_minimap"))
        self.assertTrue((WEB / "galaxy_minimap" / "index.html").is_file())

    def test_every_setting_follows_the_commander(self):
        for key in ("galaxy_minimap_overlay_enabled", "galaxy_minimap_hud_x", "galaxy_minimap_hud_y",
                    "galaxy_minimap_size", "galaxy_minimap_view", "galaxy_minimap_route",
                    "overlay_hotkey_galaxy_minimap"):
            with self.subTest(key=key):
                self.assertIn(key, config_module.PROFILE_SETTINGS)

    def test_studio_offers_and_saves_the_options(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        for marker in ('data-studio-settings="galaxy_minimap_hud"', 'data-studio-setting="galaxy_minimap_size"',
                       'data-studio-setting="galaxy_minimap_view"', 'data-overlay-option="galaxy_minimap_route"'):
            self.assertIn(marker, html)
        studio = SimpleNamespace(config={}, _persist_config=lambda: None, update_hud=lambda: None,
                                 _schedule_html_dashboard_publish=lambda **kw: None,
                                 heartbeat_hud=None, galnet_ticker_hud=None, music_player_hud=None,
                                 galaxy_minimap_hud=None, postcard_hud=None, station_info_hud=None,
                                 contact_scope_hud=None, current_docked=False)
        HtmlOverlayStudioMixin._html_overlay_settings_save(studio, {"galaxy_minimap_size": "320", "galaxy_minimap_view": "local"})
        self.assertEqual((studio.config["galaxy_minimap_size"], studio.config["galaxy_minimap_view"]), (320, "local"))
        HtmlOverlayStudioMixin._html_overlay_settings_save(studio, {"galaxy_minimap_size": "77", "galaxy_minimap_view": "?"})
        self.assertEqual((studio.config["galaxy_minimap_size"], studio.config["galaxy_minimap_view"]), (240, "route"))


STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderMinimap = options.render; return {rerender() {}}; }};")
THEME = {"bg": "#070b10", "panel": "#0d141c", "accent": "#00d1ff", "orange": "#ff7a18", "text": "#dce8ef",
         "green": "#4ee59b", "yellow": "#ffd166"}


class PageTests(unittest.TestCase):
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

    def open(self, model):
        page = self.browser.new_page(viewport={"width": 240, "height": 280})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertFalse(errors, errors))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/file":
                body, kind = minimap_file("regions")
                route.fulfill(body=body, content_type=kind)
                return
            file = WEB / path.lstrip("/")
            if not file.is_file():
                route.fulfill(status=404, body="")
            elif file.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(file))
        page.route("http://map.test/**", serve)
        page.goto("http://map.test/galaxy_minimap/index.html?token=t&overlay=galaxy-minimap")
        page.wait_for_function("Boolean(window.renderMinimap)")
        page.evaluate("data => renderMinimap(data)", {"theme": THEME, "effects": {"text_scale": 1}, "minimap": model})
        page.wait_for_function("window.__minimap.ready()", timeout=20000)
        return page

    def test_it_draws_the_galaxy_and_puts_you_on_it(self):
        rows = [row(0, 0.0, 0.0, "Sol"), row(1, -9530.5, 19808.1, "Colonia")]
        model = build_minimap_model(rows, position=[-9530.5, -910.3, 19808.1], system="Colonia")
        page = self.open(model)
        self.assertEqual(page.inner_text("#region"), "INNER SCUTUM-CENTAURUS ARM")
        self.assertIn("LY FROM SOL", page.inner_text("#facts"))
        lit = page.evaluate("""() => {
            const canvas = document.getElementById('galaxy');
            const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
            let lit = 0;
            for (let i = 3; i < data.length; i += 4) if (data[i] > 0) lit += 1;
            return lit / (data.length / 4);
        }""")
        self.assertGreater(lit, .4, "the galaxy fills most of the map")
        # You are where the projection says, and the ring is on you.
        ring = page.evaluate("() => { const r = document.getElementById('here-ring'); return [r.hidden, parseFloat(r.style.left), parseFloat(r.style.top)]; }")
        expected = page.evaluate("() => { const b = window.__minimap.bounds(); const box = document.getElementById('map').getBoundingClientRect(); return window.__minimap.project(b, box.width, box.height, -9530.5, 19808.1); }")
        self.assertFalse(ring[0])
        self.assertAlmostEqual(ring[1], expected[0], 1)
        self.assertAlmostEqual(ring[2], expected[1], 1)

    def test_your_route_frames_you_the_trail_and_the_route(self):
        rows = [row(0, 0.0, 0.0, "Sol"), row(1, 400.0, 900.0, "Mid")]
        entries = [{"StarSystem": "Mid", "StarPos": [400.0, 0.0, 900.0]}, {"StarSystem": "Far", "StarPos": [3000.0, 0.0, 5000.0]}]
        model = build_minimap_model(rows, position=[400.0, 0.0, 900.0], system="Mid", route_entries=entries,
                                    options={**minimap_options({}), "view": "route"})
        page = self.open(model)
        frame = page.evaluate("() => window.__minimap.bounds()")
        for x, z in ((0, 0), (400, 900), (3000, 5000)):
            self.assertTrue(frame["left"] < x < frame["right"] and frame["bottom"] < z < frame["top"], (x, z))
        self.assertLess(frame["span"], 8000, "close in, not the whole galaxy")
        alone = build_minimap_model([row(0, 10.0, 10.0)], position=[10.0, 0.0, 10.0], system="Here",
                                    options={**minimap_options({}), "view": "route"})
        page.evaluate("data => renderMinimap(data)", {"theme": THEME, "effects": {"text_scale": 1}, "minimap": alone})
        self.assertEqual(page.evaluate("() => window.__minimap.bounds().span"), 2000, "at least 2,000 ly across")

    def test_regions_are_named_and_systems_are_not(self):
        rows = [row(0, -9000.0, 19000.0, "Start"), row(1, -9530.5, 19808.1, "Colonia")]
        entries = [{"StarSystem": "Colonia", "StarPos": [-9530.5, -910.3, 19808.1]},
                   {"StarSystem": "Beagle Point", "StarPos": [-1111.56, -134.22, 65269.75]}]
        model = build_minimap_model(rows, position=[-9530.5, -910.3, 19808.1], system="Colonia", route_entries=entries)
        page = self.open(model)
        names = page.evaluate("() => window.__minimap.spots().map(spot => spot.name)")
        self.assertGreaterEqual(len(names), 3, "the regions on show are named")
        self.assertTrue(set(names) <= set(page.evaluate("() => window.__minimap.spots().map(s => s.name)")))
        strip = page.inner_text("#strip")
        self.assertNotIn("BEAGLE", strip.upper(), "system names are the Navigation HUD's")
        self.assertNotIn("COLONIA", strip.upper())
        self.assertIn("JUMP", strip)

    def test_the_close_up_centres_on_you(self):
        model = build_minimap_model([row(0, 1000.0, 2000.0)], position=[1000.0, 0.0, 2000.0], system="Here",
                                    options={**minimap_options({}), "view": "local"})
        page = self.open(model)
        centre = page.evaluate("() => { const b = window.__minimap.bounds(); return [(b.left + b.right) / 2, (b.top + b.bottom) / 2, b.span]; }")
        self.assertEqual(centre, [1000, 2000, 16000])


if __name__ == "__main__":
    unittest.main()


class StripAndStudioTests(unittest.TestCase):
    def test_the_strip_names_the_view(self):
        page = (WEB / "galaxy_minimap" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="view-mode"', page)
        app = (WEB / "galaxy_minimap" / "app.js").read_text(encoding="utf-8")
        self.assertIn('{route: "ROUTE", local: "LOCAL", galaxy: "GALAXY"}', app)
        self.assertIn("viewMode.textContent = VIEW_NAMES[model.options?.view]", app)

    def test_studio_lists_the_overlays_alphabetically(self):
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("const byName = [...overlays].sort((a, b) => String(a.label", app)
        self.assertIn("const index = byName.map((row) => {", app)

