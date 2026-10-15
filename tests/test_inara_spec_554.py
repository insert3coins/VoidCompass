"""Inara events checked against the official API docs (inara.cz/elite/inara-api-docs,
read 2026-10-16): each journal event becomes what the docs' own journal-to-JSON
examples show."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock

from voidcompass.services import inara

ROOT = Path(__file__).resolve().parents[1]


def names(events):
    return [name for name, _data in events]


class ShipTests(unittest.TestCase):
    HERE = {"system": "Sol", "station": "Abraham Lincoln"}

    def test_buying_storing_selling_and_swapping(self):
        stored = inara.map_event("ShipyardBuy", {"ShipType": "hauler", "StoreOldShip": "SideWinder", "StoreShipID": 2,
                                                 "MarketID": 128016640}, self.HERE)
        self.assertEqual(stored, [("setCommanderShip", {"shipType": "SideWinder", "shipGameID": 2, "starsystemName": "Sol",
                                                        "stationName": "Abraham Lincoln", "marketID": 128016640})])
        self.assertEqual(inara.map_event("ShipyardNew", {"ShipType": "hauler", "NewShipID": 4}),
                         [("addCommanderShip", {"shipType": "hauler", "shipGameID": 4})])
        sold = inara.map_event("ShipyardBuy", {"ShipType": "hauler", "SellOldShip": "SideWinder", "SellShipID": 2})
        self.assertEqual(sold, [("delCommanderShip", {"shipType": "SideWinder", "shipGameID": 2})])
        swap_sold = inara.map_event("ShipyardSwap", {"ShipType": "sidewinder", "ShipID": 10, "SellOldShip": "Asp", "SellShipID": 2})
        self.assertEqual(swap_sold, [("delCommanderShip", {"shipType": "Asp", "shipGameID": 2}),
                                     ("setCommanderShip", {"shipType": "sidewinder", "shipGameID": 10, "isCurrentShip": True})])
        swap = inara.map_event("ShipyardSwap", {"ShipType": "sidewinder", "ShipID": 10, "StoreOldShip": "Asp", "StoreShipID": 2}, self.HERE)
        self.assertEqual(swap[0][1]["starsystemName"], "Sol", "the stored ship is where you are")
        self.assertNotIn("isCurrentShip", swap[0][1])
        self.assertEqual(inara.map_event("SellShipOnRebuy", {"ShipType": "Adder", "System": "Eranin", "SellShipId": 6}),
                         [("delCommanderShip", {"shipType": "Adder", "shipGameID": 6})])

    def test_a_transfer_is_recorded_where_you_are(self):
        events = inara.map_event("ShipyardTransfer", {"ShipType": "SideWinder", "ShipID": 7, "System": "Eranin",
                                                      "TransferTime": 2262}, self.HERE)
        self.assertEqual(events, [("setCommanderShipTransfer", {"shipType": "SideWinder", "shipGameID": 7, "starsystemName": "Sol",
                                                                "stationName": "Abraham Lincoln", "transferTime": 2262})])


class StateTests(unittest.TestCase):
    def test_credits_only_with_the_game_loaded(self):
        self.assertEqual(names(inara.map_event("LoadGame", {"Credits": 800, "Loan": 0})), ["setCommanderCredits"])
        self.assertFalse(hasattr(inara.InaraUploader, "credits"))
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertNotIn("inara.credits(", source)

    def test_engineers_only_in_stages_inara_knows(self):
        events = inara.map_event("EngineerProgress", {"Engineers": [
            {"Engineer": "Elvira Martuuk", "Progress": "Unlocked", "Rank": 4},
            {"Engineer": "Liz Ryder", "Progress": "Known"},
            {"Engineer": "Felicity Farseer", "Progress": "Invited"}]})
        self.assertEqual(events[0][1], [{"engineerName": "Elvira Martuuk", "rankStage": "Unlocked", "rankValue": 4},
                                        {"engineerName": "Felicity Farseer", "rankStage": "Invited"}])
        single = inara.map_event("EngineerProgress", {"Engineer": "Liz Ryder", "Progress": "Acquainted"})
        self.assertEqual(single, [("setCommanderRankEngineer", [{"engineerName": "Liz Ryder", "rankStage": "Acquainted"}])])

    def test_minor_faction_reputation_from_jumps(self):
        events = inara.map_event("FSDJump", {"StarSystem": "Inara", "StarPos": [0, 0, 0], "JumpDist": 5, "Factions": [
            {"Name": "Inara Nexus", "MyReputation": 76.0}, {"Name": "Inara Independents", "MyReputation": -24.0}]})
        self.assertEqual(events[1], ("setCommanderReputationMinorFaction", [
            {"minorfactionName": "Inara Nexus", "minorfactionReputation": 0.76},
            {"minorfactionName": "Inara Independents", "minorfactionReputation": -0.24}]))

    def test_landed_location_and_dropships(self):
        location = inara.map_event("Location", {"StarSystem": "Inara", "Body": "Someplanet", "BodyType": "Planet",
                                                "Latitude": 7.18, "Longitude": 104.71})
        self.assertEqual(location[0][1]["starsystemBodyCoords"], [7.18, 104.71])
        drop = inara.map_event("DropShipDeploy", {"StarSystem": "Kokatese", "Body": "Kokatese A1"})
        self.assertEqual(drop, [("addCommanderTravelLand", {"starsystemName": "Kokatese", "isTaxiDropship": True,
                                                            "starsystemBodyName": "Kokatese A1"})])


class InventoryTests(unittest.TestCase):
    def test_materials_spent_and_gained_elsewhere(self):
        trade = inara.map_event("MaterialTrade", {"Paid": {"Material": "iron", "Quantity": 6},
                                                  "Received": {"Material": "nickel", "Quantity": 1}})
        self.assertEqual(trade, [("delCommanderInventoryMaterialsItem", {"itemName": "iron", "itemCount": 6}),
                                 ("addCommanderInventoryMaterialsItem", {"itemName": "nickel", "itemCount": 1})])
        for event, raw in (("Synthesis", {"Materials": [{"Name": "iron", "Count": 2}]}),
                           ("EngineerCraft", {"Ingredients": [{"Name": "iron", "Count": 2}]}),
                           ("TechnologyBroker", {"Materials": [{"Name": "iron", "Count": 2}]}),
                           ("ScientificResearch", {"Name": "iron", "Count": 2}),
                           ("EngineerContribution", {"Type": "Materials", "Material": "iron", "Quantity": 2})):
            with self.subTest(event=event):
                self.assertEqual(inara.map_event(event, raw),
                                 [("delCommanderInventoryMaterialsItem", {"itemName": "iron", "itemCount": 2})])

    def test_an_empty_hold_is_reset(self):
        self.assertEqual(inara.map_event("Cargo", {"Vessel": "Ship", "Inventory": []}),
                         [("resetCommanderInventory", {"itemType": "Commodity"})])

    def test_cargo_and_locker_snapshots_reach_inara(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('self._inara_snapshot("Cargo", {"Vessel": "Ship", "Inventory": incoming_inventory})', source)
        self.assertIn('self._inara_snapshot("ShipLocker"', source)


class MissionAndCombatTests(unittest.TestCase):
    def test_a_completed_mission_with_permits_effects_and_materials(self):
        events = inara.map_event("MissionCompleted", {
            "MissionID": 171735583, "Reward": 12000, "PermitsAwarded": ["Alioth"],
            "MaterialsReward": [{"Name": "arsenic", "Count": 2}],
            "FactionEffects": [{"Faction": "Inara Nexus", "Influence": [{"SystemAddress": 1, "Influence": "++++"}],
                                "Reputation": "++"}]})
        completed = events[0][1]
        self.assertEqual(completed["rewardPermits"], [{"starsystemName": "Alioth"}])
        self.assertEqual(completed["minorfactionEffects"], [{"minorfactionName": "Inara Nexus", "influenceGain": "++++",
                                                             "reputationGain": "++"}])
        self.assertIn(("addCommanderInventoryMaterialsItem", {"itemName": "arsenic", "itemCount": 2}), events)

    def test_interdictions_name_the_power_or_faction(self):
        events = inara.map_event("Interdicted", {"Submitted": True, "IsPlayer": False, "Faction": "Kokatese Crimson Gang"},
                                 {"system": "Lave"})
        self.assertEqual(events[0][1]["opponentName"], "Kokatese Crimson Gang")

    def test_community_goal_and_your_progress(self):
        goal = {"CGID": 726, "Title": "Alliance Research Initiative", "SystemName": "Kaushpoos", "MarketName": "Neville Horizons",
                "Expiry": "2017-08-17T14:58:14Z", "IsComplete": False, "CurrentTotal": 10062, "PlayerContribution": 562,
                "NumContributors": 101, "TopRankSize": 10, "PlayerInTopRank": False, "TierReached": "Tier 1",
                "PlayerPercentileBand": 50, "Bonus": 200000}
        events = inara.map_event("CommunityGoal", {"CurrentGoals": [goal]})
        self.assertEqual(events[0], ("setCommunityGoal", {
            "communitygoalGameID": 726, "communitygoalName": "Alliance Research Initiative", "starsystemName": "Kaushpoos",
            "stationName": "Neville Horizons", "goalExpiry": "2017-08-17T14:58:14Z", "tierReached": 1, "topRankSize": 10,
            "isCompleted": False, "contributorsNum": 101, "contributionsTotal": 10062}))
        self.assertEqual(events[1][1]["percentileBandReward"], 200000)


class EverythingInaraTakesTests(unittest.TestCase):
    """The events added so every commander event the API accepts is sent."""

    def uploader(self):
        up = inara.InaraUploader({"inara_upload_enabled": True, "inara_api_key": "key", "active_commander_name": "me"},
                                 "5.5.4", session=Mock(), clock=lambda: 1000.0)
        up._last_send = 1000.0
        return up

    def test_stored_modules(self):
        events = inara.map_event("StoredModules", {"MarketID": 128016896, "StationName": "Abraham Lincoln", "StarSystem": "Sol",
            "Items": [{"Name": "$hpt_pulselaser_gimbal_large_name;", "StarSystem": "Sol", "MarketID": 128016896, "BuyPrice": 350640,
                       "Hot": True, "EngineerModifications": "Weapon_Overcharged", "Level": 4, "Quality": 0.0},
                      {"Name": "$int_dronecontrol_collection_size5_class5_name;", "StarSystem": "Inara", "MarketID": 3226573056,
                       "BuyPrice": 4500, "Hot": False},
                      {"Name": "$int_cargorack_size7_class1_name;", "InTransit": True, "BuyPrice": 12800, "Hot": False}]})
        self.assertEqual(events[0][0], "setCommanderStorageModules")
        here, there, moving = events[0][1]
        self.assertEqual(here, {"itemName": "$hpt_pulselaser_gimbal_large_name", "itemValue": 350640, "isHot": True,
                                "starsystemName": "Sol", "marketID": 128016896, "stationName": "Abraham Lincoln",
                                "engineering": {"blueprintName": "Weapon_Overcharged", "blueprintLevel": 4, "blueprintQuality": 0.0}})
        self.assertEqual((there["starsystemName"], there["marketID"]), ("Inara", 3226573056))
        self.assertNotIn("stationName", there, "only the station you're at is known by name")
        self.assertNotIn("starsystemName", moving, "in transit: no place")

    def test_where_each_stored_ship_is(self):
        events = inara.map_event("StoredShips", {"StationName": "Jameson Memorial", "MarketID": 128666762, "StarSystem": "Shinrarta Dezhra",
            "ShipsHere": [{"ShipID": 7, "ShipType": "sidewinder", "Name": "Goldie", "Value": 30000, "Hot": False}],
            "ShipsRemote": [{"ShipID": 9, "ShipType": "asp", "StarSystem": "Sol", "ShipMarketID": 128016640, "Hot": False},
                            {"ShipID": 11, "ShipType": "python", "InTransit": True, "Hot": False}]})
        self.assertEqual(events[0], ("setCommanderShip", {"shipType": "sidewinder", "shipGameID": 7, "shipName": "Goldie",
            "starsystemName": "Shinrarta Dezhra", "stationName": "Jameson Memorial", "marketID": 128666762, "isHot": False}))
        self.assertEqual(events[1][1]["starsystemName"], "Sol")
        self.assertNotIn("starsystemName", events[2][1])

    def test_suit_loadouts_set_changed_renamed_and_deleted(self):
        up = self.uploader()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        loadout = {"timestamp": stamp, "SuitID": 1700315870155528, "SuitName": "utilitysuit_class3", "SuitMods": ["suit_backpackcapacity"],
                   "LoadoutID": 4293000004, "LoadoutName": "Scavenging",
                   "Modules": [{"SlotName": "PrimaryWeapon1", "SuitModuleID": 1700214103674125, "ModuleName": "wpn_m_sniper_plasma_charged",
                                "Class": 4, "WeaponMods": []},
                               {"SlotName": "SecondaryWeapon", "SuitModuleID": 1700711099271164, "ModuleName": "wpn_s_pistol_plasma_charged",
                                "Class": 3, "WeaponMods": ["scope", "weapon_stability"]}]}
        up.observe("SuitLoadout", loadout)
        sent = up._queue[-1]
        self.assertEqual(sent["eventName"], "setCommanderSuitLoadout")
        self.assertEqual(sent["eventData"]["suitLoadout"][1], {"slotName": "SecondaryWeapon", "itemName": "wpn_s_pistol_plasma_charged",
            "itemClass": 3, "itemGameID": 1700711099271164, "engineering": [{"blueprintName": "scope"}, {"blueprintName": "weapon_stability"}]})
        up.observe("LoadoutEquipModule", {"timestamp": stamp, "LoadoutID": 4293000004, "SlotName": "PrimaryWeapon1",
                                          "ModuleName": "wpn_m_assaultrifle_kinetic_fauto", "Class": 1, "SuitModuleID": 55, "WeaponMods": []})
        update = up._queue[-1]
        self.assertEqual(update["eventName"], "updateCommanderSuitLoadout")
        self.assertEqual(sorted(row["itemName"] for row in update["eventData"]["suitLoadout"]),
                         ["wpn_m_assaultrifle_kinetic_fauto", "wpn_s_pistol_plasma_charged"], "the whole loadout, as it now is")
        up.observe("RenameSuitLoadout", {"timestamp": stamp, "LoadoutID": 4293000004, "LoadoutName": "My loadout new name"})
        self.assertEqual(up._queue[-1]["eventData"], {"loadoutGameID": 4293000004, "loadoutName": "My loadout new name"})
        up.observe("DeleteSuitLoadout", {"timestamp": stamp, "LoadoutID": 4293000004})
        self.assertEqual((up._queue[-1]["eventName"], up._queue[-1]["eventData"]), ("delCommanderSuitLoadout", {"loadoutGameID": 4293000004}))

    def test_permits_friends_and_powerplay(self):
        events = inara.map_event("MissionCompleted", {"MissionID": 1, "PermitsAwarded": ["Alioth"]})
        self.assertIn(("addCommanderPermit", {"starsystemName": "Alioth"}), events)
        self.assertEqual(inara.map_event("Friends", {"Status": "Added", "Name": "Rumbakoule"}),
                         [("addCommanderFriend", {"commanderName": "Rumbakoule", "gamePlatform": "pc"})])
        self.assertEqual(names(inara.map_event("Friends", {"Status": "Lost", "Name": "Rumbakoule"})), ["delCommanderFriend"])
        # It sends a friend request on Inara: never for a friend merely online.
        for status in ("Online", "Offline", "Requested"):
            self.assertEqual(inara.map_event("Friends", {"Status": status, "Name": "Rumbakoule"}), [])
        up = self.uploader()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        up.observe("PowerplayRank", {"timestamp": stamp, "Power": "Felicia Winters", "Rank": 12})
        up.observe("PowerplayMerits", {"timestamp": stamp, "Power": "Felicia Winters", "MeritsGained": 50, "TotalMerits": 1452})
        self.assertEqual(up._queue[-1]["eventData"], {"powerName": "Felicia Winters", "rankValue": 12, "meritsValue": 1452})

    def test_every_commander_event_in_the_docs_is_sent(self):
        source = (ROOT / "src" / "voidcompass" / "services" / "inara.py").read_text(encoding="utf-8")
        # Writes only: the get… events read Inara, and the item-by-item cargo
        # and locker events aren't needed with whole snapshots of both.
        for name in ("addCommanderFriend", "delCommanderFriend", "addCommanderPermit", "setCommanderCredits",
                     "setCommanderGameStatistics", "setCommanderRankEngineer", "setCommanderRankPilot", "setCommanderRankPower",
                     "setCommanderReputationMajorFaction", "setCommanderReputationMinorFaction", "resetCommanderInventory",
                     "setCommanderInventory", "addCommanderInventoryMaterialsItem", "delCommanderInventoryMaterialsItem",
                     "setCommanderInventoryCargo", "setCommanderInventoryMaterials", "setCommanderStorageModules",
                     "addCommanderShip", "delCommanderShip", "setCommanderShip", "setCommanderShipLoadout", "setCommanderShipTransfer",
                     "delCommanderSuitLoadout", "setCommanderSuitLoadout", "updateCommanderSuitLoadout",
                     "addCommanderTravelCarrierJump", "addCommanderTravelDock", "addCommanderTravelFSDJump", "addCommanderTravelLand",
                     "setCommanderTravelLocation", "addCommanderMission", "setCommanderMissionAbandoned",
                     "setCommanderMissionCompleted", "setCommanderMissionFailed", "addCommanderCombatDeath",
                     "addCommanderCombatInterdicted", "addCommanderCombatInterdiction", "addCommanderCombatInterdictionEscape",
                     "addCommanderCombatKill", "setCommanderCommunityGoalProgress", "setCommunityGoal"):
            with self.subTest(name=name):
                self.assertIn(f'"{name}"', source)


class HeaderTests(unittest.TestCase):
    def uploader(self, **config):
        base = {"inara_upload_enabled": True, "inara_api_key": "key", "active_commander_name": "insert3coins"}
        return inara.InaraUploader({**base, **config}, "5.5.4", session=Mock(), clock=lambda: 1000.0)

    def test_the_in_game_name_from_the_journal(self):
        up = self.uploader(inara_cmdr_name="Typed Name")
        self.assertEqual(up.credentials()[1], "insert3coins", "the journal's name over a typed one")
        up._follow("Commander", {"Commander": "Jameson"})
        self.assertEqual(up.credentials()[1], "Jameson")
        self.assertEqual(self.uploader(active_commander_name="", inara_cmdr_name="Typed Name").credentials()[1], "Typed Name")

    def test_app_version_in_the_docs_form(self):
        self.assertEqual(inara.app_version("5.5.4"), "5.5.4")
        self.assertEqual(inara.app_version("5.5.3.9.3"), "5.5.3")
        self.assertEqual(inara.app_version("6.0"), "6.0.0")
        self.assertEqual(self.uploader()._header()["appVersion"], "5.5.4")

    def test_running_from_source_counts_as_developing(self):
        self.assertTrue(self.uploader()._header()["isBeingDeveloped"])

    def test_waiting_reputation_and_missions_are_not_replaced(self):
        up = self.uploader()
        up._last_send = 1000.0  # inside the minute: nothing goes yet
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        up.observe("FSDJump", {"timestamp": stamp, "StarSystem": "A", "Factions": [{"Name": "One", "MyReputation": 10}]})
        up.observe("FSDJump", {"timestamp": stamp, "StarSystem": "B", "Factions": [{"Name": "Two", "MyReputation": 20}]})
        waiting = [row["eventName"] for row in up._queue]
        self.assertEqual(waiting.count("setCommanderReputationMinorFaction"), 2)


if __name__ == "__main__":
    unittest.main()
