"""Time capsules and On this day (5.5.3.7)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from voidcompass.dashboard.dashboard_capsules_mixin import DashboardCapsulesMixin
from voidcompass.exploration.time_capsules import CapsuleStore, NOTE_MAX, on_this_day, span_text, years_text
from voidcompass.overlays import watcher_lines, watcher_mind
from voidcompass.overlays.watcher_mind import WatcherMind, thought_heading

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DAY = 86400.0


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def folder(test):
    path = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, path, True)
    return path


class StoreTests(unittest.TestCase):
    def test_sealed_until_you_come_back(self):
        clock = Clock()
        where = folder(self)
        store = CapsuleStore(lambda: where, clock)
        capsule = store.leave("Hatchooe", "  Bring the   SRV next time. ", here="Hatchooe")
        self.assertEqual((capsule["system"], capsule["note"], capsule["opened_at"]), ("Hatchooe", "Bring the SRV next time.", None))
        clock.now += 90 * DAY
        self.assertEqual(store.deliver("Somewhere else"), [])
        opened = store.deliver("HATCHOOE")
        self.assertEqual([row["note"] for row in opened], ["Bring the SRV next time."])
        self.assertEqual(store.deliver("Hatchooe"), [], "opened once")
        again = CapsuleStore(lambda: where, clock).rows()
        self.assertEqual(again[0]["opened_at"], clock.now, "kept on disk")

    def test_an_arrival_before_it_was_left_doesnt_open_it(self):
        clock = Clock()
        where = folder(self)
        store = CapsuleStore(lambda: where, clock)
        store.leave("Sol", "hello")
        self.assertEqual(store.deliver("Sol", arrived_at=clock.now - 60), [], "an old journal read late")
        self.assertEqual(len(store.deliver("Sol", arrived_at=clock.now + 60)), 1)

    def test_several_open_oldest_first(self):
        clock = Clock()
        where = folder(self)
        store = CapsuleStore(lambda: where, clock)
        store.leave("Sol", "first")
        clock.now += 10
        store.leave("Sol", "second")
        clock.now += 10
        self.assertEqual([row["note"] for row in store.deliver("Sol")], ["first", "second"])

    def test_each_commander_their_own(self):
        roots = {"A": folder(self), "B": folder(self)}
        who = ["A"]
        store = CapsuleStore(lambda: roots[who[0]], Clock())
        store.leave("Sol", "for A")
        who[0] = "B"
        self.assertEqual(store.rows(), [])
        store.leave("Sol", "for B")
        who[0] = "A"
        self.assertEqual([row["note"] for row in store.rows()], ["for A"])
        with open(os.path.join(roots["B"], "capsules.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)[0]["note"], "for B")

    def test_what_can_be_left_and_removed(self):
        where = folder(self)
        store = CapsuleStore(lambda: where, Clock())
        self.assertIsNone(store.leave("", "note"))
        self.assertIsNone(store.leave("Sol", "   "))
        long = store.leave("Sol", "x" * 1000)
        self.assertEqual(len(long["note"]), NOTE_MAX)
        self.assertTrue(store.remove(long["id"]))
        self.assertFalse(store.remove(long["id"]))
        self.assertEqual(store.rows(), [])

    def test_how_long(self):
        self.assertEqual(span_text(600), "a few minutes")
        self.assertEqual(span_text(3 * 3600), "3 hours")
        self.assertEqual(span_text(DAY), "a day")
        self.assertEqual(span_text(20 * DAY), "2 weeks")
        self.assertEqual(span_text(95 * DAY), "3 months")
        self.assertEqual(span_text(366 * DAY), "a year")
        self.assertEqual(span_text(460 * DAY), "a year, 3 months")
        self.assertEqual(span_text(2.1 * 365.25 * DAY), "2 years, 1 month")
        self.assertEqual((years_text(1), years_text(3)), ("a year ago", "3 years ago"))


def row(stamp, system, jump=40.0, kind=""):
    return [stamp, system, 0.0, 0.0, 0.0, "K", jump, kind]


class OnThisDayTests(unittest.TestCase):
    def test_this_date_in_years_gone_by(self):
        today = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        rows = [row("2023-10-12T10:00:00Z", "Sol", 0, "L"), row("2025-10-11T23:00:00Z", "Yesterday"),
                row("2025-10-12T08:00:00Z", "Beagle Point"), row("2025-10-12T09:00:00Z", "Stop", 50.5),
                row("2025-10-12T20:00:00Z", "Colonia", 49.5), row("2025-10-13T01:00:00Z", "Tomorrow"),
                row("2026-10-12T08:00:00Z", "Today itself")]
        days = on_this_day(rows, today)
        self.assertEqual([(day["years"], day["first"], day["last"]) for day in days],
                         [(1, "Beagle Point", "Colonia"), (3, "Sol", "Sol")])
        self.assertEqual((days[0]["jumps"], days[0]["distance"], days[0]["systems"]), (3, 140.0, 3))
        self.assertEqual((days[1]["jumps"], days[1]["date"]), (0, "2023-10-12"), "a login isn't a jump")
        self.assertEqual(on_this_day([], today), [])


class WatcherTests(unittest.TestCase):
    def test_it_hands_back_your_own_words(self):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "rare"}, clock=clock)
        thought = mind.note("capsule", {"note": "Bring the SRV.", "span": "3 months", "system": "Hatchooe"})
        self.assertIn('"Bring the SRV."', thought["text"])
        self.assertEqual(thought_heading("capsule"), ("recall", "TIME CAPSULE"))
        self.assertEqual(thought_heading("on_this_day"), ("recall", "ON THIS DAY"))

    def test_not_when_its_thoughts_are_off(self):
        mind = WatcherMind(None, {"heartbeat_thoughts": "off"}, clock=Clock())
        self.assertIsNone(mind.note("capsule", {"note": "x", "span": "a day", "system": "Sol"}))

    def test_on_this_day_once_a_day(self):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "rare"}, clock=clock)
        self.assertTrue(mind.note("on_this_day", {"ago": "A year ago", "system": "Beagle Point"}))
        clock.now += 3600
        self.assertIsNone(mind.note("on_this_day", {"ago": "A year ago", "system": "Beagle Point"}))
        clock.now += DAY
        self.assertTrue(mind.note("on_this_day", {"ago": "A year ago", "system": "Beagle Point"}))

    def test_every_line_fills_in(self):
        fields = {"note": "N", "span": "S", "system": "Y", "ago": "A"}
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            for topic in ("capsule", "on_this_day"):
                for line in bank[topic]:
                    text = line.format(**fields)
                    self.assertNotIn("Marvin", text)
                    if topic == "capsule":
                        self.assertIn('"N"', text, "your note, word for word")


class Toasts:
    def __init__(self):
        self.pushed = []

    def push(self, title, message="", **options):
        self.pushed.append((title, message))


class Heartbeat:
    def __init__(self, says=True):
        self.says, self.notes = says, []

    def note(self, kind, fields=None):
        self.notes.append((kind, dict(fields or {})))
        return {"text": "said"} if self.says else None


class DeckTests(unittest.TestCase):
    def deck(self, heartbeat=None):
        class Deck(DashboardCapsulesMixin):
            pass
        deck = Deck()
        deck.config = {}
        deck.current_sys = "Hatchooe"
        deck.toast_hud, deck.heartbeat_hud, deck.feed = Toasts(), heartbeat, []
        deck.add_event_feed_entry = lambda *args, **kwargs: deck.feed.append(args)
        where = folder(self)
        deck._capsule_store = CapsuleStore(lambda: where)
        return deck

    def jump(self, system, event="FSDJump", replay=False, deck=None):
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return deck._capsule_arrival(event, {"event": event, "StarSystem": system, "timestamp": stamp}, replay)

    def test_the_watcher_hands_it_back(self):
        heartbeat = Heartbeat()
        deck = self.deck(heartbeat)
        self.assertTrue(deck._handle_capsules_command("leave", {"system": "", "note": "Bring the SRV."}))
        sealed = deck._html_capsules_workspace()["sealed"]
        self.assertEqual((sealed[0]["system"], sealed[0]["left_from"]), ("Hatchooe", "Hatchooe"), "empty: where you are")
        for capsule in deck._capsule_store._rows:
            capsule["left_at"] -= 3600
        self.assertEqual(self.jump("Hatchooe", "Location", deck=deck), [], "logging in there isn't coming back")
        self.assertEqual(self.jump("Hatchooe", replay=True, deck=deck), [], "not from the startup replay")
        opened = self.jump("Hatchooe", deck=deck)
        self.assertEqual(len(opened), 1)
        self.assertEqual(heartbeat.notes[0][0], "capsule")
        self.assertEqual(heartbeat.notes[0][1]["note"], "Bring the SRV.")
        self.assertEqual(deck.toast_hud.pushed, [], "the Watcher said it")
        self.assertEqual(len(deck._html_capsules_workspace()["opened"]), 1)

    def test_a_notice_when_the_watcher_is_quiet(self):
        deck = self.deck(Heartbeat(says=False))
        deck._handle_capsules_command("leave", {"system": "Colonia", "note": "Tritium in the depot."})
        for capsule in deck._capsule_store._rows:
            capsule["left_at"] -= 3600
        self.jump("Colonia", "CarrierJump", deck=deck)
        self.assertEqual(deck.toast_hud.pushed[0][0], "TIME CAPSULE · COLONIA")
        self.assertIn("Tritium in the depot.", deck.toast_hud.pushed[0][1])
        self.assertTrue(any(entry[0] == "CAPSULE" for entry in deck.feed))

    def test_removing_and_unknown_operations(self):
        deck = self.deck()
        deck._handle_capsules_command("leave", {"system": "Sol", "note": "x"})
        capsule_id = deck._html_capsules_workspace()["sealed"][0]["id"]
        self.assertTrue(deck._handle_capsules_command("remove", {"id": capsule_id}))
        self.assertFalse(deck._handle_capsules_command("open_all", {}))
        self.assertEqual(deck._html_capsules_workspace()["sealed"], [])

    def test_on_this_day_on_the_page_and_from_the_watcher(self):
        heartbeat = Heartbeat()
        deck = self.deck(heartbeat)
        year_ago = datetime.now().astimezone().replace(year=datetime.now().year - 1, hour=12)
        history = type("History", (), {})()
        history.lock = __import__("threading").Lock()
        history.rows = [row(year_ago.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "Beagle Point")]
        deck.travel_history = history
        days = deck._html_capsules_workspace()["on_this_day"]
        self.assertEqual((days[0]["first"], days[0]["ago"]), ("Beagle Point", "a year ago"))
        deck._on_this_day_watcher()
        self.assertEqual(heartbeat.notes[-1], ("on_this_day", {"ago": "A year ago", "system": "Beagle Point"}))
        self.assertIsNone(deck._on_this_day_watcher(startup_replay=True))


class WiringTests(unittest.TestCase):
    def test_it_is_a_deck_page(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="capsules"', html)
        self.assertIn('data-page-name="capsules"', html)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("capsules: (data) => renderCapsules(data, WORKSHOP_UI)", app)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("DashboardCapsulesMixin,", dashboard)
        self.assertIn("self._capsule_arrival(ev, history_raw, startup_replay)", dashboard)

    def test_topics_registered(self):
        for topic in ("capsule", "on_this_day"):
            self.assertIn(topic, watcher_mind.TOPICS)
            self.assertIn(topic, watcher_mind.MOODS)


if __name__ == "__main__":
    unittest.main()
