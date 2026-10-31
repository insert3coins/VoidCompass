"""5.7.1: talking to the Watcher by voice. Push to talk (held or tapped),
Whisper on whisper.cpp's server hears what you said, and it goes to its mind
like words typed in TALK TO IT. No microphone or server runs here: both are
faked, but for one real local HTTP server standing in for whisper-server."""

import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest import mock
import wave
import zipfile

from voidcompass.core import config as config_module
from voidcompass.core.global_hotkeys import validate_hotkey_bindings
from voidcompass.core.overlay_registry import DEFAULT_OVERLAY_HOTKEYS, OVERLAY_HOTKEY_SPECS
from voidcompass.dashboard.dashboard_journey_mixin import DashboardJourneyMixin
from voidcompass.dashboard.dashboard_watcher_listen_mixin import DashboardWatcherListenMixin
from voidcompass.overlays import watcher_mind
from voidcompass.voice import listen_assets, listener as listener_module, microphone
from voidcompass.voice.listener import ListenServer, WatcherListener, clean

ROOT = Path(__file__).resolve().parents[1]
LOUD = (b"\x00\x40\x00\xc0" * 8000)        # a second of loud sound, 16-bit
QUIET = b"\x00\x00" * 16000                # a second of silence


class FakeRecorder:
    """The microphone's part: start() opens, stop() gives back what was 'said'."""

    def __init__(self, sound=LOUD, opens=True):
        self.sound = sound
        self.opens = opens
        self.level = 0.0
        self.loudest = 0.0
        self.error = ""
        self.on_full = None
        self.devices = []

    def start(self, device=None):
        self.devices.append(device)
        if not self.opens:
            self.error = "the microphone wouldn't open (Windows error 4)"
            return False
        self.level = 0.2
        return True

    def stop(self):
        self.loudest = microphone.rms(self.sound)
        self.level = 0.0
        return self.sound

    def seconds(self):
        return len(self.sound) / (microphone.RATE * 2)


class FakeHearing:
    """whisper-server's part."""

    made = []
    text = " Where are we, Watcher?"
    ready = True

    def __init__(self, exe, model, gpu=False, log_path=None):
        self.alive = False
        self.error = ""
        self.heard = []
        self.stopped = False
        FakeHearing.made.append(self)

    def start(self):
        self.alive = True
        return True

    def running(self):
        return self.alive

    def wait_ready(self, timeout=90.0, cancelled=lambda: False):
        return FakeHearing.ready

    def transcribe(self, wav, prompt=""):
        self.heard.append((wav, prompt))
        return FakeHearing.text

    def stop(self, wait=True):
        self.alive = False
        self.stopped = True


def make_listener(case, settings=None, recorder=None, **extra):
    FakeHearing.made = []
    FakeHearing.text = " Where are we, Watcher?"
    FakeHearing.ready = True
    settings = {"watcher_listen_enabled": True, "watcher_listen_mic": "", **(settings or {})}
    installed = mock.patch.object(listen_assets, "installed", return_value=True)
    installed.start()
    case.addCleanup(installed.stop)
    heard = []
    done = threading.Event()

    def on_heard(text):
        heard.append(text)
        done.set()

    listener = WatcherListener(lambda: settings, on_heard=on_heard, server_factory=FakeHearing,
                               recorder_factory=lambda: recorder or FakeRecorder(), **extra)
    listener.heard_list, listener.heard_done = heard, done
    return listener, settings


def wait_idle(listener, timeout=3.0):
    end = threading.Event()
    for _ in range(int(timeout / 0.02)):
        if listener._stage == "idle":
            return True
        end.wait(0.02)
    return False


class HearingTests(unittest.TestCase):
    def test_whispers_notes_for_sounds_are_not_words(self):
        self.assertEqual(clean(" [BLANK_AUDIO] "), "")
        self.assertEqual(clean("(wind blowing) Where are we? [Music]"), "Where are we?")
        self.assertEqual(clean(" - Hello there. "), "Hello there.")
        self.assertEqual(clean(None), "")

    def test_held_talk_reaches_its_mind(self):
        listener, _settings = make_listener(self)
        self.assertTrue(listener.start())
        self.assertEqual(listener.state()["stage"], "listening")
        self.assertIsNotNone(listener.live(), "the orb shows it's listening")
        self.assertTrue(listener.stop())
        self.assertTrue(listener.heard_done.wait(3))
        self.assertEqual(listener.heard_list, ["Where are we, Watcher?"])
        self.assertTrue(wait_idle(listener))
        self.assertEqual(listener.note, "")
        wav, prompt = FakeHearing.made[-1].heard[-1]
        with wave.open(io.BytesIO(wav)) as sound:
            self.assertEqual((sound.getframerate(), sound.getnchannels(), sound.getsampwidth()), (16000, 1, 2))
        self.assertIn("Shinrarta Dezhra", prompt, "Elite's words help it hear the names")

    def test_where_you_are_helps_it_hear(self):
        listener, _settings = make_listener(self, prompt_provider=lambda: ["Colonia", "Krait Phantom", None])
        listener.start()
        listener.stop()
        listener.heard_done.wait(3)
        prompt = FakeHearing.made[-1].heard[-1][1]
        self.assertTrue(prompt.startswith(listener_module.VOCABULARY))
        self.assertIn("Colonia Krait Phantom", prompt)

    def test_a_slipped_key_is_not_a_question(self):
        listener, _settings = make_listener(self, recorder=FakeRecorder(sound=LOUD[:3200]))
        listener.start()
        self.assertFalse(listener.stop())
        self.assertIn("Too short", listener.note)
        self.assertEqual(listener.heard_list, [])
        self.assertEqual(FakeHearing.made[-1].heard if FakeHearing.made else [], [], "nothing sent to be heard")

    def test_silence_says_which_microphone_to_check(self):
        listener, _settings = make_listener(self, recorder=FakeRecorder(sound=QUIET))
        listener.start()
        self.assertFalse(listener.stop())
        self.assertIn("heard nothing", listener.note)
        self.assertEqual(listener.heard_list, [])

    def test_no_words_heard_is_said(self):
        listener, _settings = make_listener(self)
        FakeHearing.text = " [BLANK_AUDIO]"
        listener.start()
        listener.stop()
        self.assertTrue(wait_idle(listener))
        self.assertIn("didn't catch that", listener.note)
        self.assertEqual(listener.heard_list, [])

    def test_the_mic_test_is_heard_back_not_sent(self):
        listener, _settings = make_listener(self)
        self.assertTrue(listener.start(test=True))
        self.assertIsNone(listener.live(), "a test isn't shown on the orb")
        listener.stop()
        self.assertTrue(wait_idle(listener))
        self.assertEqual(listener.heard_list, [], "a test never reaches its mind")
        self.assertIn("It heard: “Where are we, Watcher?”", listener.note)
        self.assertTrue(listener.last_test().startswith(b"RIFF"))

    def test_let_go_while_the_microphone_opened(self):
        listener, _settings = make_listener(self)
        recorder = listener._recorder
        original = recorder.start

        def slow_open(device=None):
            listener.stop()          # the key came up while it was opening
            return original(device)

        recorder.start = slow_open
        listener.start()
        self.assertFalse(listener.listening(), "not left open")
        self.assertEqual(listener.heard_list, [])

    def test_it_listens_only_when_on_and_downloaded(self):
        listener, settings = make_listener(self)
        settings["watcher_listen_enabled"] = False
        self.assertFalse(listener.start())
        self.assertEqual(listener.state()["stage"], "off")
        settings["watcher_listen_enabled"] = True
        with mock.patch.object(listen_assets, "installed", return_value=False):
            self.assertFalse(listener.start())

    def test_the_chosen_microphone_is_used(self):
        listener, _settings = make_listener(self, {"watcher_listen_mic": "Microphone (USB FS AUDIO)"})
        with mock.patch.object(microphone, "devices", return_value=["Webcam 1", "Microphone (USB FS AUDIO)"]):
            listener.start()
        self.assertEqual(listener._recorder.devices, [1])
        listener.stop()
        listener.heard_done.wait(3)
        listener2, _ = make_listener(self, {"watcher_listen_mic": "Gone"})
        with mock.patch.object(microphone, "devices", return_value=["Webcam 1"]):
            listener2.start()
        self.assertEqual(listener2._recorder.devices, [None], "a microphone that's gone: Windows' default")
        listener2.stop()

    def test_a_microphone_that_wont_open_is_said(self):
        listener, _settings = make_listener(self, recorder=FakeRecorder(opens=False))
        self.assertFalse(listener.start())
        self.assertIn("wouldn't open", listener.note)
        self.assertEqual(listener._stage, "idle")

    def test_hearing_that_wont_start_is_said(self):
        listener, _settings = make_listener(self)
        FakeHearing.ready = False
        listener.start()
        listener.stop()
        self.assertTrue(wait_idle(listener))
        self.assertIn("wouldn't start (no answer)", listener.note, "why, as the server said it")
        self.assertIsNone(listener.server)

    def test_unused_hearing_is_stopped(self):
        listener, _settings = make_listener(self)
        listener.start()
        listener.stop()
        listener.heard_done.wait(3)
        wait_idle(listener)
        server = listener.server
        self.assertIsNotNone(server)
        listener._used -= listener_module.IDLE_S
        listener._idle_check()
        self.assertTrue(server.stopped)
        self.assertIsNone(listener.server)

    def test_closing_stops_the_server_without_waiting(self):
        listener, _settings = make_listener(self)
        listener._server()
        server = listener.server
        listener.close()
        self.assertTrue(server.stopped)
        self.assertIsNone(listener._server(), "nothing starts after shutdown")

    def test_switched_off_while_you_spoke(self):
        listener, settings = make_listener(self)
        listener.start()
        settings["watcher_listen_enabled"] = False
        listener.stop()
        self.assertTrue(wait_idle(listener))
        self.assertEqual(listener.heard_list, [])
        self.assertFalse(any(server.heard for server in FakeHearing.made), "nothing sent to be heard")


class _Whisper(BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        self._answer({"status": "ok"} if self.path == f"/{self.server.key}/health" else None)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        _Whisper.seen.append((self.path, self.headers.get("Content-Type"), body))
        self._answer({"text": " Hello, Watcher."} if self.path == f"/{self.server.key}/inference" else None)

    def _answer(self, data):
        payload = json.dumps(data or {"error": "not found"}).encode()
        self.send_response(200 if data else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


class ServerTests(unittest.TestCase):
    def test_it_listens_behind_a_random_path_on_this_pc_only(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        server = ListenServer(folder / "engine" / "whisper-server.exe", folder / "model.bin", gpu=False)
        server.port, server.key = 5555, "abc123"
        args = server.arguments()
        self.assertEqual(args[args.index("--host") + 1], "127.0.0.1")
        self.assertEqual(args[args.index("--request-path") + 1], "/abc123", "no key of its own: a path only we know")
        self.assertIn("-ng", args, "the CPU: the graphics card is the game's")
        self.assertEqual(args[args.index("-l") + 1], "en")
        self.assertNotIn("--api-key", args)
        # b5454's server has no -nc (it printed its help and stopped): -mc 0 instead.
        self.assertNotIn("-nc", args)
        self.assertEqual(args[args.index("-mc") + 1], "0")
        self.assertTrue(server.matches(None, None, None, None))

    def test_why_it_wouldnt_start_is_its_error_line(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        server = ListenServer(folder / "engine" / "whisper-server.exe", folder / "model.bin", gpu=False,
                              log_path=folder / "server.log")
        (folder / "server.log").write_text("\n".join((
            "load_backend: loaded CPU backend", "error: unknown argument: -nc", "",
            "usage: whisper-server.exe [options]", "  -vo N, --vad-samples-overlap N", "")), encoding="utf-8")
        self.assertEqual(server._log_tail(), "error: unknown argument: -nc")

    def test_what_was_said_comes_back_from_the_server(self):
        httpd = HTTPServer(("127.0.0.1", 0), _Whisper)
        httpd.key = "k3y"
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        server = ListenServer(Path("whisper-server.exe"), Path("model.bin"), gpu=False)
        server.port, server.key = httpd.server_address[1], "k3y"
        server.process = mock.Mock(poll=lambda: None)
        self.assertTrue(server.ready())
        wav = microphone.to_wav(LOUD)
        self.assertEqual(server.transcribe(wav, "Elite Dangerous."), " Hello, Watcher.")
        path, kind, body = _Whisper.seen[-1]
        self.assertEqual(path, "/k3y/inference")
        self.assertTrue(kind.startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="file"; filename="said.wav"', body)
        self.assertIn(b'name="response_format"\r\n\r\njson', body)
        self.assertIn(b"Elite Dangerous.", body)
        self.assertIn(wav, body)
        server.key = "wrong"
        self.assertFalse(server.ready(), "the wrong path finds nothing")
        server.process = None


class MicrophoneTests(unittest.TestCase):
    def test_loudness(self):
        self.assertEqual(microphone.rms(b""), 0.0)
        self.assertEqual(microphone.rms(QUIET), 0.0)
        self.assertGreater(microphone.rms(LOUD), 0.4)

    def test_sound_becomes_a_wav_file(self):
        with wave.open(io.BytesIO(microphone.to_wav(LOUD))) as sound:
            self.assertEqual(sound.getnframes(), len(LOUD) // 2)

    def test_no_name_is_windows_default(self):
        self.assertIsNone(microphone.device_index(""))
        self.assertIsNone(microphone.device_index(None))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("Release/whisper-server.exe", b"MZ server")
            archive.writestr("Release/whisper.dll", b"MZ library")
            archive.writestr("Release/ggml-base.dll", b"MZ ggml")
            archive.writestr("Release/whisper-cli.exe", b"MZ not wanted")
            archive.writestr("Release/README.txt", b"not wanted")
        self.engine = bundle.getvalue()
        self.model = b"ggml model bytes" * 100
        self.files = {"engine": self.engine, "model": self.model}
        self.engine_info = {**listen_assets.ENGINE, "url": "engine", "size": len(self.engine),
                            "sha256": hashlib.sha256(self.engine).hexdigest()}
        self.model_info = {**listen_assets.MODEL, "url": "model", "size": len(self.model),
                           "sha256": hashlib.sha256(self.model).hexdigest()}

    def run_download(self):
        with mock.patch.dict(listen_assets.ENGINE, self.engine_info), mock.patch.dict(listen_assets.MODEL, self.model_info):
            download = listen_assets.ListenDownload(self.base, opener=lambda url: io.BytesIO(self.files[url]))
            finished = threading.Event()
            download.start(lambda _state: finished.set())
            self.assertTrue(finished.wait(10))
            return download.state(), listen_assets.installed(self.base)

    def test_only_the_server_and_its_libraries_are_unpacked(self):
        state, installed = self.run_download()
        self.assertEqual(state["stage"], "done", state)
        self.assertTrue(installed)
        engine = listen_assets.engine_exe(self.base).parent
        self.assertEqual(sorted(path.name for path in engine.iterdir()), ["ggml-base.dll", "whisper-server.exe", "whisper.dll"])
        self.assertFalse((listen_assets.stt_dir(self.base) / "whisper.zip").exists())
        self.assertTrue(listen_assets.remove(self.base))
        with mock.patch.dict(listen_assets.ENGINE, self.engine_info), mock.patch.dict(listen_assets.MODEL, self.model_info):
            self.assertFalse(listen_assets.installed(self.base))

    def test_a_file_that_doesnt_match_its_checksum_is_refused(self):
        self.files["model"] = b"something else"
        state, installed = self.run_download()
        self.assertEqual(state["stage"], "failed")
        self.assertIn("checksum", state["error"])
        self.assertFalse(installed)
        self.assertFalse(listen_assets.model_path(self.base).exists())

    def test_its_pins(self):
        self.assertIn("/b5454/", listen_assets.ENGINE["url"])
        self.assertIn("5359861c739e955e79d9a303bcbc70fb988958b1", listen_assets.MODEL["url"])
        self.assertEqual(len(listen_assets.ENGINE["sha256"]), 64)
        self.assertEqual(len(listen_assets.MODEL["sha256"]), 64)


class SettingsTests(unittest.TestCase):
    def test_settings_follow_the_commander(self):
        for key in ("watcher_listen_mic", "watcher_listen_mode", "overlay_hotkey_watcher_talk"):
            self.assertIn(key, config_module.PROFILE_TEXT_SETTINGS)
        self.assertIn("watcher_listen_enabled", config_module.PROFILE_BOOL_SETTINGS)

    def test_the_talk_key(self):
        self.assertIn(("watcher_talk", "overlay_hotkey_watcher_talk"), [spec[:2] for spec in OVERLAY_HOTKEY_SPECS])
        self.assertEqual(DEFAULT_OVERLAY_HOTKEYS["overlay_hotkey_watcher_talk"], "Ctrl+Alt+Shift+F8")
        bindings = {action: DEFAULT_OVERLAY_HOTKEYS.get(key, "") for action, key, _label, _attr in OVERLAY_HOTKEY_SPECS}
        self.assertEqual(validate_hotkey_bindings(bindings)[1], {}, "no default key used twice")
        source = (ROOT / "src/voidcompass/dashboard/dashboard.py").read_text(encoding="utf-8")
        self.assertIn('if action == "watcher_talk":\n            self._watcher_talk_key()', source)

    def test_main_dashboard_has_it(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        self.assertTrue(issubclass(MainDashboard, DashboardWatcherListenMixin))


class FakeMind:
    def __init__(self):
        self.said = []

    def talk(self, text, voice=False):
        self.said.append((text, voice))
        return True


class FakeLlm:
    def __init__(self):
        self.awake = True

    def listening(self):
        return self.awake


class Deck(DashboardWatcherListenMixin):
    _json_answer = staticmethod(DashboardJourneyMixin._json_answer)

    def __init__(self, config):
        self.config = config
        self.heartbeat_hud = type("Hud", (), {})()
        self.heartbeat_hud.mind = FakeMind()
        self.heartbeat_hud.set_hearing = lambda stage: self.hearing.append(stage)
        self.hearing = []
        self.llm = FakeLlm()
        self.feed = []
        self.begun = []
        self.saved = 0

    def _watcher_llm(self):
        return self.llm

    def _watcher_llm_facts(self):
        return {"system": "Sol", "ship": "Krait Phantom", "ship name": "Wanderer"}

    def _watcher_mind_watch(self):
        pass

    def _ui_post(self, callback, *args, key=None, **kwargs):
        callback(*args, **kwargs)

    def _schedule_html_dashboard_publish(self, immediate=False):
        pass

    def _persist_config(self):
        self.saved += 1

    def add_event_feed_entry(self, kind, text, severity="INFO"):
        self.feed.append(text)

    def _watcher_listen_begin(self, key=None, test=False):
        self.begun.append((key, test))
        return True


def deck_for(case, **config):
    base = {"watcher_listen_enabled": True, "watcher_llm_enabled": True, "watcher_listen_mode": "hold",
            "overlay_hotkey_watcher_talk": "Ctrl+Alt+Shift+F8"}
    deck = Deck({**base, **config})
    installed = mock.patch.object(listen_assets, "installed", return_value=True)
    installed.start()
    case.addCleanup(installed.stop)
    deck._watcher_listen = WatcherListener(lambda: deck.config, on_heard=deck._watcher_listen_heard,
                                           server_factory=FakeHearing, recorder_factory=FakeRecorder)
    return deck


class DeckTests(unittest.TestCase):
    def test_held_key_listens_until_let_go(self):
        deck = deck_for(self)
        deck._watcher_talk_key()
        self.assertEqual(deck.begun, [(0x77, False)], "F8 is watched for being let go")

    def test_tapped_key_starts_and_the_next_tap_stops(self):
        deck = deck_for(self, watcher_listen_mode="tap")
        deck._watcher_talk_key()
        self.assertEqual(deck.begun, [(None, False)])
        deck._watcher_listen._stage = "listening"
        with mock.patch.object(deck._watcher_listen, "stop") as stop:
            deck._watcher_talk_key()
        stop.assert_called_once()
        self.assertEqual(len(deck.begun), 1)

    def test_why_it_cant_listen_is_said_in_game_too(self):
        deck = deck_for(self, watcher_listen_enabled=False)
        deck._watcher_talk_key()
        self.assertEqual(deck.begun, [])
        self.assertIn("Voice in is off", deck.feed[-1])
        deck = deck_for(self)
        deck.llm.awake = False
        deck._watcher_talk_key()
        self.assertIn("own words", deck.feed[-1])
        deck = deck_for(self)
        deck.heartbeat_hud.mind = None
        deck._watcher_talk_key()
        self.assertIn("Overlay Studio", deck.feed[-1])

    def test_the_mic_test_needs_no_mind(self):
        deck = deck_for(self, watcher_llm_enabled=False)
        self.assertTrue(deck._handle_watcher_listen_command("listen_test", {}))
        self.assertEqual(deck.begun, [(None, True)])
        self.assertFalse(deck._handle_watcher_listen_command("listen_start", {}))

    def test_what_you_said_is_talk_marked_spoken(self):
        deck = deck_for(self)
        deck._watcher_listen_heard("Where are we?")
        self.assertEqual(deck.heartbeat_hud.mind.said, [("Where are we?", True)])

    def test_settings(self):
        deck = deck_for(self)
        with mock.patch.object(microphone, "devices", return_value=["Microphone (USB FS AUDIO)"]):
            self.assertFalse(deck._handle_watcher_listen_command("listen_settings", {"values": {"watcher_listen_mic": "Nope"}}))
            self.assertTrue(deck._handle_watcher_listen_command(
                "listen_settings", {"values": {"watcher_listen_mic": "Microphone (USB FS AUDIO)", "watcher_listen_mode": "tap"}}))
        self.assertEqual((deck.config["watcher_listen_mic"], deck.config["watcher_listen_mode"]), ("Microphone (USB FS AUDIO)", "tap"))
        deck._handle_watcher_listen_command("listen_settings", {"values": {"watcher_listen_mode": "shout"}})
        self.assertEqual(deck.config["watcher_listen_mode"], "tap")
        self.assertIsNone(deck._handle_watcher_listen_command("mind_talk", {}), "not one of its own")

    def test_switched_on_it_downloads_switched_off_it_stops(self):
        deck = deck_for(self, watcher_listen_enabled=False)
        with mock.patch.object(listen_assets, "installed", return_value=False), \
                mock.patch.object(Deck, "_watcher_listen_start_download") as download:
            deck._handle_watcher_listen_command("listen_toggle", {"value": True})
        download.assert_called_once()
        self.assertTrue(deck.config["watcher_listen_enabled"])
        with mock.patch.object(deck._watcher_listen, "stop_server") as stop:
            deck._handle_watcher_listen_command("listen_toggle", {"value": False})
            for thread in threading.enumerate():
                if thread.name == "watcher-hearing-stop":
                    thread.join(2)
        stop.assert_called_once()

    def test_the_page_and_the_meter(self):
        deck = deck_for(self)
        with mock.patch.object(microphone, "devices", return_value=["Microphone (USB FS AUDIO)"]):
            page = deck._html_watcher_listen()
        self.assertEqual(page["hotkey"], "Ctrl+Alt+Shift+F8")
        self.assertEqual(page["mics"], ["Microphone (USB FS AUDIO)"])
        self.assertEqual(page["mode"], "hold")
        self.assertNotIn("level", page, "a moving value redraws the page: the meter asks for it")
        self.assertNotIn("seconds", page)
        kind, body = deck._watcher_listen_data("listen")
        self.assertTrue(kind.startswith("application/json"))
        self.assertEqual(json.loads(body)["stage"], "idle")
        self.assertIsNone(deck._watcher_listen_data("listen-test"), "no test yet")

    def test_the_orb_follows(self):
        deck = deck_for(self)
        deck._watcher_listen._stage = "listening"
        deck._watcher_listen_show()
        self.assertEqual(deck.hearing, ["listening"])
        self.assertEqual(deck._watcher_listen_live()["stage"], "listening")

    def test_the_word_list_for_its_hearing(self):
        deck = deck_for(self)
        self.assertEqual(deck._watcher_listen_words()[:3], ["Sol", "Wanderer", "Krait Phantom"])


class MindTests(unittest.TestCase):
    def test_spoken_talk_is_marked(self):
        mind = watcher_mind.WatcherMind(None, {})
        mind.llm = FakeLlm()
        mind.action_provider = lambda words: "Done."
        self.assertTrue(mind.talk("Next track", voice=True))
        self.assertTrue(mind.memory["talk"][-1]["voice"])
        self.assertTrue(mind.talk("Next track"))
        self.assertNotIn("voice", mind.memory["talk"][-1])


class PageTests(unittest.TestCase):
    def test_the_mind_page(self):
        script = (ROOT / "web/dashboard/watcher.js").read_text(encoding="utf-8")
        for needle in ('id="watcher-talk-mic"', 'id="mind-hear"', 'id="watcher-hear-mic"', 'id="watcher-hear-mode"',
                       'id="watcher-hear-test"', 'id="watcher-hear-meter"', '"listen_start"', '"listen_stop"',
                       '"/api/data/listen"', "/api/data/listen-test", "Settings › Hotkeys", "SPOKEN"):
            self.assertIn(needle, script)
        style = (ROOT / "web/dashboard/watcher.css").read_text(encoding="utf-8")
        self.assertIn(".mind-mic[data-stage=\"listening\"]", style)
        self.assertIn(".mind-meter i", style)

    def test_the_orb_shows_it_listening(self):
        page = (ROOT / "web/heartbeat/index.html").read_text(encoding="utf-8")
        self.assertIn('id="hearing"', page)
        script = (ROOT / "web/heartbeat/app.js").read_text(encoding="utf-8")
        self.assertIn("live.hearing", script)
        self.assertIn("model.hearing", script)
        hud = (ROOT / "src/voidcompass/overlays/heartbeat_hud.py").read_text(encoding="utf-8")
        self.assertIn("'hearing': getattr(self, '_hearing', '')", hud)

    def test_the_hotkey_is_not_a_control_on_the_mind_page(self):
        script = (ROOT / "web/dashboard/watcher.js").read_text(encoding="utf-8")
        self.assertNotIn("overlay_hotkey_watcher_talk", script, "the key is set in Settings only")


if __name__ == "__main__":
    unittest.main()
