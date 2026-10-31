"""5.7.2: the Watcher answers what you asked. A question gets only what it
needs (where you are when you ask where, what you've done when you ask about
the past), new lookups name your cargo, describe the station you're docked
at and list the system's factions, and "remember that…" is kept. The model
is faked, as in test_watcher_llm_571."""

import threading
import time
import unittest

from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import watcher_copilot as copilot
from voidcompass.overlays import watcher_knowing

from tests.test_watcher_llm_571 import FakeServer, mind_llm, wait_ready, whole

FACTS = {"system": "Colonia", "ship": "Krait Phantom", "ship name": "Wanderer", "doing": "docked at Jaques Station",
         "region": "Inner Orion Spur", "distance from Sol": "22,000 light years"}
LATELY = ["Jumped to Colonia (41.2 light years).", "Docked at Jaques Station in Colonia."]


class TopicTests(unittest.TestCase):
    def test_everyday_words_bring_up_no_readout(self):
        for said in ("How's it going?", "Are you alive?", "What are you listening to?", "What do you need?",
                     "Where do you live?", "What's the best ship for exploring?", "Hold on a second."):
            self.assertEqual(copilot.topics_for(said), [], said)

    def test_each_question_finds_its_own_readout(self):
        self.assertEqual(copilot.topics_for("What cargo do we have?"), ["cargo"])
        self.assertEqual(copilot.topics_for("What's in the ship's hold?"), ["cargo"], "the hold, not the ship")
        self.assertEqual(copilot.topics_for("Tell me about the station we're docked at"), ["station"])
        self.assertEqual(copilot.topics_for("What factions are in this system?"), ["factions"])
        self.assertEqual(copilot.topics_for("How many jumps left?"), ["route"])
        self.assertEqual(copilot.topics_for("Where are we going?"), ["route"])
        self.assertEqual(copilot.topics_for("What could live here?"), ["life"])
        self.assertEqual(copilot.topics_for("How's our ship's hull?"), ["ship"])


class LineTests(unittest.TestCase):
    def test_cargo_by_name(self):
        rows = [{"Name": "tritium", "Count": 40},
                {"Name": "lowtemperaturediamond", "Name_Localised": "Low Temperature Diamonds", "Count": 12},
                {"Name": "$Gold_Name;", "Count": 1, "MissionID": 7},
                {"Name": "drones", "Name_Localised": "Limpet", "Count": 8},
                {"Name": "imperialslaves", "Name_Localised": "Imperial Slaves", "Count": 2, "Stolen": 2}]
        self.assertEqual(copilot.cargo_lines(rows, 64), [
            "The ship's hold carries 63 tonnes, with 1 tonne free", "Tritium: 40 tonnes", "Low Temperature Diamonds: 12 tonnes",
            "Limpet: 8 tonnes", "Imperial Slaves: 2 tonnes (stolen)", "Gold: 1 tonne (for a mission)"])
        self.assertEqual(copilot.cargo_lines([], 64), ["The ship's hold is empty, 64 tonnes free"])
        self.assertEqual(copilot.cargo_lines([{"Name": "platinum", "Count": 3}], 0, "SRV"),
                         ["The SRV's hold carries 3 tonnes", "Platinum: 3 tonnes"])
        many = [{"Name": f"good{n}", "Count": 10 - n} for n in range(10)]
        self.assertEqual(copilot.cargo_lines(many, 100)[-1], "And 2 other kinds of cargo")

    def test_the_station_as_the_game_describes_it(self):
        lines = copilot.station_lines(
            "Jaques Station", "Bernal", "Colonia", "Jaques", "Boom", "$government_Cooperative;", "Independent",
            "$economy_HighTech;", ["dock", "shipyard", "outfitting", "blackmarket", "techBroker", "vistagenomics", "refuel"],
            {"Small": 4, "Medium": 4, "Large": 8}, 1234.5)
        self.assertEqual(lines, [
            "Docked at Jaques Station, an Ocellus starport in Colonia",
            "The station belongs to the faction Jaques, which is in the Boom state",
            "Station: Cooperative government, Independent allegiance, High Tech economy",
            "Services: shipyard, outfitting, black market, technology broker, Vista Genomics, refuel",
            "Landing pads: 16 in all (8 large, 4 medium, 4 small)", "Distance from the main star: 1,234 light seconds"])
        self.assertEqual(copilot.station_lines(""), ["Not docked at a station right now"])
        self.assertIn("a fleet carrier", copilot.station_lines("K7Q-1HT", "FleetCarrier")[0])
        self.assertIn("a some new kind", copilot.station_lines("Odd", "SomeNewKind")[0], "an unknown kind, readable")
        self.assertEqual(copilot.station_lines("Hub", "Coriolis", faction_state="None")[1:], [], "no state, no line")

    def test_the_systems_factions(self):
        now = time.time()
        snap = {"ts": now - 3600, "system": "Colonia", "controlling": "Jaques", "population": 583_000,
                "government": "Cooperative", "allegiance": "Independent", "economy": "Tourism", "security": "High",
                "factions": [
                    {"name": "Colonia Council", "influence": 0.214, "state": "Election", "government": "Cooperative",
                     "reputation": 40},
                    {"name": "Jaques", "influence": 0.553, "state": "Boom", "government": "Cooperative", "reputation": 95,
                     "squadron": True},
                    {"name": "Pirates of Colonia", "influence": 0.03, "state": "None", "government": "Anarchy",
                     "reputation": -95}],
                "conflicts": [{"type": "election", "status": "active", "sides": [
                    {"name": "Colonia Council", "won_days": 2}, {"name": "Colonia Co-operative", "won_days": 1}]}]}
        lines = copilot.faction_lines(snap, now=now)
        self.assertEqual(lines[:2], ["Controlling faction: Jaques",
                                     "Colonia: Cooperative government, Independent allegiance, Tourism economy, "
                                     "High security, population 583,000"])
        self.assertEqual(lines[2], "Jaques: 55% influence, state Boom, Cooperative, the commander is allied with them, "
                                   "the commander's squadron faction")
        self.assertEqual(lines[3], "Colonia Council: 21% influence, state Election, Cooperative, "
                                   "the commander is friendly with them")
        self.assertEqual(lines[4], "Pirates of Colonia: 3% influence, Anarchy, the commander is hostile with them")
        self.assertEqual(lines[5], "Election (active): Colonia Council leads Colonia Co-operative 2 to 1 in days won")
        snap["conflicts"][0]["sides"][1]["won_days"] = 2
        self.assertIn("are level at 2 days won each", copilot.faction_lines(snap, now=now)[5])
        snap["factions"][2]["influence"] = 0.004
        self.assertTrue(any(line.startswith("Pirates of Colonia: under 1% influence")
                            for line in copilot.faction_lines(snap, now=now)))
        snap["ts"] = now - 5 * 86400
        self.assertEqual(copilot.faction_lines(snap, now=now)[-1], "These readings are 5 days old")
        self.assertIn("nobody lives here", copilot.faction_lines(None, "Sag A*")[0])

    def test_reputation_bands(self):
        for value, word in ((100, "allied"), (90, "allied"), (60, "friendly"), (10, "cordial"), (0, "neutral"),
                            (-50, "unfriendly"), (-95, "hostile"), (None, "")):
            self.assertEqual(copilot.reputation_word(value), word, value)


class RememberTests(unittest.TestCase):
    def test_what_you_ask_it_to_remember(self):
        self.assertEqual(copilot.remember_request("Remember that my carrier is the Black Rose"),
                         "My carrier is the Black Rose.")
        self.assertEqual(copilot.remember_request("please remember: I hate neutron routes!"), "I hate neutron routes.")
        self.assertEqual(copilot.remember_request("Don't forget my home is Colonia"), "My home is Colonia.")
        for not_asked in ("Remember when we went to Colonia?", "Do you remember me?", "remember what we did",
                          "I remember Colonia", "Remember?"):
            self.assertIsNone(copilot.remember_request(not_asked), not_asked)

    def test_it_is_kept_with_what_you_teach_it(self):
        deck = Deck()
        self.assertEqual(deck._watcher_mind_action("Remember that my carrier is the Black Rose"), "I'll remember that.")
        self.assertEqual(watcher_knowing.taught(deck.mind.memory)[0]["text"], "My carrier is the Black Rose.")
        self.assertTrue(deck.mind.saved)
        self.assertEqual(deck._watcher_mind_action("remember that my carrier is the Black Rose"), "I know that already.")
        self.assertEqual(deck._watcher_mind_action("Remember that Raxxla is real"), "Not that. Some things I don't keep.")
        self.assertEqual(deck._watcher_mind_action(f"Remember that {'x' * 400}"),
                         "That's too much to keep in one go. Say it shorter.")
        self.assertIsNone(deck._watcher_mind_action("What do you remember?"), "a question goes to its mind")


class FakeMind:
    def __init__(self):
        self.memory = {}
        self.lock = threading.RLock()
        self.saved = False
        self.random = None

    def save(self):
        self.saved = True


class FakeStore:
    def __init__(self, snap):
        self.snap = snap
        self.asked = []

    def latest_snapshot(self, address):
        self.asked.append(address)
        return self.snap


class Deck(DashboardWatcherVoiceMixin):
    def __init__(self):
        self.mind = FakeMind()
        self.heartbeat_hud = type("Hud", (), {"mind": self.mind})()
        self.config = {}

    def _watcher_mind(self):
        return self.mind

    def _schedule_html_dashboard_publish(self, immediate=False):
        pass


class LookupTests(unittest.TestCase):
    def test_the_station_only_when_docked(self):
        deck = Deck()
        deck.current_docked = False
        self.assertEqual(deck._watcher_lookup_station(), ["Not docked at a station right now"])
        deck.current_docked, deck.current_station_name, deck.current_sys = True, "Jaques Station", "Colonia"
        deck.current_station_type, deck.current_station_faction = "Bernal", {"name": "Jaques", "state": "Boom"}
        deck.current_station_services = ["shipyard"]
        lines = deck._watcher_lookup_station()
        self.assertEqual(lines[0], "Docked at Jaques Station, an Ocellus starport in Colonia")
        self.assertIn("Services: shipyard", lines)

    def test_factions_from_this_systems_reading(self):
        deck = Deck()
        deck.current_system_address, deck.current_sys = 3238296097059, "Colonia"
        deck.bgs_store = FakeStore({"system": "Colonia", "controlling": "Jaques", "factions": [
            {"name": "Jaques", "influence": 0.5, "state": "None"}]})
        self.assertEqual(deck._watcher_lookup_factions()[:2], ["Controlling faction: Jaques", "Jaques: 50% influence"])
        self.assertEqual(deck.bgs_store.asked, [3238296097059])
        deck.bgs_store = FakeStore(None)
        self.assertIn("No faction readings for Colonia", deck._watcher_lookup_factions()[0])

    def test_the_hold_in_use(self):
        deck = Deck()
        deck.current_cargo_vessel = "Ship"
        deck.current_cargo_inventory = [{"Name": "tritium", "Count": 5}]
        deck._active_cargo_capacity = lambda: 32
        self.assertEqual(deck._watcher_lookup_cargo(), ["The ship's hold carries 5 tonnes, with 27 tonnes free",
                                                        "Tritium: 5 tonnes"])
        deck.current_cargo_vessel = "SRV"
        self.assertEqual(deck._watcher_lookup_cargo()[0], "The SRV's hold carries 5 tonnes", "the ship's size isn't the SRV's")


class AskedTests(unittest.TestCase):
    def ask(self, question, lookup=(), lately=LATELY):
        llm, _settings = mind_llm(self)
        searched = []
        llm.library_provider = lambda words: searched.append(words) or ["Jameson Memorial: an Orbis starport in Shinrarta Dezhra."]
        wait_ready(llm)
        FakeServer.replies = ["Forty tonnes of tritium."]
        llm.talk(question, FACTS, lately=lately, lookup=list(lookup)).done.wait(2)
        return whole(FakeServer.made[-1].asked[-1]), searched

    def test_a_question_with_a_readout_gets_only_that(self):
        said, searched = self.ask("What cargo do we have?", lookup=["The ship's hold: 40 of 64 tonnes", "Tritium: 40 tonnes"])
        self.assertIn("- Tritium: 40 tonnes", said)
        for left_out in ("Krait Phantom", "Wanderer", "Colonia", "22,000", "Jumped to"):
            self.assertNotIn(left_out, said, left_out)
        self.assertEqual(searched, [], "no library cards beside the ship's own readout")
        self.assertNotIn("Jameson Memorial", said)
        self.assertNotIn("What you know of the galaxy", said, "nor its own cards (the traders' card padded it)")
        self.assertIn("only what was asked", said)

    def test_where_you_are_when_you_ask_where(self):
        said, _ = self.ask("Which station are we at and where is it?", lookup=["Docked at Jaques Station"])
        self.assertIn("- system: Colonia", said)
        self.assertNotIn("Krait Phantom", said)

    def test_everyday_talk_leaves_the_ship_and_the_jumps_out(self):
        said, searched = self.ask("What do you make of all this?")
        self.assertIn("- system: Colonia", said)
        for left_out in ("Krait Phantom", "Wanderer", "22,000", "Jumped to"):
            self.assertNotIn(left_out, said, left_out)
        self.assertEqual(searched, ["What do you make of all this?"], "the ship isn't added to its search")

    def test_what_you_did_when_you_ask_about_the_past(self):
        said, _ = self.ask("What have we done today?")
        self.assertIn("Jumped to Colonia", said)

    def test_how_far_from_home_when_asked(self):
        said, _ = self.ask("How far are we from Sol?")
        self.assertIn("22,000 light years", said)


if __name__ == "__main__":
    unittest.main()
