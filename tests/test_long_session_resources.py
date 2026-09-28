"""What a long session with Void Compass open must not wear out.

The command deck's page was lost every 17-20 minutes with music on: each of
its fifteen-a-second visualizer reports left its fetch reply unread, and an
unread reply holds native buffers until the garbage collector happens by, so
the page's process grew about 40 MB a minute until WebView2 dropped it. The
survey and Captain's Log also forgot which journals they had read once there
were more than 400, and reread the oldest at every start; and profile files
were written with the slow pure-Python JSON encoder.
"""

import json
from pathlib import Path
import re
import tempfile
import unittest

from voidcompass.core.persistence_queue import PersistenceQueue, flush_persistence
from voidcompass.exploration.captains_log import CaptainsLog
from voidcompass.exploration.deep_survey import LIMITS, DeepSurveyTracker

WEB = Path(__file__).resolve().parents[1] / "web"


class FetchRepliesAreReadTests(unittest.TestCase):
    def test_the_frequent_reporters_read_every_reply(self):
        music = (WEB / "dashboard" / "music.js").read_text(encoding="utf-8")
        post = music[music.index("function post(payload"):]
        post = post[:post.index("\n  }\n")]
        self.assertIn("response.arrayBuffer()", post, "visualizer levels, fifteen a second")
        client = (WEB / "assets" / "overlay-client.js").read_text(encoding="utf-8")
        for path in ("/api/ready", "/api/rendered"):
            call = client[client.index(f"fetch(`{path}"):]
            self.assertIn("await drain(response)", call[:call.index("response.ok")], path)
        atlas = (WEB / "galactic_map" / "app.js").read_text(encoding="utf-8")
        command = atlas[atlas.index("function command(payload)"):]
        self.assertIn("arrayBuffer()", command[:command.index("\n}\n")], "the atlas heartbeat")
        deck = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        sender = deck[deck.index("async function command(action"):]
        self.assertIn("arrayBuffer()", sender[:sender.index("\n}\n")])

    def test_no_fire_and_forget_post_ignores_its_reply(self):
        # A POST whose promise goes straight to .catch never reads its reply.
        for file in WEB.rglob("*.js"):
            if "vendor" in file.parts:
                continue
            text = file.read_text(encoding="utf-8")
            for match in re.finditer(r"fetch\([^;]*?method:\s*['\"]POST['\"][^;]*?\}\)\s*\.catch", text, re.S):
                self.fail(f"{file.relative_to(WEB)} posts without reading the reply: {match.group(0)[:80]}")


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.queue = PersistenceQueue()

    def test_large_files_are_written_compact_and_the_slowest_is_named(self):
        compact, pretty = self.root / "survey.json", self.root / "settings.json"
        self.queue.submit_json(compact, {"rows": [{"a": 1}, {"b": 2}]}, indent=None, immediate=True)
        self.queue.submit_json(pretty, {"a": 1}, indent=2, immediate=True)
        self.assertTrue(self.queue.flush(timeout=5))
        self.assertEqual(compact.read_text(encoding="utf-8"), '{"rows":[{"a":1},{"b":2}]}')
        self.assertEqual(json.loads(pretty.read_text(encoding="utf-8")), {"a": 1})
        self.assertIn("\n", pretty.read_text(encoding="utf-8"))
        self.assertIn(self.queue.stats()["max_write_file"], {"survey.json", "settings.json"})


class JournalBookkeepingTests(unittest.TestCase):
    def test_every_journal_read_is_remembered(self):
        self.assertGreaterEqual(LIMITS["imported_files"], 10000)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        journals = Path(folder.name) / "journals"
        journals.mkdir()
        for index in range(450):
            (journals / f"Journal.2026-01-01T{index:06d}.01.log").write_text(
                json.dumps({"timestamp": "2026-01-01T00:00:00Z", "event": "Fileheader"}) + "\n", encoding="utf-8")
        for tracker in (DeepSurveyTracker(str(Path(folder.name) / "deep.json")),
                        CaptainsLog(str(Path(folder.name) / "log.json"))):
            with self.subTest(tracker=type(tracker).__name__):
                tracker.import_journals(str(journals))
                self.assertEqual(len(tracker.data["imported_files"]), 450)
                flush_persistence(tracker.path, timeout=5)


if __name__ == "__main__":
    unittest.main()
