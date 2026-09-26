"""Planet Waypoint compass: bridge state and real-browser checks.

The compass reads like the SRV and suit HUDs: a heading tape with the target on
it, Elite's target-compass ring, the distance, the turn to make and an approach
bar. Closing speed and ETA come only from measured position changes.
"""

from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

from voidcompass.core.overlay_registry import DEFAULT_SIZES
from voidcompass.overlays.html_ground_overlay import HtmlGroundOverlayBridge


WEB = Path(__file__).resolve().parents[1] / "web"


def _bridge(config=None, app=None):
    bridge = object.__new__(HtmlGroundOverlayBridge)
    bridge.overlay_id = "ground"
    bridge.x_key = "ground_popup_x"
    bridge.y_key = "ground_popup_y"
    bridge.enabled_key = "ground_popup_enabled"
    bridge.config = dict(config or {})
    bridge.app = app or SimpleNamespace(target_lat=1.0, target_lon=2.0, current_body_name="A 3")
    bridge._closing_key = None
    bridge._closing_sample = None
    bridge._closing_mps = None
    return bridge


class GroundOverlayBridgeTests(unittest.TestCase):
    def test_browser_height_resizes_host_and_studio_footprint(self):
        self.assertEqual(DEFAULT_SIZES["ground_popup"], (420, 208))
        bridge = _bridge({
            "ground_popup_x": 25, "ground_popup_y": 30,
            "ground_popup_enabled": True,
        })
        bridge.win = SimpleNamespace(
            master=SimpleNamespace(_voidcompass_startup_presentation_held=False),
            state=lambda: "normal", _html_ready=False,
            _html_window_size=(420, 208),
        )
        bridge._active = lambda solution=None: True
        bridge._browser_content_height = 0
        bridge._ready = False
        bridge._last_fingerprint = None
        bridge._sync_job = None
        bridge._schedule = lambda: None
        bridge._snapshot = lambda: {"window": bridge._window_payload({"state": "OK"})}
        published = []
        bridge.surface = SimpleNamespace(
            startup_failed=False, ready=True,
            server=SimpleNamespace(rendered_content_height=lambda overlay_id: 312),
            publish=published.append,
        )

        self.assertEqual(bridge._window_payload()["height"], 208)
        bridge._sync()
        self.assertEqual(bridge.win._html_window_size, (420, 312))
        self.assertEqual(published[-1]["window"]["height"], 312)
        self.assertTrue(published[-1]["window"]["visible"])
        bridge._browser_content_height = 999
        self.assertEqual(bridge._dimensions(), (420, 400))

    def test_text_size_scales_the_whole_instrument(self):
        bridge = _bridge({"overlay_text_scale_percent": 150})
        bridge._browser_content_height = 0
        self.assertEqual(bridge._dimensions(), (630, 312))
        bridge._browser_content_height = 380
        self.assertEqual(bridge._dimensions(), (630, 380))
        bridge._browser_content_height = 999
        self.assertEqual(bridge._dimensions(), (630, 600))

    def test_closing_speed_is_measured_from_real_positions_only(self):
        bridge = _bridge()
        ok = lambda metres: {"state": "OK", "distance_m": metres}
        # One position is not a speed.
        self.assertEqual(bridge._closing(ok(1000), now=10.0), (None, None))
        self.assertEqual(bridge._closing(ok(980), now=11.0), (20.0, 49))
        # Smoothed rather than jumping with every Status.json write.
        closing, _eta = bridge._closing(ok(950), now=12.0)
        self.assertEqual(closing, 24.0)
        # Elite repeats the position while nothing moves: stopped, no ETA.
        self.assertEqual(bridge._closing(ok(950), now=13.0)[0], 24.0)
        self.assertEqual(bridge._closing(ok(950), now=15.5), (0.0, None))
        # Moving away is reported as such, never as an ETA.
        bridge._closing(ok(960), now=16.5)
        closing, eta = bridge._closing(ok(975), now=17.5)
        self.assertLess(closing, 0)
        self.assertIsNone(eta)

    def test_closing_speed_resets_for_a_new_fix_or_a_jump(self):
        app = SimpleNamespace(target_lat=1.0, target_lon=2.0, current_body_name="A 3")
        bridge = _bridge(app=app)
        ok = lambda metres: {"state": "OK", "distance_m": metres}
        bridge._closing(ok(1000), now=1.0)
        self.assertIsNotNone(bridge._closing(ok(990), now=2.0)[0])
        app.target_lat = 5.0
        self.assertEqual(bridge._closing(ok(800), now=3.0), (None, None))
        bridge._closing(ok(790), now=4.0)
        # Faster than any glide: a relog or respawn, not one approach.
        self.assertEqual(bridge._closing(ok(40000), now=5.0), (None, None))
        self.assertEqual(bridge._closing({"state": "WAIT_POS"}, now=6.0), (None, None))
        self.assertIsNone(bridge._closing_sample)

    def test_snapshot_reports_vehicle_altitude_only_in_flight_and_short_body(self):
        app = SimpleNamespace(
            target_lat=-12.4, target_lon=88.1, current_body_name="Synuefe XR-H d11-102 A 3",
            current_sys="Synuefe XR-H d11-102", ground_target_label="Return to ship",
            current_latitude=-12.3, current_longitude=88.0, current_heading=90.0,
            current_altitude_m=2140.0, current_landed=False, current_in_srv=False,
            current_on_foot=False, current_in_fighter=False, current_in_taxi=False,
            current_in_multicrew=False,
            _ground_target_solution=lambda: {"state": "OK", "distance_m": 1200.0,
                                             "bearing": 100.0, "heading_delta": 10.0},
            _format_ground_distance=lambda metres: f"{metres / 1000:.2f} km",
        )
        bridge = _bridge({"ground_popup_enabled": True}, app)
        bridge._active = lambda solution=None: True
        bridge._window_payload = lambda solution=None: {}
        bridge._theme = lambda: {}
        navigation = bridge._snapshot()["navigation"]
        self.assertEqual((navigation["mode"], navigation["body_short"]), ("ship", "A 3"))
        self.assertEqual(navigation["altitude_m"], 2140.0)
        app.current_in_srv = True
        self.assertIsNone(bridge._snapshot()["navigation"]["altitude_m"])
        self.assertEqual(bridge._snapshot()["navigation"]["mode"], "srv")
        app.current_in_srv = False
        app.current_landed = True
        self.assertIsNone(bridge._snapshot()["navigation"]["altitude_m"])


class GroundOverlayBrowserTests(unittest.TestCase):
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

    NAVIGATION = {
        "active": True, "state": "OK", "body": "Achenar 3", "body_short": "3",
        "target_label": "Field marker", "target_lat": 0, "target_lon": 0,
        "current_lat": 0, "current_lon": 0,
        "heading": 270, "bearing": 312, "heading_delta": 42,
        "distance_m": 1234.5, "distance_label": "1.23 km",
        "mode": "srv", "landed": False, "altitude_m": None,
        "closing_mps": 27.4, "eta_s": 45,
    }

    def open(self, width=420, height=600):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path.name == "overlay-client.js":
                route.fulfill(
                    content_type="application/javascript",
                    body=path.read_text(encoding="utf-8")
                    + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, "
                    "startPolling: options => { window.__renderGround = options.render; "
                    "window.__groundHeight = options.contentHeight; }};",
                )
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")

        page.route("http://ground.test/**", serve)
        page.goto("http://ground.test/ground/index.html")
        return page

    def render(self, page, scale=1, reduced=True, **overrides):
        payload = {
            "navigation": {**self.NAVIGATION, **overrides},
            "theme": {"accent": "#bb66dd", "yellow": "#e5c95f", "green": "#57b98e"},
            "effects": {"text_scale": scale, "crt": False, "reduced_motion": reduced},
        }
        page.evaluate("payload => __renderGround(payload)", payload)
        return payload

    def read(self, page):
        return page.evaluate("""() => {
          const text = (id) => document.getElementById(id).textContent;
          const target = document.getElementById('tape-target');
          const edge = document.getElementById('tape-edge');
          return {
            state: document.getElementById('ground').dataset.state,
            chip: text('state-label'), distance: text('distance'), turn: text('turn-value'),
            tone: document.getElementById('turn-value').dataset.tone,
            closing: text('closing'), aux: text('aux'), mode: text('mode'),
            body: text('body-name'), heading: text('heading'),
            target: target.hidden ? null : parseFloat(target.style.left),
            edge: edge.hidden ? null : edge.textContent,
            behind: document.getElementById('ground').classList.contains('target-behind'),
            strip: document.getElementById('tape-strip').hidden ? null
              : document.getElementById('tape-strip').style.transform,
          };
        }""")

    def test_guidance_reads_like_the_surface_hud(self):
        page = self.open()
        self.render(page)
        view = self.read(page)
        self.assertEqual((view["distance"], view["turn"], view["chip"]), ("1.23 KM", "RIGHT 42°", "EN ROUTE"))
        self.assertEqual((view["mode"], view["body"], view["heading"]), ("SRV", "3", "270°"))
        # 42° right of the nose on a tape showing ±60°.
        self.assertAlmostEqual(view["target"], 85.0, delta=.01)
        self.assertEqual(view["closing"], "CLOSING 27 M/S · ETA 00:45")
        self.assertEqual(view["aux"], "BRG 312°")
        self.assertEqual(page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"), "#bb66dd")

        self.render(page, heading_delta=-81)
        view = self.read(page)
        self.assertEqual((view["target"], view["edge"], view["turn"]), (None, "◀ 81°", "LEFT 81°"))
        self.render(page, heading_delta=10, distance_m=70, distance_label="70 m")
        view = self.read(page)
        self.assertEqual((view["turn"], view["tone"], view["chip"], view["state"]), ("AHEAD", "ahead", "NEAR FIX", "near"))
        self.render(page, heading_delta=-180)
        view = self.read(page)
        self.assertEqual((view["turn"], view["edge"]), ("TURN AROUND", "◀ 180°"))
        self.assertTrue(view["behind"], "a target behind the beam shows a hollow dot")
        self.render(page, distance_m=12, distance_label="12 m", heading_delta=3)
        view = self.read(page)
        self.assertEqual((view["state"], view["chip"], view["turn"], view["closing"]),
                         ("at-fix", "ON TARGET", "ON TARGET", ""))

    def test_measured_closing_altitude_and_mode(self):
        page = self.open()
        self.render(page, closing_mps=-6.2, eta_s=None)
        self.assertEqual(self.read(page)["closing"], "OPENING 6 M/S")
        self.render(page, closing_mps=0.0, eta_s=None)
        self.assertEqual(self.read(page)["closing"], "HOLDING POSITION")
        # Nothing measured yet: no guess.
        self.render(page, closing_mps=None, eta_s=None)
        self.assertEqual(self.read(page)["closing"], "")
        self.render(page, mode="ship", altitude_m=2140, closing_mps=388, eta_s=4000)
        view = self.read(page)
        self.assertEqual((view["mode"], view["aux"], view["closing"]),
                         ("SHIP", "ALT 2.1 KM", "CLOSING 388 M/S · ETA 1:06:40"))
        self.render(page, mode="ship", landed=True)
        self.assertEqual(self.read(page)["mode"], "SHIP · LANDED")
        self.render(page, mode="foot")
        self.assertEqual(self.read(page)["mode"], "ON FOOT")

    def test_heading_tape_turns_through_north_without_spinning_back(self):
        page = self.open()
        self.render(page, heading=350, heading_delta=0)
        first = self.read(page)["strip"]
        self.render(page, heading=10, heading_delta=0)
        # 350° → 10° is a 20° turn: the strip follows to 370°, the same ticks
        # as 10°, instead of sliding back across the whole compass.
        self.assertEqual(self.read(page)["strip"], f"translateX({-(370 + 180) / 720 * 100:.4f}%)")
        self.assertNotEqual(first, self.read(page)["strip"])
        centre = page.evaluate("""() => {
          const tape = document.getElementById('tape').getBoundingClientRect();
          const middle = tape.left + tape.width / 2;
          const labels = [...document.querySelectorAll('#tape-strip .tick.major > span')];
          const nearest = labels.map((label) => {
            const box = label.getBoundingClientRect();
            return [Math.abs(box.left + box.width / 2 - middle), label.textContent];
          }).sort((a, b) => a[0] - b[0])[0];
          return nearest[1];
        }""")
        self.assertEqual(centre, "015", "the label nearest the caret belongs to 10°")

    def test_standby_and_missing_heading_never_invent_guidance(self):
        page = self.open()
        self.render(page, heading=None, heading_delta=None)
        view = self.read(page)
        self.assertEqual((view["strip"], view["heading"], view["turn"], view["target"], view["edge"]),
                         (None, "HDG N/A", "HEADING N/A", None, None))
        self.assertEqual(view["aux"], "BRG 312°", "the bearing is still true without a heading")
        self.render(page, active=False, state="WAIT_BODY", distance_m=100, distance_label="100 m")
        view = self.read(page)
        self.assertEqual((view["chip"], view["distance"], view["turn"], view["closing"]),
                         ("AWAITING TARGET BODY", "—", "STANDBY", ""))

    def test_reduced_motion_stops_the_arrival_pulse(self):
        page = self.open()
        self.render(page, reduced=False, distance_m=12, distance_label="12 m")
        self.assertTrue(page.evaluate("document.getAnimations().length > 0"))
        self.render(page, reduced=True, distance_m=12, distance_label="12 m")
        self.assertEqual(page.evaluate("document.getAnimations().length"), 0)

    def test_every_text_size_fits_its_scaled_window(self):
        for scale in (.75, 1, 1.5, 2):
            with self.subTest(scale=scale):
                width = round(420 * scale)
                page = self.open(width, 800)
                payload = self.render(page, scale=scale, target_label="Bacterium Tela · sample 2 of 3",
                                      closing_mps=388, eta_s=4000, mode="ship", altitude_m=21400,
                                      heading_delta=-81)
                height = page.evaluate("__groundHeight()")
                self.assertLessEqual(height, 400 * scale)
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("payload => __renderGround(payload)", payload)
                geometry = page.evaluate("""() => {
                  const root = document.querySelector('#ground');
                  const outer = root.getBoundingClientRect();
                  const bands = [...root.querySelectorAll(':scope > header, :scope > div:not(.corners):not(.scanlines), :scope > section, :scope > footer')];
                  const values = [...root.querySelectorAll('#target-label, #distance, #turn-value, #closing, #target, #coordinates, #aux, #body-name')];
                  return {
                    width: outer.width, height: outer.height,
                    bandsFit: bands.every((el) => el.getBoundingClientRect().bottom <= outer.bottom + 1),
                    clipped: values.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.id),
                    scrolls: document.documentElement.scrollHeight > innerHeight + 1
                      || document.documentElement.scrollWidth > innerWidth + 1,
                  };
                }""")
                self.assertAlmostEqual(geometry["width"], width, delta=1)
                self.assertLess(abs(height - geometry["height"]), 2)
                self.assertTrue(geometry["bandsFit"], geometry)
                self.assertEqual(geometry["clipped"], [], geometry)
                self.assertFalse(geometry["scrolls"], geometry)

        # A larger native host must not feed its previous height back into
        # the intrinsic browser measurement on the next poll.
        page = self.open()
        payload = self.render(page)
        intrinsic = page.evaluate("__groundHeight()")
        page.set_viewport_size({"width": 420, "height": 390})
        page.evaluate("payload => __renderGround(payload)", payload)
        self.assertEqual(page.evaluate("__groundHeight()"), intrinsic)


if __name__ == "__main__":
    unittest.main()
