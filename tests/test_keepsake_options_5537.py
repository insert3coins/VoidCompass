"""Time Capsules and Constellation settings and extras (5.5.3.7): "Not
before…", how capsules are handed back, capsules on the Galaxy Minimap, and
the constellation's choices, tonight's star and the Watcher naming one."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest

from tests.test_constellation_5537 import history
from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_capsules_mixin import (
    CAPSULE_SETTINGS, CONSTELLATION_SETTINGS, DashboardCapsulesMixin, wait_text,
)
from voidcompass.exploration.constellation import constellation_options, constellations
from voidcompass.exploration.time_capsules import CapsuleStore
from voidcompass.overlays import watcher_lines, watcher_mind
from voidcompass.overlays.galaxy_minimap_hud import build_minimap_model, minimap_options

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DAY = 86400.0


class Toasts:
    def __init__(self):
        self.pushed = []

    def push(self, title, message="", **options):
        self.pushed.append((title, message, options.get("duration_s")))


class Heartbeat:
    def __init__(self, says=True):
        self.says, self.notes = says, []
        self.mind = type("Mind", (), {"memory": {}, "lock": threading.Lock()})()

    def note(self, kind, fields=None):
        self.notes.append((kind, dict(fields or {})))
        return {"text": "said"} if self.says else None


def jump(deck, system, event="FSDJump", position=None, at=None):
    stamp = datetime.fromtimestamp(at or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = {"event": event, "StarSystem": system, "timestamp": stamp}
    if position:
        raw["StarPos"] = position
    return deck._capsule_arrival(event, raw)


class Deck(DashboardCapsulesMixin):
    pass


def make_deck(test, says=True, **config):
    deck = Deck()
    deck.config = dict(config)
    deck.current_sys, deck.current_coords = "Hatchooe", [10.0, 0.0, 20.0]
    deck.toast_hud, deck.heartbeat_hud = Toasts(), Heartbeat(says)
    deck.add_event_feed_entry = lambda *args, **kwargs: None
    folder = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, folder, True)
    deck._capsule_store = CapsuleStore(lambda: folder)
    return deck


def age(deck, seconds):
    for row in deck._capsule_store._rows:
        row["left_at"] -= seconds
        if row.get("not_before"):
            row["not_before"] -= seconds


class NotBeforeTests(unittest.TestCase):
    def test_sealed_for_later_stays_shut_until_then(self):
        deck = make_deck(self)
        self.assertTrue(deck._handle_capsules_command("leave", {"system": "Sol", "note": "Later.", "wait": "month"}))
        age(deck, 3600)
        self.assertEqual(jump(deck, "Sol"), [], "back too soon")
        kind, fields = deck.heartbeat_hud.notes[-1]
        self.assertEqual((kind, fields["system"]), ("capsule_early", "Sol"))
        self.assertEqual(fields["wait"], "5 weeks")
        self.assertEqual(deck._html_capsules_workspace()["sealed"][0]["opens_in"], "5 weeks")
        age(deck, 31 * DAY)
        self.assertEqual(len(jump(deck, "Sol")), 1, "a month on: opened")

    def test_an_unknown_wait_is_no_wait(self):
        deck = make_deck(self)
        deck._handle_capsules_command("leave", {"system": "Sol", "note": "x", "wait": "forever"})
        self.assertIsNone(deck._capsule_store._rows[0]["not_before"])

    def test_how_long_to_wait_reads_with_a_number(self):
        self.assertEqual([wait_text(seconds) for seconds in (600, 5 * 3600, DAY, 3.5 * DAY, 20 * DAY, 100 * DAY, 365 * DAY, 800 * DAY)],
                         ["1 hour", "5 hours", "1 day", "4 days", "3 weeks", "4 months", "1 year", "2.2 years"])


class DeliveryTests(unittest.TestCase):
    def leave_and_arrive(self, deck, event="FSDJump"):
        deck._handle_capsules_command("leave", {"system": "Sol", "note": "Hello."})
        age(deck, 3600)
        return jump(deck, "Sol", event)

    def test_a_notice_only(self):
        deck = make_deck(self, capsule_delivery="notice", capsule_notice_s=45)
        self.leave_and_arrive(deck)
        self.assertEqual(deck.heartbeat_hud.notes, [], "the Watcher keeps out of it")
        self.assertEqual(deck.toast_hud.pushed[0][2], 45.0, "for as long as chosen")

    def test_the_watcher_only(self):
        deck = make_deck(self, says=False, capsule_delivery="watcher")
        self.assertEqual(len(self.leave_and_arrive(deck)), 1)
        self.assertEqual(deck.toast_hud.pushed, [], "no notice, even when it's quiet")

    def test_logging_in_there_opens_it_when_chosen(self):
        self.assertEqual(self.leave_and_arrive(make_deck(self), "Location"), [])
        self.assertEqual(len(self.leave_and_arrive(make_deck(self, capsule_open_on_login=True), "Location")), 1)

    def test_on_this_day_can_be_kept_quiet(self):
        deck = make_deck(self, on_this_day_watcher=False)
        deck._on_this_day_cache = ((datetime.now().astimezone().strftime("%Y-%m-%d"), "x"), [{"years": 1, "first": "Sol"}])
        self.assertIsNone(deck._on_this_day_watcher())
        self.assertEqual(deck.heartbeat_hud.notes, [])


class SettingTests(unittest.TestCase):
    def test_settings_kept_to_their_choices(self):
        deck = make_deck(self)
        saved = []
        deck._persist_config = lambda: saved.append(True)
        command = deck._handle_capsules_command
        self.assertTrue(command("set", {"key": "capsule_delivery", "value": "notice"}))
        self.assertFalse(command("set", {"key": "capsule_delivery", "value": "carrier pigeon"}))
        self.assertTrue(command("set", {"key": "capsule_notice_s", "value": "60"}))
        self.assertEqual(deck.config["capsule_notice_s"], 60)
        self.assertFalse(command("set", {"key": "capsule_notice_s", "value": 999}))
        self.assertTrue(command("set", {"key": "capsule_blur_sealed", "value": False}))
        self.assertFalse(command("set", {"key": "constellation_stars", "value": 7}), "the other page's setting")
        sky = deck._handle_constellation_command
        self.assertTrue(sky("set", {"key": "constellation_stars", "value": "7"}))
        self.assertFalse(sky("set", {"key": "constellation_stars", "value": 13}))
        self.assertTrue(sky("set", {"key": "constellation_shape", "value": "MAP"}))
        self.assertEqual((deck.config["constellation_stars"], deck.config["constellation_shape"]), (7, "map"))
        self.assertEqual(len(saved), 5)
        data = deck._html_capsules_workspace()
        self.assertEqual((data["settings"]["capsule_delivery"], data["settings"]["capsule_blur_sealed"]), ("notice", False))

    def test_every_setting_follows_the_commander(self):
        for key in [*CAPSULE_SETTINGS, *CONSTELLATION_SETTINGS, "galaxy_minimap_capsules"]:
            with self.subTest(key=key):
                self.assertIn(key, config_module.PROFILE_SETTINGS)

    def test_the_pages_offer_them(self):
        capsules = (WEB / "dashboard" / "capsules.js").read_text(encoding="utf-8")
        sky = (WEB / "dashboard" / "constellation.js").read_text(encoding="utf-8")
        for key in CAPSULE_SETTINGS:
            self.assertIn(f'"{key}"', capsules)
        for key in CONSTELLATION_SETTINGS:
            self.assertIn(f'"{key}"', sky)
        self.assertIn('id="capsule-wait"', capsules)


class MinimapTests(unittest.TestCase):
    def test_sealed_capsules_are_marked(self):
        deck = make_deck(self)
        deck.travel_history = type("H", (), {"lock": threading.Lock(), "rows": [["2026-01-01T00:00:00Z", "Colonia", -9530.5, 0, 19808.1, "F", 0, ""]]})()
        deck._handle_capsules_command("leave", {"system": "", "note": "here"})
        deck._handle_capsules_command("leave", {"system": "Colonia", "note": "there"})
        deck._handle_capsules_command("leave", {"system": "Nowhere Known", "note": "?"})
        self.assertEqual(sorted(deck._capsule_marks()), [[-9530.5, 19808.1], [10.0, 20.0]],
                         "where you were, the history's Colonia; unknown left out")
        age(deck, 3600)
        jump(deck, "Nowhere Known", position=[1.0, 2.0, 3.0])
        self.assertEqual(len(deck._capsule_marks()), 2, "opened: no longer marked")

    def test_the_minimap_draws_them_unless_switched_off(self):
        model = build_minimap_model([], [0, 0, 0], "Sol", capsules=[[1.0, 2.0]])
        self.assertEqual(model["capsules"], [[1.0, 2.0]])
        off = minimap_options({"galaxy_minimap_capsules": False})
        self.assertEqual(build_minimap_model([], [0, 0, 0], "Sol", options=off, capsules=[[1.0, 2.0]])["capsules"], [])
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-overlay-option="galaxy_minimap_capsules"', html)
        page = (WEB / "galaxy_minimap" / "app.js").read_text(encoding="utf-8")
        self.assertIn("for (const point of model.capsules || [])", page)


class ConstellationOptionTests(unittest.TestCase):
    def stays(self, count):
        return [(f"Star {index}", 25, "K") for index in range(count)]

    def test_stars_per_constellation_and_what_counts(self):
        rows = history(self.stays(12))
        self.assertEqual([len(item["stars"]) for item in constellations(rows, options=constellation_options({"constellation_stars": 5}))], [5, 5, 2])
        strict = constellation_options({"constellation_linger_min": 30})
        self.assertEqual(constellations(rows, options=strict), [], "25-minute stays aren't 30")
        self.assertEqual(constellation_options({"constellation_stars": 99})["per"], 12)

    def test_every_stay_or_one_a_session(self):
        rows = history([("A", 30, "K")])
        rows.insert(2, [rows[1][0][:-3] + "05Z", "B", 5.0, 0.0, 5.0, "G", 10.0, ""])  # a second stop
        one = constellations(rows, options=constellation_options({}))
        every = constellations(rows, options=constellation_options({"constellation_source": "every", "constellation_linger_min": 5}))
        self.assertLessEqual(len(one[0]["stars"]), len(every[0]["stars"]))

    def test_true_to_the_map(self):
        rows = history(self.stays(6))
        item = constellations(rows, options=constellation_options({"constellation_shape": "map"}))[0]
        keys = item["keys"]
        self.assertEqual(item["lines"], [[a, b] for a, b in zip(keys, keys[1:])], "joined in the order you flew")
        xs = [star["x"] for star in item["stars"]]
        self.assertEqual(xs, sorted(xs), "the history's systems run one way: so do the stars")

    def test_tonight_so_far(self):
        deck = make_deck(self)
        now = time.time()
        rows = [[datetime.fromtimestamp(now - seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), name, 0, 0, 0, "K", 1, ""]
                for name, seconds in (("Start", 4000), ("Long stop", 3900), ("Here", 300))]
        deck.travel_history = type("H", (), {"session_rows": lambda self: rows})()
        tonight = deck._tonight(600)
        self.assertEqual((tonight["system"], tonight["minutes"], tonight["here"], tonight["lingering"]), ("Long stop", 60, False, True))

    def test_the_watcher_names_a_finished_one(self):
        deck = make_deck(self)
        rows = history(self.stays(9))
        deck.travel_history = type("H", (), {"lock": threading.Lock(), "rows": rows, "revision": 1, "session_start": "s1"})()
        self.assertIsNone(deck._constellation_watch(), "the first look only counts: old ones aren't news")
        self.assertEqual(deck.heartbeat_hud.mind.memory["constellations_named"], 1)
        deck.travel_history.rows = history(self.stays(18))
        deck.travel_history.revision, deck.travel_history.session_start = 2, "s2"
        self.assertTrue(deck._constellation_watch())
        kind, fields = deck.heartbeat_hud.notes[-1]
        self.assertEqual((kind, fields["count"]), ("constellation_named", 9))
        self.assertTrue(fields["name"].startswith("The "))
        self.assertIsNone(deck._constellation_watch(), "once a session")

    def test_the_watchers_new_lines(self):
        for topic, fields in (("capsule_early", {"system": "Sol", "wait": "3 weeks"}),
                              ("constellation_named", {"name": "The Quiet Kite", "count": 9})):
            self.assertIn(topic, watcher_mind.TOPICS)
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10)
                for line in bank[topic]:
                    text = line.format(**fields)
                    self.assertTrue(text[0].isupper() or text[0].isdigit(), text)


if __name__ == "__main__":
    unittest.main()
