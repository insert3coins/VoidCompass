"""The crew (5.7.4): how the four companions came aboard and found each other."""
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from voidcompass.core import companions
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.overlays import companion_personas, crew_lore, watcher_mind
from tests.test_aster_companion import Clock

ROOT = Path(__file__).resolve().parents[1]
SEALED = ("Marr", "Haskell", "Varga", "Okonkwo", "Quist", "Pell", "Lattice", "Moreau", "Errand",
          "Leadline", "Rook", "Penhallow", "Ellery", "Sallow", "Wayfarer")


def mind(identity):
    config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
    return companions.create_mind(None, config, clock=Clock(), rng=random.Random(3))


class CrewContentTests(unittest.TestCase):
    def test_every_companion_tells_six_passages_and_meets_each_crewmate_once(self):
        self.assertEqual(sum(len(arc) for arc in crew_lore.PASSAGES.values()), 24)
        for identity in crew_lore.CREW:
            arc = crew_lore.PASSAGES[identity]
            self.assertEqual(len(arc), 6)
            self.assertEqual([row[2] for row in arc[:3]], [None, None, None], "arrival, the others, the rota")
            self.assertEqual(sorted(row[2] for row in arc[3:]), sorted(set(crew_lore.CREW) - {identity}))
            for row in arc:
                self.assertFalse(any(name in row[3] for name in SEALED), f"{identity}: no story spoilers in {row[1]}")

    def test_every_pair_has_a_handover_and_remarks_in_every_mind(self):
        for identity in crew_lore.CREW:
            others = set(crew_lore.CREW) - {identity}
            self.assertEqual(set(crew_lore.HANDOVERS[identity]), others)
            self.assertEqual(set(crew_lore.REMARKS[identity]), others)
            for other in others:
                for topic in (f"handover_from_{other}", f"idle_crew_{other}"):
                    if identity == "watcher":
                        self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 5, topic)
                    else:
                        lines = companion_personas.get(identity).lines
                        self.assertGreaterEqual(len(lines.event_lines(topic, True)), 3, topic)
                        self.assertEqual(lines.event_lines(topic), lines.event_lines(topic, True))


class CrewPacingTests(unittest.TestCase):
    def test_due_waits_for_time_a_second_companion_and_each_crewmate(self):
        memory, now = {}, 1_000_000.0
        self.assertIsNone(crew_lore.due("axiom", memory, {"axiom", "aster"}, 1.0, now), "not before two hours together")
        self.assertIsNone(crew_lore.due("axiom", memory, {"axiom"}, 5.0, now), "not before a second companion")
        order = []
        for _ in range(6):
            row = crew_lore.due("axiom", memory, {"axiom", "meridian"}, 5.0, now)
            if row is None:
                break
            order.append(row[0])
            memory.setdefault("crew_lore", []).append([row[0], now])
            self.assertIsNone(crew_lore.due("axiom", memory, {"axiom", "meridian"}, 5.0, now + 60), "an hour apart")
            now += crew_lore.GAP_S + 1
        self.assertEqual(order, ["crew_axiom_01", "crew_axiom_02", "crew_axiom_03", "crew_axiom_06"],
                         "the Watcher's and Aster's passages wait until you've flown with them")
        self.assertEqual(crew_lore.due("axiom", memory, {"axiom", "meridian", "watcher"}, 5.0, now)[0], "crew_axiom_04")

    def test_both_kinds_of_mind_tell_their_part_in_order_with_its_heading(self):
        for identity in crew_lore.CREW:
            companion = mind(identity)
            companion.session_start()
            companion.memory["hours"] = 3
            companion.learn({"crew": {"flown": list(crew_lore.CREW)}})
            companion.clock.now += 20 * 60
            if identity == "watcher":
                # Its own story comes first while a passage is due.
                self.assertEqual(companion.remember()["topic"], "lore_fragment")
                companion.clock.now += 2 * 3600
                thought = companion._crew_passage(companion.clock.now)
            else:
                story = companion.persona.story
                companion.memory["lore"] = [[row[0], 1.0] for row in story.passages]
                thought = companion.remember()
            self.assertEqual(thought["topic"], "crew_lore", identity)
            self.assertTrue(thought["heading"].startswith("THE CREW · "))
            self.assertTrue(thought["heading"].endswith("1 OF 6"))
            self.assertEqual(companion.memory["crew_lore"][0][0], f"crew_{identity}_01")
            self.assertEqual(crew_lore.arc_page(identity, companion.memory, set(crew_lore.CREW))["told"], 1)

    def test_remarks_about_a_crewmate_wait_for_its_passage(self):
        companion = mind("meridian")
        self.assertEqual(companion._crew_choices(), [])
        companion.memory["crew_lore"] = [["crew_meridian_05", 1.0]]
        self.assertEqual(companion._crew_choices(), [("idle_crew_aster", {})])
        watcher = mind("watcher")
        watcher.memory["crew_lore"] = [["crew_watcher_06", 1.0]]
        self.assertEqual(watcher._crew_choices(), [("idle_crew_meridian", {})])


class HandoverTests(unittest.TestCase):
    def test_the_incoming_companion_takes_the_watch_by_name(self):
        for identity in crew_lore.CREW:
            for previous in set(crew_lore.CREW) - {identity}:
                with self.subTest(identity=identity, previous=previous):
                    companion = mind(identity)
                    thought = companion.note("crew_handover", {"previous": previous})
                    self.assertEqual(thought["heading"], "CHANGE OF WATCH")
                    fields = crew_lore.handover_fields(previous)
                    self.assertIn(thought["text"], [line.format(**fields) for line in crew_lore.handover_lines(identity, previous)])
                    self.assertNotIn("{", thought["text"])
            self.assertIsNone(mind(identity).note("crew_handover", {"previous": identity}))

    def test_handovers_rotate_through_every_line_and_survive_a_restart(self):
        for identity in crew_lore.CREW:
            previous = "aster" if identity != "aster" else "watcher"
            lines = crew_lore.handover_lines(identity, previous)
            self.assertGreaterEqual(len(lines), 15 if identity != "watcher" else 20)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "memory.json"
                config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
                heard = []
                for _ in range(len(lines) * 2):
                    companion = companions.create_mind(path, config, clock=Clock(), rng=random.Random(len(heard)))
                    heard.append(companion.note("crew_handover", {"previous": previous})["text"])
                    companion.save()
                first, second = heard[:len(lines)], heard[len(lines):]
                self.assertEqual(len(set(first)), len(lines), "every line once before any repeats")
                self.assertEqual(len(set(second)), len(lines))
                self.assertNotEqual(first[-1], second[0], "never the same line twice in a row")

    def test_handover_names_read_naturally_and_respect_thoughts_off(self):
        self.assertEqual(crew_lore.handover_fields("watcher"), {"previous": "the Watcher", "Previous": "The Watcher", "name": "Watcher"})
        self.assertEqual(crew_lore.handover_fields("axiom")["Previous"], "Axiom")
        quiet = companions.create_mind(None, {"companion_identity": "axiom", "axiom_thoughts": "off"}, clock=Clock(), rng=random.Random(1))
        self.assertIsNone(quiet.note("crew_handover", {"previous": "aster"}))

    def test_switching_on_the_deck_asks_for_the_handover(self):
        notes = []
        deck = SimpleNamespace(config={"companion_identity": "aster"},
                               heartbeat_hud=SimpleNamespace(note=lambda kind, fields: notes.append((kind, fields))))
        deck._companion_switch_inner = lambda selected: deck.config.update(companion_identity=selected) or True
        DashboardWatcherVoiceMixin._companion_switch(deck, "meridian")
        self.assertEqual(notes, [("crew_handover", {"previous": "aster"})])
        DashboardWatcherVoiceMixin._companion_switch(deck, "meridian")
        self.assertEqual(len(notes), 1, "no handover when nothing changed")


class DeckTests(unittest.TestCase):
    def test_the_snapshot_reads_every_companions_memory_and_feeds_the_achievements(self):
        events = []
        with tempfile.TemporaryDirectory() as folder:
            paths = {identity: Path(folder) / f"{identity}_memory.json" for identity in crew_lore.CREW}
            paths["watcher"].write_text(json.dumps({"hours": 4, "crew_lore": [["crew_watcher_01", 1]]}), encoding="utf-8")
            paths["axiom"].write_text(json.dumps({"hours": .5}), encoding="utf-8")
            active = mind("aster")
            active.memory["hours"] = 1
            deck = SimpleNamespace(config={"companion_identity": "aster"}, heartbeat_hud=SimpleNamespace(mind=active),
                                   achievement_engine=SimpleNamespace(process_event=events.append))
            deck._watcher_story = lambda story: MainDashboard._watcher_story(deck, story)
            fake_path = lambda config: paths[companions.identity(config)]
            with mock.patch("voidcompass.overlays.heartbeat_hud._memory_path", fake_path):
                snapshot = MainDashboard._crew_snapshot(deck)
                self.assertEqual(snapshot["flown"], ["watcher", "aster", "axiom"])
                self.assertEqual(snapshot["told"], 1)
                active.memory["crew_lore"] = [["crew_aster_01", 2]]
                MainDashboard._crew_snapshot(deck, fresh=True)
                deck._crew_snapshot = lambda fresh=False: MainDashboard._crew_snapshot(deck, fresh)
                page = HtmlDashboardMixin._html_crew_page(deck)
        self.assertEqual(events[-1]["CrewTold"], 2)
        self.assertEqual(events[-1]["CrewFlown"], 3)
        self.assertEqual([arc["identity"] for arc in page["arcs"]], list(crew_lore.CREW))
        self.assertEqual((page["told"], page["total"], page["flown"]), (2, 24, 3))
        meridian = page["arcs"][3]
        self.assertFalse(meridian["flown"])
        aster = page["arcs"][1]
        self.assertEqual(aster["passages"][0]["title"], "Received Aboard")
        self.assertTrue(aster["passages"][0]["heard"])
        self.assertEqual(aster["passages"][5]["waits_for"], "Fly with Meridian")

    def test_crew_achievements_listen_for_the_crew_totals(self):
        rows = {row["id"]: row for row in json.loads((ROOT / "data" / "achievements.json").read_text(encoding="utf-8"))
                if row["id"].startswith("crew_")}
        self.assertEqual(set(rows), {"crew_introductions", "crew_full", "crew_watch_rota"})
        self.assertEqual(rows["crew_full"]["trigger"]["field"], "CrewFlown")
        self.assertEqual(rows["crew_watch_rota"]["trigger"]["value"], 24)


if __name__ == "__main__":
    unittest.main()
