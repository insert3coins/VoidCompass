"""Every overlay, every place it has to be registered.

Adding an overlay touches a dozen files, and missing one fails quietly. In
5.5.18 the Rhino Map's template was missing from the overlay host, so its
window could never be made, and because the host makes windows one at a time
in manifest order the Navigation HUD after it never appeared either.

This walks every spec in OVERLAY_SPECS and checks each place in turn, so a new
overlay can't skip a step. Each overlay's template is read from the deck's own
attach code rather than a list kept here.
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPECS, TEXT_SIZE_KEYS
from voidcompass.dashboard.dashboard_tools_mixin import GROUP_OF
from voidcompass.overlays import html_overlay_host
from voidcompass.overlays.html_overlay_host import _OverlayHost

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "voidcompass"
DASHBOARD = (SRC / "dashboard" / "dashboard.py").read_text(encoding="utf-8")

# The planet compass is a plain window the deck makes and destroys itself
# (_destroy_ground_popup); its page takes the theme from the model.
OWN_WINDOW = {"ground_popup"}
# These place themselves from the screen until you move them, so their saved
# position has no default (see the note in config.load_config).
SCREEN_PLACED = {"gravity_warning_hud", "toast_hud", "achievement_hud", "heartbeat_hud"}


def _module_template(module):
    source = (SRC / "overlays" / f"{module}.py").read_text(encoding="utf-8")
    templates = set(re.findall(r'template="([a-z_-]+)"', source))
    assert len(templates) == 1, (module, templates)
    return templates.pop()


def overlay_templates():
    """{attr: template}, from the branches of _attach_html_overlay_renderers."""
    start = DASHBOARD.index("def _attach_html_overlay_renderers")
    body = DASHBOARD[start:DASHBOARD.index("\n    def ", start + 1)]
    imports = dict((name, module) for module, name in re.findall(
        r"^from voidcompass\.overlays\.(html_\w+) import (attach_\w+)", DASHBOARD, re.M))
    templates = {"hud": _module_template("html_navigation_hud")}
    for condition, function in re.findall(r"attr (?:==|in) ([^:]+):\s*\n\s*(attach_\w+)\(", body):
        for attr in re.findall(r'"(\w+)"', condition):
            templates[attr] = _module_template(imports[function])
    return templates


def _tuple_after(source, marker):
    start = source.index(marker)
    return source[start:source.index("):", start)]


def _host():
    host = _OverlayHost.__new__(_OverlayHost)
    host.token, host.origin = "t", "http://127.0.0.1:1"
    return host


class ChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = overlay_templates()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(config_module, "PROFILE_DIR", str(Path(directory) / "profiles")), \
                patch.object(config_module, "CONFIG_FILE", str(Path(directory) / "config.json")), \
                patch.object(config_module, "detect_elite_journal_path", return_value=""):
            cls.config = config_module.load_config()
            config_module.apply_profile_config(cls.config, "checklist")

    def test_the_deck_attaches_it_and_the_host_can_open_its_page(self):
        host = _host()
        for spec in OVERLAY_SPECS:
            self.assertIn(spec.attr, self.templates,
                          f"{spec.attr}: no branch for it in MainDashboard._attach_html_overlay_renderers")
            path = host.page_url(spec.overlay_id, self.templates[spec.attr]).split("?")[0]
            page = ROOT / "web" / path.replace(host.origin, "").lstrip("/")
            self.assertTrue(page.is_file(), f"{spec.attr}: html_overlay_host.page_url points at a missing page: {page}")
            if spec.html_managed:
                self.assertIn("/assets/overlay-client.js", page.read_text(encoding="utf-8"), spec.attr)

    def test_its_settings_exist_in_the_defaults_and_per_commander(self):
        hotkeys = {action: key for action, key, _label, attr in OVERLAY_HOTKEY_SPECS if attr}
        for spec in OVERLAY_SPECS:
            keys = (spec.enabled_key, spec.x_key, spec.y_key, TEXT_SIZE_KEYS.get(spec.attr), spec.hotkey_key)
            for key in keys:
                self.assertIsNotNone(key, f"{spec.attr}: no text size key in TEXT_SIZE_KEYS")
                self.assertIn(key, config_module.PROFILE_SETTINGS, f"{spec.attr}: {key} missing from the config.py PROFILE_* tuples")
                if key in (spec.x_key, spec.y_key) and spec.attr in SCREEN_PLACED:
                    continue
                self.assertIn(key, self.config, f"{spec.attr}: {key} missing from the config defaults")
            if spec.available:
                self.assertEqual(hotkeys.get(spec.hotkey_action), spec.hotkey_key, f"{spec.attr}: no OVERLAY_HOTKEY_SPECS row")

    def test_the_deck_themes_and_closes_it(self):
        theme = _tuple_after(DASHBOARD[DASHBOARD.index("def _apply_active_profile_theme"):], "for attr in (")
        closing = _tuple_after(DASHBOARD, '"hud", "cargo_hud", "carrier_hud"')
        for spec in OVERLAY_SPECS:
            if spec.attr in OWN_WINDOW:
                continue
            self.assertIn(f'"{spec.attr}"', theme, f"{spec.attr}: missing from _apply_active_profile_theme's overlay list")
            self.assertIn(f'"{spec.attr}"', closing, f"{spec.attr}: missing from the overlays destroyed on close")

    def test_it_has_a_group_and_an_api_line(self):
        api = (ROOT / "api.md").read_text(encoding="utf-8")
        for spec in OVERLAY_SPECS:
            self.assertIn(spec.attr, GROUP_OF, f"{spec.attr}: not in dashboard_tools_mixin.OVERLAY_GROUPS (it would land in 'other')")
            self.assertIn(f"| `{spec.overlay_id}` |", api, f"{spec.attr}: no row for {spec.overlay_id} in api.md")


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
