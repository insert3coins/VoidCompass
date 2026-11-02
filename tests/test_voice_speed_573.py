"""Fast hearing, warm startup and immediate reply delivery, without a real mic."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from tests.test_settings_page import dashboard
from tests.test_watcher_listen_571 import LOUD, QUIET, FakeHearing, make_listener, deck_for
from voidcompass.core import config
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.voice import listen_assets, listener as hearing


class FastHearingTests(unittest.TestCase):
    def test_quiet_ends_are_trimmed_but_speech_and_padding_are_preserved(self):
        pcm = QUIET * 2 + LOUD + QUIET * 3
        trimmed = hearing.trim_silence(pcm)
        self.assertIn(LOUD, trimmed)
        self.assertEqual(len(trimmed), len(LOUD) + 2 * 13 * 640)
        self.assertEqual(hearing.trim_silence(LOUD), LOUD)
        self.assertEqual(hearing.trim_silence(QUIET), QUIET)
        self.assertEqual(hearing.trim_silence(b""), b"")

    def test_fast_requests_use_one_greedy_pass_accuracy_keeps_fallback(self):
        server = hearing.ListenServer(Path("server.exe"), Path("model.bin"))
        for fast in (False, True):
            server.fast = fast
            with mock.patch.object(hearing._OPENER, "open", return_value=io.BytesIO(b'{"text":"open galaxy map"}')) as request:
                self.assertEqual(server.transcribe(b"wav"), "open galaxy map")
            body = request.call_args.args[0].data
            self.assertEqual(b'name="temperature_inc"\r\n\r\n0.0' in body, fast)
            self.assertEqual(b'name="best_of"\r\n\r\n1' in body, fast)
            self.assertEqual(b'name="beam_size"\r\n\r\n1' in body, fast)

    def test_warming_never_opens_the_mic_and_reuses_the_process(self):
        listener, settings = make_listener(self, {"watcher_listen_model": "fast"})
        listener.warm()
        for thread in threading.enumerate():
            if thread.name == "watcher-hearing-warm":
                thread.join(2)
        server = listener.server
        self.assertIsNotNone(server)
        self.assertTrue(server.fast)
        self.assertEqual(listener._recorder.devices, [])
        self.assertIs(listener._server(), server)
        self.assertEqual(listener.state()["engine"], "ready")
        settings["watcher_listen_model"] = "accurate"
        self.assertIsNot(listener._server(), server)
        self.assertTrue(server.stopped)
        self.assertFalse(listener.server.fast)

    def test_release_records_latency_and_dispatches_without_a_refresh_tick(self):
        listener, _ = make_listener(self)
        listener.start()
        listener.stop()
        self.assertTrue(listener.heard_done.wait(3))
        self.assertIsInstance(listener.state()["latency_ms"], int)
        deck = deck_for(self)
        deck.heartbeat_hud._redraw = mock.Mock()
        deck._watcher_mind_watch = lambda: DashboardWatcherVoiceMixin._watcher_mind_watch(deck)
        deck._watcher_listen_heard("open galaxy map")
        deck.heartbeat_hud._redraw.assert_called_once()
        self.assertEqual(deck.heartbeat_hud.mind.said, [("open galaxy map", True)])

    def test_latency_includes_closing_the_microphone(self):
        listener, _ = make_listener(self)
        clock = [1000.0]
        stop = listener._recorder.stop
        def close_mic():
            clock[0] += 0.2
            return stop()
        listener._recorder.stop = close_mic
        with mock.patch.object(hearing.time, "monotonic", side_effect=lambda: clock[0]):
            listener.start()
            listener.stop()
            self.assertTrue(listener.heard_done.wait(3))
            self.assertEqual(listener.latency_ms, 200)

    def test_switching_off_or_replacing_listener_drops_inflight_words(self):
        listener, _ = make_listener(self)
        server = listener._server()
        entered, release = threading.Event(), threading.Event()
        def transcribe(*_args):
            entered.set()
            release.wait(2)
            return "boost"
        server.transcribe = transcribe
        worker = threading.Thread(target=listener._hear, args=(LOUD, False))
        worker.start()
        self.assertTrue(entered.wait(2))
        listener.close()
        release.set()
        worker.join(2)
        self.assertEqual(listener.heard_list, [])

    def test_enabling_installed_hearing_and_download_completion_warm_it(self):
        deck = deck_for(self)
        with mock.patch.object(deck._watcher_listen, "warm") as warm:
            deck._watcher_listen_switched()
            warm.assert_called_once()
            deck._watcher_listen_downloaded({"stage": "done"})
            self.assertEqual(warm.call_count, 2)


class ModelInstallTests(unittest.TestCase):
    def test_fast_download_preserves_legacy_accuracy_receipt_and_avoids_engine_download(self):
        with tempfile.TemporaryDirectory() as base:
            root = listen_assets.stt_dir(base)
            root.mkdir(parents=True)
            engine = listen_assets.engine_exe(base)
            engine.parent.mkdir()
            engine.write_bytes(b"engine")
            listen_assets.model_path(base).write_bytes(b"small")
            listen_assets._receipt(base).write_text(json.dumps({"engine": listen_assets.ENGINE["sha256"],
                                                                "model": listen_assets.MODEL["sha256"]}))
            self.assertTrue(listen_assets.installed(base))
            data = b"base model stand-in"
            spec = {**listen_assets.MODELS["fast"], "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            opened = []
            def fetch(url):
                opened.append(url)
                return io.BytesIO(data)
            with mock.patch.dict(listen_assets.MODELS, {"fast": spec}):
                self.assertFalse(listen_assets.installed(base, "fast"))
                self.assertEqual(listen_assets.download_bytes(base, "fast"), len(data))
                download = listen_assets.ListenDownload(base, opener=fetch, model="fast")
                done = threading.Event()
                download.start(lambda _state: done.set())
                self.assertTrue(done.wait(3))
                self.assertEqual(download.state()["stage"], "done")
                self.assertEqual(opened, [spec["url"]])
                self.assertTrue(listen_assets.installed(base, "fast"))
                self.assertTrue(listen_assets.installed(base, "accurate"))
                self.assertEqual(listen_assets.download_bytes(base, "accurate"), 0)
                self.assertTrue(listen_assets.remove(base))
                self.assertFalse(listen_assets.model_path(base, "fast").exists())
                self.assertFalse(listen_assets.model_path(base, "accurate").exists())

    def test_model_setting_follows_profiles_and_rejects_changes_during_download(self):
        self.assertIn("watcher_listen_model", config.PROFILE_TEXT_SETTINGS)
        app = dashboard()
        app._watcher_listen_model_changed = mock.Mock()
        save = lambda value: app._handle_html_workspace_command({"page": "settings", "operation": "save",
                      "save_id": 3, "values": {"watcher_listen_model": value}})
        self.assertTrue(save("fast"))
        app._watcher_listen_model_changed.assert_called_once()
        app._watcher_listen_download = mock.Mock(running=lambda: True)
        self.assertFalse(save("accurate"))
        self.assertEqual(app.config["watcher_listen_model"], "fast")
        self.assertFalse(app._html_settings_last_save["ok"])

    def test_existing_config_keeps_accuracy_new_install_starts_fast(self):
        with tempfile.TemporaryDirectory() as base:
            path = Path(base) / "config.json"
            with mock.patch.object(config, "CONFIG_FILE", str(path)), \
                 mock.patch.object(config, "PROFILE_DIR", str(Path(base) / "profiles")), \
                 mock.patch.object(config, "detect_elite_journal_path", return_value=""):
                self.assertEqual(config.load_config()["watcher_listen_model"], "fast")
                path.write_text('{}')
                self.assertEqual(config.load_config()["watcher_listen_model"], "accurate")
