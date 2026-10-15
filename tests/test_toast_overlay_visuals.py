"""Real browser checks for the notification and achievement cards (rebuilt in
5.5.4: one page for both overlays, every size growing with the text size)."""

from pathlib import Path
import time
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"


class ToastOverlayVisualTests(unittest.TestCase):
    def test_cards_fit_and_keep_their_lifecycle(self):
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
                page = browser.new_page(viewport={"width": 400, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve(route):
                    path = WEB / urlsplit(route.request.url).path.lstrip("/")
                    if path.name == "overlay-client.js":
                        route.fulfill(
                            content_type="application/javascript",
                            body=path.read_text(encoding="utf-8")
                            + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, "
                            "startPolling: options => { window.__renderToast = options.render; "
                            "window.__measure = options.contentHeight; }};",
                        )
                    elif path.is_file():
                        route.fulfill(path=str(path))
                    else:
                        route.fulfill(status=404, body="")

                page.route("http://toast.test/**", serve)
                page.goto("http://toast.test/toast/index.html")
                expires = time.time() + 30
                items = [
                    {"id": 1, "kind": "notice", "severity": "info", "title": "NEW SIGNAL",
                     "message": "Discovery logged in the current system", "expire_at": expires},
                    {"id": 2, "kind": "notice", "severity": "fail", "title": "UNDER ATTACK",
                     "message": "Ship shields are taking damage near the planetary ring",
                     "expire_at": expires},
                    {"id": 3, "kind": "achievement", "icon": "★", "title": "Star Hopper",
                     "message": "Complete one hundred hyperspace jumps", "expire_at": expires,
                     "meta": {"points": 2000, "category": "Exploration", "tier": "Gold"}},
                ]
                for scale in (1, 1.5, 2):
                    page.set_viewport_size({"width": round(400 * scale), "height": 900})
                    page.evaluate("payload => __renderToast(payload)", {
                        "effects": {"text_scale": scale, "crt": True}, "notifications": items, "design_width": 400,
                    })
                    geometry = page.evaluate("""() => [...document.querySelectorAll('.card')].map(card => {
                        const box = card.getBoundingClientRect();
                        const copy = card.querySelector('.card-copy').getBoundingClientRect();
                        const cut = [...card.querySelectorAll('strong, p, b, small, span')]
                          .some(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1);
                        return {width: box.width, top: box.top, bottom: box.bottom,
                                fits: copy.top >= box.top - .5 && copy.bottom <= box.bottom + .5 && !cut};
                    })""")
                    self.assertTrue(all(row["fits"] for row in geometry), (scale, geometry))
                    self.assertTrue(all(abs(row["width"] - 400 * scale) < 1 for row in geometry), (scale, geometry))
                    gaps = [round(later["top"] - earlier["bottom"], 1) for earlier, later in zip(geometry, geometry[1:])]
                    self.assertTrue(all(abs(gap - 8 * scale) < 1 for gap in gaps), (scale, gaps))
                    self.assertGreaterEqual(page.evaluate("__measure()"), geometry[-1]["bottom"] - 1)
                    self.assertEqual(page.locator(".achievement-head small").inner_text(), "EXPLORATION · GOLD")
                    self.assertEqual(page.locator(".achievement-points").inner_text(), "+2,000 POINTS")
                    self.assertEqual(page.locator(".notice.fail .card-head b").inner_text(), "CRITICAL")

                page.evaluate("""items => {
                  const first = document.querySelector('[data-notification-id="1"]');
                  const milestone = document.querySelector('[data-notification-id="3"]');
                  __renderToast({effects: {text_scale: 2}, notifications: [...items, {
                    id: 4, kind: 'notice', severity: 'warn', title: 'LOW FUEL',
                    message: 'Main tank at 12%', expire_at: items[0].expire_at,
                  }]});
                  if (document.querySelector('[data-notification-id="1"]') !== first
                    || document.querySelector('[data-notification-id="3"]') !== milestone)
                    throw Error('Existing cards were rebuilt when a notification arrived');
                  __renderToast({effects: {text_scale: 2}, notifications: items.slice(1)});
                  if (document.querySelector('[data-notification-id="1"]')
                    || document.querySelector('[data-notification-id="3"]') !== milestone)
                    throw Error('Dismissal did not preserve the remaining cards');
                }""", items)

                themed = items[:2] + [
                    {"id": 4, "kind": "notice", "severity": "warn", "title": "LOW FUEL", "expire_at": expires},
                    {"id": 5, "kind": "notice", "severity": "success", "title": "SCAN COMPLETE", "expire_at": expires},
                    items[2],
                ]
                page.set_viewport_size({"width": 400, "height": 900})
                for theme, expected in (
                    ({"accent": "#ff4fd8", "orange": "#00e5ff", "red": "#ff5c7a", "green": "#54e39a", "yellow": "#f5c76d"},
                     {"accent": "rgb(255, 79, 216)", "orange": "rgb(0, 229, 255)", "red": "rgb(255, 92, 122)",
                      "green": "rgb(84, 227, 154)", "yellow": "rgb(245, 199, 109)"}),
                    ({"accent": "#00e88a", "orange": "#b8e04d", "red": "#ff6b70", "green": "#7ddb6f", "yellow": "#e0d84d"},
                     {"accent": "rgb(0, 232, 138)", "orange": "rgb(184, 224, 77)", "red": "rgb(255, 107, 112)",
                      "green": "rgb(125, 219, 111)", "yellow": "rgb(224, 216, 77)"}),
                ):
                    page.evaluate("payload => __renderToast(payload)", {
                        "theme": theme, "effects": {"text_scale": 1, "crt": True}, "notifications": themed,
                    })
                    colors = page.evaluate("""() => {
                      const color = selector => getComputedStyle(document.querySelector(selector)).color;
                      return {info: color('.notice.info .notice-mark'), warn: color('.notice.warn .notice-mark'),
                              fail: color('.notice.fail .notice-mark'), success: color('.notice.success .notice-mark'),
                              badge: color('.achievement-badge'),
                              points: getComputedStyle(document.querySelector('.achievement-points')).backgroundColor};
                    }""")
                    self.assertEqual(colors, {"info": expected["accent"], "warn": expected["orange"],
                                              "fail": expected["red"], "success": expected["green"],
                                              "badge": expected["yellow"], "points": expected["yellow"]})

                page.evaluate("payload => __renderToast(payload)", {
                    "effects": {"text_scale": 2, "reduced_motion": True, "crt": False}, "notifications": items,
                })
                self.assertEqual(page.locator(".card-life").first.evaluate("element => getComputedStyle(element).display"), "none")
                self.assertEqual(page.locator(".card-scan").first.evaluate("element => getComputedStyle(element).display"), "none")
                self.assertEqual(page.evaluate("document.getAnimations().length"), 0)
                page.emulate_media(reduced_motion="reduce")
                page.evaluate("payload => __renderToast(payload)", {
                    "effects": {"text_scale": 1, "reduced_motion": False, "crt": True}, "notifications": items,
                })
                self.assertEqual(page.evaluate("document.getAnimations().length"), 0)
                self.assertEqual(errors, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
