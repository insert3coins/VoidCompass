from pathlib import Path
import re
import unittest

from voidcompass.core.version import APP_VERSION
from voidcompass.dashboard.dashboard_core_mixin import release_is_newer


ROOT = Path(__file__).resolve().parents[1]


class CommandDeckConsolidation548Tests(unittest.TestCase):
    def test_release_version_comparison_handles_elite_style_patch_versions(self):
        self.assertEqual(APP_VERSION, "5.5.16")
        self.assertTrue(release_is_newer("v5.4.8.2", "5.4.8.1"))
        self.assertTrue(release_is_newer("5.4.7.1", "5.4.7"))
        self.assertTrue(release_is_newer("5.4.10", "5.4.9.9"))
        self.assertFalse(release_is_newer("v5.4.8.2", "5.4.8.2"))
        self.assertFalse(release_is_newer("5.4.7.9", "5.4.8"))
        self.assertFalse(release_is_newer("not-a-release", "5.4.8.2"))

    def test_left_rail_contains_seventeen_workflow_destinations(self):
        document = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        rail = document.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
        labels = re.findall(r'<button class="nav-item[^>]*>.*?<span>(.*?)</span>', rail)

        # 5.4.9.8 added Music, under its own COCKPIT heading; 5.5.2 Colonisation;
        # 5.5.2.4 BGS; 5.5.2.6 Trading; 5.5.3.2 The Watcher; 5.5.3.7 Postcards, Screenshots, Time Capsules, Constellation;
        # 5.5.4 Tools, and the Exploration Archive became Explore & Survey's Archive tab;
        # 5.5.10 Void Wrapped, the Ship Workshop gone, and each heading's pages
        # in alphabetical order ("The" aside).
        self.assertEqual(len(labels), 22)
        self.assertEqual(labels, [
            "Dashboard", "Explore & Survey", "Galactic Atlas", "Planetary Operations",
            "Commander Record",
            "BGS", "Carrier Command", "Colonisation", "Mining Command", "Powerplay", "Trading",
            "Constellation", "Music", "Postcards", "Screenshots", "Time Capsules", "Void Wrapped", "The Watcher",
            "About", "Overlay Studio", "Settings", "Tools",
        ])
        self.assertEqual([int(number) for number in re.findall(r"<b>(\d+)</b></button>", rail)], list(range(1, 23)))
        self.assertNotIn("Field Tools", labels)

    def test_merged_pages_remain_available_as_compatibility_routes(self):
        document = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for page in (
            "mission", "recon", "ledger", "records", "achievements",
            "chronicle", "overlay-studio",
        ):
            self.assertIn(f'data-page-name="{page}"', document)
        # Ground & Exobio is the Planetary page's ON THE GROUND tab (5.5.12).
        self.assertNotIn('data-page-name="ground"', document)

        script = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const PAGE_SUITES", script)
        self.assertIn("function navigationPage(pageName)", script)
        self.assertIn('node.dataset.page === navPage', script)
        for suite in ("EXPLORATION COMMAND", "COMMANDER RECORD"):
            self.assertIn(suite, script)
        self.assertIn('ground: "planet-materials"', script)
        self.assertIn('if (name === "ground") setPlanetaryView("ground");', script)
        self.assertNotIn("SHIP WORKSHOP", script, "the Ship Workshop is gone (5.5.10)")
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
