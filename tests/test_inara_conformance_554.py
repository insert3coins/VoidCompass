"""Every field sent to Inara, checked against the property tables of its API
docs (a snapshot in fixtures/inara_api_spec.json) using journal events of
every kind Void Compass maps. Nested fields are checked against the docs'
own examples by test_inara_spec_554."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from voidcompass.services import inara

SPEC = json.loads((Path(__file__).parent / "fixtures" / "inara_api_spec.json").read_text(encoding="utf-8"))["events"]
TS = "2026-10-15T20:14:00Z"
HERE = {"system": "Sol", "station": "Abraham Lincoln", "ship_type": "anaconda", "ship_id": 4, "power_rank": 12}
ENG = {"BlueprintName": "Weapon_Overcharged", "Level": 5, "Quality": 0.5, "ExperimentalEffect": "special_incendiary_rounds",
       "Modifiers": [{"Label": "DamageType", "ValueStr": "$Thermic;", "ValueStr_Localised": "Thermal"},
                     {"Label": "Damage", "Value": 40.5, "OriginalValue": 30.0, "LessIsGood": 0}]}
# Journal events as the game writes them (fields from the Frontier journal manual).
SAMPLES = [
    ("LoadGame", {"Commander": "Jameson", "FID": "F123", "Ship": "anaconda", "ShipID": 4, "ShipName": "Goldie", "ShipIdent": "OK-475",
                  "Credits": 1000000, "Loan": 0}),
    ("Location", {"StarSystem": "Sol", "StarPos": [0.0, 0.0, 0.0], "Docked": True, "StationName": "Abraham Lincoln", "MarketID": 128016640,
                  "Body": "Earth", "BodyType": "Planet", "Latitude": 1.5, "Longitude": 2.5,
                  "Factions": [{"Name": "Mother Gaia", "MyReputation": 55.5}]}),
    ("FSDJump", {"StarSystem": "Lave", "StarPos": [75.75, 48.75, 70.75], "JumpDist": 10.28, "Taxi": False,
                 "Factions": [{"Name": "Lave Signs", "MyReputation": -20.0}]}),
    ("CarrierJump", {"StarSystem": "Kokatese", "StarPos": [1.0, 2.0, 3.0], "StationName": "A12-B3C", "MarketID": 3700000000}),
    ("Docked", {"StarSystem": "Kokatese", "StationName": "Koontz Enterprise", "MarketID": 3221456896, "Taxi": False}),
    ("Touchdown", {"StarSystem": "Kokatese", "Body": "Kokatese A1", "Latitude": 7.1, "Longitude": 104.7, "PlayerControlled": True}),
    ("DropShipDeploy", {"StarSystem": "Kokatese", "Body": "Kokatese A1"}),
    ("Rank", {"Combat": 3, "Trade": 2, "Explore": 5, "Soldier": 0, "Exobiologist": 1, "Empire": 4, "Federation": 2, "CQC": 0}),
    ("Progress", {"Combat": 42, "Trade": 31, "Explore": 67, "Soldier": 0, "Exobiologist": 10, "Empire": 1, "Federation": 2, "CQC": 0}),
    ("Promotion", {"Explore": 6}),
    ("Reputation", {"Empire": 84.0, "Federation": 36.0, "Independent": 0.0, "Alliance": 12.5}),
    ("Powerplay", {"Power": "Felicia Winters", "Rank": 12, "Merits": 1452, "TimePledged": 1000}),
    ("PowerplayRank", {"Power": "Felicia Winters", "Rank": 13}),
    ("PowerplayMerits", {"Power": "Felicia Winters", "MeritsGained": 50, "TotalMerits": 1502}),
    ("PowerplayLeave", {"Power": "Felicia Winters"}),
    ("EngineerProgress", {"Engineers": [{"Engineer": "Elvira Martuuk", "EngineerID": 300160, "Progress": "Unlocked", "RankProgress": 0, "Rank": 4},
                                        {"Engineer": "Liz Ryder", "EngineerID": 300080, "Progress": "Known"}]}),
    ("EngineerProgress", {"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Invited"}),
    ("Statistics", {"Bank_Account": {"Current_Wealth": 1560432}, "Combat": {"Bounties_Claimed": 5}}),
    ("Loadout", {"Ship": "anaconda", "ShipID": 4, "ShipName": "Goldie", "ShipIdent": "OK-475", "HullValue": 140000000, "ModulesValue": 80000000,
                 "Hot": False, "Rebuy": 11000000, "MaxJumpRange": 55.3, "CargoCapacity": 256, "UnladenMass": 900.0,
                 "Modules": [{"Slot": "HugeHardpoint1", "Item": "hpt_multicannon_gimbal_huge", "On": True, "Priority": 0, "Health": 1.0,
                              "Value": 6377600, "AmmoInClip": 90, "AmmoInHopper": 2100, "Engineering": ENG},
                             {"Slot": "Armour", "Item": "anaconda_armour_grade3", "On": True, "Priority": 1, "Health": 0.95}]}),
    ("ShipyardBuy", {"ShipType": "hauler", "ShipPrice": 46262, "StoreOldShip": "SideWinder", "StoreShipID": 2, "MarketID": 128016640}),
    ("ShipyardBuy", {"ShipType": "hauler", "ShipPrice": 46262, "SellOldShip": "SideWinder", "SellShipID": 2, "SellPrice": 35600}),
    ("ShipyardNew", {"ShipType": "hauler", "NewShipID": 4}),
    ("ShipyardSwap", {"ShipType": "sidewinder", "ShipID": 10, "StoreOldShip": "Asp", "StoreShipID": 2, "MarketID": 128016640}),
    ("ShipyardSwap", {"ShipType": "sidewinder", "ShipID": 10, "SellOldShip": "Asp", "SellShipID": 2}),
    ("ShipyardSell", {"ShipType": "Adder", "SellShipID": 6, "ShipPrice": 79027, "System": "Eranin"}),
    ("SellShipOnRebuy", {"ShipType": "Adder", "System": "Eranin", "SellShipId": 6, "ShipPrice": 79027}),
    ("SetUserShipName", {"Ship": "cobramkiii", "ShipID": 2, "UserShipName": "Enterprise", "UserShipId": "NCC 1701"}),
    ("ShipyardTransfer", {"ShipType": "SideWinder", "ShipID": 7, "System": "Eranin", "Distance": 85.6, "TransferPrice": 580,
                          "TransferTime": 2262, "MarketID": 128016640}),
    ("StoredShips", {"StationName": "Abraham Lincoln", "MarketID": 128016640, "StarSystem": "Sol",
                     "ShipsHere": [{"ShipID": 7, "ShipType": "sidewinder", "Name": "Goldie", "Value": 30000, "Hot": False}],
                     "ShipsRemote": [{"ShipID": 9, "ShipType": "asp", "StarSystem": "Lave", "ShipMarketID": 128000000, "TransferPrice": 100,
                                      "TransferTime": 300, "Value": 6000000, "Hot": False},
                                     {"ShipID": 11, "ShipType": "python", "InTransit": True, "Value": 50000000, "Hot": False}]}),
    ("StoredModules", {"MarketID": 128016640, "StationName": "Abraham Lincoln", "StarSystem": "Sol",
                       "Items": [{"Name": "$hpt_pulselaser_gimbal_large_name;", "StorageSlot": 1, "StarSystem": "Sol", "MarketID": 128016640,
                                  "TransferCost": 0, "TransferTime": 0, "BuyPrice": 350640, "Hot": True,
                                  "EngineerModifications": "Weapon_Overcharged", "Level": 4, "Quality": 0.0},
                                 {"Name": "$int_cargorack_size7_class1_name;", "StorageSlot": 2, "InTransit": True, "BuyPrice": 12800, "Hot": False}]}),
    ("Materials", {"Raw": [{"Name": "iron", "Count": 30}], "Manufactured": [{"Name": "shieldemitters", "Count": 4}],
                   "Encoded": [{"Name": "shielddensityreports", "Count": 2}]}),
    ("MaterialCollected", {"Category": "Raw", "Name": "nickel", "Count": 2}),
    ("MaterialDiscarded", {"Category": "Raw", "Name": "nickel", "Count": 1}),
    ("MaterialTrade", {"MarketID": 1, "TraderType": "raw", "Paid": {"Material": "iron", "Category": "Raw", "Quantity": 6},
                       "Received": {"Material": "nickel", "Category": "Raw", "Quantity": 1}}),
    ("Synthesis", {"Name": "FSD Basic", "Materials": [{"Name": "carbon", "Count": 1}, {"Name": "vanadium", "Count": 1}]}),
    ("EngineerCraft", {"Engineer": "Felicity Farseer", "BlueprintName": "FSD_LongRange", "Level": 1,
                       "Ingredients": [{"Name": "atypicaldisruptedwakeechoes", "Count": 1}]}),
    ("TechnologyBroker", {"BrokerType": "guardian", "Materials": [{"Name": "guardian_sentinel_weaponparts", "Count": 4, "Category": "Manufactured"}]}),
    ("ScientificResearch", {"Name": "iron", "Category": "Raw", "Count": 3}),
    ("EngineerContribution", {"Engineer": "Felicity Farseer", "Type": "Materials", "Material": "meta_alloys", "Quantity": 1}),
    ("Cargo", {"Vessel": "Ship", "Count": 3, "Inventory": [{"Name": "gold", "Count": 2, "Stolen": 0},
                                                           {"Name": "modularterminals", "Count": 1, "Stolen": 1, "MissionID": 170577201}]}),
    ("Cargo", {"Vessel": "Ship", "Count": 0, "Inventory": []}),
    ("ShipLocker", {"Items": [{"Name": "suitschematic", "OwnerID": 0, "Count": 6}], "Components": [{"Name": "graphene", "OwnerID": 0, "Count": 3}],
                    "Consumables": [{"Name": "healthpack", "OwnerID": 0, "Count": 2}], "Data": []}),
    ("MissionAccepted", {"Faction": "Inara Crimson Vision Network", "Name": "Mission_Massacre_Legal_Military", "TargetType": "$MissionUtil_FactionTag_Pirate;",
                         "TargetFaction": "Social Warnones Resistance", "KillCount": 16, "DestinationSystem": "HIP 15415",
                         "DestinationStation": "Bisson Landing", "Expiry": "2017-10-18T10:48:33Z", "Wing": False, "Influence": "+++++",
                         "Reputation": "+++", "Reward": 100000, "MissionID": 170577201}),
    ("MissionAccepted", {"Faction": "People's HIP 15415 League", "Name": "Mission_PassengerVIP", "Commodity": "$ConsumerTechnology_Name;",
                         "Count": 2, "DestinationSystem": "Tougeir", "DestinationStation": "Janes Dock", "Expiry": "2017-07-20T01:06:32Z",
                         "Influence": "+++", "Reputation": "+++++", "PassengerCount": 6, "PassengerVIPs": True, "PassengerWanted": False,
                         "PassengerType": "Tourist", "MissionID": 173224636}),
    ("MissionCompleted", {"Faction": "Inara Nexus", "Name": "Mission_Courier", "MissionID": 171735583, "Reward": 12000, "Donated": 0,
                          "PermitsAwarded": ["Alioth"], "CommodityReward": [{"Name": "NeofabricInsulation", "Count": 4}],
                          "MaterialsReward": [{"Name": "arsenic", "Category": "Raw", "Count": 2}],
                          "FactionEffects": [{"Faction": "Inara Nexus", "Effects": [], "Influence": [{"SystemAddress": 1, "Trend": "UpGood", "Influence": "++++"}],
                                              "ReputationTrend": "UpGood", "Reputation": "++"}]}),
    ("MissionFailed", {"Name": "Mission_Courier", "MissionID": 171735583}),
    ("MissionAbandoned", {"Name": "Mission_Courier", "MissionID": 171735583}),
    ("Died", {"KillerName": "$ShipName_MilitaryFighter_Federation;", "KillerShip": "viper", "KillerRank": "Deadly"}),
    ("Died", {"Killers": [{"Name": "Cmdr Narkoleptik", "Ship": "fdl", "Rank": "Elite"}, {"Name": "Cmdr Almara", "Ship": "anaconda", "Rank": "Elite"}]}),
    ("Interdicted", {"Submitted": True, "Interdictor": "White Rabbit Revenger", "IsPlayer": True}),
    ("Interdicted", {"Submitted": False, "IsPlayer": False, "Faction": "Kokatese Crimson Gang"}),
    ("Interdiction", {"Success": True, "Interdicted": "Mad White Rabbit", "IsPlayer": True}),
    ("EscapeInterdiction", {"Interdictor": "White Rabbit Revenger", "IsPlayer": True}),
    ("PVPKill", {"Victim": "Cmdr White Rabbit Revenger", "CombatRank": 3}),
    ("CommunityGoal", {"CurrentGoals": [{"CGID": 726, "Title": "Alliance Research Initiative", "SystemName": "Kaushpoos", "MarketName": "Neville Horizons",
                                         "Expiry": "2017-08-17T14:58:14Z", "IsComplete": False, "CurrentTotal": 10062, "PlayerContribution": 562,
                                         "NumContributors": 101, "TopRankSize": 10, "PlayerInTopRank": False, "TierReached": "Tier 1",
                                         "PlayerPercentileBand": 50, "Bonus": 200000}]}),
    ("SuitLoadout", {"SuitID": 1700315870155528, "SuitName": "utilitysuit_class3", "SuitMods": ["suit_backpackcapacity"],
                     "LoadoutID": 4293000004, "LoadoutName": "Scavenging",
                     "Modules": [{"SlotName": "PrimaryWeapon1", "SuitModuleID": 1700214103674125, "ModuleName": "wpn_m_sniper_plasma_charged",
                                  "Class": 4, "WeaponMods": ["weapon_stability"]}]}),
    ("RenameSuitLoadout", {"SuitID": 1, "SuitName": "utilitysuit_class3", "LoadoutID": 4293000004, "LoadoutName": "New name"}),
    ("DeleteSuitLoadout", {"SuitID": 1, "SuitName": "utilitysuit_class3", "LoadoutID": 4293000004, "LoadoutName": "New name"}),
    ("Friends", {"Status": "Added", "Name": "Rumbakoule"}),
    ("Friends", {"Status": "Lost", "Name": "Rumbakoule"}),
]


def kind_ok(kind, value):
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "timestamp":
        return isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is not None
    return True


class ConformanceTests(unittest.TestCase):
    def test_every_field_is_in_the_docs_with_its_type(self):
        produced = set()
        for event, raw in SAMPLES:
            raw = {"timestamp": TS, "event": event, **raw}
            for name, data in inara.map_event(event, raw, dict(HERE)):
                produced.add(name)
                self.assertIn(name, SPEC, f"{event}: {name} isn't an Inara event")
                if name == "setCommanderGameStatistics":
                    continue
                for row in (data if isinstance(data, list) else [data]):
                    for key, value in row.items():
                        with self.subTest(event=event, name=name, key=key):
                            self.assertIn(key, SPEC[name], f"{name}.{key} isn't in the docs")
                            self.assertTrue(kind_ok(SPEC[name][key], value), f"{name}.{key} should be {SPEC[name][key]}: {value!r}")
        # Every write the docs list, but the item-by-item cargo and locker
        # events (whole snapshots of both are sent instead).
        by_item = {"addCommanderInventoryItem", "delCommanderInventoryItem", "setCommanderInventoryItem",
                   "addCommanderInventoryCargoItem", "delCommanderInventoryCargoItem", "setCommanderInventoryCargoItem",
                   "setCommanderInventoryMaterialsItem"}
        writes = {name for name in SPEC if not name.startswith("get")} - by_item
        self.assertEqual(writes - produced, set())


if __name__ == "__main__":
    unittest.main()
