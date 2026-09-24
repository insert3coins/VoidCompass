"""Ground waypoint overlay state and real-browser layout checks."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

from voidcompass.core.overlay_registry import DEFAULT_SIZES
from voidcompass.overlays.html_ground_overlay import HtmlGroundOverlayBridge


WEB = Path(__file__).resolve().parents[1] / "web"


class GroundOverlayBridgeTests(unittest.TestCase):
    def test_browser_height_resizes_host_and_studio_footprint(self):
        self.assertEqual(DEFAULT_SIZES["ground_popup"], (420, 208))
        bridge = object.__new__(HtmlGroundOverlayBridge)
        bridge.overlay_id = "ground"
        bridge.x_key = "ground_popup_x"
        bridge.y_key = "ground_popup_y"
        bridge.enabled_key = "ground_popup_enabled"
        bridge.config = {
            "ground_popup_x": 25, "ground_popup_y": 30,
            "ground_popup_enabled": True,
        }
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


class GroundOverlayBrowserTests(unittest.TestCase):
    def test_guidance_states_theme_and_scaled_content_fit(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f"Playwright Chromium is unavailable: {exc}")
            try:
                page = browser.new_page(viewport={"width": 420, "height": 600})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve(route):
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
                navigation = {
                    "active": True, "state": "OK", "body": "Achenar 3",
                    "target_label": "Field marker", "target_lat": 0, "target_lon": 0,
                    "current_lat": 0, "current_lon": 0,
                    "heading": 270, "bearing": 312, "heading_delta": 42,
                    "distance_m": 1234.5, "distance_label": "1.23 km",
                }

                def render(**overrides):
                    payload = {
                        "navigation": {**navigation, **overrides},
                        "theme": {"accent": "#bb66dd", "yellow": "#e5c95f", "green": "#57b98e"},
                        "effects": {"text_scale": 1, "crt": False, "reduced_motion": True},
                    }
                    page.evaluate("payload => __renderGround(payload)", payload)
                    return payload

                render()
                self.assertEqual(page.locator("#distance").inner_text(), "1.23 km")
                self.assertEqual(page.locator("#turn-value").inner_text(), "RIGHT 42°")
                self.assertEqual(page.locator("#target").inner_text(), "0.00000, 0.00000")
                self.assertEqual(page.locator("#bearing").inner_text(), "270° / 312°")
                self.assertEqual(page.locator("#ground").get_attribute("data-state"), "tracking")
                self.assertEqual(page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"), "#bb66dd")
                self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('.dial-ring')).animationName"), "none")

                render(heading=0, bearing=180, heading_delta=-180)
                self.assertEqual(page.locator("#turn-value").inner_text(), "LEFT 180°")
                self.assertEqual(page.evaluate("document.querySelector('#ground').style.getPropertyValue('--turn-position')"), "0%")
                render(heading=0, bearing=180, heading_delta=180)
                self.assertEqual(page.locator("#turn-value").inner_text(), "RIGHT 180°")
                self.assertEqual(page.evaluate("document.querySelector('#ground').style.getPropertyValue('--turn-position')"), "100%")
                render(distance_m=70, distance_label="70 m", heading_delta=10)
                self.assertEqual(page.locator("#ground").get_attribute("data-state"), "near")
                self.assertEqual(page.locator("#turn-value").inner_text(), "AHEAD")
                self.assertEqual(page.locator("#direction").inner_text(), "TARGET STRAIGHT AHEAD")
                render(distance_m=0, distance_label="0 m")
                self.assertEqual(page.locator("#state-label").inner_text(), "WITHIN 25 M")
                render(distance_m=None, distance_label="---", heading=None, heading_delta=None)
                self.assertEqual(page.locator("#ground").get_attribute("data-state"), "range-unavailable")
                self.assertEqual(page.locator("#distance").inner_text(), "—")
                self.assertEqual(page.locator("#turn-value").inner_text(), "HEADING N/A")
                self.assertTrue(page.locator("#ground").evaluate("el => el.classList.contains('heading-unavailable')"))
                render(active=False, state="WAIT_BODY", distance_m=100, distance_label="100 m")
                self.assertEqual(page.locator("#state-label").inner_text(), "AWAITING TARGET BODY")
                self.assertEqual(page.locator("#distance").inner_text(), "—")

                for scale in (.75, 1, 1.5, 2):
                    payload = render(distance_m=1234.5, distance_label="1.23 km")
                    payload["effects"]["text_scale"] = scale
                    page.evaluate("payload => __renderGround(payload)", payload)
                    height = page.evaluate("__groundHeight()")
                    self.assertLessEqual(height, 400)
                    page.set_viewport_size({"width": 420, "height": height})
                    geometry = page.evaluate("""() => {
                      const root = document.querySelector('#ground');
                      const outer = root.getBoundingClientRect();
                      const bands = [...root.querySelectorAll(':scope > header, :scope > section, :scope > footer')];
                      const values = [...root.querySelectorAll('#target, #coordinates, #bearing, #distance, #turn-value')];
                      return {
                        height: outer.height, scroll: root.scrollHeight,
                        bandsFit: bands.every(el => el.getBoundingClientRect().bottom <= outer.bottom + 1),
                        valuesFit: values.every(el => el.scrollWidth <= el.clientWidth + 1),
                        hasScroll: document.documentElement.scrollHeight > innerHeight + 1,
                      };
                    }""")
                    self.assertGreaterEqual(height - geometry["height"], 0)
                    self.assertLess(height - geometry["height"], 2)
                    self.assertTrue(geometry["bandsFit"], geometry)
                    self.assertTrue(geometry["valuesFit"], geometry)
                    self.assertFalse(geometry["hasScroll"], geometry)
                    self.assertFalse(errors, errors)

                # A larger native host must not feed its previous height back
                # into the intrinsic browser measurement on the next poll.
                payload = render()
                intrinsic_height = page.evaluate("__groundHeight()")
                page.set_viewport_size({"width": 420, "height": 390})
                page.evaluate("payload => __renderGround(payload)", payload)
                self.assertEqual(page.evaluate("__groundHeight()"), intrinsic_height)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
