"""TALK answers more (5.7.6): the nearest station with a service, how far to a
named system, materials by grade, community goals; and the officers' habit
summaries in depth. Spansh is faked."""
import random
import re
import unittest
from unittest import mock

from voidcompass.core import companion_features, journal_files
from voidcompass.overlays import companion_personas, officer_habits, talk_replies, watcher_copilot as copilot
from tests.test_watcher_uplink_573 import Deck as UplinkDeck

NOW = 1_800_000_000
INVENTORY = {"raw": {"arsenic": {"name": "Arsenic", "count": 42}, "polonium": {"name": "Polonium", "count": 150},
                     "tellurium": {"name": "Tellurium", "count": 12}},
             "manufactured": {"militarygradealloys": {"name": "Military Grade Alloys", "count": 7}}, "encoded": {}}


class Deck(UplinkDeck):
    def __init__(self, online=True, here=(0.0, 0.0, 0.0)):
        super().__init__(online)
        self.current_sys = "Sol"
        self.here = list(here) if here is not None else None
        self.travel_history = type("History", (), {"rows": [["2026-01-01T00:00:00Z", "Shinrarta Dezhra", 55.71875, 17.59375, 27.15625]]})()
        self.engineer_materials = INVENTORY

    def _galaxy_minimap_position(self):
        return self.here

    def _expedition_jump_range(self):
        return 50.0


class ParseTests(unittest.TestCase):
    def test_how_far_names_a_system_and_leaves_the_route_alone(self):
        for question, name in (("How far is Colonia?", "Colonia"), ("how far to Beagle Point", "Beagle Point"),
                               ("How far is it to Sol?", "Sol"), ("What's the distance to Sagittarius A*?", "Sagittarius A*"),
                               ("how far are we from Shinrarta Dezhra", "Shinrarta Dezhra"), ("distance to HIP 22460", "HIP 22460")):
            self.assertEqual(copilot.distance_request(question), name, question)
        for question in ("how far to the next system", "how far is the destination", "how far have we travelled",
                         "how far to go?", "How far until the next jump?", "where are we"):
            self.assertIsNone(copilot.distance_request(question), question)

    def test_nearest_names_the_service(self):
        cases = {"Where's the nearest material trader?": ("Material Trader", None),
                 "nearest raw trader": ("Material Trader", "Raw"),
                 "closest encoded material trader": ("Material Trader", "Encoded"),
                 "nearest interstellar factors": ("Interstellar Factors Contact", None),
                 "where is the closest shipyard?": ("Shipyard", None),
                 "nearest tech broker": ("Technology Broker", None),
                 "nearest station": ("Dock", None)}
        for question, (service, trader) in cases.items():
            found = copilot.station_request(question)
            self.assertEqual((found["service"], found["trader"]), (service, trader), question)
        for question in ("nearest neutron star", "nearest fuel star", "where can I sell my data", "material trader"):
            self.assertIsNone(copilot.station_request(question), question)
        self.assertTrue(copilot.station_request("nearest carrier with a shipyard")["carriers"])

    def test_spansh_service_names_are_real(self):
        known = {"Flight Controller", "Refuel", "Market", "Repair", "Restock", "Black Market", "Interstellar Factors Contact",
                 "Universal Cartographics", "Outfitting", "Shipyard", "Vista Genomics", "Bartender", "Pioneer Supplies",
                 "Apex Interstellar", "Frontline Solutions", "Refinery Contact", "Redemption Office", "Technology Broker",
                 "Material Trader", "Search and Rescue", "Dock"}
        for _pattern, service, _trader, _label in copilot.NEAREST_SERVICES:
            self.assertIn(service, known)


class LineTests(unittest.TestCase):
    def test_distance_and_jumps(self):
        self.assertEqual(copilot.distance_lines("Colonia", (-9530.5, -910.28125, 19808.125), "Sol", (0, 0, 0), 65),
                         ["Colonia is 22,000 light years from Sol", "About 339 jumps at your 65 light year range"])
        self.assertEqual(copilot.distance_lines("Alpha Centauri", (3.03, -0.09, 3.16), "Sol", (0, 0, 0), 50),
                         ["Alpha Centauri is 4.4 light years from Sol"], "within one jump, no count")
        self.assertEqual(copilot.distance_lines("Sol", (0, 0, 0), "Sol", (0, 0, 0)), ["We're in Sol"])

    def test_nearest_stations(self):
        rows = [{"station": "Jameson Memorial", "system": "Shinrarta Dezhra", "distance": 12.3, "dist_ls": 347, "large_pad": True},
                {"station": "Daedalus", "system": "Sol", "distance": 0, "dist_ls": 5000, "large_pad": False}]
        lines = copilot.nearest_station_lines("material trader", rows, "Sol")
        self.assertEqual(lines[0], "Nearest material trader: Jameson Memorial, in Shinrarta Dezhra, 12.3 light years away "
                                   "(347 ls from the star, large pads)")
        self.assertEqual(lines[1], "Then Daedalus, here in Sol (5,000 ls from the star, no large pads)")
        self.assertEqual(copilot.nearest_station_lines("shipyard", [], "Sol"), ["No shipyard found near Sol"])
        self.assertIn("timed out", copilot.nearest_station_lines("shipyard", [], "Sol", "timed out")[0])

    def test_materials_by_grade(self):
        from voidcompass.engineering.engineering_data import material_info
        grade = lambda symbol: material_info(symbol).get("grade")
        self.assertEqual(copilot.materials_lines(INVENTORY, "how much arsenic?", grade_of=grade), ["Arsenic: 42 of 250 (raw, grade 2)"])
        self.assertEqual(copilot.materials_lines(INVENTORY, "materials by grade", grade_of=grade),
                         ["Raw by grade: grade 2 42, grade 4 162", "Manufactured by grade: grade 5 7"])
        self.assertEqual(copilot.materials_lines(INVENTORY, "grade 4 raw materials", grade_of=grade),
                         ["Raw grade 4: 162 in all, 2 kinds, 1 full at 150. Most: Polonium 150, Tellurium 12"])
        self.assertEqual(copilot.materials_lines(INVENTORY, "any grade 1 materials?", grade_of=grade), ["No grade 1 materials"])
        self.assertEqual(copilot.materials_lines(INVENTORY, "how much arsenic?"), ["Arsenic: 42 (raw)"], "no grades: as before")

    def test_community_goals(self):
        self.assertEqual(copilot.topics_for("How are my community goals doing?"), ["goals"])
        self.assertEqual(copilot.topics_for("any CGs?"), ["goals"])
        goal = companion_features.community_goal({
            "CGID": 726, "Title": "Defend Tionisla", "SystemName": "Tionisla", "MarketName": "Lave Station",
            "Expiry": "2027-01-10T12:00:00Z", "IsComplete": False, "PlayerContribution": 120000, "NumContributors": 900,
            "TopTier": {"Name": "Tier_8", "Bonus": ""}, "TierReached": "Tier 3", "PlayerPercentileBand": 25})
        self.assertEqual((goal["tier"], goal["top_tier"]), (3, 8))
        lines = copilot.community_goal_lines([goal], NOW)
        self.assertEqual(lines[0], "Community goals joined: 1")
        self.assertTrue(lines[1].startswith("Defend Tionisla: at Lave Station, Tionisla, your part 120,000, top 25%, tier 3 of 8, "))
        self.assertIn("No community goals", copilot.community_goal_lines([], NOW)[0])
        self.assertIn("CommunityGoal", journal_files.SESSION_HEADER_EVENTS)

    def test_goals_follow_the_journal(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        deck = mock.MagicMock()
        deck.companion_state = {}
        current = {"event": "CommunityGoal", "CurrentGoals": [
            {"CGID": 1, "Title": "Build It", "SystemName": "A", "MarketName": "B", "Expiry": "2027-01-01T00:00:00Z"},
            {"CGID": 2, "Title": "Fight It", "SystemName": "C", "MarketName": "D", "Expiry": "2027-01-01T00:00:00Z"}]}
        MainDashboard._process_companion_event(deck, "CommunityGoal", current, {})
        self.assertEqual(sorted(deck.companion_state["community_goals"]), ["1", "2"])
        MainDashboard._process_companion_event(deck, "CommunityGoalJoin", {"CGID": 3, "Name": "Haul It", "System": "E"}, {})
        MainDashboard._process_companion_event(deck, "CommunityGoalDiscard", {"CGID": 2, "Name": "Fight It"}, {})
        MainDashboard._process_companion_event(deck, "CommunityGoalReward", {"CGID": 1, "Name": "Build It", "Reward": 5}, {})
        goals = deck.companion_state["community_goals"]
        self.assertEqual([row["title"] for row in goals.values()], ["Haul It"])


class DeckTests(unittest.TestCase):
    def test_distance_from_history_landmarks_and_home(self):
        deck = Deck(online=False)
        said = deck._watcher_mind_action("How far is Shinrarta Dezhra?")
        self.assertTrue(said.startswith("Shinrarta Dezhra is 64.4 light years from Sol"), said)
        self.assertIn("About 2 jumps", said)
        self.assertTrue(deck._watcher_mind_action("how far to colonia").startswith("Colonia is 22,000 light years from Sol"))
        deck.here = [-9530.5, -910.28125, 19808.125]
        deck.current_sys = "Colonia"
        self.assertTrue(deck._watcher_mind_action("how far is home?").startswith("Sol is 22,000 light years from Colonia"))
        self.assertEqual(deck.tasks, [], "nothing went online")

    def test_unknown_systems_go_to_the_uplink_only_when_allowed(self):
        offline = Deck(online=False)
        self.assertIn("trading searches", offline._watcher_mind_action("How far is Hip 12345?"))
        deck = Deck()
        with mock.patch("voidcompass.services.spansh.system_position",
                        return_value={"name": "HIP 12345", "coords": [30.0, 40.0, 0.0]}) as lookup:
            said = deck._watcher_mind_action("How far is Hip 12345?")
        self.assertTrue(said["waiting"])
        lookup.assert_called_once_with("Hip 12345")
        (words, lines), = deck.mind.answers
        self.assertEqual(lines[0], "HIP 12345 is 50.0 light years from Sol")
        nowhere = Deck(here=None)
        self.assertIn("where we are", nowhere._watcher_mind_action("How far is Colonia?"))

    def test_the_nearest_station_through_the_uplink(self):
        self.assertIn("Integrations", Deck(online=False)._watcher_mind_action("Where's the nearest shipyard?"))
        deck = Deck()
        rows = [{"station": "X-Carrier", "system": "Sol", "distance": 0.0, "dist_ls": 10, "large_pad": True, "carrier": True},
                {"station": "Galileo", "system": "Sol", "distance": 0.0, "dist_ls": 505, "large_pad": True, "carrier": False}]
        with mock.patch("voidcompass.services.spansh.service_stations", return_value=rows) as search:
            said = deck._watcher_mind_action("Where's the nearest shipyard?")
        self.assertTrue(said["waiting"])
        self.assertIn("shipyard", said["say"])
        self.assertEqual(search.call_args.args[:2], ("Sol", "Shipyard"))
        (_words, lines), = deck.mind.answers
        self.assertEqual(len(lines), 1, "the carrier is left out unless asked for")
        self.assertIn("Galileo", lines[0])
        deck = Deck()
        with mock.patch("voidcompass.services.spansh.material_traders", return_value=[]) as traders:
            deck._watcher_mind_action("nearest raw material trader")
        self.assertEqual(traders.call_args.args[:2], ("Sol", "Raw"))

    def test_a_material_named_alone_is_looked_up(self):
        deck = Deck()
        self.assertIn("Arsenic: 42 of 250 (raw, grade 2)", deck._watcher_lookup("How much arsenic do I have?"))


class OfficerTests(unittest.TestCase):
    def test_every_new_reply_in_every_voice(self):
        for identity in ("aster", "axiom", "meridian"):
            persona = companion_personas.get(identity)
            commands = getattr(persona.lines, "COMMANDS", None) or persona.lines.BANK.COMMANDS
            for key in ("station_opening", "distance_opening", "distance_unknown", "distance_nowhere"):
                self.assertIn(key, copilot.REPLIES)
                self.assertIn(key, commands, (identity, key))
                self.assertEqual(set(talk_replies.OFFICERS[identity]), set(talk_replies.OFFICERS["aster"]))
            rng = random.Random(3)
            rng.companion_identity = identity
            self.assertNotIn("{", copilot.reply("station_opening", rng, label="shipyard"))
            self.assertNotIn("can't reach", copilot.reply("distance_unknown", rng, name="Colonia"))

    def test_habit_summaries_in_depth_and_style_reads_right(self):
        fields = {"style": "an explorer", "share": "62", "jumps": "900", "ly": "30,000", "longest": "70", "scoops": "300",
                  "scooped_t": "900", "low_fuel": "2", "landings": "40", "star": "K", "bodies": "4,000", "firsts": "900",
                  "mapped": "200", "efficient": "150", "bio": "80", "commodity": "Tritium", "tonnes": "5,000",
                  "limpets": "300", "mined": "Painite", "mined_n": "400", "bounties": "50", "bounty_cr": "9 million",
                  "target": "Pirate", "target_n": "20", "interdicted": "12", "escaped": "9", "bonds": "30",
                  "sold": "Gold", "sold_t": "2,000", "profit": "50 million", "best": "Gold", "best_cr": "2 million"}
        for identity in ("aster", "axiom", "meridian"):
            lines = companion_personas.get(identity).lines
            for topic in ("habit_flight", "habit_scans", "habit_cargo", "habit_combat", "habit_trade", "habit_style"):
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))
                for line in lines.event_lines(topic):
                    for field in re.findall(r"\{(\w+)\}", line):
                        self.assertIn(field, fields, (identity, topic, line))
                    self.assertNotIn("{", line.format(**fields))
            for line in lines.event_lines("habit_style"):
                self.assertFalse(line.startswith("{style}"), line)
                self.assertNotRegex(line, r"(towards|leans|preference for|gives|activity is|work is) \{style\}")
        self.assertEqual(set(officer_habits.STYLE), {"aster", "axiom", "meridian"})


if __name__ == "__main__":
    unittest.main()
