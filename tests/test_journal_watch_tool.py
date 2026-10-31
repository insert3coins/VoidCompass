"""tools/journal_watch.py: a developer tool, separate from Void Compass, that
spots journal events and fields the game starts writing after an update."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.journal_watch import Watch, describe

ROOT = Path(__file__).resolve().parents[1]
BEFORE = [
    {"timestamp": "2026-10-20T10:00:00Z", "event": "FSDJump", "StarSystem": "Sol"},
    {"timestamp": "2026-10-20T10:05:00Z", "event": "Bounty", "Target": "pirate", "TotalReward": 1000},
]


class JournalWatchTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.journals = self.root / "journals"
        self.journals.mkdir()
        self.journal = self.journals / "Journal.2026-10-20T100000.01.log"
        self.write(BEFORE)

    def write(self, rows, text=None):
        with open(self.journal, "a", encoding="utf-8") as handle:
            handle.write(text if text is not None else "".join(json.dumps(row) + "\n" for row in rows))

    def watch(self):
        return Watch(self.root / "seen.json", self.root / "report.jsonl")

    def test_after_an_update(self):
        watch = self.watch()
        self.assertEqual(watch.learn(self.journals), 2)
        self.assertEqual(watch.check(self.journals), [], "nothing new yet")
        self.write([{"timestamp": "2026-10-27T09:00:00Z", "event": "FSDJump", "StarSystem": "Lave"},
                    {"timestamp": "2026-10-27T09:01:00Z", "event": "CrimeReport", "Fine": 400},
                    {"timestamp": "2026-10-27T09:02:00Z", "event": "Bounty", "Target": "x", "TotalReward": 5, "Notoriety": 2},
                    {"timestamp": "2026-10-27T09:03:00Z", "event": "CrimeReport", "Fine": 900}])
        found = self.watch().check(self.journals)
        self.assertEqual([(row["event"], row["new_event"], row["new_keys"]) for row in found],
                         [("CrimeReport", True, []), ("Bounty", False, ["Notoriety"])])
        report = [json.loads(line) for line in (self.root / "report.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(report[0]["example"]["Fine"], 400)
        self.assertIn("NEW EVENT", describe(found[0]))
        self.assertIn("Notoriety", describe(found[1]))

    def test_only_whole_lines_and_only_once(self):
        watch = self.watch()
        watch.learn(self.journals)
        self.write([], '{"timestamp": "2026-10-27T09:00:00Z", "event": "MiningRig')
        self.assertEqual(watch.check(self.journals), [], "the game is still writing that line")
        self.write([], 'Complete", "Rig": 1}\n')
        self.assertEqual([row["event"] for row in watch.check(self.journals)], ["MiningRigComplete"])
        self.assertEqual(watch.check(self.journals), [])

    def test_never_part_of_the_app(self):
        tool = (ROOT / "tools" / "journal_watch.py").read_text(encoding="utf-8")
        self.assertNotIn("voidcompass", tool.split('"""', 2)[2])
        for path in (ROOT / "src").rglob("*.py"):
            self.assertIsNone(re.search(r"\bjournal_watch\b", path.read_text(encoding="utf-8")), path)
        self.assertIn("tools/journal_watch/", (ROOT / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
