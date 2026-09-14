import os
import tempfile
import unittest

from voidcompass.mining.specialist_engine import SpecialistEngine


class MiningSessionTests(unittest.TestCase):
    def test_specialist_engine_is_the_mining_session_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = SpecialistEngine(os.path.join(tmp, "specialist.json"))
            context = {"system": "Borann", "body": "Borann A 2 Ring A"}
            engine.observe_event({
                "event": "ProspectedAsteroid",
                "Materials": [{"Name_Localised": "Platinum", "Proportion": 42.2}],
                "MotherlodeMaterial_Localised": "Monazite",
            }, event_uid="prospect", context=context)
            engine.observe_event(
                {"event": "MiningRefined", "Type_Localised": "Platinum"},
                event_uid="refined", context=context,
            )
            engine.observe_event(
                {"event": "AsteroidCracked"}, event_uid="cracked", context=context,
            )

            state = engine.mining_snapshot()["session"]
            self.assertTrue(state["active"])
            self.assertEqual(state["asteroids_prospected"], 1)
            self.assertEqual(state["body"], "Borann A 2 Ring A")
            self.assertEqual(state["asteroids_cracked"], 1)
            self.assertEqual(state["refined_t"], 1)
            self.assertEqual(state["prospected_materials"][0]["best_pct"], 42.2)

            self.assertTrue(engine.end_mining("manual"))
            ended = engine.mining_snapshot()
            self.assertFalse(ended["active"])
            self.assertEqual(ended["history"][0]["refined_t"], 1)

    def test_rhino_yield_uses_positive_srv_cargo_gains(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = SpecialistEngine(os.path.join(tmp, "specialist.json"))
            context = {
                "system": "Shinrarta Dezhra", "body": "AB 3 c",
                "in_srv": True, "vehicle": "RHINO",
                "cargo_vessel": "SRV", "cargo_capacity": 72,
            }
            engine.observe_event({
                "event": "LaunchSRV", "SRVType": "mev_rhino",
                "SRVType_Localised": "SRV Rhino", "ID": 86,
            }, event_uid="launch", context=context)
            for index in range(4):
                engine.observe_event({
                    "event": "MiningRefined", "Type": "$tantalum_name;",
                    "Type_Localised": "Tantalum",
                }, event_uid=f"pulse-a-{index}", context=context)
            engine.observe_event(
                {"event": "Cargo", "Vessel": "SRV", "Count": 4},
                event_uid="cargo-4", context=context,
            )
            engine.update_cargo(
                [{"Name": "tantalum", "Name_Localised": "Tantalum", "Count": 4}],
                vessel="SRV", capacity=72, vehicle="RHINO",
            )

            # Transferring the first load to the ship must not erase the haul
            # already recovered during this run.
            engine.observe_event(
                {"event": "Cargo", "Vessel": "SRV", "Count": 0},
                event_uid="cargo-0", context=context,
            )
            engine.update_cargo([], vessel="SRV", capacity=72, vehicle="RHINO")
            for index in range(2):
                engine.observe_event({
                    "event": "MiningRefined", "Type": "$tantalum_name;",
                    "Type_Localised": "Tantalum",
                }, event_uid=f"pulse-b-{index}", context=context)
            engine.observe_event(
                {"event": "Cargo", "Vessel": "SRV", "Count": 2},
                event_uid="cargo-2", context=context,
            )
            engine.update_cargo(
                [{"Name": "tantalum", "Name_Localised": "Tantalum", "Count": 2}],
                vessel="SRV", capacity=72, vehicle="RHINO",
            )

            state = engine.mining_snapshot()["session"]
            self.assertEqual(state["mode"], "surface")
            self.assertEqual(state["cargo_capacity"], 72)
            self.assertEqual(state["cargo_current_t"], 2)
            self.assertEqual(state["cargo_removed_t"], 4)
            self.assertEqual(state["processing_events"], 6)
            self.assertEqual(state["refined_t"], 6)
            self.assertEqual(state["cargo_yield"][0]["name"], "Tantalum")
            self.assertEqual(state["cargo_yield"][0]["count"], 6)

    def test_active_legacy_rhino_session_keeps_its_cargo_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = SpecialistEngine(os.path.join(tmp, "specialist.json"))
            context = {
                "system": "Shinrarta Dezhra", "body": "AB 3 c",
                "in_srv": True, "vehicle": "RHINO",
                "cargo_vessel": "SRV", "cargo_capacity": 72,
            }
            engine.observe_event({
                "event": "MiningRefined", "Type": "$tantalum_name;",
                "Type_Localised": "Tantalum",
            }, event_uid="legacy-pulse", context=context)
            session = engine.state["mining"]["session"]
            for key in (
                "cargo_gained_t", "cargo_removed_t", "cargo_gain_unassigned_t",
                "cargo_gained", "cargo_count_start", "cargo_count_current",
            ):
                session.pop(key, None)
            session["cargo_start"] = {}
            session["cargo_current"] = {
                "tantalum": {"name": "Tantalum", "count": 18, "stolen": 0},
            }

            engine.update_cargo(
                [{"Name": "tantalum", "Name_Localised": "Tantalum", "Count": 18}],
                vessel="SRV", capacity=72, vehicle="RHINO",
            )
            engine.observe_event(
                {"event": "Cargo", "Vessel": "SRV", "Count": 20},
                event_uid="legacy-cargo-20", context=context,
            )
            engine.update_cargo(
                [{"Name": "tantalum", "Name_Localised": "Tantalum", "Count": 20}],
                vessel="SRV", capacity=72, vehicle="RHINO",
            )

            state = engine.mining_snapshot()["session"]
            self.assertEqual(state["cargo_current_t"], 20)
            self.assertEqual(state["refined_t"], 20)
            self.assertEqual(state["cargo_yield"][0]["count"], 20)


if __name__ == "__main__":
    unittest.main()
