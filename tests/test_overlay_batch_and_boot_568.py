"""5.6.8: batch overlay updates and a silent boot handoff."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD
from voidcompass.overlays.html_overlay_host import _OverlayHost, _request_json
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]


class BatchTests(unittest.TestCase):
    def test_composition_creates_and_applies_every_surface_before_reporting(self):
        host = _OverlayHost('http://127.0.0.1:1/?token=test', None)
        events = []
        host.runtime = SimpleNamespace(call=lambda fn: fn())
        specs = {f'overlay-{i}': {'window': {'visible': True}, 'content_ready': True} for i in range(19)}

        def create(overlay_id, spec, hidden=True):
            events.append(('create', overlay_id))
            host.controllers[overlay_id] = SimpleNamespace(
                window=SimpleNamespace(), navigation_retries=0, reload_revision=0,
                apply=lambda *_args, **_kwargs: events.append(('apply', overlay_id)) or {'ok': True},
            )

        def manifest():
            host.closing = True
            return specs

        host.create_window, host.manifest = create, manifest
        with patch('voidcompass.overlays.html_overlay_host._request_json',
                   side_effect=lambda url, data: events.append(('report', data))):
            host.control_loop()
        self.assertEqual(len(host.controllers), 19)
        self.assertEqual([item[0] for item in events].count('report'), 1)
        self.assertEqual(events[-1][0], 'report')
        self.assertEqual(set(events[-1][1]['overlays']), set(specs))

    def test_batch_status_is_authenticated_and_bad_input_is_atomic(self):
        server = HtmlOverlayServer(ROOT / 'web')
        self.addCleanup(server.stop)
        server.register('cargo', 'cargo')
        server.register('heartbeat', 'heartbeat')
        host = _OverlayHost(server.url, None)
        url = host._url('/api/host-status-batch')
        statuses = {'cargo': {'ok': True, 'visible': True}, 'heartbeat': {'ok': True, 'visible': False}}
        self.assertTrue(_request_json(url, {'overlays': statuses})['accepted'])
        self.assertEqual(server.host_status('cargo'), statuses['cargo'])
        self.assertEqual(server.host_status('heartbeat'), statuses['heartbeat'])
        with self.assertRaises(HTTPError) as caught:
            _request_json(url.replace(host.token, 'wrong-token'), {'overlays': statuses})
        self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(HTTPError) as caught:
            _request_json(url, {'overlays': {'cargo': {'ok': False}, 'heartbeat': []}})
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(server.host_status('cargo'), statuses['cargo'])
        # Malformed roots must also be rejected rather than raising in the server.
        with self.assertRaises(HTTPError) as caught:
            _request_json(url, [])
        self.assertEqual(caught.exception.code, 400)

    def test_three_assets_can_be_reused_by_the_overlay_browser(self):
        server = HtmlOverlayServer(ROOT / 'web')
        self.addCleanup(server.stop)
        host = _OverlayHost(server.url, None)
        with urlopen(host._url('/galactic_map/vendor/three.core.min.js')) as response:
            self.assertIn('max-age=3600', response.headers['Cache-Control'])
        with urlopen(host._url('/assets/overlay-client.js')) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')


class VoiceBootTests(unittest.TestCase):
    def make_deck(self):
        deck = DashboardWatcherVoiceMixin()
        deck.root = SimpleNamespace(_voidcompass_startup_presentation_held=True,
                                    _voidcompass_startup_splash=object())
        deck.config = {'watcher_voice_enabled': True}
        deck.heartbeat_hud = Mock()
        deck._watcher_voice = Mock()
        deck._startup_overlay_handoff_pending = {'hud'}
        return deck

    @patch('voidcompass.voice.voice_assets.installed', return_value=True)
    def test_warm_during_boot_but_neither_thoughts_nor_voice_tests_are_queued(self, _installed):
        deck = self.make_deck()
        deck._watcher_voice_sync()
        deck._watcher_voice.warm.assert_called_once()
        deck.heartbeat_hud.set_voice_active.assert_called_once_with(False)
        self.assertFalse(deck._watcher_voice_say('A star.', 'journal'))
        self.assertFalse(deck._handle_watcher_settings_command('voice_test', {}))
        deck._watcher_voice.say.assert_not_called()
        deck.root._voidcompass_startup_presentation_held = False
        deck.root._voidcompass_startup_splash = None
        self.assertFalse(deck._watcher_voice_say('Still handing off.'))
        deck._startup_overlay_handoff_pending = None
        deck._watcher_voice_sync()
        deck.heartbeat_hud.set_voice_active.assert_called_with(True)
        self.assertTrue(deck._watcher_voice_say('Now we can speak.', 'journal'))
        deck._watcher_voice.say.assert_called_once_with('Now we can speak.', 'journal', feel=None)

    def test_the_greeting_shown_behind_the_curtain_is_said_when_the_voice_returns(self):
        # 5.6.9: the boot hold kept the greeting silent, and nothing said it later.
        said, shown = [], {'thought': {'id': 't1', 'text': 'Welcome back.', 'topic': 'session_start', 'importance': 1}}
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.config = {'watcher_voice_level': 'every'}
        hud.mind = SimpleNamespace(voice_active=False, find_voice=lambda: False,
                                   current=lambda: dict(shown['thought']) if shown['thought'] else None,
                                   spoken_words=lambda thought: thought['text'])
        hud.voice_listener = lambda words, key, feel=None: said.append((words, key)) or True
        hud._redraw = lambda: None
        hud._spoken_id = 't1'  # it went out, unspoken, while the voice was held
        hud.set_voice_active(True)
        self.assertEqual(said, [('Welcome back.', 't1')])
        self.assertEqual(hud._voiced, ('t1', True))
        hud.set_voice_active(False)
        hud.set_voice_active(True)
        self.assertEqual(len(said), 1, 'said once, not again on every switch')
        # A thought that has already left the screen stays unsaid.
        shown['thought'], hud._spoken_id = None, 't2'
        hud.set_voice_active(False)
        hud.set_voice_active(True)
        self.assertEqual(len(said), 1)


if __name__ == '__main__':
    unittest.main()
