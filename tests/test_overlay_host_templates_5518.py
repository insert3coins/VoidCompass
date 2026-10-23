"""5.5.18: the Rhino Map's template was missing from the overlay host, so its
window could never be made, and because the host makes windows one at a time
in manifest order, every overlay after it (the Navigation HUD included) never
appeared. Every template must have a page, and one window that can't be made
must not hold back the rest."""

import re
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voidcompass.overlays import html_overlay_host
from voidcompass.overlays.html_overlay_host import _OverlayHost

ROOT = Path(__file__).resolve().parents[1]


def _host():
    host = _OverlayHost.__new__(_OverlayHost)
    host.token, host.origin = "t", "http://127.0.0.1:1"
    return host


class TemplateTests(unittest.TestCase):
    def test_every_overlay_template_has_a_page(self):
        sources = (ROOT / "src" / "voidcompass" / "overlays").glob("*.py")
        templates = set()
        for source in sources:
            templates.update(re.findall(r'template="([a-z_-]+)"', source.read_text(encoding="utf-8")))
        self.assertIn("rhino_map", templates)
        host = _host()
        for template in sorted(templates):
            with self.subTest(template=template):
                path = host.page_url("x", template).split("?")[0].replace(host.origin, "")
                self.assertTrue((ROOT / "web" / path.lstrip("/")).is_file(), path)


class CreationTests(unittest.TestCase):
    def test_a_window_that_cannot_be_made_does_not_hold_back_the_rest(self):
        host = _host()
        host.runtime, host.controllers, host.closing = None, {}, False
        host.last_contact = host.last_window_created_at = 0.0
        host.failed_windows, host.presentation_held = set(), False
        manifest = {"broken": {"template": "nope"}, "navigation": {"template": "navigation"}}
        calls = []

        def read_manifest():
            calls.append(1)
            if len(calls) > 3:
                host.closing = True
            return manifest

        def create(overlay_id, spec, hidden=True):
            if overlay_id == "broken":
                raise ValueError("no page")
            host.controllers[overlay_id] = Mock(reload_revision=0, navigation_retries=0,
                                                apply=Mock(return_value={}))

        host.manifest, host.create_window = read_manifest, create
        with patch.object(html_overlay_host, "WINDOW_CREATE_INTERVAL_S", 0.0), \
                patch.object(html_overlay_host, "_request_json"), patch("builtins.print"):
            host.control_loop()
        self.assertIn("navigation", host.controllers)
        self.assertEqual(host.failed_windows, {"broken"})


if __name__ == "__main__":
    unittest.main()
