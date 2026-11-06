"""More of the journal, in every companion's words (5.7.6): danger and the
law, missions and community goals, ships and engineers, the carrier,
colonies and Powerplay, the crew, wings and the kit you wear. Fields as the
journal schema (schemas.edomh.nl) gives them."""
import random
import re
import unittest

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, life_events, ship_life, watcher_mind
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian")
EVENTS = {
    "CockpitBreached": ({}, "cockpit_breached"),
    "SystemsShutdown": ({}, "systems_shutdown"),
    "SelfDestruct": ({}, "self_destruct"),
    "CommitCrime": ({"CrimeType": "fireInNoFireZone", "Faction": "Police", "Fine": 400}, "crime_committed"),
    "CrimeVictim": ({"Offender": "Cmdr Rude", "CrimeType": "assault", "Bounty": 200}, "crime_victim"),
    "PayFines": ({"Amount": 1200, "AllFines": True, "ShipID": 4}, "paid_off"),
    "ClearImpound": ({"ShipType": "python", "ShipType_Localised": "Python", "ShipID": 3, "ShipMarketID": 1, "MarketID": 2}, "impound_cleared"),
    "RebootRepair": ({"Modules": ["FrameShiftDrive"]}, "reboot_repair"),
    "Interdiction": ({"Success": True, "Interdicted": "Ruthless Pirate", "IsPlayer": False}, "interdicted_them"),
    "MissionAccepted": ({"Faction": "F", "Name": "Mission_Delivery", "LocalisedName": "Deliver 12 units of Gold", "MissionID": 9,
                         "DestinationSystem": "Lave", "DestinationStation": "Lave Station", "Wing": False, "Influence": "+", "Reputation": "+"},
                        "mission_accepted"),
    "MissionFailed": ({"Name": "Mission_Courier", "LocalisedName": "Courier run to Diso", "MissionID": 9}, "mission_failed"),
    "MissionAbandoned": ({"Name": "Mission_Courier", "LocalisedName": "Courier run to Diso", "MissionID": 9}, "mission_abandoned"),
    "MissionRedirected": ({"MissionID": 9, "Name": "Mission_Massacre", "LocalisedName": "Kill pirates", "NewDestinationStation": "Lave Station",
                           "NewDestinationSystem": "Lave", "OldDestinationStation": "", "OldDestinationSystem": "Diso"}, "mission_redirected"),
    "SearchAndRescue": ({"MarketID": 1, "Name": "occupiedcryopod", "Name_Localised": "Occupied Escape Pod", "Count": 3, "Reward": 30000},
                        "rescue_handed_in"),
    "CommunityGoalJoin": ({"CGID": 1, "Name": "Defend Tionisla", "System": "Tionisla"}, "cg_joined"),
    "CommunityGoalReward": ({"CGID": 1, "Name": "Defend Tionisla", "System": "Tionisla", "Reward": 5000000}, "cg_reward"),
    "CommunityGoalDiscard": ({"CGID": 1, "Name": "Defend Tionisla", "System": "Tionisla"}, "cg_left"),
    "ShipyardBuy": ({"ShipType": "mandalay", "ShipType_Localised": "Mandalay", "ShipPrice": 17000000, "MarketID": 1}, "ship_bought"),
    "ShipyardSell": ({"ShipType": "sidewinder", "SellShipID": 1, "ShipPrice": 30000, "MarketID": 1}, "ship_sold"),
    "SetUserShipName": ({"Ship": "mandalay", "ShipID": 9, "UserShipName": "Long Way Round"}, "ship_named"),
    "ModuleBuy": ({"Slot": "Slot01", "BuyItem": "int_fuelscoop_size5_class5", "BuyItem_Localised": "5A Fuel Scoop", "MarketID": 1,
                   "BuyPrice": 9000000, "Ship": "mandalay", "ShipID": 9}, "outfitted"),
    "ShipyardTransfer": ({"ShipType": "python", "ShipType_Localised": "Python", "ShipID": 3, "System": "Shinrarta Dezhra",
                          "ShipMarketID": 1, "Distance": 120.5, "TransferPrice": 40000, "TransferTime": 1460, "MarketID": 2}, "ship_transfer"),
    "EngineerProgress": ({"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Unlocked", "Rank": 3}, "engineer_rank"),
    "MaterialDiscovered": ({"Category": "Raw", "Name": "polonium", "Name_Localised": "Polonium", "DiscoveryNumber": 30}, "material_discovered"),
    "MaterialTrade": ({"MarketID": 1, "TraderType": "raw", "Paid": {"Material": "iron", "Category": "Raw", "Quantity": 36},
                       "Received": {"Material": "arsenic", "Material_Localised": "Arsenic", "Category": "Raw", "Quantity": 2}}, "material_traded"),
    "CarrierBuy": ({"CarrierID": 1, "BoughtAtMarket": 2, "Location": "Sol", "SystemAddress": 3, "Price": 5000000000, "Variant": "x",
                    "Callsign": "XNG-40Z"}, "carrier_bought"),
    "CarrierNameChange": ({"CarrierID": 1, "Name": "THE LONG WAY", "Callsign": "XNG-40Z"}, "carrier_renamed"),
    "CarrierDecommission": ({"CarrierID": 1, "ScrapRefund": 1, "ScrapTime": 2}, "carrier_decommission"),
    "CarrierCancelDecommission": ({"CarrierID": 1}, "carrier_kept"),
    "CarrierDepositFuel": ({"CarrierID": 1, "Amount": 200, "Total": 1000}, "carrier_fuelled"),
    "CarrierTradeOrder": ({"CarrierID": 1, "BlackMarket": False, "Commodity": "tritium", "Commodity_Localised": "Tritium",
                           "PurchaseOrder": 500, "Price": 50000}, "carrier_order"),
    "ColonisationSystemClaim": ({"StarSystem": "HIP 12345", "SystemAddress": 1}, "colony_claimed"),
    "ColonisationSystemClaimRelease": ({"StarSystem": "HIP 12345", "SystemAddress": 1}, "colony_released"),
    "ColonisationBeaconDeployed": ({}, "colony_beacon"),
    "ColonisationContribution": ({"MarketID": 1, "Contributions": [{"Name": "$Steel_Name;", "Name_Localised": "Steel", "Amount": 600},
                                                                   {"Name": "$CMMComposite_Name;", "Name_Localised": "CMM Composite", "Amount": 120}]},
                                 "colony_contribution"),
    "PowerplayJoin": ({"Power": "Nakato Kaine"}, "power_joined"),
    "PowerplayLeave": ({"Power": "Nakato Kaine"}, "power_left"),
    "PowerplayDefect": ({"FromPower": "Nakato Kaine", "ToPower": "Archon Delaine"}, "power_defected"),
    "PowerplayMerits": ({"Power": "Nakato Kaine", "MeritsGained": 120, "TotalMerits": 4300}, "power_merits"),
    "PowerplaySalary": ({"Power": "Nakato Kaine", "Amount": 500000}, "power_salary"),
    "BuySuit": ({"Name": "explorationsuit_class1", "Name_Localised": "Artemis Suit", "Price": 150000, "SuitID": 1, "SuitMods": []}, "suit_bought"),
    "BuyWeapon": ({"Name": "wpn_m_assaultrifle_kinetic_fauto", "Name_Localised": "Karma AR-50", "Class": 1, "Price": 1, "SuitModuleID": 1,
                   "WeaponMods": []}, "weapon_bought"),
    "UpgradeSuit": ({"Name": "explorationsuit_class1", "Name_Localised": "Artemis Suit", "SuitID": 1, "Class": 3, "Cost": 1}, "kit_upgraded"),
    "DropshipDeploy": ({"StarSystem": "Sol", "SystemAddress": 1, "Body": "Mars", "BodyID": 4, "OnStation": False, "OnPlanet": True},
                       "dropship_deployed"),
    "JoinACrew": ({"Captain": "Cmdr Friend"}, "multicrew_joined"),
    "QuitACrew": ({"Captain": "Cmdr Friend"}, "multicrew_left"),
    "CrewMemberJoins": ({"Crew": "Cmdr Buddy"}, "multicrew_member_joined"),
    "CrewMemberQuits": ({"Crew": "Cmdr Buddy"}, "multicrew_member_left"),
    "CrewHire": ({"Name": "Vera Hale", "CrewID": 1, "Faction": "F", "Cost": 1, "CombatRank": 2}, "npc_hired"),
    "CrewFire": ({"Name": "Vera Hale", "CrewID": 1}, "npc_fired"),
    "NpcCrewRank": ({"NpcCrewName": "Vera Hale", "NpcCrewId": 1, "RankCombat": 5}, "npc_ranked"),
    "WingInvite": ({"Name": "Cmdr Wingmate"}, "wing_invite"),
    "WingLeave": ({}, "wing_left"),
}


class MomentTests(unittest.TestCase):
    def test_every_event_reads_its_fields(self):
        for event, (raw, topic) in EVENTS.items():
            with self.subTest(event=event):
                found = ship_life.moment(event, {"event": event, **raw})
                self.assertEqual(found[0], topic)
        self.assertEqual(ship_life.moment("CommitCrime", {"CrimeType": "dockingMinorBlockingAirlock", "Faction": "x"})[1]["crime"],
                         "blocking the airlock")
        self.assertEqual(life_events.crime("onFoot_detectionOfWeapon"), "carrying a weapon where it's banned")
        self.assertEqual(life_events.crime("someNewCrime"), "some new crime", "an unknown kind still reads as words")
        self.assertEqual(ship_life.moment("NpcCrewRank", EVENTS["NpcCrewRank"][0])[1]["rank"], "Master")
        self.assertEqual(ship_life.moment("ShipyardTransfer", EVENTS["ShipyardTransfer"][0])[1]["minutes"], "24")
        self.assertEqual(ship_life.moment("ColonisationContribution", EVENTS["ColonisationContribution"][0])[1],
                         {"tonnes": "720", "commodity": "Steel", "Tonnes": "720", "Commodity": "Steel"})

    def test_what_stays_quiet(self):
        self.assertIsNone(ship_life.moment("Interdiction", {"Success": False, "Interdicted": "X", "IsPlayer": False}))
        self.assertIsNone(ship_life.moment("EngineerProgress", {"Engineers": [{"Engineer": "X", "Progress": "Unlocked"}]}),
                          "the start-of-session list isn't news")
        self.assertIsNone(ship_life.moment("PowerplayMerits", {"Power": "X", "MeritsGained": 0, "TotalMerits": 9}))
        self.assertIsNone(ship_life.moment("PayFines", {"Amount": 0, "ShipID": 1}))
        self.assertIsNone(ship_life.moment("CarrierTradeOrder", {"CarrierID": 1, "BlackMarket": False, "Commodity": "gold"}))


class CompanionTests(unittest.TestCase):
    def test_every_companion_speaks_to_every_event(self):
        for identity in CREW:
            config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
            companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(4))
            companion.memory["hours"] = 30
            companion.session_start()
            companion.random.random = lambda: 0.0
            for event, (raw, topic) in EVENTS.items():
                with self.subTest(identity=identity, event=event):
                    companion.clock.now += 1300
                    thought = companion.observe(event, {"event": event, **raw})
                    self.assertEqual((thought or {}).get("topic"), topic)
                    self.assertNotIn("{", thought["text"])
                    self.assertFalse(re.match(r"[a-z]", thought["text"]), thought["text"])

    def test_depth_for_every_companion(self):
        fields = {"crime": "x", "Crime": "X", "penalty": "p", "Penalty": "P", "offender": "o", "credits": "1 credits", "kind": "fines",
                  "Kind": "Fines", "ship": "S", "target": "T", "mission": "M", "where": "W", "station": "St", "system": "Sy", "item": "i",
                  "count": "2", "goal": "G", "name": "N", "module": "Mo", "minutes": "3", "engineer": "E", "rank": "R",
                  "material": "Ma", "paid": "a", "paid_n": "1", "received": "b", "received_n": "2", "callsign": "C", "tonnes": "4",
                  "total": "5", "commodity": "Co", "order": "buy order", "power": "P", "old": "O", "merits": "6", "suit": "Su",
                  "weapon": "We", "grade": "3", "body": "B", "captain": "Ca"}
        fields.update({key[:1].upper() + key[1:]: value for key, value in list(fields.items())})
        for topic, level in life_events.IMPORTANCE.items():
            self.assertEqual(watcher_mind.IMPORTANCE[topic], level)
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10, topic)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10, topic)
            for line in list(watcher_mind.TOPICS[topic][1]) + list(watcher_mind.WEARY[topic]):
                self.assertNotIn("{", line.format(**fields), (topic, line))
            for identity in ("aster", "axiom", "meridian"):
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))
                for line in lines.event_lines(topic):
                    self.assertNotIn("{", line.format(**fields), (identity, topic, line))


if __name__ == "__main__":
    unittest.main()
