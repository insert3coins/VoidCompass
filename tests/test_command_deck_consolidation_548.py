from pathlib import Path
import re
import unittest

from voidcompass.core.version import APP_VERSION
from voidcompass.dashboard.dashboard_core_mixin import release_is_newer


ROOT = Path(__file__).resolve().parents[1]


class CommandDeckConsolidation548Tests(unittest.TestCase):
    def test_release_version_comparison_handles_elite_style_patch_versions(self):
        self.assertEqual(APP_VERSION, "5.4.8.2")
        self.assertTrue(release_is_newer("v5.4.8.2", "5.4.8.1"))
        self.assertTrue(release_is_newer("5.4.7.1", "5.4.7"))
        self.assertTrue(release_is_newer("5.4.10", "5.4.9.9"))
        self.assertFalse(release_is_newer("v5.4.8.2", "5.4.8.2"))
        self.assertFalse(release_is_newer("5.4.7.9", "5.4.8"))
        self.assertFalse(release_is_newer("not-a-release", "5.4.8.2"))

    def test_left_rail_contains_thirteen_workflow_destinations(self):
        document = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        rail = document.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
        labels = re.findall(r'<button class="nav-item[^>]*>.*?<span>(.*?)</span>', rail)

        self.assertEqual(len(labels), 13)
        self.assertEqual(labels, [
            "Dashboard", "Explore & Survey", "Planetary Operations", "Galactic Atlas",
            "Commander Record", "Exploration Archive", "Mining Command", "Ship Workshop",
            "Carrier Command", "Powerplay", "Overlay Studio", "Settings", "About",
        ])
        self.assertNotIn("Field Tools", labels)

    def test_merged_pages_remain_available_as_compatibility_routes(self):
        document = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for page in (
            "mission", "recon", "ledger", "ground", "records", "achievements",
            "chronicle", "engineering", "overlay-studio",
        ):
            self.assertIn(f'data-page-name="{page}"', document)

        script = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const PAGE_SUITES", script)
        self.assertIn("function navigationPage(pageName)", script)
        self.assertIn('node.dataset.page === navPage', script)
        for suite in (
            "EXPLORATION COMMAND", "PLANETARY OPERATIONS", "COMMANDER RECORD",
            "EXPLORATION ARCHIVE", "SHIP WORKSHOP",
        ):
            self.assertIn(suite, script)
        self.assertNotIn('{parent: "settings"', script)

    def test_release_notice_is_in_app_and_opens_the_matching_github_release(self):
        document = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        backend = (
            ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py"
        ).read_text(encoding="utf-8")

        self.assertIn('id="release-update"', document)
        self.assertIn('id="release-update-open"', document)
        self.assertIn('data-command="check_updates"', document)
        self.assertIn("renderUpdateNotice(model.update || {})", script)
        self.assertIn('target == "release_update"', backend)
        self.assertIn('action == "check_updates"', backend)


if __name__ == "__main__":
    unittest.main()
