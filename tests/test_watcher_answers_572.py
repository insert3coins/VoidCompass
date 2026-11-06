"""The Watcher answers plain questions from only the requested ship systems.

Cargo, station, faction, route, world and survey facts remain deterministic
when no language model or source library exists.
"""

from pathlib import Path
import tempfile
import threading
import time
import unittest

from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import watcher_copilot as copilot
from voidcompass.overlays import watcher_mind


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


class PlainAnswerTests(unittest.TestCase):
    def test_question_uses_only_the_requested_readout(self):
        deck = Deck()
        deck._watcher_lookup_cargo = lambda question: ["The ship's hold carries 40 tonnes", "Tritium: 40 tonnes"]
        deck._watcher_lookup_ship = lambda: self.fail("unasked ship details")
        deck._watcher_lookup_route = lambda: self.fail("unasked route details")
        mind = watcher_mind.WatcherMind(None, {})
        mind.lookup_provider = deck._watcher_lookup
        self.assertTrue(mind.talk("What cargo do we have?"))
        self.assertEqual(mind.memory["talk"][-1]["it"], "The ship's hold carries 40 tonnes. Tritium: 40 tonnes.")
        self.assertEqual(mind.thought["text"], mind.memory["talk"][-1]["it"])
        self.assertFalse(mind.talk_waiting())

    def test_everyday_talk_does_not_add_ship_or_trip_facts(self):
        mind = watcher_mind.WatcherMind(None, {})
        mind.lookup_provider = lambda question: self.fail("non-question should not look up the ship")
        self.assertTrue(mind.talk("Hello, Watcher."))
        from voidcompass.overlays import watcher_chat
        self.assertIn(mind.memory["talk"][-1]["it"], watcher_chat.GREETINGS)
        self.assertTrue(mind.talk("Just passing the time."))
        self.assertIn(mind.memory["talk"][-1]["it"], copilot.REPLIES["plain"])


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


# -- planet materials, mining sites, your materials and your Codex -----------------------
SITES = [
    {"name": "North ridge", "materials": "Painite, Platinum", "density": "High", "amount": "Medium",
     "tons_left": "Estimated 220–600 t left", "distance_m": 1240},
    {"name": "Crater floor", "materials": "Osmium", "amount": "Depleted", "tons_left": "Depleted", "distance_m": 300},
]
REFERENCE = {
    "$Codex_Ent_Bacterial_01_G_Name;": ("Bacterium Aurasus - Teal", "Biology"),
    "$Codex_Ent_Bacterial_01_L_Name;": ("Bacterium Aurasus - Lime", "Biology"),
    "$Codex_Ent_Bacterial_01_R_Name;": ("Bacterium Aurasus - Red", "Biology"),
    "$Codex_Ent_Stratum_02_T_Name;": ("Stratum Tectonicas - Green", "Biology"),
    "$Codex_Ent_Seed_Name;": ("Roseum Brain Tree", "Biology"),
    "$Codex_Ent_Green_Water_Giant_Name;": ("Green Water Giant", "Tourist"),
}


class PlanetTopicTests(unittest.TestCase):
    def test_planet_materials_your_materials_and_the_codex(self):
        self.assertEqual(copilot.topics_for("What planet materials do we have?"), ["planet"])
        self.assertEqual(copilot.topics_for("What materials are on this planet?"), ["planet"], "here: the planet's")
        self.assertEqual(copilot.topics_for("Where are the mining sites?"), ["planet"])
        self.assertEqual(copilot.topics_for("What does the ground here hold?"), ["planet"])
        self.assertEqual(copilot.topics_for("What materials do we have?"), ["materials"], "no place: your stock")
        self.assertEqual(copilot.topics_for("What have we logged in the Codex?"), ["codex"])
        self.assertEqual(copilot.topics_for("Have we logged Bacterium Aurasus?"), ["codex"], "the Codex, not a forecast")
        self.assertIn("life", copilot.topics_for("Could Bacterium Aurasus live here?"))
        self.assertEqual(copilot.topics_for("What should I scan here?"), ["survey"])


class PlanetLineTests(unittest.TestCase):
    def test_the_planets_materials_ground_and_sites(self):
        lines = copilot.planet_lines(
            "Colonia 3 C", [{"name": "Iron", "percent": 19.8}, {"name": "Polonium", "percent": 0.6, "rare": True}],
            [{"material": "Painite", "pct": 12.4, "median": 260000}], "Metal-Rich World", SITES, 2, {1: {}, 3: {}},
            [("Colonia 4", 1)], "Colonia")
        self.assertEqual(lines, [
            "Raw materials on Colonia 3 C, from its scan: Iron 20%, Polonium under 1% (rare)",
            "Mining locations its scan found on Colonia 3 C: 2",
            "Metal-Rich World ground tends to hold: Painite (at 12% of sites like it, about 260,000 credits a tonne)",
            "Your saved mining sites on Colonia 3 C: 2",
            "Saved site Crater floor, 300 metres from here: Osmium (depleted)",
            "Saved site North ridge, 1.2 kilometres from here: Painite, Platinum "
            "(high density, medium amount left, about 220 to 600 tonnes left)",
            "Rigs you marked as deployed here (not sites): 2 rigs, rig 1 and rig 3",
            "Saved mining sites elsewhere in the system: 1 on Colonia 4"])

    def test_asked_where_the_sites_are_it_leaves_out_the_crust(self):
        lines = copilot.planet_lines("Colonia 3 C", [{"name": "Iron", "percent": 19.8}], (), "", SITES, 2, focus="sites")
        self.assertFalse(any(line.startswith(("Raw materials", "Mining locations")) for line in lines))
        self.assertEqual(lines[0], "Your saved mining sites on Colonia 3 C: 2")

    def test_no_sites_and_no_planet(self):
        self.assertIn("No saved mining sites on Colonia 3 C", copilot.planet_lines("Colonia 3 C"))
        self.assertEqual(copilot.planet_lines("", elsewhere=[("Colonia 4", 2)], system="Colonia"),
                         ["Not at or near a planet right now", "Saved mining sites in Colonia: 2 on Colonia 4"])

    def test_your_materials(self):
        stock = {"raw": {"iron": {"name": "Iron", "count": 150}, "carbon": {"name": "Carbon", "count": 290}},
                 "encoded": {"echo": {"name": "Atypical Disrupted Wake Echoes", "count": 12}}}
        self.assertEqual(copilot.materials_lines(stock, "how much iron have we got"), ["Iron: 150 (raw)"])
        self.assertEqual(copilot.materials_lines(stock, "what materials do we have"), [
            "Raw materials: 440 in all, 2 kinds", "Encoded materials: 12 in all, 1 kind",
            "Most plentiful raw: Carbon 290, Iron 150"])
        self.assertEqual(copilot.materials_lines(stock, "what encoded materials do we have"), [
            "Encoded materials: 12 in all, 1 kind", "Most plentiful encoded: Atypical Disrupted Wake Echoes 12"])
        self.assertIn("No engineering materials", copilot.materials_lines({}, "materials")[0])


class CodexLineTests(unittest.TestCase):
    def test_what_youve_logged(self):
        now = time.time()
        rows = [["2026-10-01T10:00:00Z", "$Codex_Ent_Bacterial_01_G_Name;", 18, 1, 2],
                ["2026-10-02T10:00:00Z", "$Codex_Ent_Bacterial_01_G_Name;", 20, 1, 2],
                ["2026-10-03T10:00:00Z", "$Codex_Ent_Bacterial_01_L_Name;", 20, 1, 2],
                ["2026-10-04T10:00:00Z", "$Codex_Ent_Seed_Name;", 20, 1, 2],
                ["2026-10-05T10:00:00Z", "$Codex_Ent_Green_Water_Giant_Name;", 18, 1, 0]]
        lines = copilot.codex_lines(rows, REFERENCE, 18, "Inner Orion Spur", "what's in our codex?", now=now)
        self.assertEqual(lines[0], "Biology logged in the commander's Codex: 2 species (3 colours in all), "
                                   "across 2 different galactic regions")
        self.assertEqual(lines[1], "Logged in Inner Orion Spur: 1 colour")
        self.assertTrue(lines[2].startswith("Most recently logged: Roseum Brain Tree ("), lines[2])
        self.assertNotIn("Green Water Giant", " ".join(lines), "biology only")

    def test_a_species_you_name(self):
        rows = [["2026-10-01T10:00:00Z", "$Codex_Ent_Bacterial_01_G_Name;", 20, 1, 2]]
        lines = copilot.codex_lines(rows, REFERENCE, 18, "Inner Orion Spur", "have we logged bacterium aurasus?",
                                    here=["$Codex_Ent_Bacterial_01_G_Name;"], now=time.time())
        self.assertIn("Bacterium Aurasus: 1 of 3 colours logged (Teal)", lines)
        self.assertIn("Bacterium Aurasus colours not logged yet (2): Lime, Red", lines)
        self.assertIn("Bacterium Aurasus is not yet logged in Inner Orion Spur", lines)
        self.assertIn("Logged on this body: Bacterium Aurasus - Teal", lines)
        self.assertFalse(any(line.startswith("Most recently") for line in lines), "the species is the answer")

    def test_nothing_logged(self):
        self.assertEqual(copilot.codex_lines([], REFERENCE), ["No biology logged in the Codex yet"])

    def test_the_games_names_for_its_entries(self):
        from voidcompass.exploration import codex_index
        self.assertEqual(codex_index.reference()["$Codex_Ent_Bacterial_01_O_Name;"],
                         ("Bacterium Aurasus - Turquoise", "Biology"))


class FakeRigs:
    def rigs(self, system, body):
        return {2: {"lat": 1, "lon": 2}}


class FakeIndex:
    def entries(self):
        return [["2026-10-01T10:00:00Z", "$Codex_Ent_Bacterial_01_O_Name;", 18, 99, 4]]

    def entries_on(self, address, body_id):
        return ["$Codex_Ent_Bacterial_01_O_Name;"] if (address, body_id) == (99, 4) else []


class PlanetLookupTests(unittest.TestCase):
    def deck(self):
        deck = Deck()
        deck._html_planet_materials_workspace = lambda: {
            "system": "Colonia", "body": "Colonia 3 C",
            "bodies": [{"body": "Colonia 3 C", "short_name": "3 C", "materials": [{"name": "Iron", "percent": 20}],
                        "ground": "metal-rich", "ground_label": "Metal-Rich World", "class": "Metal rich body",
                        "landable": True, "mining_locations": 1},
                       {"body": "Colonia 4", "short_name": "4", "materials": [{"name": "Sulphur", "percent": 25}]}],
            "sites": [{"system": "Colonia", "body": "Colonia 3 C", "name": "North ridge", "materials": "Painite",
                       "latitude": 10.0, "longitude": 20.0, "planet_radius": 1_000_000, "amount": "High"},
                      {"system": "Colonia", "body": "Colonia 4", "name": "Far side", "materials": "Osmium",
                       "latitude": 0.0, "longitude": 0.0}],
            "current_position": {"latitude": 10.0, "longitude": 20.01, "planet_radius": 1_000_000}}
        deck.rig_store = lambda: FakeRigs()
        return deck

    def test_the_planet_youre_on(self):
        lines = self.deck()._watcher_lookup_planet("what planet materials do we have?")
        self.assertEqual(lines[0], "Raw materials on Colonia 3 C, from its scan: Iron 20%")
        site = next(line for line in lines if line.startswith("Saved site North ridge"))
        self.assertIn("metres from here", site)
        self.assertIn("Rigs you marked as deployed here (not sites): 1 rig, rig 2", lines)
        self.assertIn("Saved mining sites elsewhere in the system: 1 on Colonia 4", lines)

    def test_a_planet_you_name(self):
        lines = self.deck()._watcher_lookup_planet("what materials are on Colonia 4?")
        self.assertEqual(lines[0], "Raw materials on Colonia 4, from its scan: Sulphur 25%")
        self.assertFalse(any("from here" in line for line in lines), "no distance to another planet's sites")

    def test_the_codex_from_its_index(self):
        deck = Deck()
        deck.codex_index = FakeIndex()
        deck._bio_location_context = lambda: (18, (0, 0, 0))
        deck.current_system_address, deck.current_body_id = 99, 4
        lines = deck._watcher_lookup_codex("what have we logged here in the codex?")
        self.assertEqual(lines[1], "Logged in Inner Orion Spur: 1 colour")
        self.assertIn("Logged on this body: Bacterium Aurasus - Turquoise", lines)

    def test_your_materials_from_the_journal(self):
        deck = Deck()
        deck.engineer_materials = {"raw": {"iron": {"name": "Iron", "count": 9}}}
        self.assertEqual(deck._watcher_lookup_materials("how much iron?"), ["Iron: 9 of 300 (raw, grade 1)"])


# -- missions, ranks, carrier, unsold data, the world here, your record, rebuy -----------
class MoreTopicTests(unittest.TestCase):
    def test_each_finds_its_own(self):
        for said, topic in (("What missions do we have?", "missions"), ("What rank am I in exploration?", "ranks"),
                            ("What's our reputation with the Federation?", "ranks"), ("Where is our carrier?", "carrier"),
                            ("How much is our exploration data worth?", "data"), ("What's the gravity here?", "world"),
                            ("Tell me about this planet", "world"), ("What's this moon like?", "world"),
                            ("How many jumps have we made in total?", "record"), ("How long have we played?", "record"),
                            ("What's our rebuy?", "ship"), ("Are we wanted?", "ship")):
            self.assertEqual(copilot.topics_for(said), [topic], said)
        self.assertEqual(copilot.topics_for("How many jumps left?"), ["route"], "the route, not your record")


class MoreLineTests(unittest.TestCase):
    def test_missions_soonest_first(self):
        now = time.mktime((2026, 11, 1, 12, 0, 0, 0, 0, 0)) - time.timezone
        lines = copilot.missions_lines([
            {"name": "Deliver Gold", "destination_system": "Sol", "destination_station": "Abraham Lincoln",
             "commodity": "Gold", "count": 20, "reward": 1250000, "expiry": "2026-11-04T12:00:00Z"},
            {"name": "Kill pirates", "target": "Pirates", "kill_count": 12, "reward": 3000000, "expiry": "2026-11-02T12:00:00Z",
             "illegal": True}], now)
        self.assertEqual(lines, ["Active missions: 2, paying 4,250,000 credits in all",
                                 "Kill pirates: 12 kills of Pirates, pays 3,000,000 credits, 24 hours left, illegal",
                                 "Deliver Gold: to Abraham Lincoln, Sol, 20 tonnes of Gold, pays 1,250,000 credits, 3 days left"])
        self.assertEqual(copilot.missions_lines([], now), ["No active missions"])

    def test_ranks_and_the_superpowers(self):
        from voidcompass.core import ranks
        lines = copilot.ranks_lines({"Combat": 6, "Explore": 9, "Federation": 0, "Empire": 3}, {"Combat": 45},
                                    {"Federation": 100.0, "Empire": -40.0}, names=ranks.name)
        self.assertEqual(lines, ["Combat: Dangerous, 45% of the way to the next rank", "Exploration: Elite I",
                                 "Imperial Navy: Master", "Superpower reputation: Federation allied, Empire unfriendly"])
        self.assertIn("No ranks on record", copilot.ranks_lines({}, names=ranks.name)[0])

    def test_the_carrier(self):
        lines = copilot.carrier_lines({"carrier_id": 1, "name": "Black Rose", "callsign": "K7Q-1HT", "system": "Colonia",
                                       "status": "jumping", "jump_destination": "Sol", "fuel_level": 640,
                                       "fuel_capacity": 1000, "fuel_level_estimated": True, "balance": 2_500_000_000,
                                       "available_balance": 1_900_000_000, "docking_access": "squadron",
                                       "space_free": 12000})
        self.assertEqual(lines, ["The carrier Black Rose (K7Q-1HT) is in Colonia", "Jumping to Sol",
                                 "Tritium in its tank: 640 of 1000 tonnes (estimated)",
                                 "Its balance: 2,500,000,000 credits, 1,900,000,000 available",
                                 "Docking open to the squadron only", "Free space: 12,000 tonnes"])
        self.assertEqual(copilot.carrier_lines(None), ["No fleet carrier on record"])

    def test_unsold_data(self):
        self.assertEqual(copilot.data_lines(48_210_000, 12_400_000)[-1],
                         "Together about 60,610,000 credits, lost if the ship is destroyed")
        self.assertEqual(copilot.data_lines(0, 0), ["No unsold exploration or exobiology data"])

    def test_the_world_here(self):
        world = {"full_name": "Colonia 3 C", "planet_class": "High metal content body", "landable": True, "gravity_g": 2.4,
                 "surface_temp": 180, "atmosphere_type": "Thin Ammonia", "distance_to_arrival": 1240, "reward": 45000,
                 "dss_reward": 210000, "was_discovered": False, "was_mapped": False, "radius": 1_800_000,
                 "rotation_period": 216000, "tidal_lock": True}
        lines = copilot.world_lines(world)
        self.assertEqual(lines, ["Colonia 3 C: a High metal content body, landable", "Gravity: 2.40 g (heavy)",
                                 "Surface temperature: -93 degrees Celsius", "Atmosphere: Thin Ammonia",
                                 "Distance from the arrival star: 1,240 light seconds",
                                 "Worth about 45,000 credits scanned and 210,000 credits mapped",
                                 "The commander was the first to discover it and map it"])
        detailed = copilot.world_lines(world, "how big is it?")
        self.assertIn("Radius: 1,800 kilometres", detailed)
        self.assertIn("One rotation takes 2.5 days (tidally locked)", detailed)
        self.assertEqual(copilot.world_lines({"full_name": "Hypio A", "is_star": True, "star_type": "N"})[0],
                         "Hypio A: a neutron star")
        self.assertEqual(copilot.world_lines(None), ["No scanned world here to describe"])

    def test_your_record(self):
        stats = {"Exploration": {"Time_Played": 3600 * 412, "Systems_Visited": 5120, "Total_Hyperspace_Jumps": 8800},
                 "Combat": {"Bounties_Claimed": 40}, "Bank_Account": {"Current_Wealth": 3.4e9}}
        self.assertIn("Lifetime hyperspace jumps: 8,800", copilot.record_lines(stats, "how many jumps in total"))
        self.assertEqual(copilot.record_lines(stats, "how many bounties have I claimed?"), ["Lifetime bounties claimed: 40"])
        self.assertEqual(copilot.record_lines(stats, "show me our stats"), [
            "Lifetime time played: 412 hours", "Lifetime systems visited: 5,120", "Lifetime hyperspace jumps: 8,800",
            "Lifetime current wealth: 3,400,000,000 credits"])
        self.assertIn("No lifetime record", copilot.record_lines(None)[0])

    def test_rebuy_and_legal_status_with_the_ship(self):
        lines = copilot.ship_lines("Krait Phantom", rebuy=4_200_000, legal="Wanted")
        self.assertIn("Rebuy (the insurance to replace the ship): 4,200,000 credits", lines)
        self.assertIn("Legal status: wanted", lines)
        self.assertIn("Legal status: carrying illegal cargo", copilot.ship_lines(legal="IllegalCargo"))


class MoreLookupTests(unittest.TestCase):
    def test_from_the_decks_own_records(self):
        deck = Deck()
        deck.companion_state = {"missions": {"7": {"name": "Deliver Gold", "reward": 10}}, "unsold_exploration_cr": 500,
                                "unsold_bio_cr": 100, "unsold_bio_bonus_potential_cr": 400,
                                "statistics": {"Exploration": {"Systems_Visited": 9}}}
        self.assertEqual(deck._watcher_lookup_missions()[0], "Active missions: 1, paying 10 credits in all")
        self.assertEqual(deck._watcher_lookup_data()[1], "Unsold exobiology samples: about 500 credits (sold at Vista Genomics)")
        self.assertEqual(deck._watcher_lookup_record("how many systems have we visited"), ["Lifetime systems visited: 9"])
        deck.cmdr_ranks, deck.cmdr_rank_progress, deck.cmdr_reputation = {"Explore": 8}, {"Explore": 50}, {}
        self.assertEqual(deck._watcher_lookup_ranks(), ["Exploration: Elite, 50% of the way to the next rank"])
        deck.carrier_tracker = type("Tracker", (), {"display_carrier": lambda self: {"carrier_id": 1, "name": "Rose"}})()
        self.assertEqual(deck._watcher_lookup_carrier(), ["The carrier Rose"])

    def test_the_world_you_name_or_are_at(self):
        deck = Deck()
        deck.scan_items = [{"name": "3 C", "full_name": "Colonia 3 C", "planet_class": "Icy body"},
                           {"name": "4", "full_name": "Colonia 4", "planet_class": "Rocky body"}]
        deck.current_body_name = "Colonia 3 C"
        self.assertEqual(deck._watcher_lookup_world("what's the gravity here?")[0], "Colonia 3 C: an Icy body")
        self.assertEqual(deck._watcher_lookup_world("tell me about planet 4?")[0], "Colonia 4: a Rocky body")


# -- what the cargo is worth, and commodity prices -----------------------------------------
HELD = [{"symbol": "tritium", "name": "Tritium", "count": 40, "stolen": 0},
        {"symbol": "lowtemperaturediamond", "name": "Low Temperature Diamonds", "count": 12, "stolen": 0},
        {"symbol": "imperialslaves", "name": "Imperial Slaves", "count": 2, "stolen": 2}]
ITEMS = [{"symbol": "gold", "name": "Gold", "buy": 48000, "sell": 47000, "mean": 46000, "stock": 500, "demand": 0},
         {"symbol": "tritium", "name": "Tritium", "buy": 0, "sell": 51000, "mean": 42000, "stock": 0, "demand": 900},
         {"symbol": "water", "name": "Water", "buy": 200, "sell": 150, "mean": 400, "stock": 9000, "demand": 0},
         {"symbol": "painite", "name": "Painite", "buy": 0, "sell": 300000, "mean": 250000, "stock": 0, "demand": 20}]


class PriceTopicTests(unittest.TestCase):
    def test_prices_and_value(self):
        self.assertEqual(copilot.topics_for("What's the value of my cargo?"), ["cargo"])
        self.assertEqual(copilot.topics_for("What's the price of gold?"), ["market"])
        self.assertEqual(copilot.topics_for("What's good to sell here?"), ["market"])
        self.assertEqual(copilot.topics_for("How much can I sell our exploration data for?"), ["data"], "the data, not a market")


class PriceLineTests(unittest.TestCase):
    def test_the_cargo_priced_where_youre_docked(self):
        lines = copilot.cargo_value_lines(HELD, "Jaques Station", {"tritium": 51000, "lowtemperaturediamond": 180000},
                                          {"tritium": 42000, "lowtemperaturediamond": 120000},
                                          {"lowtemperaturediamond": 650000}, {"tritium": 38000})
        self.assertEqual(lines, [
            "The cargo would sell for 4,200,000 credits in all at Jaques Station",
            "Tritium, 40 tonnes: 2,040,000 credits here, 51,000 a tonne, galactic average 42,000 a tonne, "
            "bought for about 38,000 a tonne",
            "Low Temperature Diamonds, 12 tonnes: 2,160,000 credits here, 180,000 a tonne, galactic average 120,000 a tonne, "
            "best price anywhere right now 650,000 a tonne",
            "Imperial Slaves, 2 tonnes: not bought at Jaques Station, stolen, so only a black market buys it"])

    def test_the_cargo_at_galactic_averages_in_flight(self):
        lines = copilot.cargo_value_lines(HELD[:2], "", {}, {"tritium": 42000, "lowtemperaturediamond": 120000})
        self.assertEqual(lines[0], "At the galactic average prices, the cargo is worth about 3,120,000 credits in all")
        self.assertIn("No prices known", copilot.cargo_value_lines(HELD[:1], "", {}, {})[0])
        self.assertEqual(copilot.cargo_value_lines([], "", {}, {}), [])

    def test_a_commodity_you_name(self):
        lines = copilot.market_lines("Jaques Station", ITEMS, [("gold", "Gold"), ("painite", "Painite"), ("voidopal", "Void Opal")],
                                     True, None, {"Painite": (None, 520000)})
        self.assertEqual(lines, [
            "Prices at Jaques Station",
            "Gold: Jaques Station sells it for 48,000 a tonne (500 in stock), galactic average 46,000 a tonne",
            "Painite: Jaques Station buys it for 300,000 a tonne, galactic average 250,000 a tonne",
            "Painite, best prices anywhere right now: sells for up to 520,000 a tonne",
            "Void Opal: not traded at Jaques Station"])

    def test_what_sells_well_and_whats_cheap(self):
        lines = copilot.market_lines("Jaques Station", ITEMS, (), False, 3 * 86400)
        self.assertEqual(lines, [
            "Prices at Jaques Station, the last market the commander opened (3 days ago)",
            "Best to sell there (above the galactic average): Tritium 51,000 (average 42,000), Painite 300,000 (average 250,000)",
            "Cheapest to buy there (below the galactic average): Water 200 (average 400)"])

    def test_best_prices_being_fetched_and_no_market_yet(self):
        self.assertEqual(copilot.market_lines("", [], [("gold", "Gold")], fetching=True),
                         ["Best prices anywhere are being fetched from Spansh: ask again in a moment"])
        self.assertIn("No market prices known yet", copilot.market_lines("", [], ())[0])


class PriceLookupTests(unittest.TestCase):
    def deck(self, folder):
        import json
        deck = Deck()
        deck.config = {"journal_path": folder}
        deck.current_docked, deck.current_station_market_id = True, 128666762
        (Path(folder) / "Market.json").write_text(json.dumps({
            "timestamp": "2026-11-01T10:00:00Z", "MarketID": 128666762, "StationName": "Jaques Station",
            "Items": [{"Name": "$gold_name;", "Name_Localised": "Gold", "BuyPrice": 48000, "SellPrice": 47000,
                       "MeanPrice": 46000, "Stock": 500, "Demand": 0},
                      {"Name": "$tritium_name;", "Name_Localised": "Tritium", "BuyPrice": 0, "SellPrice": 51000,
                       "MeanPrice": 42000, "Stock": 0, "Demand": 900},
                      {"Name": "$lowtemperaturediamond_name;", "Name_Localised": "Low Temperature Diamonds",
                       "BuyPrice": 0, "SellPrice": 180000, "MeanPrice": 120000, "Stock": 0, "Demand": 50}]}),
            encoding="utf-8")
        deck.trading_names = None
        deck._trading_online = lambda: False
        deck._trading_cargo = lambda: [{"symbol": "tritium", "name": "Tritium", "count": 10, "stolen": 0}]
        deck.trading_store = FakeTrades()
        deck.current_cargo_inventory = [{"Name": "tritium", "Count": 10}]
        deck.current_cargo_vessel = "Ship"
        deck._active_cargo_capacity = lambda: 64
        return deck

    def test_the_cargo_value_from_the_games_market_file(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = self.deck(folder)
            lines = deck._watcher_lookup_cargo("what's the value of my cargo?")
            self.assertEqual(lines[0], "The cargo would sell for 510,000 credits in all at Jaques Station")
            self.assertIn("bought for about 36,000 a tonne", lines[1], "6 at 40,000 and 4 at 30,000: your buys since the last sale")
            self.assertEqual(lines[-1], "Tritium: 10 tonnes")
            self.assertEqual(deck._watcher_lookup_cargo("what cargo do we have?")[0],
                             "The ship's hold carries 10 tonnes, with 54 tonnes free", "no prices unless asked")

    def test_a_price_and_a_named_commodity(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = self.deck(folder)
            lines = deck._watcher_lookup_market("what are LTDs going for?")
            self.assertIn("Low Temperature Diamonds: Jaques Station buys it for 180,000 a tonne, galactic average 120,000 a tonne",
                          lines)
            self.assertEqual(deck._watcher_commodities_named("price of gold and low temperature diamonds",
                                                             deck._watcher_market_file()["items"]),
                             [("lowtemperaturediamond", "Low Temperature Diamonds"), ("gold", "Gold")])

    def test_a_commodity_you_carry_with_a_price_word_finds_its_value(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = self.deck(folder)
            deck._watcher_lookup_market = lambda question="": ["market"]
            self.assertEqual(deck._watcher_lookup("what's my tritium worth?")[0],
                             "The cargo would sell for 510,000 credits in all at Jaques Station")


class FakeTrades:
    def query(self, sql, params=()):
        if params == ("tritium",):
            return [{"kind": "buy", "count": 6, "price": 40000}, {"kind": "buy", "count": 10, "price": 30000},
                    {"kind": "sell", "count": 4, "price": 50000}]
        return []


if __name__ == "__main__":
    unittest.main()
