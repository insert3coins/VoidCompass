"""Exercise Aster's quiet-watch triggers, facts, age gates and persisted rests."""
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from voidcompass.overlays import aster_idle, aster_lines, aster_lore, watcher_habits, watcher_mind
from voidcompass.overlays.aster_mind import AsterMind


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.

    def __call__(self):
        return self.now


class AsterIdleTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def mind(self, path=None, frequency="occasional", humour="dry", port=False):
        mind = AsterMind(path, {"companion_identity": "aster", "aster_thoughts": frequency,
                               "aster_humour": humour}, clock=self.clock, rng=random.Random(17))
        mind.observe("LoadGame", {"Ship_Localised": "Mandalay", "ShipName": "Quiet Hours"})
        mind.observe("Location", {"StarSystem": "Sol", "Docked": port,
                                  "StationName": "Galileo" if port else ""})
        return mind

    def archived(self, mind):
        old = self.clock() - 3 * 86400
        mind.memory["postcards"] = [[old, "Achenar postcard", "system"]]
        mind.memory["aster_moments"] = [
            {"event": "FSDJump", "at": old, "system": "Achenar", "station": ""},
            {"event": "Docked", "at": old, "system": "Sol", "station": "Galileo"},
            {"event": "MissionCompleted", "at": old, "system": "Altair", "station": ""},
        ]
        mind.memory["lore"] = [[row[0], old] for row in aster_lore.PASSAGES[:8]]

    def choices(self, mind):
        return aster_idle.choices(mind.memory, mind.random, self.clock())

    def test_no_invented_habits_postcards_memories_or_unheard_story(self):
        mind = self.mind()
        self.assertEqual(self.choices(mind), [])
        shared = dict(mind._idle_choices(self.clock(), {}))
        self.assertNotIn("idle_lore", shared)
        self.assertNotIn("aster_lore_recall", shared)
        self.assertNotIn("idle_postcard", shared)
        self.assertNotIn("aster_after", shared)

    def test_real_journal_activity_unlocks_factual_habits_in_both_modes(self):
        for humour in ("dry", "off"):
            mind = self.mind(humour=humour)
            for index in range(20):
                mind.observe("FSDJump", {"StarSystem": f"Route {index}", "JumpDist": 25,
                                         "StarClass": "K"})
            fields = dict(self.choices(mind))["habit_flight"]
            self.assertEqual((fields["jumps"], fields["ly"], fields["longest"]), ("20", "500", "25.0"))
            with patch.object(mind.random, "random", return_value=0.):
                self.clock.now += 301
                thought = mind.consider("habit_flight", fields)
            self.assertIsNotNone(thought)
            self.assertTrue(any(fact in thought["text"] for fact in ("20", "25.0", "orange", "K-class")))
            self.clock.now += watcher_habits.HABIT_REST_S - 1
            self.assertIsNone(mind.consider("habit_flight", fields))

    def test_every_supported_habit_fact_has_eligible_officer_wording(self):
        cases = {"flight": [{"jumps": "20", "ly": "500", "longest": "25.0"}, {"star": "red dwarfs"},
                            {"scoops": "10", "scooped_t": "20"}, {"landings": "10"}, {"low_fuel": "3"}],
                 "scans": [{"bodies": "30"}, {"firsts": "10"}, {"mapped": "5"}, {"bio": "5"}],
                 "cargo": [{"mined": "Gold", "mined_n": "10"}, {"commodity": "Gold", "tonnes": "50"}, {"limpets": "20"}],
                 "combat": [{"bounties": "5", "bounty_cr": "100"}, {"target": "Pirate", "target_n": "3"},
                            {"interdicted": "3"}, {"bonds": "5"}],
                 "trade": [{"sold": "Gold", "sold_t": "100"}, {"profit": "1,000,000"}, {"best": "Gold", "best_cr": "100,000"}],
                 "style": [{"style": "exploration", "share": "80"}]}
        for humour in ("dry", "off"):
            for subject, options in cases.items():
                for fields in options:
                    with self.subTest(humour=humour, subject=subject, fields=fields):
                        mind = self.mind(humour=humour)
                        thought = mind.consider("habit_" + subject, fields, force=True)
                        self.assertIsNotNone(thought)
                        self.assertNotIn("{", thought["text"])

    def test_story_recollections_wait_for_completed_old_chapters(self):
        mind = self.mind()
        old = self.clock() - 3 * 86400
        mind.memory["lore"] = [[row[0], old] for row in aster_lore.PASSAGES[:5]]
        self.assertIn("idle_aster_lore", dict(self.choices(mind)))
        self.assertNotIn("aster_lore_recall", dict(self.choices(mind)))
        mind.memory["lore"].append([aster_lore.PASSAGES[5][0], self.clock()])
        self.assertNotIn("aster_lore_recall", dict(self.choices(mind)), "a day must pass after the chapter")
        self.clock.now += 86401
        fields = dict(self.choices(mind))["aster_lore_recall"]
        self.assertIn("cI", fields)
        self.assertFalse(any(f"c{numeral}" in fields for numeral in ("II", "III", "IV", "V", "VI", "VII", "VIII")))
        for humour in ("dry", "off"):
            listener = self.mind(humour=humour)
            thought = listener.consider("aster_lore_recall", fields, force=True)
            self.assertIsNotNone(thought)
            # Later captains stay sealed until their chapters are heard.
            self.assertFalse(any(name in thought["text"] for name in ("Marr", "Haskell", "Varga", "Okonkwo", "Quist", "Pell")))

    def test_postcards_and_service_records_have_real_age_gates_and_places(self):
        mind = self.mind()
        mind.memory["postcards"] = [[self.clock(), "Altair", "system"]]
        mind.memory["aster_moments"] = [{"event": "Docked", "at": self.clock(), "system": "Sol", "station": "Galileo"}]
        self.assertEqual(self.choices(mind), [])
        self.clock.now += 6 * 3600
        self.assertEqual(dict(self.choices(mind))["idle_postcard"]["place"], "Altair")
        self.assertNotIn("idle_moment", dict(self.choices(mind)))
        self.clock.now += 2 * 86400
        fields = dict(self.choices(mind))["idle_moment"]
        self.assertIn("Galileo in Sol", fields["about"])
        self.assertTrue(fields["when"])
        mind.memory["aster_moments"].append({"event": "MadeUp", "at": self.clock() - 3 * 86400, "system": "Sol"})
        self.assertEqual(sum(topic == "idle_moment" for topic, _ in self.choices(mind)), 1)

    def test_recall_identity_survives_restart_and_does_not_consume_deferred_memories(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            self.archived(mind)
            first = dict(self.choices(mind))["idle_postcard"]
            self.assertIsNone(mind.consider("idle_postcard", first), "a recent report defers idle speech")
            self.assertEqual(mind.memory.get("aster_idle_recalled", {}), {})
            for topic in ("idle_postcard", "aster_recall", "idle_moment", "aster_lore_recall"):
                fields = next(fields for kind, fields in self.choices(mind) if kind == topic)
                self.assertIsNotNone(mind.consider(topic, fields, force=True))
                self.assertIsNone(mind.consider(topic, fields, force=True), "changing words cannot repeat an artifact")
            heard = dict(mind.memory["aster_idle_recalled"])
            mind.save()
            resumed = self.mind(path)
            self.assertEqual(resumed.memory["aster_idle_recalled"], heard)
            self.assertFalse(any(fields.get("_recall") in heard for _, fields in self.choices(resumed)))
            self.clock.now += aster_idle.RECALL_REST_S
            self.assertTrue(any(fields.get("_recall") in heard for _, fields in self.choices(resumed)))

    def test_postcard_topic_rests_even_when_a_different_card_is_available(self):
        mind = self.mind()
        self.archived(mind)
        first = dict(self.choices(mind))["idle_postcard"]
        self.assertIsNotNone(mind.consider("idle_postcard", first, force=True))
        mind.memory["postcards"].append([self.clock() - 86400, "Second place", "system"])
        fields = dict(self.choices(mind))["idle_postcard"]
        self.clock.now += 9 * 3600
        with patch.object(mind.random, "random", return_value=0.):
            self.assertIsNone(mind.consider("idle_postcard", fields))
            self.clock.now += 3601
            self.assertIsNotNone(mind.consider("idle_postcard", fields))

    def test_service_capture_uses_location_and_biology_sale_in_current_system(self):
        mind = self.mind()
        mind.observe("Location", {"StarSystem": "Altair", "Docked": True, "StationName": "Port"})
        mind.observe("SellOrganicData", {})
        moment = mind.memory["aster_moments"][-1]
        self.assertEqual((moment["event"], moment["system"]), ("SellOrganicData", "Altair"))
        self.clock.now += 3 * 86400
        fields = dict(self.choices(mind))["idle_moment"]
        self.assertEqual(fields["about"], "the biological data we sold in Altair")

    def test_all_queued_commander_facts_eventually_speak_in_officer_words(self):
        for event, raw, topic, fact in (
            ("Statistics", {"Exploration": {"Systems_Visited": 1234}}, "cmdr_record", "1,234"),
            ("Statistics", {"Exploration": {"Time_Played": 7200}}, "cmdr_record", "2 hours"),
            ("Powerplay", {"Power": "Aisling Duval"}, "cmdr_power", "Aisling Duval"),
            ("SquadronStartup", {"SquadronName": "Night Watch"}, "cmdr_squadron", "Night Watch"),
            ("CarrierStats", {"Name": "Safe Harbour"}, "cmdr_carrier", "Safe Harbour"),
        ):
            with self.subTest(topic=topic, raw=raw):
                mind = self.mind()
                mind.observe(event, raw)
                self.clock.now += 601
                with patch.object(mind.random, "random", return_value=0.), patch.object(mind, "remember", return_value=None):
                    thought = mind.tick()
                self.assertEqual(thought["topic"], topic)
                self.assertIn(fact, thought["text"])
                self.assertNotIn(topic, [key for key, _ in mind._say_next])

    def test_long_watch_reminder_waits_for_idle_interval_and_rests_an_hour(self):
        mind = self.mind(frequency="rare")
        start = self.clock()
        self.clock.now = start + 3 * 3600 + 1
        mind._last_spoke = self.clock() - 901
        mind.memory["aster_wording"]["idle"] = self.clock() - 1000
        with patch.object(mind, "remember", return_value=None), patch.object(mind.random, "random", return_value=0.):
            self.assertIsNone(mind.tick())
            self.clock.now += 201
            thought = mind.tick()
            self.assertEqual(thought["topic"], "long_session")
            self.assertIn("3", thought["text"])
            self.clock.now += 1201
            self.assertNotEqual((mind.tick() or {}).get("topic"), "long_session")

    def test_contextual_call_and_rapid_repeat_have_distinct_replies(self):
        mind = self.mind(port=True)
        with patch.object(mind.random, "random", return_value=0.):
            first = mind.poke()
            self.assertTrue(first["topic"].startswith("idle_"))
            self.assertNotEqual(mind.poke()["topic"], "poked_again")
            self.assertEqual(mind.poke()["topic"], "poked_again")

    def test_new_casual_topics_are_rare_eligible_but_do_not_become_spoken_warnings(self):
        mind = self.mind(frequency="rare")
        self.archived(mind)
        self.clock.now += 901
        with patch.object(mind.random, "random", return_value=0.):
            thought = mind.consider("idle_postcard", dict(self.choices(mind))["idle_postcard"])
        self.assertIsNotNone(thought)
        self.assertEqual(thought["importance"], 1)
        mind._in_danger = True
        for topic, fields in self.choices(mind):
            self.assertIsNone(mind.consider(topic, fields, force=True))
        off = self.mind(frequency="off")
        self.archived(off)
        for topic, fields in self.choices(off):
            self.assertIsNone(off.consider(topic, fields, force=True))

    def test_long_watches_mix_archive_habits_and_port_or_space_at_selected_pace(self):
        for port in (False, True):
            for frequency in ("occasional", "rare"):
                for humour in ("dry", "off"):
                    with self.subTest(port=port, frequency=frequency, humour=humour):
                        self.clock = Clock()
                        mind = self.mind(port=port, frequency=frequency, humour=humour)
                        self.archived(mind)
                        for index in range(30):
                            watcher_habits.observe(mind.memory, "FSDJump", {"JumpDist": 25, "StarClass": "K"})
                            watcher_habits.observe(mind.memory, "Scan", {"PlanetClass": "Water world"})
                        start = self.clock()
                        heard, times, topics = [], [], set()
                        with patch.object(mind, "remember", return_value=None):
                            for step in range(1, 16 * 120 + 1):
                                self.clock.now = start + step * 30
                                thought = mind.tick()
                                if thought:
                                    heard.append(thought["text"])
                                    times.append(self.clock())
                                    topics.add(thought["topic"])
                        self.assertEqual(len(heard), len(set(heard)))
                        self.assertTrue(all(b - a >= watcher_mind.FREQUENCIES[frequency]["mutter"]
                                            for a, b in zip(times, times[1:])))
                        self.assertTrue(any(topic.startswith("habit_") for topic in topics))
                        self.assertIn("long_session", topics)
                        self.assertTrue(topics & {"idle_moment", "idle_postcard", "aster_recall", "aster_lore_recall"})
                        # With no new activity, finite banks can eventually
                        # exhaust; quiet is preferable to recycled company.
                        self.assertGreater(times[-1], start + 12 * 3600)

    def test_every_chapter_has_original_recollections_in_both_modes(self):
        numerals = [chapter["numeral"] for chapter in aster_lore.CHAPTERS]
        for humour in ("dry", "off"):
            for chapter, numeral in enumerate(numerals, 1):
                with self.subTest(humour=humour, chapter=numeral):
                    mind = self.mind(humour=humour)
                    mind.memory["lore"] = [[row[0], self.clock() - 3 * 86400]
                                           for row in aster_lore.PASSAGES[:chapter * 6]]
                    fields = next(fields for topic, fields in self.choices(mind)
                                  if topic == "aster_lore_recall" and f"c{numeral}" in fields)
                    thought = mind.consider("aster_lore_recall", fields, force=True)
                    self.assertIsNotNone(thought)
                    self.assertNotIn("{", thought["text"])
                    self.assertEqual(thought["heading"], "OFFICER ON WATCH")

if __name__ == "__main__":
    unittest.main()
