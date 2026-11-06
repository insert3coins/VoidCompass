"""Richer words for the ground, vehicles, mining and exploration, and a full
system scan reported with what's in it (5.7.5)."""
import random
import re
import unittest

from voidcompass.core import companions
from voidcompass.overlays import (aster_field, axiom_field, companion_personas, meridian_field, survey_report,
                                  watcher_mind)
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian", "lyra")
FIELD = re.compile(r"mine|mining|rhino|prospect|crack|motherlode|srv|scarab|scorpion|nomad|launch|fighter|foot|touchdown|"
                   r"landed|taxi|fss|map|sample|analys|codex|world|planet|first|discover|valuable|ring|green|big_system|"
                   r"small_system|near_body|star|survey")
SEALED = ("Marr", "Haskell", "Varga", "Okonkwo", "Quist", "Pell", "Lattice", "Moreau", "Errand", "Leadline", "Rook",
          "Penhallow", "Ellery", "Sallow", "Wayfarer", "HAL", "2001", "Marvin")


def field_topics():
    return [topic for topic in watcher_mind.TOPICS if FIELD.search(topic)
            and not topic.startswith(("lore", "echo", "idle_crew", "handover", "watchers_meet", "name_", "habit", "route"))]


def mind(identity, frequency="chatty", seed=2):
    config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(seed))
    companion.memory["hours"] = 20
    companion.session_start()
    return companion


def scan(companion, name, planet="", star="", terraform="", discovered=False):
    raw = {"event": "Scan", "BodyName": name, "WasDiscovered": discovered}
    raw.update({"PlanetClass": planet} if planet else {"StarType": star})
    if terraform:
        raw["TerraformState"] = terraform
    companion.observe("Scan", raw)


class FieldWordsTests(unittest.TestCase):
    def test_every_field_topic_has_depth_for_every_officer(self):
        topics = field_topics()
        self.assertGreater(len(topics), 55)
        for identity in ("aster", "axiom", "meridian", "lyra"):
            lines = companion_personas.get(identity).lines
            for topic in topics:
                with self.subTest(identity=identity, topic=topic):
                    self.assertGreaterEqual(len(lines.event_lines(topic)), 9)
                    self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, "the plain style too")

    def test_new_lines_use_only_fields_the_topic_provides(self):
        for module in (aster_field, axiom_field, meridian_field):
            for bank in (module.PLAIN, module.VOICED):
                for topic, lines in bank.items():
                    known = set(re.findall(r"\{(\w+)", " ".join(watcher_mind.TOPICS[topic][1]))) | {"cmdr"}
                    for line in lines:
                        with self.subTest(module=module.__name__, topic=topic, line=line):
                            self.assertLessEqual(set(re.findall(r"\{(\w+)", line)), known)
                            self.assertFalse(any(name in line for name in SEALED))


class SurveyReportTests(unittest.TestCase):
    def test_the_summary_says_what_the_system_holds(self):
        tally = survey_report.SurveyTally()
        self.assertEqual(tally.summary(), "")
        tally.observe("Scan", {"BodyName": "A", "StarType": "K", "WasDiscovered": True})
        tally.observe("Scan", {"BodyName": "A 1", "PlanetClass": "Icy body", "WasDiscovered": True})
        self.assertEqual(tally.summary(2), "2 bodies. Nothing worth mapping.")
        self.assertFalse(tally.notable())
        tally.observe("Scan", {"BodyName": "A 2", "PlanetClass": "Earthlike body", "WasDiscovered": False})
        tally.observe("Scan", {"BodyName": "A 3", "PlanetClass": "Water world", "WasDiscovered": False})
        tally.observe("Scan", {"BodyName": "A 4", "PlanetClass": "Water world", "WasDiscovered": False})
        tally.observe("Scan", {"BodyName": "A 5", "PlanetClass": "High metal content body", "TerraformState": "Terraformable"})
        tally.observe("FSSBodySignals", {"BodyName": "A 1", "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 2},
                                                                        {"Type": "$SAA_SignalType_Geological;", "Count": 5}]})
        tally.observe("FSSBodySignals", {"BodyName": "A 5", "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 3}]})
        self.assertEqual(tally.summary(6), "6 bodies. Worth mapping: an Earth-like, 2 water worlds and a terraformable. "
                                           "Biology on 2 worlds, 5 signals. 3 first discoveries.")
        tally.observe("FSDJump", {})
        self.assertEqual(tally.summary(), "", "a new system starts afresh")
        tally.observe("Scan", {"BodyName": "B", "StarType": "M", "WasDiscovered": False})
        self.assertEqual(tally.summary(1), "One body. Nothing worth mapping. Every one a first discovery.")

    def test_every_companion_reports_a_full_scan(self):
        for identity in CREW:
            companion = mind(identity)
            companion.random.random = lambda: 0.0
            companion.clock.now += 120
            scan(companion, "Sim 1", planet="Water world")
            scan(companion, "Sim 2", planet="Rocky body", terraform="Terraformable")
            companion.clock.now += 120
            thought = companion.observe("FSSAllBodiesFound", {"event": "FSSAllBodiesFound", "SystemName": "Sim", "Count": 2})
            self.assertEqual((thought or {}).get("topic"), "survey_report", identity)
            self.assertIn("Worth mapping: a water world and a terraformable.", thought["text"])

    def test_a_report_that_cannot_be_said_yet_waits_its_turn(self):
        for identity in CREW:
            companion = mind(identity)
            scan(companion, "Sim 1", planet="Ammonia world")
            companion.consider("green_giant", {"system": "Sim"}, force=True)  # something was just said
            thought = companion.observe("FSSAllBodiesFound", {"event": "FSSAllBodiesFound", "SystemName": "Sim", "Count": 1})
            self.assertNotEqual((thought or {}).get("topic"), "survey_report", "too soon after the last thought")
            heard = None
            for _ in range(30):
                companion.clock.now += 5
                thought = companion.tick()
                if thought and thought["topic"] == "survey_report":
                    heard = thought
                    break
            self.assertIsNotNone(heard, identity)
            self.assertIn("ammonia world", heard["text"])

    def test_every_companion_has_report_lines_in_both_styles(self):
        self.assertEqual(watcher_mind.IMPORTANCE["survey_report"], 2, "said even on Occasional")
        self.assertGreaterEqual(len(watcher_mind.TOPICS["survey_report"][1]), 10)
        self.assertGreaterEqual(len(watcher_mind.WEARY["survey_report"]), 10)
        for identity in ("aster", "axiom", "meridian", "lyra"):
            lines = companion_personas.get(identity).lines
            self.assertGreaterEqual(len(lines.event_lines("survey_report")), 10)
            self.assertGreaterEqual(len(lines.event_lines("survey_report", True)), 4)
            for line in lines.event_lines("survey_report"):
                self.assertIn("{summary}", line)


if __name__ == "__main__":
    unittest.main()
