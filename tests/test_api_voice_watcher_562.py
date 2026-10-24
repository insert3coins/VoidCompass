"""5.6.2: the Watcher's API made whole, and its voice sharing the air.

Answer its question, share it, meet another, keep its book; and for another
app's voice, hush it (for a while, or until lifted) and hear when it starts
and stops, so the two take turns."""

import math
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_local_api_557 import Provider, ServerCase
from voidcompass.dashboard.dashboard_api_mixin import DashboardApiMixin
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays.watcher_mind import WatcherMind
from voidcompass.services.local_api import ApiError, LocalApi
from voidcompass.voice.watcher_voice import WatcherSpeaker

ROOT = Path(__file__).resolve().parents[1]


class FakeSpeaker:
    def __init__(self, owner):
        self.owner, self.speaking, self.said = owner, False, []

    def say(self, words, key=None, feel=None):
        self.said.append(words)
        return True

    def start(self):
        self.speaking = True
        self.owner._watcher_voice_changed()

    def finish(self):
        self.speaking = False
        self.owner._watcher_voice_changed()

    def stop(self):
        was, self.speaking = self.speaking, False
        if was:
            self.owner._watcher_voice_changed()

    def live(self):
        return {"key": None} if self.speaking else None


class Deck(DashboardWatcherVoiceMixin, DashboardApiMixin):
    def __init__(self):
        self.config = {"watcher_voice_enabled": True}
        self.events = []
        self._watcher_voice = FakeSpeaker(self)

    def _api_publish(self, kind, data):
        self.events.append((kind, data))


@patch("voidcompass.voice.voice_assets.installed", return_value=True)
class HushTests(unittest.TestCase):
    def test_hushed_for_a_while_then_lifted(self, _installed):
        deck = Deck()
        deck._watcher_voice.start()
        answer = deck.api_voice_hush(30)
        self.assertTrue(answer["hushed"])
        self.assertTrue(28 <= answer["hushed_for"] <= 30)
        self.assertEqual(deck.events[-1], ("voice", {"state": "hushed", "from": "watcher"}), "cut off, and said so")
        self.assertFalse(deck._watcher_voice_say("Another star."), "its own thoughts aren't said while hushed")
        with self.assertRaises(ApiError) as caught:
            deck.api_voice_say("Hello")
        self.assertEqual(caught.exception.status, 409)
        self.assertTrue(deck.api_voice()["hushed"])
        self.assertFalse(deck.api_voice_hush(0)["hushed"], "0 lifts it")
        self.assertTrue(deck._watcher_voice_say("Another star."))

    def test_hushed_until_lifted(self, _installed):
        deck = Deck()
        answer = deck.api_voice_hush(None)
        self.assertEqual((answer["hushed"], answer["hushed_for"]), (True, None))
        self.assertEqual(deck._voice_hush_until, math.inf)
        self.assertEqual(deck.events, [], "nothing was being said, so nothing was cut off")

    def test_started_then_finished_or_stopped(self, _installed):
        deck = Deck()
        deck._watcher_voice_say("Hello, Commander.", key="api-1")
        self.assertEqual(deck.events[-1], ("voice", {"state": "started", "text": "Hello, Commander.", "from": "api"}))
        deck._watcher_voice.start()
        deck._watcher_voice.finish()
        self.assertEqual(deck.events[-1], ("voice", {"state": "finished", "from": "api"}))
        deck._watcher_voice.start()
        deck.api_voice_stop()
        self.assertEqual(deck.events[-1], ("voice", {"state": "stopped", "from": "api"}))
        deck._watcher_voice.finish()
        self.assertEqual(len([row for row in deck.events if row[1]["state"] != "started"]), 2, "each end said once")


class SpeakerEndTests(unittest.TestCase):
    def test_a_line_ending_is_told_without_polling(self):
        told = []
        speaker = WatcherSpeaker(on_change=lambda: told.append(speaker.live()), player=lambda path: None)
        start = time.time()
        speaker._live = {"key": None, "start": start, "duration": 5.0, "envelope": []}
        speaker._ended(start - 1)
        self.assertEqual(told, [], "an older line's timer is ignored")
        speaker._ended(start)
        self.assertEqual(told, [None])
        self.assertIsNone(speaker._live)


class Routes(Provider):
    def __init__(self):
        super().__init__()
        self.calls = []

    def api_voice_hush(self, seconds):
        self.calls.append(("hush", seconds))
        return {"hushed": seconds != 0}

    def api_watcher_answer(self, answer):
        self.calls.append(("answer", answer))
        return {"answered": True}

    def api_watcher_code(self):
        return {"code": "VCWATCH1abc"}

    def api_watcher_meet(self, code):
        self.calls.append(("meet", code))
        return {"met": True}

    def api_watcher_book(self):
        return {"saved": True}


class RouteTests(ServerCase):
    def setUp(self):
        self.provider = Routes()
        self.api = LocalApi(self.provider, version="test")
        from tests.test_local_api_557 import free_port
        self.port = free_port()
        self.assertTrue(self.api.configure(enabled=True, port=self.port))
        self.addCleanup(self.api.stop)

    def test_hush_takes_seconds_none_or_zero(self):
        self.assertEqual(self.call("/voice/hush", "POST", {"seconds": 30})[0], 200)
        self.assertEqual(self.call("/voice/hush", "POST", {})[0], 200)
        self.assertEqual(self.call("/voice/hush", "POST", {"seconds": "0"})[0], 200)
        self.assertEqual(self.call("/voice/hush", "POST", {"seconds": 99999999})[0], 200)
        self.assertEqual(self.provider.calls, [("hush", 30), ("hush", None), ("hush", 0), ("hush", 86400)])
        self.assertEqual(self.call("/voice/hush", "POST", {"seconds": "soon"})[0], 400)

    def test_the_watcher_routes(self):
        self.assertEqual(self.call("/watcher/answer", "POST", {"answer": 2}), (200, {"answered": True}))
        self.call("/watcher/answer", "POST", {"answer": "less"})
        self.assertEqual(self.call("/watcher/answer", "POST", {})[0], 400)
        self.assertEqual(self.call("/watcher/code")[1], {"code": "VCWATCH1abc"})
        self.assertEqual(self.call("/watcher/meet", "POST", {"code": "VCWATCH1xyz"})[0], 200)
        self.assertEqual(self.call("/watcher/meet", "POST", {"code": ""})[0], 400)
        self.assertEqual(self.call("/watcher/book", "POST", {})[1], {"saved": True})
        self.assertEqual(self.provider.calls, [("answer", 2), ("answer", "less"), ("meet", "VCWATCH1xyz")])

    def test_changes_need_control(self):
        self.api.configure(enabled=True, port=self.port, allow_control=False)
        for path in ("/voice/hush", "/watcher/answer", "/watcher/meet", "/watcher/book"):
            self.assertEqual(self.call(path, "POST", {"seconds": 1, "answer": 1, "code": "x"})[0], 403, path)
        self.assertEqual(self.call("/watcher/code")[0], 200, "reading the code is fine")


class WatcherAnswerTests(unittest.TestCase):
    def test_answered_by_number_or_key_and_only_when_asked(self):
        class App(DashboardApiMixin):
            pass

        with tempfile.TemporaryDirectory() as folder:
            mind = WatcherMind(Path(folder, "memory.json"), {"heartbeat_thoughts": "occasional"})
            app = App()
            app.config = {}
            hud = SimpleNamespace(mind=mind, answer=lambda answer: mind.answer(answer), _redraw=lambda: None)
            app.heartbeat_hud = hud
            app._watcher_mind = lambda: mind
            app._watcher_answer = lambda answer: bool(hud.answer(answer))
            with self.assertRaises(ApiError) as caught:
                app.api_watcher_answer(1)
            self.assertEqual(caught.exception.status, 409)
            self.assertTrue(mind.ask("talk_less", force=True))
            with self.assertRaises(ApiError) as caught:
                app.api_watcher_answer(7)
            self.assertEqual(caught.exception.status, 400)
            self.assertEqual(app.api_watcher_answer(2), {"answered": True, "question": "talk_less"})
            self.assertEqual(mind.memory["questions"]["talk_less"]["answer"], "same")


class DocsTests(unittest.TestCase):
    def test_the_new_routes_and_events_are_documented(self):
        api = (ROOT / "api.md").read_text(encoding="utf-8")
        for text in ("/api/v1/voice/hush", "/api/v1/watcher/answer", "/api/v1/watcher/code", "/api/v1/watcher/meet",
                     "/api/v1/watcher/book", "Sharing the air with your own voice", '"state": "finished"', "`hushed_for`"):
            self.assertIn(text, api)


if __name__ == "__main__":
    unittest.main()
