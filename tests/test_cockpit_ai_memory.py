import json
import pathlib
import tempfile
import unittest
from unittest import mock

from cockpit_ai_memory import CockpitMemory, ordinal
import config as config_module


class CockpitMemoryTests(unittest.TestCase):
    def test_live_events_build_and_reload_bounded_profile_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "cockpit_ai_memory.json"
            memory = CockpitMemory(path)
            for _ in range(3):
                memory.observe("FSDJump", {"StarSystem": "Sol"}, {"star_system": "Sol"})
            memory.observe("Scan", {"BodyName": "Sol A 1", "WasDiscovered": False},
                           {"body_name": "Sol A 1", "was_discovered": False})
            memory.observe("ScanOrganic", {"ScanType": "Analyse"},
                           {"species": "Bacterium Acies", "is_complete": True})
            memory.observe("Loadout", {"ShipName": "Wayfarer"}, {"ship_name": "Wayfarer"})

            self.assertTrue(path.is_file())
            self.assertEqual(memory.system_visits("Sol"), 3)
            self.assertEqual(memory.species_analyses("Bacterium Acies"), 1)
            self.assertEqual(memory.count("first_discoveries"), 1)
            self.assertIn("Sol", " ".join(memory.arrival_lines("Sol", "Balanced")))

            restored = CockpitMemory(path)
            self.assertEqual(restored.summary()["jumps"], 3)
            self.assertEqual(restored.state["ships"]["Wayfarer"]["count"], 1)
            self.assertGreaterEqual(restored.summary()["memories"], 2)

    def test_startup_replay_does_not_relearn_old_journal_events(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CockpitMemory(pathlib.Path(folder) / "memory.json")
            changed = memory.observe(
                "FSDJump", {"StarSystem": "Achenar"}, {"star_system": "Achenar"},
                startup_replay=True,
            )

            self.assertFalse(changed)
            self.assertEqual(memory.count("jumps"), 0)
            self.assertEqual(memory.system_visits("Achenar"), 0)

    def test_personality_levels_control_familiar_system_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CockpitMemory(pathlib.Path(folder) / "memory.json")
            for _ in range(3):
                memory.observe("FSDJump", {"StarSystem": "Colonia"}, {"star_system": "Colonia"})

            self.assertEqual(memory.arrival_lines("Colonia", "Quiet"), ())
            self.assertTrue(memory.arrival_lines("Colonia", "Balanced"))
            self.assertTrue(memory.arrival_lines("Colonia", "Chatty"))
            self.assertFalse(memory.should_reference_repeat(2, "Balanced"))
            self.assertTrue(memory.should_reference_repeat(2, "Chatty"))

    def test_voice_pool_expands_through_relationship_stages(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CockpitMemory(pathlib.Path(folder) / "memory.json")
            base = tuple(f"Arrival line {index}" for index in range(5))
            expected = {
                0: ("new", 2),
                25: ("developing", 3),
                100: ("familiar", 5),
                500: ("trusted", 7),
                2000: ("veteran", 8),
            }

            for score, (stage, size) in expected.items():
                memory.state["counters"] = {"jumps": score}
                self.assertEqual(memory.voice_stage(), stage)
                pool = memory.voice_pool(base, key="system-arrival:Sol")
                self.assertEqual(len(pool), size)
                self.assertEqual(pool[0], base[0])

    def test_personality_setting_advances_or_restrains_voice_evolution(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CockpitMemory(pathlib.Path(folder) / "memory.json")
            memory.state["counters"] = {"jumps": 100}

            self.assertEqual(memory.voice_stage("Quiet"), "developing")
            self.assertEqual(memory.voice_stage("Balanced"), "familiar")
            self.assertEqual(memory.voice_stage("Chatty"), "trusted")

    def test_evolved_safety_pool_retains_direct_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CockpitMemory(pathlib.Path(folder) / "memory.json")
            memory.state["counters"] = {"jumps": 2500}
            warning = "Warning. Ship temperature critical."
            pool = memory.voice_pool(
                (warning, "Thermal telemetry critical.", "Immediate cooling recommended."),
                key="ship-overheat",
            )

            self.assertIn(warning, pool)
            self.assertGreater(len(pool), 3)
            self.assertTrue(any("cool" in line.casefold() or "thermal" in line.casefold()
                                for line in pool[3:]))

    def test_configurable_caps_prune_existing_memory_immediately(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "memory.json"
            memory = CockpitMemory(path, limits={"systems": 30, "memories": 20})
            for index in range(30):
                system = f"System {index:02d}"
                memory.observe("FSDJump", {"StarSystem": system}, {"star_system": system})
            for index in range(15):
                memory.observe(
                    "Scan", {"BodyName": f"Body {index}", "WasDiscovered": False},
                    {"body_name": f"Body {index}", "was_discovered": False},
                )

            applied = memory.configure_limits({
                "systems": 25, "species": 25, "ships": 5, "memories": 10,
            })

            self.assertEqual(applied, {"systems": 25, "species": 25, "ships": 5, "memories": 10})
            self.assertEqual(len(memory.state["systems"]), 25)
            self.assertEqual(len(memory.state["memories"]), 10)
            restored = CockpitMemory(path, limits=applied)
            self.assertEqual(len(restored.state["systems"]), 25)
            self.assertEqual(len(restored.state["memories"]), 10)

    def test_memory_caps_are_guarded_against_accidental_extremes(self):
        limits = CockpitMemory.normalize_limits({
            "systems": 0, "species": 999999, "ships": "bad", "memories": -20,
        })

        self.assertEqual(limits, {"systems": 0, "species": 2000, "ships": 30, "memories": 0})

    def test_reset_forgets_learned_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "memory.json"
            memory = CockpitMemory(path)
            memory.observe("HeatWarning")
            memory.reset()

            self.assertEqual(memory.count("heat_warnings"), 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["counters"], {})

    def test_voice_changes_become_part_of_compass_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = CockpitMemory(pathlib.Path(folder) / "memory.json")
            self.assertTrue(memory.voice_selected("voice-a", "Voice A"))
            self.assertTrue(memory.voice_selected("voice-b", "Voice B"))
            self.assertFalse(memory.voice_selected("voice-b", "Voice B"))

            self.assertEqual(memory.count("voice_changes"), 1)
            self.assertIn("Voice B", memory.state["memories"][-1]["text"])

    def test_ordinals_are_spoken_naturally(self):
        self.assertEqual([ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21)],
                         ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st"])

    def test_memory_preferences_persist_per_commander(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(config_module, "PROFILE_DIR", folder), \
                mock.patch.object(config_module, "CONFIG_FILE", str(pathlib.Path(folder) / "config.json")):
            settings = {
                "active_commander_profile": "test_commander",
                "active_commander_name": "Test Commander",
                "active_commander_fid": "F123",
                "commander_profiles": {},
                "cockpit_memory_enabled": False,
                "cockpit_personality_level": "Quiet",
                "cockpit_memory_system_limit": 750,
                "cockpit_memory_species_limit": 500,
                "cockpit_memory_ship_limit": 60,
                "cockpit_memory_episode_limit": 240,
            }
            config_module.save_config(settings)
            saved = json.loads(
                pathlib.Path(folder, "test_commander", "config.json").read_text(encoding="utf-8")
            )

            self.assertFalse(saved["cockpit_memory_enabled"])
            self.assertEqual(saved["cockpit_personality_level"], "Quiet")
            self.assertEqual(saved["cockpit_memory_system_limit"], 750)
            self.assertEqual(saved["cockpit_memory_species_limit"], 500)
            self.assertEqual(saved["cockpit_memory_ship_limit"], 60)
            self.assertEqual(saved["cockpit_memory_episode_limit"], 240)


if __name__ == "__main__":
    unittest.main()
