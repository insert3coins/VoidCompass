"""Bundled web assets reach WebView2 even through transient Windows file locks."""

import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from voidcompass.core.static_assets import asset_type, read_asset
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer


class _FlakyFile:
    """A path whose first reads fail as a scanning antivirus lock would."""

    def __init__(self, failures, error=PermissionError):
        self.failures = failures
        self.error = error
        self.reads = 0

    def read_bytes(self):
        self.reads += 1
        if self.reads <= self.failures:
            raise self.error("locked")
        return b"ok"


class StaticAssetTests(unittest.TestCase):
    def test_script_and_style_types_do_not_depend_on_the_registry(self):
        self.assertEqual(asset_type(Path("app.js")), "text/javascript; charset=utf-8")
        self.assertEqual(asset_type(Path("styles.CSS")), "text/css; charset=utf-8")
        self.assertEqual(asset_type(Path("index.html")), "text/html; charset=utf-8")
        self.assertEqual(asset_type(Path("Anaconda.png")), "image/png")

    def test_transient_locks_are_retried_and_real_failures_still_raise(self):
        waits = []
        flaky = _FlakyFile(failures=3)
        self.assertEqual(read_asset(flaky, sleep=waits.append), b"ok")
        self.assertEqual((flaky.reads, len(waits)), (4, 3))
        stuck = _FlakyFile(failures=99)
        with self.assertRaises(PermissionError):
            read_asset(stuck, attempts=4, sleep=lambda _s: None)
        self.assertEqual(stuck.reads, 4)
        # A file that is genuinely absent is not worth waiting for.
        missing = _FlakyFile(failures=99, error=FileNotFoundError)
        with self.assertRaises(FileNotFoundError):
            read_asset(missing, sleep=lambda _s: None)
        self.assertEqual(missing.reads, 1)

    def test_servers_name_the_asset_that_failed_and_pin_script_types(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "dashboard").mkdir()
            (root / "dashboard" / "app.js").write_text("eventLoop();", encoding="utf-8")
            (root / "survey").mkdir()
            (root / "survey" / "app.js").write_text("render();", encoding="utf-8")
            messages = []
            dashboard = HtmlDashboardServer(root / "dashboard", on_asset_error=messages.append)
            overlays = HtmlOverlayServer(root, on_asset_error=messages.append)
            try:
                with urlopen(f"{dashboard.origin}/app.js", timeout=5) as response:
                    self.assertEqual(response.headers["Content-Type"], "text/javascript; charset=utf-8")
                with self.assertRaises(HTTPError) as missing:
                    urlopen(f"{dashboard.origin}/explore.js", timeout=5)
                missing.exception.close()
                with urlopen(f"http://127.0.0.1:{overlays.port}/survey/app.js", timeout=5) as response:
                    self.assertEqual(response.headers["Content-Type"], "text/javascript; charset=utf-8")
                with self.assertRaises(HTTPError) as missing:
                    urlopen(f"http://127.0.0.1:{overlays.port}/survey/missing.js", timeout=5)
                missing.exception.close()
            finally:
                dashboard.stop()
                overlays.stop()
            self.assertEqual(messages, [
                "Dashboard asset unavailable: /explore.js (not found)",
                "Overlay asset unavailable: /survey/missing.js (not found)",
            ])


if __name__ == "__main__":
    unittest.main()
