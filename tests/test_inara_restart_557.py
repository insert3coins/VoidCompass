"""5.5.7: restarting Void Compass mid-session doesn't send Inara the same
state again. What Inara accepted is remembered beside the waiting queue; a
new game session (LoadGame while running) still sends the whole state once."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from voidcompass.services import inara


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Inline:
    """Runs the uploader's send thread straight away."""

    def __init__(self, target=None, args=(), **_kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class InaraHarness(unittest.TestCase):
    """An uploader on temp files, its sends answered as Inara would."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.sent_path = str(Path(folder.name) / "inara_sent.json")
        self.queue_path = str(Path(folder.name) / "inara_queue.json")
        patcher = patch.object(inara.threading, "Thread", Inline)
        patcher.start()
        self.addCleanup(patcher.stop)

    def uploader(self, refuse=()):
        config = {"inara_upload_enabled": True, "inara_api_key": "key", "active_commander_name": "insert3coins"}
        session = Mock()

        def reply(*_args, **kwargs):
            events = json.loads(kwargs.get("data") or "{}").get("events") if kwargs.get("data") else None
            events = events or (kwargs.get("json") or {}).get("events") or []
            answer = Mock()
            answer.json.return_value = {"header": {"eventStatus": 200}, "events": [
                {"eventStatus": 400 if row["eventName"] in refuse else 200} for row in events]}
            return answer
        session.post.side_effect = reply
        up = inara.InaraUploader(config, "5.5.7", session=session, clock=lambda: 10_000.0,
                                 queue_path=self.queue_path, sent_path=self.sent_path)
        up.start = lambda: (up._load_queue(), up._load_sent())  # no timer thread in a test
        up.start()
        return up, session

    @staticmethod
    def sent(session):
        names = []
        for call in session.post.call_args_list:
            body = call.kwargs.get("json") or json.loads(call.kwargs.get("data") or "{}")
            names += [row["eventName"] for row in body.get("events") or []]
        return names

    def play(self, up, startup, credits=1000):
        up.observe("LoadGame", {"timestamp": stamp(), "Commander": "insert3coins", "Credits": credits, "Loan": 0,
                                "Ship": "panthermkii", "ShipID": 110}, startup=startup)
        up.observe("Rank", {"timestamp": stamp(), "Combat": 3, "Trade": 5, "Explore": 8}, startup=startup)
        up.flush(force=True)


class RestartTests(InaraHarness):
    def test_a_restart_sends_only_what_changed(self):
        first, session = self.uploader()
        self.play(first, startup=False)
        self.assertIn("setCommanderCredits", self.sent(session))
        first.stop()

        again, session = self.uploader()
        self.play(again, startup=True)
        self.assertEqual(self.sent(session), [], "the same session re-read after a restart: nothing new")
        again.observe("Rank", {"timestamp": stamp(), "Combat": 4, "Trade": 5, "Explore": 8}, startup=True)
        again.flush(force=True)
        self.assertEqual(self.sent(session), ["setCommanderRankPilot"], "only what changed goes")

    def test_a_new_game_session_sends_the_state_once(self):
        first, _session = self.uploader()
        self.play(first, startup=False)
        first.stop()
        again, session = self.uploader()
        self.play(again, startup=False)
        self.assertIn("setCommanderCredits", self.sent(session), "LoadGame while running: Inara wants it all")
        session.post.reset_mock()
        self.play(again, startup=True)
        self.assertEqual(self.sent(session), [])

    def test_only_what_inara_accepted_is_remembered(self):
        first, _session = self.uploader(refuse={"setCommanderCredits"})
        self.play(first, startup=False)
        first.stop()
        saved = json.loads(Path(self.sent_path).read_text(encoding="utf-8"))["state"]
        self.assertNotIn("setCommanderCredits", saved, "refused, so it can go again")
        self.assertIn("setCommanderRankPilot", saved)
        again, session = self.uploader()
        self.play(again, startup=True)
        self.assertEqual(self.sent(session), ["setCommanderCredits"])

    def test_the_app_keeps_it_with_the_commander(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"inara_sent.json"', source)


if __name__ == "__main__":
    unittest.main()
