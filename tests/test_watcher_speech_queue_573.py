"""Speech finishes before another line starts; hush cancels all waiting work."""
from array import array
import json
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import wave

from voidcompass.dashboard.dashboard_watcher_listen_mixin import DashboardWatcherListenMixin
from voidcompass.voice import watcher_voice


class SpeechQueueTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.synthesized = []
        self.played = []
        self.changed = []
        self.condition = threading.Condition()
        self.synthesizing = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.duration = 0.12
        self.payload = None

        def write(payload):
            self.payload = json.loads(payload)

        def flush():
            payload = self.payload
            self.synthesized.append(payload["text"])
            self.synthesizing.set()
            if not self.release.wait(3):
                raise OSError("test synthesis gate timed out")
            with wave.open(payload["output_file"], "wb") as wav:
                wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                wav.writeframes(array("h", [1000 * len(self.synthesized)] * int(8000 * self.duration)).tobytes())

        def play(path):
            sample = None
            if path is not None:
                with wave.open(path, "rb") as wav:
                    sample = array("h", wav.readframes(1))[0]
            with self.condition:
                self.played.append((sample, time.monotonic()))
                self.condition.notify_all()

        def changed():
            live = self.speaker.live()
            with self.condition:
                self.changed.append((live["key"] if live else None, time.monotonic()))
                self.condition.notify_all()

        self.speaker = watcher_voice.WatcherSpeaker(folder.name, player=play, on_change=changed,
                                                    settings=lambda: {"watcher_voice_volume": 100})
        engine = SimpleNamespace(stdin=SimpleNamespace(write=write, flush=flush),
                                 stdout=SimpleNamespace(readline=lambda: "ready\n"))
        self.speaker._ensure_engine = lambda: engine
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.release.set()
        self.speaker.close()
        if self.speaker._worker is not None:
            self.speaker._worker.join(2)
            self.assertFalse(self.speaker._worker.is_alive())

    def wait_for(self, predicate, timeout=4):
        with self.condition:
            self.assertTrue(self.condition.wait_for(predicate, timeout), (self.played, self.changed))

    def starts(self):
        return [(sample, at) for sample, at in self.played if sample is not None]

    def test_lines_arriving_during_synthesis_and_playback_wait_in_order_with_a_pause(self):
        self.release.clear()
        self.assertTrue(self.speaker.say("First.", 1))
        self.assertTrue(self.synthesizing.wait(2))
        self.speaker.say("Second.", 2)
        self.release.set()
        self.wait_for(lambda: len(self.starts()) == 1)
        self.speaker.say("Third.", 3)
        self.wait_for(lambda: len(self.changed) == 6)
        self.assertEqual(self.synthesized, ["First.", "Second.", "Third."])
        self.assertEqual([sample for sample, _ in self.starts()], [1000, 2000, 3000])
        self.assertEqual([key for key, _ in self.changed], [1, None, 2, None, 3, None])
        for index in (0, 2):
            began, ended, following = self.changed[index:index + 3]
            self.assertGreaterEqual(ended[1] - began[1], self.duration - .02)
            self.assertGreaterEqual(following[1] - ended[1], watcher_voice.SPEECH_PAUSE_S - .02)
        self.assertFalse(any(sample is None for sample, _ in self.played), "new lines never stop playback")

    def test_hush_stops_playback_discards_queue_and_new_speech_can_start_immediately(self):
        self.duration = 2
        self.speaker.say("Playing.", 1)
        self.wait_for(lambda: len(self.starts()) == 1)
        self.speaker.say("Discard this.", 2)
        self.speaker.stop()
        stopped = time.monotonic()
        self.assertIsNone(self.played[-1][0])
        self.assertIsNone(self.speaker.live())
        self.speaker.say("Fresh.", 3)
        self.wait_for(lambda: len(self.starts()) == 2)
        self.assertEqual(self.synthesized, ["Playing.", "Fresh."])
        self.assertLess(self.starts()[1][1] - stopped, 1)

    def test_hush_while_synthesizing_discards_unplayed_audio(self):
        self.release.clear()
        self.speaker.say("Discard this.", 1)
        self.assertTrue(self.synthesizing.wait(2))
        self.speaker.stop()
        self.speaker.say("Fresh.", 2)
        self.release.set()
        self.wait_for(lambda: len(self.starts()) == 1)
        self.assertEqual([sample for sample, _ in self.starts()], [2000])
        self.assertEqual(self.speaker.live()["key"], 2)

    def test_caption_status_distinguishes_synthesis_queue_playback_and_cancellation(self):
        self.release.clear()
        self.speaker.say('Loading.', 1)
        self.assertTrue(self.synthesizing.wait(2))
        self.assertEqual(self.speaker.status(1), 'preparing')
        self.speaker.say('Waiting.', 2)
        self.assertEqual(self.speaker.status(2), 'queued')
        self.release.set()
        self.wait_for(lambda: len(self.starts()) == 1)
        self.assertEqual(self.speaker.status(1), 'playing')
        self.wait_for(lambda: len(self.changed) >= 2)
        self.assertEqual(self.speaker.status(1), 'finished')
        self.speaker.stop()
        self.assertEqual(self.speaker.status(2), 'cancelled')

    def test_unavailable_engine_releases_the_caption_wait(self):
        self.speaker._ensure_engine = lambda: None
        self.speaker.say('Text fallback.', 10)
        self.wait_for(lambda: self.speaker.status(10) == 'failed', timeout=.5)

    def test_talk_microphone_clears_queue_during_the_pause(self):
        self.speaker.say("First.", 1)
        self.wait_for(lambda: len(self.changed) == 1)
        self.speaker.say("Discard this.", 2)
        self.wait_for(lambda: len(self.changed) == 2)
        self.assertIsNone(self.speaker.live())
        deck = DashboardWatcherListenMixin()
        deck._watcher_voice = self.speaker
        deck._watcher_listen_quiet()
        self.assertFalse(self.speaker._pending)
        self.speaker.say("Fresh.", 3)
        self.wait_for(lambda: len(self.starts()) == 2)
        self.assertEqual(self.synthesized, ["First.", "Fresh."])
        self.assertEqual(self.speaker.live()["key"], 3)


if __name__ == "__main__":
    unittest.main()
