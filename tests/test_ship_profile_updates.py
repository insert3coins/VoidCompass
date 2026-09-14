import unittest

from voidcompass.core import companion_features


class ShipProfileUpdateTests(unittest.TestCase):
    def test_live_purchase_loadout_and_rename_sequence(self):
        ship = {
            "ship": "diamondbackxl",
            "ship_localised": "Diamondback Explorer",
            "ship_id": 121,
            "ship_name": "Old Explorer",
            "ship_ident": "OLD-1",
            "modules_value": 12_000_000,
        }

        ship, _ = companion_features.update_active_ship(ship, "ShipyardBuy", {
            "ShipType": "lakonminer",
            "ShipType_Localised": "Type-11 Prospector",
            "StoreOldShip": "DiamondBackXL",
            "StoreShipID": 121,
        })
        self.assertEqual(ship["ship_localised"], "Type-11 Prospector")
        self.assertNotIn("ship_name", ship)
        self.assertNotIn("modules_value", ship)

        ship, _ = companion_features.update_active_ship(ship, "ShipyardNew", {
            "ShipType": "lakonminer",
            "ShipType_Localised": "Type-11 Prospector",
            "NewShipID": 130,
        })
        self.assertEqual(ship["ship_id"], 130)

        ship, _ = companion_features.update_active_ship(ship, "Loadout", {
            "Ship": "lakonminer",
            "ShipID": 130,
            "ShipName": "",
            "ShipIdent": "IN-17L",
            "CargoCapacity": 256,
        })
        self.assertEqual(ship["ship_localised"], "Type-11 Prospector")
        self.assertEqual(ship["ship_name"], "")
        self.assertEqual(ship["ship_ident"], "IN-17L")

        ship, changed = companion_features.update_active_ship(ship, "SetUserShipName", {
            "Ship": "lakonminer",
            "ShipID": 130,
            "UserShipName": "Through The Black",
            "UserShipId": "BLK-3C",
        })
        self.assertTrue(changed)
        self.assertEqual(ship["ship_name"], "Through The Black")
        self.assertEqual(ship["ship_ident"], "BLK-3C")

        ship, changed = companion_features.update_active_ship(ship, "SetUserShipName", {
            "Ship": "lander01",
            "ShipID": 131,
            "UserShipName": "The Far Roamer",
            "UserShipId": "FAR-3C",
        })
        self.assertFalse(changed)
        self.assertEqual(ship["ship_name"], "Through The Black")

    def test_shipyard_swap_clears_outgoing_identity(self):
        ship, changed = companion_features.update_active_ship({
            "ship": "lakonminer",
            "ship_localised": "Type-11 Prospector",
            "ship_id": 130,
            "ship_name": "Through The Black",
            "ship_ident": "BLK-3C",
        }, "ShipyardSwap", {
            "ShipType": "typex_3",
            "ShipType_Localised": "Alliance Challenger",
            "ShipID": 123,
            "StoreOldShip": "LakonMiner",
            "StoreShipID": 130,
        })
        self.assertTrue(changed)
        self.assertEqual(ship["ship_localised"], "Alliance Challenger")
        self.assertEqual(ship["ship_id"], 123)
        self.assertNotIn("ship_name", ship)
        self.assertNotIn("ship_ident", ship)

    def test_companion_loadout_and_fleet_follow_shipyard_events(self):
        state = {
            "loadout": {"ShipID": 130, "ShipName": "", "ShipIdent": "IN-17L"},
            "stored_ships": {
                "here": [{"ship_id": 123, "type": "Alliance Challenger"}],
                "remote": [],
            },
        }
        changed = companion_features.update_ship_companion_state(state, "ShipyardSwap", {
            "ShipID": 123,
            "ShipType": "typex_3",
            "ShipType_Localised": "Alliance Challenger",
            "StoreShipID": 130,
            "StoreOldShip": "LakonMiner",
            "timestamp": "2026-07-17T01:00:00Z",
        })
        self.assertTrue(changed)
        self.assertEqual(state["loadout"]["ShipID"], 123)
        self.assertEqual(state["loadout"]["Ship"], "typex_3")
        self.assertTrue(state["loadout"]["Provisional"])
        self.assertEqual(state["loadout"]["Modules"], [])
        self.assertEqual([row["ship_id"] for row in state["stored_ships"]["here"]], [130])

        state["loadout"] = {"ShipID": 123, "ShipName": "", "ShipIdent": ""}
        companion_features.update_ship_companion_state(state, "SetUserShipName", {
            "ShipID": 123,
            "UserShipName": "Guardian",
            "UserShipId": "GU-123",
        })
        self.assertEqual(state["loadout"]["ShipName"], "Guardian")
        self.assertEqual(state["loadout"]["ShipIdent"], "GU-123")

        companion_features.update_ship_companion_state(state, "SetUserShipName", {
            "ShipID": 131,
            "UserShipName": "SRV Name",
            "UserShipId": "SRV-1",
        })
        self.assertEqual(state["loadout"]["ShipName"], "Guardian")

    def test_stored_ship_retains_id_and_internal_type(self):
        row = companion_features.normalise_stored_ship({
            "ShipID": 128,
            "ShipType": "mediumtransport01",
            "ShipType_Localised": "Lynx Highliner",
        })
        self.assertEqual(row["ship_id"], 128)
        self.assertEqual(row["type_symbol"], "mediumtransport01")
        self.assertEqual(row["type"], "Lynx Highliner")

if __name__ == "__main__":
    unittest.main()
