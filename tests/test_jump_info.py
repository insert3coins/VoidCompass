"""5.5.1.5 Jump Info overlay: the system a hyperspace jump is heading for,
shown while the drive charges and in witch space (after SrvSurvey's jump
panel), in the commander's own theme."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPEC_BY_ATTR
from voidcompass.dashboard.dashboard_jump_info_mixin import DashboardJumpInfoMixin
from voidcompass.overlays.jump_info_hud import (
    build_jump_info_model, elite_date, intel_lines, route_plan, star_kind,
)
from voidcompass.services.edsm_handler import EDSMHandler

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

ROUTE = [
    {"StarSystem": "Sol", "SystemAddress": 1, "StarPos": [0, 0, 0], "StarClass": "G"},
    {"StarSystem": "Alpha Centauri", "SystemAddress": 2, "StarPos": [3, 0, 4], "StarClass": "G"},
    {"StarSystem": "Barnard's Star", "SystemAddress": 3, "StarPos": [3, 0, 14], "StarClass": "N"},
    {"StarSystem": "Ross 128", "SystemAddress": 4, "StarPos": [3, 0, 24], "StarClass": "M"},
]

KNOWN = {
    "system": "Barnard's Star", "available": True, "known": True,
    "discovered_by": "Jededdiah Stahl", "discovered_at": "2022-04-04 10:11:12",
    "updated_at": "2025-01-09 08:00:00", "traffic": {"day": 0, "week": 3, "total": 1204},
    "body_count": 12, "bodies_logged": 12, "landable": 4, "terraformable": 2,
    "notable": {"earth_like": 1, "water": 0, "ammonia": 0},
    "ports": {"starports": 1, "outposts": 0, "settlements": 0, "carriers": 3},
}


def items(lines, key):
    row = next(line for line in lines if line["key"] == key)
    return [(item["label"], item["value"]) for item in row["items"]]


class ModelTests(unittest.TestCase):
    def test_route_places_the_jump_and_measures_every_hop(self):
        plan = route_plan(ROUTE, "barnard's star")
        self.assertEqual((plan["hop"], plan["hops"], plan["remaining"]), (2, 3, 1))
        self.assertEqual((plan["jump_ly"], plan["total_ly"]), (10.0, 25.0))
        self.assertEqual([segment["state"] for segment in plan["segments"]], ["behind", "next", "ahead"])
        self.assertEqual([segment["scoop"] for segment in plan["segments"]], [True, False, True])
        self.assertTrue(plan["segments"][1]["neutron"])
        self.assertEqual(route_plan(ROUTE, "Elsewhere"), None)
        self.assertEqual(route_plan(ROUTE, "", target_address=4)["hop"], 3)
        # The system the route starts from is never a hop of its own.
        self.assertIsNone(route_plan(ROUTE, "Sol"))

    def test_star_kinds(self):
        for code, label in (("K", "SCOOPABLE"), ("M_RedGiant", "SCOOPABLE"), ("N", "NEUTRON STAR"),
                            ("DA", "WHITE DWARF"), ("H", "BLACK HOLE"), ("AeBe", "NOT SCOOPABLE"),
                            ("TTS", "NOT SCOOPABLE"), ("L", "NOT SCOOPABLE")):
            with self.subTest(code=code):
                self.assertEqual(star_kind(code)["label"], label)
        self.assertIsNone(star_kind(""))

    def test_edsm_lines(self):
        lines = intel_lines(KNOWN)
        self.assertEqual(items(lines, "history"),
                         [("DISCOVERED BY", "JEDEDDIAH STAHL · 4 APR 3308"), ("UPDATED", "9 JAN 3311")])
        self.assertEqual(items(lines, "traffic"), [("TRAFFIC 24H", "0"), ("WEEK", "3"), ("EVER", "1,204")])
        self.assertEqual(items(lines, "bodies"), [("BODIES", "12"), ("EARTH-LIKE", "1"),
                                                   ("TERRAFORMABLE", "2"), ("LANDABLE", "4")])
        self.assertEqual(items(lines, "ports"), [("STARPORTS", "1"), ("CARRIERS", "3")])
        # Updated no later than the discovery says nothing new.
        same = intel_lines({**KNOWN, "updated_at": KNOWN["discovered_at"]})
        self.assertEqual(items(same, "history"), [("DISCOVERED BY", "JEDEDDIAH STAHL · 4 APR 3308")])
        self.assertEqual(intel_lines(None)[0]["items"][0]["value"], "QUERYING...")
        self.assertEqual(intel_lines({"available": False})[0]["items"][0]["value"], "UNAVAILABLE")
        self.assertEqual(intel_lines({"known": False})[0]["items"][0]["label"], "NOT LOGGED")
        self.assertEqual(elite_date("not a date"), ("", None))

    def test_now_entering_only_when_the_region_changes(self):
        regions = lambda x, y, z: (1, "Galactic Centre") if z > 10 else (18, "Inner Orion Spur")
        model = build_jump_info_model("charging", {"name": "Ross 128"}, ROUTE, KNOWN,
                                      current_region="Inner Orion Spur", find_region=regions)
        self.assertEqual(items(model["lines"], "entering"), [("NOW ENTERING", "GALACTIC CENTRE")])
        self.assertEqual(model["star"]["label"], "SCOOPABLE", "the route knows the star when the journal didn't")
        self.assertNotIn("position", model["route"])
        same = build_jump_info_model("charging", {"name": "Alpha Centauri"}, ROUTE, KNOWN,
                                     current_region="Inner Orion Spur", find_region=regions)
        self.assertNotIn("entering", [line["key"] for line in same["lines"]])
        self.assertIsNone(build_jump_info_model("charging", {}, ROUTE))


class EdsmTests(unittest.TestCase):
    def intel(self, replies):
        handler = EDSMHandler.__new__(EDSMHandler)
        calls = []

        def get(url, params=None, **_):
            calls.append(url.rsplit("/", 1)[-1])
            reply = replies[url.rsplit("/", 1)[-1]]
            if isinstance(reply, Exception):
                raise reply
            return SimpleNamespace(json=lambda: reply)

        handler._limited_get = get
        return handler._jump_intel("Barnard's Star"), calls

    def test_a_known_system(self):
        intel, calls = self.intel({
            "traffic": {"id": 9, "name": "Barnard's Star", "traffic": {"day": 1, "week": 2, "total": 3},
                        "discovery": {"commander": "Jededdiah Stahl", "date": "2022-04-04 10:11:12"}},
            "bodies": {"bodyCount": 14, "bodies": [
                {"subType": "Earth-like world", "isLandable": False, "updateTime": "2023-09-01 08:00:00",
                 "terraformingState": "Not terraformable"},
                {"subType": "High metal content world", "isLandable": True,
                 "terraformingState": "Candidate for terraforming", "updateTime": "2022-05-01 08:00:00"},
            ]},
            "stations": {"stations": [{"type": "Coriolis Starport"}, {"type": "Fleet Carrier"},
                                      {"type": "Odyssey Settlement"}, {"type": "Planetary Outpost"}]},
        })
        self.assertEqual(calls, ["traffic", "bodies", "stations"])
        self.assertTrue(intel["known"])
        self.assertEqual((intel["body_count"], intel["landable"], intel["terraformable"]), (14, 1, 1))
        self.assertEqual(intel["notable"]["earth_like"], 1)
        self.assertEqual(intel["updated_at"], "2023-09-01 08:00:00")
        self.assertEqual(intel["ports"], {"starports": 1, "outposts": 1, "settlements": 1, "carriers": 1})

    def test_unlogged_failing_and_older_systems(self):
        intel, calls = self.intel({"traffic": []})
        self.assertEqual((intel["known"], intel["available"], calls), (False, True, ["traffic"]))
        intel, _calls = self.intel({"traffic": TimeoutError("slow")})
        self.assertFalse(intel["available"])
        # No system discovery on record: the earliest body discovery stands in.
        intel, _calls = self.intel({
            "traffic": {"id": 9, "traffic": {"total": 2}},
            "bodies": {"bodies": [{"discovery": {"commander": "Later", "date": "2020-01-02 00:00:00"}},
                                  {"discovery": {"commander": "First", "date": "2019-01-02 00:00:00"}}]},
            "stations": ValueError("down"),
        })
        self.assertEqual((intel["discovered_by"], intel["discovered_at"]), ("First", "2019-01-02 00:00:00"))


class PhaseTests(unittest.TestCase):
    def app(self, linger=0):
        app = DashboardJumpInfoMixin.__new__(type("App", (DashboardJumpInfoMixin,), {}))
        app.config = {"jump_info_linger_s": linger}
        app.current_coords = [0, 0, 0]
        app.nav_route_entries = ROUTE
        app._ui_post = lambda callback, key=None: callback()
        app.edsm = SimpleNamespace(fetch_jump_intel=Mock(side_effect=lambda name, callback: callback(KNOWN)))
        hud = SimpleNamespace(visible=False, lingering=False, _html_render_model=None)
        hud.update = Mock(side_effect=lambda model: setattr(hud, "visible", True) or setattr(hud, "_html_render_model", model) or True)
        hud.clear = Mock(side_effect=lambda: setattr(hud, "visible", False) or True)
        hud.linger = Mock(return_value=True)
        app.jump_info_hud = hud
        return app, hud

    def test_shows_while_charging_and_in_witch_space_then_goes(self):
        app, hud = self.app()
        app._jump_info_observe("FSDTarget", {"Name": "Barnard's Star", "SystemAddress": 3, "StarClass": "N"})
        app.edsm.fetch_jump_intel.assert_called_once()
        app._jump_info_observe("FSDTarget", {"Name": "Barnard's Star"})
        self.assertEqual(app.edsm.fetch_jump_intel.call_count, 1, "asked once per system")
        for phase in ("charging", "hyperspace"):
            app._navigation_jump_phase, app._navigation_jump_target = phase, "Barnard's Star"
            app._update_jump_info()
            model = hud.update.call_args.args[0]
            self.assertEqual((model["phase"], model["system"], model["star"]["label"]),
                             (phase, "Barnard's Star", "NEUTRON STAR"))
            self.assertEqual(items(model["lines"], "history")[0][0], "DISCOVERED BY")
        app._navigation_jump_phase = "arrival"
        app._update_jump_info()
        self.assertEqual(hud.linger.call_args.args[0]["phase"], "arrival")
        self.assertEqual(hud.linger.call_args.args[1], 0, "hides on arrival by default")
        app._navigation_jump_phase = ""
        app._update_jump_info()
        hud.clear.assert_called()

    def test_a_cancelled_charge_and_replays_hide_it(self):
        app, hud = self.app(linger=10)
        app._jump_info_observe("StartJump", {"JumpType": "Hyperspace", "StarSystem": "Ross 128"}, startup_replay=True)
        app.edsm.fetch_jump_intel.assert_not_called()
        app._jump_info_observe("StartJump", {"JumpType": "Supercruise"})
        app._navigation_jump_phase, app._navigation_jump_target = "charging", ""
        app._update_jump_info()
        hud.update.assert_called_with(None)


class WiringTests(unittest.TestCase):
    def test_registered_profile_aware_and_themed(self):
        spec = OVERLAY_SPEC_BY_ATTR["jump_info_hud"]
        self.assertEqual((spec.overlay_id, spec.hotkey_action), ("jump-info", "jump_info"))
        self.assertIn("jump_info", [row[0] for row in OVERLAY_HOTKEY_SPECS])
        self.assertIn("jump_info_overlay_enabled", config_module.PROFILE_BOOL_SETTINGS)
        for key in ("jump_info_hud_x", "jump_info_hud_y", "jump_info_linger_s"):
            self.assertIn(key, config_module.PROFILE_VALUE_SETTINGS)
        self.assertIn("overlay_hotkey_jump_info", config_module.PROFILE_TEXT_SETTINGS)
        self.assertIn("'jump_info_hud'", (ROOT / "src/voidcompass/core/theme_state.py").read_text(encoding="utf-8"))
        studio = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-studio-settings="jump_info_hud"', studio)
        self.assertIn('data-studio-setting="jump_info_linger_s"', studio)
        page = (WEB / "jump_info" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<style", page)
        css = (WEB / "jump_info" / "styles.css").read_text(encoding="utf-8")
        # Colours come from the theme: only the :root fallbacks name hex values,
        # besides the star orbs' physical star colours (as on the Nav HUD).
        rules = "\n".join(line for line in css.split("}", 1)[1].splitlines() if "star-" not in line)
        self.assertNotRegex(rules, r"#[0-9a-fA-F]{6}")
        # Never clip the page itself: clipped corners paint as blocks.
        self.assertNotRegex(css.split(".jump::before", 1)[0], r"\.jump \{[^}]*clip-path")

    def test_studio_saves_the_linger_choice(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {}
        for name in ("_persist_config", "update_hud", "_schedule_html_dashboard_publish"):
            setattr(studio, name, Mock())
        studio._html_overlay_settings_save({"jump_info_linger_s": "20"})
        self.assertEqual(studio.config["jump_info_linger_s"], 20)
        studio._html_overlay_settings_save({"jump_info_linger_s": "17"})
        self.assertEqual(studio.config["jump_info_linger_s"], 0)


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

    def open(self):
        page = self.browser.new_page(viewport={"width": 560, "height": 240})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8")
                              + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: o => {"
                              " window.__render = o.render; window.__height = o.contentHeight; }};")
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")

        page.route("http://jump.test/**", serve)
        page.goto("http://jump.test/jump_info/index.html")
        page.wait_for_selector("#jump", state="attached")
        return page

    def test_renders_the_jump_route_and_edsm_lines(self):
        page = self.open()
        regions = lambda x, y, z: (1, "Galactic Centre") if z > 10 else (18, "Inner Orion Spur")
        model = build_jump_info_model("hyperspace", {"name": "Barnard's Star", "star_class": "N"}, ROUTE, KNOWN,
                                      current_region="Inner Orion Spur", find_region=regions)
        page.evaluate("m => __render({jump: m, theme: {accent: '#22ccff'}, effects: {reduced_motion: true}})", model)
        self.assertEqual(page.locator("#phase").inner_text(), "WITCH SPACE")
        self.assertEqual(page.locator("#system-name").inner_text(), "BARNARD'S STAR")
        self.assertEqual(page.locator("#star-line").inner_text(), "CLASS N · NEUTRON STAR")
        self.assertEqual(page.locator("#route-count").inner_text(), "JUMP 2 OF 3")
        self.assertEqual(page.locator("#jump-ly").inner_text(), "10.0")
        self.assertEqual(page.locator("#route-line .seg.next").count(), 1)
        self.assertEqual(page.locator("#route-line .dot.target").count(), 1)
        self.assertEqual(page.locator("#route-line .scoop").count(), 2)
        self.assertEqual(page.locator(".line").count(), 5)
        self.assertIn("NOW ENTERING", page.locator('.line[data-key="entering"]').inner_text())
        # Every line fits the panel's width without spilling out.
        overflow = page.evaluate("""() => [...document.querySelectorAll('.line')]
            .some((line) => line.getBoundingClientRect().right > innerWidth)""")
        self.assertFalse(overflow)
        self.assertGreater(page.evaluate("__height()"), 120)
        # Off route: no route line, and the panel still says where it goes.
        alone = build_jump_info_model("charging", {"name": "Elsewhere"}, ROUTE, None)
        page.evaluate("m => __render({jump: m, theme: {}, effects: {reduced_motion: true}})", alone)
        self.assertTrue(page.locator("#route").is_hidden())
        self.assertEqual(page.locator("#star-line").inner_text(), "STAR CLASS UNKNOWN")
        self.assertIn("QUERYING", page.locator(".line").inner_text())


if __name__ == "__main__":
    unittest.main()
