import json
import os
import tempfile
import unittest
import zipfile

from voidcompass.core.diagnostic_bundle import create_support_bundle
from voidcompass.core.onboarding import should_show
from voidcompass.core.persistence_queue import PersistenceQueue
from voidcompass.core.session_recovery import ProfileSessionGuard
from voidcompass.core.ui_dispatcher import ApplicationDispatcher


class _FakeRoot:
    def __init__(self):
        self.callbacks = []

    def call_later(self, _delay, callback):
        self.callbacks.append(callback)


class ReleaseFoundationTests(unittest.TestCase):
    def test_persistence_coalesces_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "state.json")
            queue = PersistenceQueue()
            queue.submit_json(path, {"value": 1}, delay_s=2)
            queue.submit_json(path, {"value": 2}, delay_s=2)
            self.assertTrue(queue.flush(path, timeout=2))
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["value"], 2)
            self.assertGreaterEqual(queue.stats()["coalesced"], 1)

    def test_session_guard_detects_stale_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "session.active")
            first = ProfileSessionGuard(path, "5.0.0")
            second = ProfileSessionGuard(path, "5.0.0")
            self.assertTrue(second.unclean)
            second.close()

    def test_support_bundle_redacts_secrets_and_raw_journal_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(os.path.join(folder, "logs"))
            with open(os.path.join(folder, "logs", "runtime_trace.log"), "w", encoding="utf-8") as handle:
                handle.write(r"C:\Users\Jeff\Saved Games")
            journal = os.path.join(folder, "journal")
            os.makedirs(journal)
            with open(os.path.join(journal, "Journal.01.log"), "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"timestamp": "now", "event": "FSDJump", "StarSystem": "Secret"}) + "\n")
            bundle = create_support_bundle(folder, {
                "edsm_api_key": "secret",
                "journal_path": journal,
                "commander_profiles": {"secret_commander-f123": {"fid": "F123"}},
                "active_commander_profile": "secret_commander-f123",
            }, "5.0.0")
            with zipfile.ZipFile(bundle) as archive:
                config = archive.read("config.redacted.json").decode()
                events = archive.read("journal-events.redacted.json").decode()
                log = archive.read("logs/runtime_trace.log").decode()
            self.assertNotIn("secret", config.casefold())
            self.assertNotIn("f123", config.casefold())
            self.assertNotIn("Secret", events)
            self.assertNotIn("Jeff", log)

    def test_onboarding_only_shows_until_completed(self):
        self.assertTrue(should_show({}))
        self.assertFalse(should_show({"onboarding_complete": True}))

    def test_application_dispatcher_coalesces_cross_thread_updates(self):
        root = _FakeRoot()
        dispatcher = ApplicationDispatcher(root)
        values = []
        dispatcher.post(values.append, "old", key="hud")
        dispatcher.post(values.append, "latest", key="hud")
        root.callbacks.pop(0)()
        dispatcher.stop()
        self.assertEqual(values, ["latest"])
        self.assertEqual(dispatcher.stats()["processed"], 1)


if __name__ == "__main__":
    unittest.main()
