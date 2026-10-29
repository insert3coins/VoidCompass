"""Opt-in Watcher renderer diagnostics report actual, per-surface results."""

import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from voidcompass.core import config, watcher_renderer_diagnostics as diagnostics
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]


class WatcherRendererLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / "watcher_renderer.log"
        for item in (patch.object(diagnostics, "resolve_log_path", return_value=str(self.log)),
                     patch.object(diagnostics, "_log_path", None), patch.object(diagnostics, "_reported", set())):
            item.start()
            self.addCleanup(item.stop)

    def test_global_config_defaults_off_and_persists_across_profiles(self):
        with patch.object(config, "CONFIG_FILE", str(Path(self.temp.name) / "config.json")), \
             patch.object(config, "PROFILE_DIR", str(Path(self.temp.name) / "profiles")), \
             patch.object(config, "detect_elite_journal_path", return_value=""):
            settings = config.load_config()
            self.assertIs(settings['watcher_renderer_logging'], False)
            settings['watcher_renderer_logging'] = True
            config.apply_profile_config(settings, 'test_commander')
            config.save_config(settings)
            self.assertIs(json.loads(Path(config.CONFIG_FILE).read_text())['watcher_renderer_logging'], True)
            self.assertIs(config.load_config()['watcher_renderer_logging'], True)

    def test_diagnostic_is_thread_safe_and_logs_each_surface_once(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            self.assertTrue(all(executor.map(lambda _: diagnostics.record('overlay', 'three'), range(20))))
        self.assertTrue(diagnostics.record('boot', 'canvas', 'module-error'))
        self.assertTrue(diagnostics.record('dashboard', 'three'))
        self.assertFalse(diagnostics.record('invalid', 'three'))
        self.assertFalse(diagnostics.record('overlay', 'unknown'))
        lines = self.log.read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(any('overlay: Three.js active' in line for line in lines))
        self.assertTrue(any('boot: Canvas fallback (canvas): Three.js module failed to load' in line for line in lines))

    def test_dashboard_logging_requires_the_switch_and_an_allowed_surface(self):
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.config = {'watcher_renderer_logging': False}
        report = {'action': 'watcher_renderer', 'surface': 'boot', 'renderer': 'three'}
        self.assertFalse(runtime._receive_command(report))
        self.assertFalse(self.log.exists())
        runtime.config['watcher_renderer_logging'] = True
        self.assertFalse(runtime._receive_command({**report, 'surface': 'overlay'}))
        self.assertTrue(runtime._receive_command(report))
        self.assertTrue(runtime._receive_command(report))
        self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def test_overlay_report_requires_token_enabled_setting_and_heartbeat_surface(self):
        server = HtmlOverlayServer(ROOT / 'web')
        self.addCleanup(server.stop)
        server.register('heartbeat', 'heartbeat')
        server.register('hatchling', 'hatchling')
        connection = HTTPConnection('127.0.0.1', server.port, timeout=5)
        self.addCleanup(connection.close)

        def report(token, overlay, renderer='three'):
            connection.request('POST', f'/api/watcher-renderer?token={token}&overlay={overlay}',
                               body=json.dumps({'renderer': renderer}))
            response = connection.getresponse()
            response.read()
            return response.status

        server.publish('heartbeat', {'heartbeat': {'orb': {'renderer_logging': False}}})
        self.assertEqual(report('wrong-token', 'heartbeat'), 403)
        self.assertEqual(report(server.token, 'heartbeat'), 403)
        self.assertFalse(self.log.exists())
        server.publish('heartbeat', {'heartbeat': {'orb': {'renderer_logging': True}}})
        self.assertEqual(report(server.token, 'heartbeat'), 202)
        self.assertEqual(report(server.token, 'heartbeat', 'canvas'), 202)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.assertIn('Three.js active', self.log.read_text())
        server.publish('hatchling', {'heartbeat': {'orb': {'renderer_logging': True}}})
        self.assertEqual(report(server.token, 'hatchling'), 403)

    def test_real_dashboard_boot_sends_its_actual_renderer_when_enabled(self):
        from playwright.sync_api import sync_playwright
        from tests.test_dashboard_overview_visuals import overview_state

        reports = []
        server = HtmlDashboardServer(ROOT / 'web' / 'dashboard',
                                     command_callback=lambda item: reports.append(item) or True)
        self.addCleanup(server.stop)
        server.publish({**overview_state(), 'watcher_renderer_logging': True,
                        'boot': {'active': True, 'progress': .3, 'status': 'STARTING'}})
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1200, 'height': 800})
            page.goto(server.url)
            page.wait_for_function("window.bootScene?.state().orb?.renderer === 'three'")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not any(item.get('action') == 'watcher_renderer' for item in reports):
                page.wait_for_timeout(50)
            found = [item for item in reports if item.get('action') == 'watcher_renderer']
            self.assertEqual(len(found), 1)
            self.assertEqual((found[0]['surface'], found[0]['renderer']), ('boot', 'three'))
            browser.close()


if __name__ == '__main__':
    unittest.main()
