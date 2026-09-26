"""Browser checks for the profile-local Explore Return Later board."""

import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from tests.test_dashboard_overview_visuals import overview_state


WEB = Path(__file__).resolve().parents[1] / "web"


class ReturnLaterVisualTests(unittest.TestCase):
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1380, "height": 850})
        self.commands = []
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                route.fulfill(content_type="application/json", body='{"closing":true}')
                return
            if path == "/api/command":
                self.commands.append(route.request.post_data_json)
                route.fulfill(content_type="application/json", body='{"accepted":true}')
                return
            if path == "/api/snapshot":
                route.fulfill(content_type="application/json", body=json.dumps(overview_state()))
                return
            file = WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                source = file.read_text(encoding="utf-8")
                source += """
                  window.__returnLaterHarness = {
                    render(data) {
                      document.body.classList.add('ready');
                      document.getElementById('boot').hidden = true;
                      document.getElementById('app').setAttribute('aria-hidden', 'false');
                      document.querySelectorAll('.page').forEach(node =>
                        node.classList.toggle('active', node.dataset.pageName === 'explore'));
                      currentPage = 'explore';
                      renderExploreWorkspace(data, EXPLORE_WORKSPACE_UI);
                    }
                  };
                """
                route.fulfill(content_type="application/javascript", body=source)
            elif file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://return-later.test/**", serve)
        self.page.goto("http://return-later.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__returnLaterHarness)")

    def tearDown(self):
        self.page.close()

    def render(self, entries):
        self.page.evaluate("entries => window.__returnLaterHarness.render({current: 'TEST SYSTEM', return_later: {entries}})", entries)
        # Return Later lives in the Explore page's Prospects view.
        self.page.locator("#explore-tab-prospects").click()

    def test_journal_evidence_and_actions_are_accessible(self):
        self.render([
            {"id": "a:2", "system": "SYNUEFE AA-A H1", "body": "SYNUEFE AA-A H1 2",
             "reasons": ["Biological signals: 1/3 samples", "Pinned survey target"],
             "last_visited": "2026-09-25T10:20:00Z", "source": "journal + pin"},
            {"id": "a:fss", "system": "SYNUEFE AA-A H1", "body": "",
             "reasons": ["4 FSS bodies unresolved"], "last_visited": "2026-09-25T10:20:00Z",
             "source": "journal"},
        ])
        board = self.page.locator(".return-later-board")
        self.assertTrue(board.is_visible())
        self.assertIn("2 OPEN", board.locator("header > b").inner_text())
        self.assertEqual(board.locator(".return-later-entry").count(), 2)
        self.assertIn("Biological signals", board.inner_text())
        self.assertIn("SYSTEM SURVEY", board.inner_text())
        self.assertTrue(board.locator('[data-ws-op="return_later_waypoint"]').first.is_visible())
        for operation, target_id, position in (
            ("return_later_waypoint", "a:2", "first"),
            ("return_later_copy", "a:fss", "last"),
            ("return_later_dismiss", "a:fss", "last"),
        ):
            button = getattr(board.locator(f'[data-ws-op="{operation}"]'), position)
            with self.page.expect_request(lambda request: urlsplit(request.url).path == "/api/command"
                                          and request.method == "POST") as request:
                button.click()
            self.assertEqual(request.value.post_data_json["operation"], operation)
            self.assertEqual(request.value.post_data_json["id"], target_id)
        self.assertFalse(self.errors, self.errors)

    def test_large_board_stays_bounded_and_keeps_scroll_on_refresh(self):
        entries = [{"id": f"target:{index}", "system": f"TEST SYSTEM {index}",
                    "body": f"TEST SYSTEM {index} 1", "reasons": ["DSS not mapped"],
                    "source": "journal"} for index in range(35)]
        self.render(entries)
        board = self.page.locator(".return-later-entries")
        self.assertEqual(board.locator(".return-later-entry").count(), 35)
        self.assertTrue(board.evaluate("node => node.scrollHeight > node.clientHeight"))
        board.evaluate("node => node.scrollTop = 240")
        self.render(entries)
        self.assertGreater(board.evaluate("node => node.scrollTop"), 0)
        self.page.set_viewport_size({"width": 590, "height": 700})
        self.assertFalse(self.page.locator(".return-later-board").evaluate(
            "node => node.scrollWidth > node.clientWidth + 1"))
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
