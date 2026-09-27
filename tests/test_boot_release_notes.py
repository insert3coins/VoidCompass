"""The boot screen presents this release's notes and the journal it restores.

Release notes come from the update log's first section, and only when that
section is this version's. The build bundles the log, so the packaged app
reads the same notes as a source run. The boot model also carries how many
journal events startup has restored, which the watcher on the boot screen
takes in as they arrive.
"""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from voidcompass.core.release_notes import MAX_NOTES, current_release
from voidcompass.core.version import APP_VERSION
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

ROOT = Path(__file__).resolve().parents[1]

LOG = """# VoidCompass // UPDATE LOG

## v1.2.3 // Test **Flight**
**Release Date:** 2026-Sep-27

* Added `one` thing.
* Fixed **another**.

## Earlier releases

* **v1.2.2** — Older work.
"""


class ReleaseNotesTests(unittest.TestCase):
    def write(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "mini-readme.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_reads_the_current_release_section_only(self):
        release = current_release("1.2.3", self.write(LOG))
        self.assertEqual(release, {
            "version": "1.2.3", "title": "Test Flight", "date": "2026-Sep-27",
            "notes": ["Added one thing.", "Fixed another."],
        })

    def test_a_log_for_another_version_is_not_presented_as_new(self):
        self.assertIsNone(current_release("1.2.4", self.write(LOG)))
        self.assertIsNone(current_release("1.2.3", Path(tempfile.gettempdir()) / "no-such-update-log.md"))
        self.assertIsNone(current_release("1.2.3", self.write("# Nothing here\n")))

    def test_notes_are_bounded(self):
        bullets = "\n".join(f"* Change {index} " + "x" * 900 for index in range(12))
        release = current_release("1.2.3", self.write(f"## v1.2.3 // Many\n{bullets}\n"))
        self.assertEqual(len(release["notes"]), MAX_NOTES)
        self.assertTrue(all(len(note) <= 600 for note in release["notes"]))

    def test_the_shipped_update_log_matches_this_version(self):
        release = current_release(APP_VERSION)
        self.assertIsNotNone(release, "mini-readme.md's first section must be the current version")
        self.assertTrue(release["title"] and release["notes"])

    def test_the_build_bundles_the_update_log(self):
        build = (ROOT / "tools" / "build.py").read_text(encoding="utf-8")
        self.assertIn('project_dir / "mini-readme.md"', build)


class BootModelTests(unittest.TestCase):
    def runtime(self):
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.app_version = "1.2.3"
        runtime._release = {"version": "1.2.3", "title": "Test", "date": "", "notes": ["One."]}
        runtime._latest_app_model = {}
        runtime._boot = {"active": True, "status": "", "detail": "", "progress": 0.0}
        runtime._onboarding = {"active": False}
        runtime.server = SimpleNamespace(update_host_state=Mock(), publish=Mock())
        return runtime

    def test_snapshot_carries_release_notes_and_restored_events(self):
        runtime = self.runtime()
        runtime.set_runtime_status("RESTORING RECENT JOURNAL", "Reduced 400 events", 0.76, 400)
        payload = runtime.server.publish.call_args.args[0]
        self.assertEqual(payload["app"]["release"]["notes"], ["One."])
        self.assertEqual(payload["boot"]["events"], 400)
        # A status without a count keeps the last one.
        runtime.set_runtime_status("LIVE STATE READY", "", 0.91)
        self.assertEqual(runtime.server.publish.call_args.args[0]["boot"]["events"], 400)

    def test_boot_page_can_load_the_shared_watcher_orb(self):
        # The boot screen wakes the same orb the heartbeat overlay draws.
        server = HtmlDashboardServer.__new__(HtmlDashboardServer)
        server.static_root = (ROOT / "web" / "dashboard").resolve()
        server.image_root = None
        orb = server._static_path("/assets/heartbeat-orb.js")
        self.assertEqual(orb, (ROOT / "web" / "assets" / "heartbeat-orb.js").resolve())
        self.assertTrue(orb.is_file())
        # Only the listed assets reach the shared folder; anything else stays
        # inside the dashboard's own.
        unlisted = server._static_path("/assets/overlay-client.js")
        self.assertEqual(unlisted.relative_to(server.static_root).parts[0], "assets")

    def test_dashboard_passes_the_count_only_when_it_has_one(self):
        boot = SimpleNamespace(set_runtime_status=Mock())
        app = MainDashboard.__new__(MainDashboard)
        app.root = SimpleNamespace(_voidcompass_startup_splash=SimpleNamespace(_voidcompass_boot=boot))
        app._startup_boot_update("BUILDING DASHBOARD CORE", "Loading", 0.18)
        boot.set_runtime_status.assert_called_with("BUILDING DASHBOARD CORE", "Loading", 0.18)
        app._startup_boot_update("RESTORING RECENT JOURNAL", "Reduced", 0.8, 1288)
        boot.set_runtime_status.assert_called_with("RESTORING RECENT JOURNAL", "Reduced", 0.8, 1288)


if __name__ == "__main__":
    unittest.main()
