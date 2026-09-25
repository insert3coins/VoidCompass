"""Browser regressions for the journal-backed Exploration Archive renderer."""

from pathlib import Path
import json
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web" / "dashboard"


def archive_data(status="ready"):
    return {
        "current": {"elapsed": "01:14:09", "distance": 63.2, "jumps": 3, "systems": 4},
        "sessions": [
            {"started": "2026-09-25T10:00:00Z", "ended": "2026-09-25T11:00:00Z",
             "start_system": "Sol", "end_system": "Achenar", "jumps": 5, "distance": 120.4,
             "fss": 3, "dss": 2, "bio": 1, "codex": 1},
            {"started": "2026-09-24T12:00:00Z", "ended": "",
             "start_system": "Col 285", "end_system": "SYNUEFE AA-A H1", "jumps": 7,
             "distance": 180.6, "fss": 4, "dss": 3, "bio": 2, "codex": 0},
            {"started": "2026-09-23T09:00:00Z", "ended": "2026-09-23T10:00:00Z",
             "start_system": "Shinrarta Dezhra", "end_system": "Sol", "jumps": 1,
             "distance": 4.2, "fss": 0, "dss": 0, "bio": 0, "codex": 0},
        ],
        "science": {
            "systems": 7, "bodies": 12, "biological_bodies": 4,
            "species_total": 2, "analyses": 3, "valuable": 5, "terraformable": 1,
            "species": [
                {"name": "Bacterium Vesicula", "genus": "Bacterium", "analyses": 2,
                 "worlds": 2, "systems": 2, "value": 1200000},
                {"name": "Fonticulua Campestris", "genus": "Fonticulua", "analyses": 1,
                 "worlds": 1, "systems": 1, "value": 2500000},
            ],
            "atmospheres": [{"label": "Thin CO2", "count": 3}],
            "gravity": [{"label": "LOW 0.15–0.5G", "count": 2}],
            "body_classes": [{"label": "Rocky body", "count": 6}],
            "star_classes": [{"label": "K", "count": 4}],
        },
        "passport": {
            "visited": 2, "total": 3, "percent": 66.7, "systems": 7,
            "distance": 305.2, "biology": 3,
            "rows": [
                {"id": 1, "name": "Inner Orion Spur", "visited": True, "systems": 4,
                 "distance": 130.2, "fss": 3, "dss": 2, "biology": 1, "codex": 0,
                 "last_system": "Sol", "last_visit": "2026-09-25T10:00:00Z"},
                {"id": 2, "name": "Outer Orion Spur", "visited": False},
                {"id": 3, "name": "Perseus Arm", "visited": True, "systems": 3,
                 "distance": 175, "fss": 2, "dss": 1, "biology": 2, "codex": 1,
                 "last_system": "Achenar", "last_visit": "2026-09-24T12:00:00Z"},
            ],
        },
        "science_status": {"state": status, "age_seconds": 0},
    }


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/dashboard/styles.css"><link rel="stylesheet" href="/dashboard/archive.css"></head><body><main style="max-width:1500px;padding:20px;margin:auto"><div id="analytics-workspace" class="workspace-shell loading-panel"></div></main><script type="module">
import {renderExplorationArchive} from '/dashboard/archive.js';
const number = (value, fallback=0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const numeric = (value, digits=0) => Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined, {minimumFractionDigits:digits,maximumFractionDigits:digits}) : '—';
const credits = (value) => Number.isFinite(Number(value)) ? `${Math.round(Number(value)).toLocaleString()} CR` : '—';
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
window.archiveRender = (data, analyticsView='trends', profileKey) => renderExplorationArchive(data, {byId:id=>document.getElementById(id), number, numeric, credits, escapeHtml, analyticsView, profileKey});
</script></body></html>"""


class ExplorationArchiveVisualTests(unittest.TestCase):
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
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 900})
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/archive-test":
                route.fulfill(content_type="text/html", body=HTML)
                return
            file = WEB.parent / path.lstrip("/")
            if file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://archive.test/**", serve)
        self.page.goto("http://archive.test/archive-test")
        self.page.wait_for_function("Boolean(window.archiveRender)")

    def tearDown(self):
        self.page.close()

    def render(self, data, view="trends", profile_key=None):
        self.page.evaluate("([data, view, profileKey]) => window.archiveRender(data, view, profileKey)",
                           [data, view, profile_key])

    def test_flight_dossier_uses_retained_sample_and_keeps_log_and_atlas_links(self):
        self.render(archive_data())
        self.assertIn("EXPLORATION ARCHIVE", self.page.locator(".archive-masthead h2").inner_text().upper())
        self.assertIn("not lifetime career totals", self.page.locator("#archive-trends").inner_text())
        self.assertEqual(self.page.locator(".archive-flight-table tbody tr").count(), 3)
        self.assertEqual(self.page.locator(".archive-chart-card").count(), 2)
        self.assertEqual(self.page.locator(".archive-chart-card:first-child .archive-chart > i").count(), 3)
        self.assertIn("305.2", self.page.locator("#archive-trends .archive-metrics").inner_text())
        self.assertIn("3", self.page.locator("#archive-trends .archive-metrics").inner_text())
        self.assertEqual(self.page.locator(".archive-masthead-actions [data-page='chronicle']").count(), 1)
        self.assertEqual(self.page.locator(".archive-masthead-actions [data-page='map']").count(), 1)
        self.assertIn("END NOT RECORDED", self.page.locator(".archive-flight-table").inner_text())
        self.assertEqual(self.page.locator("[role='tab']").count(), 3)
        self.assertEqual(self.page.locator("[role='tabpanel']:visible").count(), 1)
        self.assertFalse(self.errors, self.errors)

    def test_search_filters_visible_ledger_and_survives_refresh(self):
        data = archive_data()
        self.render(data)
        self.page.locator("#archive-flight-search").fill("achenar")
        self.assertEqual(self.page.locator(".archive-flight-table tbody tr:visible").count(), 1)
        self.assertIn("1 OF 3", self.page.locator("#archive-ledger-count").inner_text())
        self.page.locator("#archive-flight-search").evaluate("node => node.setSelectionRange(2, 5)")
        self.render(data)
        self.assertEqual(self.page.locator("#archive-flight-search").input_value(), "achenar")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "archive-flight-search")
        self.assertEqual(self.page.locator("#archive-flight-search").evaluate(
            "node => [node.selectionStart, node.selectionEnd]"), [2, 5])
        self.assertEqual(self.page.locator(".archive-flight-table tbody tr:visible").count(), 1)
        self.page.locator("#archive-flight-search").fill("unrecorded destination")
        self.assertEqual(self.page.locator(".archive-flight-table tbody tr:visible").count(), 0)
        self.assertTrue(self.page.locator("#archive-search-empty").is_visible())
        self.render(data, profile_key="another-commander")
        self.assertEqual(self.page.locator("#archive-flight-search").input_value(), "")
        self.assertEqual(self.page.locator(".archive-flight-table tbody tr:visible").count(), 3)
        self.assertFalse(self.errors, self.errors)

    def test_science_and_passport_expose_evidence_and_bound_large_lists(self):
        data = archive_data()
        self.render(data, "science")
        self.assertTrue(self.page.locator("#archive-science").is_visible())
        self.assertIn("base values are not earnings", self.page.locator("#archive-science").inner_text())
        self.assertEqual(self.page.locator(".archive-species-table tbody tr").count(), 2)
        self.assertEqual(self.page.locator(".archive-distribution").count(), 4)
        self.assertIn("1,200,000 CR", self.page.locator(".archive-species-table").inner_text())
        self.render(data, "passport")
        self.assertTrue(self.page.locator("#archive-passport").is_visible())
        self.assertEqual(self.page.locator(".archive-region").count(), 3)
        self.assertEqual(self.page.locator(".archive-region.visited").count(), 2)
        self.assertIn("PERSEUS ARM", self.page.locator(".archive-region:nth-child(2)").inner_text().upper())
        self.assertLessEqual(self.page.locator(".archive-regions").evaluate("node => node.getBoundingClientRect().height"), 652)
        self.assertEqual(self.page.locator("#archive-passport [data-page='map']").count(), 1)
        self.assertFalse(self.errors, self.errors)

    def test_pending_index_does_not_assert_zero_and_stale_index_is_labelled(self):
        loading = archive_data("loading")
        loading["science"] = {}
        loading["passport"] = {}
        self.render(loading, "science")
        self.assertIn("INDEX LOADING", self.page.locator("#archive-science .archive-status").inner_text())
        self.assertEqual(self.page.locator("#archive-science .archive-metric").count(), 0)
        self.assertIn("—", self.page.locator(".archive-index-strip").inner_text())
        self.render(loading, "passport")
        self.assertEqual(self.page.locator(".archive-region").count(), 0)
        self.assertIn("INDEX PENDING", self.page.locator("#archive-passport .archive-section-head").inner_text())
        self.render(archive_data("stale"), "science")
        self.assertIn("CACHED INDEX", self.page.locator("#archive-science .archive-status").inner_text())
        self.assertEqual(self.page.locator(".archive-species-table tbody tr").count(), 2)
        self.assertFalse(self.errors, self.errors)

    def test_retained_window_and_full_passport_remain_scrollable(self):
        data = archive_data()
        data["sessions"] = [
            {**data["sessions"][index % 3], "started": f"2026-09-{(index % 25) + 1:02d}T10:00:00Z"}
            for index in range(120)
        ]
        data["passport"]["rows"] += [
            {"id": index, "name": f"Region {index}", "visited": False}
            for index in range(4, 43)
        ]
        self.render(data)
        self.assertEqual(self.page.locator(".archive-flight-table tbody tr").count(), 120)
        self.assertEqual(self.page.locator(".archive-chart-card:first-child .archive-chart > i").count(), 40)
        self.assertTrue(self.page.locator(".archive-flight-scroll").evaluate(
            "node => node.scrollHeight > node.clientHeight && node.clientHeight <= 550"))
        self.render(data, "passport")
        self.assertEqual(self.page.locator(".archive-region").count(), 42)
        self.assertTrue(self.page.locator(".archive-regions").evaluate(
            "node => node.scrollHeight > node.clientHeight && node.clientHeight <= 650"))
        self.assertFalse(self.errors, self.errors)

    def test_escapes_journal_text_and_respects_compact_width(self):
        data = archive_data()
        data["sessions"][0]["start_system"] = "<img src=x onerror=alert(1)>"
        self.page.set_viewport_size({"width": 490, "height": 760})
        self.render(data)
        self.assertEqual(self.page.locator(".archive-flight-table img").count(), 0)
        self.assertEqual(self.page.locator(".archive-tabs > button").count(), 3)
        self.assertEqual(self.page.locator(".archive-tabs").evaluate("node => getComputedStyle(node).gridTemplateColumns.split(' ').length"), 1)
        self.assertLessEqual(self.page.locator(".archive-shell").evaluate("node => node.getBoundingClientRect().right"), 490)
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
