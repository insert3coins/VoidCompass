"""Headless layout checks for the compact Planet Materials overlay."""

from pathlib import Path
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"


class PlanetMaterialsOverlayVisualTests(unittest.TestCase):
    def test_compact_bounded_panel_pages_all_sites_with_target_pinned(self):
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
                page = browser.new_page(viewport={"width": 440, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve(route):
                    path = urlsplit(route.request.url).path
                    if path == "/assets/overlay-client.js":
                        route.fulfill(content_type="application/javascript", body="""
                          window.VoidCompassOverlay = {
                            applyTheme(root, theme, effects) {
                              document.documentElement.style.setProperty('--scale',
                                String(effects.text_scale || 1));
                              document.documentElement.style.setProperty('--accent',
                                theme.accent || '#00d1ff');
                              root.classList.toggle('reduced-motion', !!effects.reduced_motion);
                            },
                            startPolling(options) { window.__render = options.render;
                              window.__contentHeight = options.contentHeight; }
                          };
                        """)
                        return
                    file = WEB / path.lstrip("/")
                    if file.is_file():
                        route.fulfill(path=str(file))
                    else:
                        route.fulfill(status=404, body="")

                page.route("http://planet.test/**", serve)
                page.goto("http://planet.test/planet-materials-overlay/index.html")
                model = {
                    "system": "Sol", "body": "Sol Moon", "short_body": "Moon",
                    "on_planet": True, "rhino_active": True,
                    "details": {"class": "Rocky body", "landable": True,
                                "gravity": .12, "temperature": 185,
                                "volcanism": "Silicate vapour geysers",
                                "ground": "Rocky World [silicate]", "ground_sample": 12,
                                "mining_locations": 5},
                    "materials": [{"name": f"Material {i}", "percent": 9.5 - i,
                                   "rare": i == 0} for i in range(8)],
                    "best_materials": [{"name": f"Estimate {i}", "percent": 4.2 - i,
                                        "median": 25000 + i * 1000} for i in range(3)],
                    "sites": [{"id": i, "name": f"Surface site {i}",
                               "materials": ["Iron", "Nickel", "Ruby", "Sapphire"],
                               "distance_m": None if i == 12 else i * 1000}
                              for i in range(1, 13)],
                    "site_count": 12,
                    "target": {"active": True, "site_id": 12, "label": "Surface site 12"},
                    "position": {"latitude": 10.2, "longitude": -15.3, "heading": 27},
                }

                def render(scale):
                    page.evaluate("([model, scale]) => __render({planet_materials: model, "
                                  "theme: {accent: '#b860f1'}, "
                                  "effects: {text_scale: scale, reduced_motion: true}})",
                                  [model, scale])

                def geometry():
                    return page.evaluate("""() => {
                      const panel = document.querySelector('#panel').getBoundingClientRect();
                      const parts = [...document.querySelectorAll('#panel > header, #panel > section, #panel > footer')];
                      return {
                        width: panel.width, height: __contentHeight(),
                        partsFit: parts.every(part => {const box = part.getBoundingClientRect();
                          return box.top >= panel.top - 1 && box.bottom <= panel.bottom + 1
                            && box.left >= panel.left - 1 && box.right <= panel.right + 1;}),
                        horizontalOverflow: document.documentElement.scrollWidth > 440,
                        accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
                        parts: parts.map(part => [part.className || part.tagName, Math.round(part.getBoundingClientRect().height)]),
                      };
                    }""")

                render(1)
                normal = geometry()
                self.assertEqual(normal["width"], 440)
                self.assertLessEqual(normal["height"], 520, normal)
                self.assertTrue(normal["partsFit"], normal)
                self.assertFalse(normal["horizontalOverflow"], normal)
                self.assertEqual(normal["accent"], "#b860f1")
                self.assertEqual(page.locator("#materials article").count(), 8)
                self.assertEqual(page.locator("#best-materials article").count(), 3)
                self.assertIn("185 K", page.locator("#facts").inner_text())
                self.assertIn("Silicate vapour geysers", page.locator("#facts").inner_text())
                self.assertEqual(page.locator(".target-site").get_attribute("data-site-id"), "12")
                self.assertIn("DISTANCE —", page.locator(".target-site").inner_text())
                self.assertEqual(page.evaluate("VoidCompassPlanetMaterials.getState().pages"), 6)
                seen = set()
                for _ in range(6):
                    seen.update(page.locator("#site-list article").evaluate_all(
                        "rows => rows.map(row => Number(row.dataset.siteId))"))
                    page.evaluate("VoidCompassPlanetMaterials.nextSitePage()")
                self.assertEqual(seen, set(range(1, 13)))

                page.evaluate("VoidCompassPlanetMaterials.nextSitePage()")
                self.assertEqual(page.evaluate("VoidCompassPlanetMaterials.getState().page"), 1)
                model["sites"].reverse()  # A moving commander can change distance order.
                render(1)
                self.assertEqual(page.evaluate("VoidCompassPlanetMaterials.getState().page"), 1)
                self.assertEqual(page.locator(".target-site").get_attribute("data-site-id"), "12")

                render(2)
                large = geometry()
                self.assertLessEqual(large["height"], 680, large)
                self.assertTrue(large["partsFit"], large)
                self.assertFalse(large["horizontalOverflow"], large)
                self.assertEqual(page.evaluate("VoidCompassPlanetMaterials.getState().pages"), 11)
                self.assertEqual(page.locator(".target-site").count(), 1)
                self.assertFalse(errors, errors)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
