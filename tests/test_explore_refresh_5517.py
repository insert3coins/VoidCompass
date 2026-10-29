"""5.5.17: Explore & Survey kept redrawing and wouldn't scroll. Its workspace
carries the archive, whose science read reports its age in tenths of a
second: every refresh looked new, so the orrery was rebuilt each time. That
age, like the session clock, no longer counts as a change. (5.6.9: the orrery
became the System Map tab, so the prospects panel stands in as the witness.)"""

import copy
import unittest
from pathlib import Path

from tests.test_dashboard_overview_visuals import overview_state
from tests.test_exploration_archive_visuals import archive_data
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def explore_data(age):
    archive = archive_data()
    archive["science_status"] = {"state": "ready", "age_seconds": age}
    return {"current": "Sol", "destination": "", "nav_route": [], "waypoints": [], "next_waypoint": "",
            "return_later": {"entries": [], "count": 0},
            "cartography": {"system": "Sol", "target": None, "orrery": {"bodies": [], "stars": 1, "planets": 0},
                            "queue": {}, "resources": {}},
            "scout": {"results": [], "modes": [], "audit": {}, "codex": {}}, "plotter": {}, "archive": archive}


class ExploreRefreshTests(unittest.TestCase):
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

    def test_the_science_age_alone_does_not_redraw(self):
        server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images",
                                     command_callback=lambda payload: True)
        self.addCleanup(server.stop)
        state = overview_state()
        server.publish(state)
        context = self.browser.new_context(viewport={"width": 1600, "height": 900}, bypass_csp=True)
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server.url)
        page.wait_for_function("document.body.classList.contains('ready')", timeout=15000)
        page.locator('.nav-item[data-page="explore"]').click()
        published = copy.deepcopy(state)
        published["workspace"] = {"page": "explore", "ready": True, "data": explore_data(0.0)}
        server.publish(published)
        page.wait_for_selector("#explore-prospects .explore-card", state="attached", timeout=10000)
        page.evaluate("""() => {
          window.__rebuilt = 0;
          new MutationObserver(() => { window.__rebuilt += 1; })
            .observe(document.getElementById('explore-prospects'), {childList: true});
        }""")
        for age in (1.2, 2.4, 3.6):
            published = copy.deepcopy(published)
            published["workspace"]["data"] = explore_data(age)
            server.publish(published)
            page.wait_for_timeout(600)
        self.assertEqual(page.evaluate("window.__rebuilt"), 0, "Explore stays put while only the age changes")
        published = copy.deepcopy(published)
        published["workspace"]["data"]["return_later"] = {"count": 1, "entries": [
            {"id": "r:1", "system": "Colonia", "body": "", "reasons": ["4 FSS bodies unresolved"],
             "last_visited": "2026-09-25T10:20:00Z", "source": "journal"}]}
        server.publish(published)
        page.wait_for_timeout(800)
        self.assertGreater(page.evaluate("window.__rebuilt"), 0, "a real change still redraws")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
