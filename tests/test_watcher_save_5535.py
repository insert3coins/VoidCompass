"""5.5.3.5: the game's Shutdown, then the Watcher's sign-off, then its memory
on disk. It saved at Shutdown, but the sign-off comes a moment later (once
the Captain's Log has the session's figures), and that waited for the
periodic save: up to five minutes, so a quick close or a killed app lost it,
and the Watcher could repeat a sign-off line it had already used."""

import json
from pathlib import Path
import tempfile
import unittest

from tests.test_watcher_mind import Always, Clock
from voidcompass.overlays.watcher_mind import WatcherMind


class SignOffSavedTests(unittest.TestCase):
    def test_the_sign_off_is_on_disk_at_once(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            mind = WatcherMind(path, {"heartbeat_thoughts": "rare"}, clock, Always())
            mind.observe("LoadGame")
            for _ in range(12):  # two hours of play, an event every 10 minutes
                clock.now += 600
                mind.observe("FuelScoop", {})
            mind.observe("Shutdown")  # the dashboard sends the sign-off after this
            thought = mind.note("sign_off", {"summary": "41 jumps and 12.4M credits", "hours": "2h 00m"})
            self.assertEqual(thought["topic"], "sign_off")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["log"][-1][1:], ["sign_off", thought["text"]], "on disk without waiting")
            self.assertTrue(any(row[0] == "sign_off" for row in saved["said"]), "remembered, so never repeated")
            self.assertGreaterEqual(saved["hours"], 2.0, "the hours together counted to the end")

    def test_a_save_restarts_the_periodic_timer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            mind = WatcherMind(path, {"heartbeat_thoughts": "rare"}, Clock(), Always())
            mind._unsaved = True
            mind.save()
            self.assertFalse(mind._unsaved)
            path.unlink()
            mind.save_if_due()
            self.assertFalse(path.exists(), "nothing new since the save: no second write")


class AppCloseSavesTests(unittest.TestCase):
    """Closing Void Compass only hides the orb; HeartbeatHUD.destroy (which
    saved) never ran, so thoughts since the last periodic save were lost."""

    def test_closing_the_app_writes_the_memory(self):
        import inspect
        from types import SimpleNamespace
        from voidcompass.dashboard.dashboard import MainDashboard

        clock = Clock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            mind = WatcherMind(path, {"heartbeat_thoughts": "rare"}, clock, Always())
            mind.observe("LoadGame")
            clock.now += 120
            app = MainDashboard.__new__(MainDashboard)
            app.heartbeat_hud = SimpleNamespace(mind=mind)
            app._save_watcher_memory()
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["last_seen"], clock.now)
            self.assertIn("self._save_watcher_memory()", inspect.getsource(MainDashboard.on_close))

    def test_no_orb_no_save(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        app = MainDashboard.__new__(MainDashboard)
        app.heartbeat_hud = None
        app._save_watcher_memory()  # nothing to save, nothing raised


if __name__ == "__main__":
    unittest.main()
