"""Time capsules shared between commanders, with no server (5.5.4): codes
passed by hand, .vccapsule files, packs, capsules for a station or a body, and
the page's new options."""
from __future__ import annotations

from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

from voidcompass.dashboard import dashboard_capsules_mixin as mixin
from voidcompass.exploration import time_capsules as capsules
from voidcompass.overlays import watcher_lines, watcher_mind

ROOT = Path(__file__).resolve().parents[1]


def store(clock=1000.0):
    folder = tempfile.mkdtemp()
    return capsules.CapsuleStore(lambda: folder, clock=lambda: clock)


class CodeTests(unittest.TestCase):
    def test_a_code_round_trips_and_survives_a_message_around_it(self):
        mine = store()
        first = mine.leave("Colonia", "The geysers on A 1 are worth it", kind="memory", target="Colonia A 1")
        second = mine.leave("Sol", "Gold run", wait="year")
        code = capsules.encode([first, second], sender="insert3coins")
        self.assertTrue(code.startswith("VCCAP1-"))
        found, problem = capsules.decode(f"o7 here you go: {code} fly safe")
        self.assertEqual(problem, "")
        self.assertEqual([row["system"] for row in found], ["Colonia", "Sol"])
        self.assertEqual((found[0]["sender"], found[0]["target"], found[0]["kind"]), ("insert3coins", "Colonia A 1", "memory"))
        self.assertTrue(found[1]["not_before"])

    def test_a_damaged_code_is_refused_not_misread(self):
        code = capsules.encode([store().leave("Sol", "Hello")])
        self.assertIn("damaged", capsules.decode(code[:-1] + ("0" if code[-1] != "0" else "1"))[1])
        self.assertIn("VCCAP1", capsules.decode("just some words")[1])
        self.assertEqual(capsules.decode("")[0], [])

    def test_nothing_about_where_you_were_travels(self):
        row = store().leave("Sol", "Hello", here="Achenar")
        code_row = capsules._share_row(row)
        self.assertNotIn("Achenar", str(code_row))

    def test_a_file_carries_the_same(self):
        rows = [store().leave("Sol", "Hello")]
        text = capsules.export_file(rows, sender="Jameson")
        found, problem = capsules.decode(text)
        self.assertEqual((problem, found[0]["note"], found[0]["sender"]), ("", "Hello", "Jameson"))
        self.assertIn("isn't a capsule file", capsules.decode('{"format": "something else"}')[1])

    def test_packs_are_capped(self):
        mine = store()
        rows = [mine.leave("Sol", f"note {index}") for index in range(capsules.PACK_MAX + 5)]
        self.assertEqual(len(capsules.decode(capsules.encode(rows))[0]), capsules.PACK_MAX)


class ReceivingTests(unittest.TestCase):
    def test_received_once_and_opened_where_they_were_left(self):
        mine = store()
        code = capsules.encode([mine.leave("Colonia", "Land here", target="Colonia A 1"),
                                mine.leave("Colonia", "Welcome to Colonia")], sender="Jameson")
        theirs = store(clock=2000.0)
        found, _problem = capsules.decode(code)
        self.assertEqual(theirs.receive(found), 2)
        self.assertEqual(theirs.receive(found), 0, "the same code twice adds nothing")
        self.assertEqual([row["note"] for row in theirs.deliver("Colonia", 3000)], ["Welcome to Colonia"])
        self.assertEqual([row["target"] for row in theirs.waiting_here("Colonia")], ["Colonia A 1"])
        self.assertEqual(theirs.deliver("Colonia", 3000, place="Jameson Memorial"), [])
        landed = theirs.deliver("Colonia", 3000, place="Colonia A 1")
        self.assertEqual((landed[0]["note"], landed[0]["sender"]), ("Land here", "Jameson"))

    def test_a_date_and_resealing(self):
        mine = store()
        dated = mine.leave("Sol", "Happy anniversary", wait="date", opens_on=5000.0)
        self.assertEqual(dated["not_before"], 5000.0)
        self.assertEqual(mine.deliver("Sol", 3000), [], "not before its date")
        self.assertEqual(len(mine.deliver("Sol", 6000)), 1)
        again = mine.reseal(dated["id"], wait="year")
        self.assertEqual(again["note"], "Happy anniversary")
        self.assertIsNone(again["opened_at"])


class DeckTests(unittest.TestCase):
    def deck(self):
        deck = mixin.DashboardCapsulesMixin()
        deck.config = {"capsule_sign_shares": True, "active_commander_name": "insert3coins"}
        deck.cmdr_name = "insert3coins"
        deck._capsule_store = store()
        deck.current_sys = "Sol"
        deck._html_copy_text = Mock(return_value=True)
        deck.add_event_feed_entry = Mock()
        deck._persist_config = Mock()
        return deck

    def test_share_copies_a_code_with_a_line_explaining_it(self):
        deck = self.deck()
        self.assertTrue(deck._handle_capsules_command("leave", {"system": "Sol", "note": "Hi", "kind": "greeting",
                                                                 "target": "Abraham Lincoln", "wait": "date",
                                                                 "opens_on": "2099-01-01"}))
        row = deck.capsule_store().rows()[0]
        self.assertEqual((row["kind"], row["target"]), ("greeting", "Abraham Lincoln"))
        self.assertGreater(row["not_before"], 4_000_000_000)
        self.assertTrue(deck._handle_capsules_command("share", {"ids": [row["id"]]}))
        message = deck._html_copy_text.call_args[0][0]
        self.assertIn("CMDR insert3coins", message)
        self.assertIn("VCCAP1-", message)
        self.assertEqual(capsules.decode(message)[0][0]["note"], "Hi")

    def test_export_preview_and_receive(self):
        deck = self.deck()
        deck._handle_capsules_command("leave", {"system": "Sol", "note": "Hi"})
        row = deck.capsule_store().rows()[0]
        folder = Path(tempfile.mkdtemp())
        with patch.object(mixin.DashboardCapsulesMixin, "capsule_folder", staticmethod(lambda: folder)):
            self.assertTrue(deck._handle_capsules_command("export", {"ids": [row["id"]]}))
        saved = list(folder.glob("*.vccapsule"))
        self.assertEqual(len(saved), 1)
        other = self.deck()
        text = saved[0].read_text(encoding="utf-8")
        self.assertTrue(other._handle_capsules_command("preview", {"text": text}))
        self.assertEqual((other._capsule_preview["count"], other._capsule_preview["senders"]), (1, ["insert3coins"]))
        self.assertEqual(other.capsule_store().rows(), [], "a preview adds nothing")
        self.assertTrue(other._handle_capsules_command("receive", {"text": text}))
        self.assertEqual(len(other.capsule_store().rows()), 1)
        self.assertFalse(other._handle_capsules_command("receive", {"text": "nonsense"}))
        self.assertIn("VCCAP1", other._capsule_preview["problem"])

    def test_received_notes_stay_unread_on_the_page(self):
        deck = self.deck()
        deck._on_this_day = lambda: []
        found, _problem = capsules.decode(capsules.encode([store().leave("Colonia", "Secret")], sender="Jameson"))
        deck.capsule_store().receive(found)
        page = deck._html_capsules_workspace()
        self.assertEqual(page["received"][0]["note"], "")
        self.assertTrue(page["received"][0]["hidden"])
        self.assertEqual(page["vault"]["received"], 1)

    def test_unsigned_when_asked(self):
        deck = self.deck()
        deck.config["capsule_sign_shares"] = False
        self.assertEqual(deck._capsule_sender(), "")


class WatcherTests(unittest.TestCase):
    def test_it_hands_back_another_commanders_words(self):
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            self.assertGreaterEqual(len(bank["capsule_shared"]), 10)
        mind = watcher_mind.WatcherMind(None, {"heartbeat_thoughts": "rare"}, lambda: 1_800_000_000.0, random.Random(4))
        thought = mind.note("capsule_shared", {"sender": "CMDR Jameson", "note": "Hello", "span": "a year", "system": "Sol"})
        self.assertIn("Jameson", thought["text"])
        self.assertEqual(watcher_mind.thought_heading("capsule_shared")[1], "TIME CAPSULE · FROM ANOTHER COMMANDER")

    def test_settings_are_per_commander(self):
        from voidcompass.core import config
        for key in ("capsule_sign_shares", "capsule_hide_received"):
            self.assertIn(key, config.PROFILE_BOOL_SETTINGS)
        page = (ROOT / "web" / "dashboard" / "capsules.js").read_text(encoding="utf-8")
        for needed in ("data-capsule-share-chosen", "capsule-file", "data-capsule-receive", "data-capsule-reseal", 'type="date"'):
            self.assertIn(needed, page)


if __name__ == "__main__":
    unittest.main()
