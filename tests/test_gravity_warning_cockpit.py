"""Gravity Warning: when it warns, what it publishes and how the page reads.

It warns once on ApproachBody, which fires at orbital cruise, and once more on
the hand-flown final descent over the same body, where the danger actually is.
"""

from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

from voidcompass.overlays.gravity_warning_hud import GravityWarningHUD
from voidcompass.overlays.html_gravity_overlay import HtmlGravityOverlayBridge


WEB = Path(__file__).resolve().parents[1] / "web"
BODY = "Synuefe XR-H d11-102 A 2"


def _warning():
    hud = GravityWarningHUD.__new__(GravityWarningHUD)
    hud.root = SimpleNamespace(_voidcompass_startup_presentation_held=False)
    hud.config = {"gravity_warning_threshold_g": 2.5}
    hud._hide_job = None
    hud._last_body = None
    hud._last_gravity = None
    hud._phase = "approach"
    hud._final_warned = False
    hud._telemetry = None
    hud.shows = 0

    def show():
        hud.shows += 1
        return True

    hud.show = show
    hud._schedule_hide = lambda: None
    hud.hide = lambda: None
    return hud


class GravityWarningBehaviourTests(unittest.TestCase):
    def test_final_descent_rewarns_once_for_the_same_body(self):
        hud = _warning()
        hud.check_body(BODY, 3.42)
        self.assertEqual((hud.shows, hud._phase), (1, "approach"))
        # Orbital cruise and glide: telemetry only.
        self.assertFalse(hud.observe_descent(BODY, 48200, 1240))
        self.assertEqual(hud._telemetry, {"altitude_m": 48200.0, "descent_mps": 1240.0})
        # Hovering or climbing near the surface is not the risky descent.
        self.assertFalse(hud.observe_descent(BODY, 1800, 0.5))
        self.assertFalse(hud.observe_descent(BODY, 1800, -12))
        self.assertTrue(hud.observe_descent(BODY.upper(), 1800, 42))
        self.assertEqual((hud.shows, hud._phase), (2, "final"))
        self.assertFalse(hud.observe_descent(BODY, 900, 30), "once per approach")
        self.assertEqual(hud.shows, 2)

    def test_other_bodies_and_leaving_reset_the_approach(self):
        hud = _warning()
        hud.check_body(BODY, 3.42)
        self.assertFalse(hud.observe_descent("Synuefe XR-H d11-102 A 3", 1800, 42))
        self.assertIsNone(hud._telemetry)
        self.assertFalse(hud.observe_descent(BODY, None, 0.0), "landed, SRV or on foot")
        hud.observe_descent(BODY, 1800, 42)
        hud.clear()
        self.assertEqual((hud._phase, hud._final_warned, hud._telemetry), ("approach", False, None))
        self.assertFalse(hud.observe_descent(BODY, 1800, 42), "nothing warned after LeaveBody")
        hud.check_body("Achenar 5", 4.1)
        self.assertTrue(hud.observe_descent("Achenar 5", 1200, 25))

    def test_bridge_publishes_short_name_phase_telemetry_and_scaled_window(self):
        hud = _warning()
        hud._threshold = lambda: 2.5
        hud.check_body(BODY, 3.42)
        hud.observe_descent(BODY, 1800, 42)
        bridge = HtmlGravityOverlayBridge.__new__(HtmlGravityOverlayBridge)
        bridge.overlay = hud
        bridge.config = {"overlay_text_scale_percent": 150, "gravity_warning_overlay_enabled": True}
        bridge.app = SimpleNamespace(current_sys="Synuefe XR-H d11-102")
        bridge.overlay_id = "gravity"
        bridge.enabled_key = "gravity_warning_overlay_enabled"
        bridge.x_key, bridge.y_key = "gravity_warning_hud_x", "gravity_warning_hud_y"
        bridge.win = SimpleNamespace(
            master=SimpleNamespace(_voidcompass_startup_presentation_held=False),
            state=lambda: "normal", winfo_x=lambda: 10, winfo_y=lambda: 20,
        )
        snapshot = bridge._snapshot()
        gravity = snapshot["gravity"]
        self.assertEqual((gravity["body_short"], gravity["system"]), ("A 2", "Synuefe XR-H d11-102"))
        self.assertEqual((gravity["phase"], gravity["severity"]), ("final", "high"))
        self.assertEqual((gravity["altitude_m"], gravity["descent_mps"]), (1800.0, 42.0))
        self.assertEqual((snapshot["window"]["width"], snapshot["window"]["height"]), (480, 159))
        self.assertEqual(hud._html_window_size, (480, 159))
        self.assertEqual(snapshot["effects"]["text_scale"], 1.5)


class GravityWarningBrowserTests(unittest.TestCase):
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

    def open(self, scale=1):
        page = self.browser.new_page(viewport={"width": round(320 * scale), "height": round(106 * scale)})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8")
                              + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: o => {"
                              " window.__render = o.render; }};")
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")

        page.route("http://gravity.test/**", serve)
        page.goto("http://gravity.test/gravity/index.html")
        return page

    def render(self, page, scale=1, reduced=True, **gravity):
        data = {"body": BODY, "body_short": "A 2", "system": "Synuefe XR-H d11-102", "g": 3.42,
                "threshold": 2.5, "severity": "high", "phase": "approach",
                "altitude_m": 48200, "descent_mps": 1240, **gravity}
        page.evaluate("p => __render(p)", {"gravity": data, "theme": {"red": "#ff6b70"},
                                          "effects": {"text_scale": scale, "reduced_motion": reduced}})
        return page.evaluate("""() => ({
          tag: document.getElementById('tag').textContent,
          value: document.getElementById('value').textContent,
          ratio: document.getElementById('ratio').textContent,
          body: document.getElementById('body').textContent,
          phase: document.getElementById('phase').textContent,
          marker: parseFloat(document.getElementById('marker').style.left),
          oneG: document.getElementById('one-g').hidden ? null : parseFloat(document.getElementById('one-g').style.left),
          limit: document.getElementById('limit').textContent,
          max: document.getElementById('max').textContent,
          offScale: document.getElementById('gravity').classList.contains('off-scale'),
        })""")

    def test_severity_value_and_gauge(self):
        page = self.open()
        view = self.render(page)
        self.assertEqual((view["tag"], view["value"], view["ratio"]), ("WARNING", "3.42 G", "1.37× LIMIT"))
        self.assertEqual(view["body"], "A 2 · SYNUEFE XR-H D11-102")
        # 0 to twice the limit: 3.42 of 5.0 G, the limit in the middle.
        self.assertAlmostEqual(view["marker"], 68.4, delta=.01)
        self.assertAlmostEqual(view["oneG"], 20.0, delta=.01)
        self.assertEqual((view["limit"], view["max"]), ("LIMIT 2.5 G", "5.0 G"))
        self.assertEqual(view["phase"], "APPROACH · ALT 48.2 KM · ▼ 1,240 M/S")
        self.assertEqual(self.render(page, g=2.9, severity="warning")["tag"], "CAUTION")
        critical = self.render(page, g=5.6, severity="critical", altitude_m=None, descent_mps=None)
        self.assertEqual((critical["tag"], critical["marker"], critical["offScale"], critical["phase"]),
                         ("WARNING", 100.0, True, "APPROACH"))
        # 1 G would sit on top of a 1 G limit, so it steps aside.
        self.assertIsNone(self.render(page, threshold=1.0, g=1.4)["oneG"])

    def test_final_approach_and_motion(self):
        page = self.open()
        self.assertEqual(self.render(page, phase="final", altitude_m=1840, descent_mps=42)["phase"],
                         "FINAL APPROACH · ALT 1.8 KM · ▼ 42 M/S")
        self.render(page, reduced=False, severity="critical", g=5.6)
        self.assertTrue(page.evaluate("document.querySelector('.notice').getAnimations().length > 0"))
        self.render(page, reduced=True, severity="critical", g=5.6)
        self.assertEqual(page.evaluate("document.getAnimations().length"), 0)

    def test_every_text_size_fits_its_window(self):
        for scale in (.75, 1, 1.5, 2):
            with self.subTest(scale=scale):
                page = self.open(scale)
                self.render(page, scale=scale, body_short="AB 12 C 4", system="Plaa Aec IZ-N c20-1",
                            phase="final", altitude_m=1840, descent_mps=1420, g=12.34, severity="critical")
                fit = page.evaluate("""() => {
                  const root = document.getElementById('gravity').getBoundingClientRect();
                  const rows = [...document.querySelectorAll('.notice, .identity, .gauge, .scale, .phase')];
                  const values = [...document.querySelectorAll('.title, #value, #body, #ratio, #phase')];
                  return {
                    rows: rows.every((row) => { const box = row.getBoundingClientRect();
                      return box.top >= root.top - .5 && box.bottom <= root.bottom + .5; }),
                    clipped: values.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.id || el.className),
                    scrolls: document.documentElement.scrollHeight > innerHeight + 1,
                  };
                }""")
                self.assertTrue(fit["rows"], fit)
                self.assertEqual(fit["clipped"], [], fit)
                self.assertFalse(fit["scrolls"], fit)


if __name__ == "__main__":
    unittest.main()
