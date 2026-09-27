"""What the boot screen is told while Void Compass starts.

The boot model carries the version and how many journal events startup has
restored, which the watcher on the boot screen takes in as they arrive. The
boot screen wakes the same orb the heartbeat overlay draws, served to the
dashboard from the shared assets folder.
"""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

ROOT = Path(__file__).resolve().parents[1]


class BootModelTests(unittest.TestCase):
    def runtime(self):
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.app_version = "1.2.3"
        runtime._latest_app_model = {}
        runtime._boot = {"active": True, "status": "", "detail": "", "progress": 0.0}
        runtime._onboarding = {"active": False}
        runtime.server = SimpleNamespace(update_host_state=Mock(), publish=Mock())
        return runtime

    def test_snapshot_carries_the_version_and_restored_events(self):
        runtime = self.runtime()
        runtime.set_runtime_status("RESTORING RECENT JOURNAL", "Reduced 400 events", 0.76, 400)
        payload = runtime.server.publish.call_args.args[0]
        self.assertEqual(payload["app"]["version"], "1.2.3")
        self.assertNotIn("release", payload["app"], "the boot screen shows no release notes")
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
