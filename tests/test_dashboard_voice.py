import unittest

from dashboard import MainDashboard
from voice_callouts import choose_line


class DashboardVoiceTests(unittest.TestCase):
    def _app(self, route=None):
        app = MainDashboard.__new__(MainDashboard)
        app.route_list = list(route or [])
        app.config = {"cockpit_memory_enabled": True, "cockpit_personality_level": "Balanced"}
        app.cockpit_memory = None
        app.spoken = []
        app._speak = lambda text, **kwargs: app.spoken.append(
            (choose_line(text, key=kwargs.get("key")), kwargs)
        ) or True
        return app

    def test_live_jump_announces_entered_system(self):
        app = self._app()

        self.assertTrue(app._announce_system_arrival("Shinrarta Dezhra"))
        self.assertIn("Shinrarta Dezhra", app.spoken[0][0])
        self.assertEqual(app.spoken[0][1]["category"], "navigation")

    def test_route_arrival_replaces_generic_system_callout(self):
        app = self._app(["Sol", "Achenar"])

        app._announce_system_arrival("Sol")
        self.assertEqual(len(app.spoken), 1)
        self.assertIn("Achenar", app.spoken[0][0])
        self.assertNotIn("Entered system", app.spoken[0][0])

    def test_learned_system_memory_replaces_generic_arrival_wording(self):
        app = self._app()

        class Memory:
            def arrival_lines(self, system, level):
                return (f"I remember {system}. This is visit three.",)

        app.cockpit_memory = Memory()
        app._announce_system_arrival("Sol")

        self.assertEqual(app.spoken[0][0], "I remember Sol. This is visit three.")

    def test_startup_replay_is_silent(self):
        app = self._app()

        self.assertFalse(app._announce_system_arrival("Sol", startup_replay=True))
        self.assertEqual(app.spoken, [])

    def test_jet_cone_boost_keeps_toast_but_has_no_voice(self):
        app = self._app()
        app.is_first_load = False

        class Toast:
            def __init__(self):
                self.messages = []

            def push(self, *args, **kwargs):
                self.messages.append((args, kwargs))

        app.toast_hud = Toast()
        app._handle_live_journal_toast("JetConeBoost", {}, {})

        self.assertEqual(len(app.toast_hud.messages), 1)
        self.assertEqual(app.toast_hud.messages[0][0][0], "FSD SUPERCHARGED")
        self.assertEqual(app.spoken, [])

    def test_cockpit_intentions_receive_live_route_data_and_engineering_work(self):
        app = MainDashboard.__new__(MainDashboard)
        app.config = {"cockpit_memory_enabled": True}
        app.current_sys = "Sol"
        app.route_list = ["Sol", "Achenar"]
        app.companion_state = {
            "unsold_exploration_cr": 12_000_000,
            "unsold_bio_cr": 3_000_000,
            "missions": [{"id": 1}],
        }
        app.engineer_materials = {
            "pinned_blueprints": [{"name": "Frame Shift Drive", "grade": 5}]
        }
        app._sampling_snapshot = lambda: {"species": "Bacterium Acies", "progress": 2}

        class Memory:
            def update_intentions(self, intentions):
                self.intentions = intentions

        app.cockpit_memory = Memory()
        app._sync_cockpit_intentions()

        self.assertEqual(app.cockpit_memory.intentions["route"]["destination"], "Achenar")
        self.assertEqual(app.cockpit_memory.intentions["unsold_data_cr"], 15_000_000)
        self.assertEqual(app.cockpit_memory.intentions["engineering"][0]["grade"], 5)

    def test_ai_feed_reports_state_changes_without_reporting_routine_growth(self):
        before = {
            "mood": "calm", "mood_reason": "systems nominal",
            "voice_stage": "developing", "habits": (),
            "systems": 24, "species": 3, "ships": 1, "memories": 11,
            "limits": {"systems": 300, "species": 200, "ships": 30, "memories": 80},
            "expedition_id": None, "expedition_name": None, "expedition_jumps": 0,
        }
        after = dict(before)
        after.update(
            mood="curious", mood_reason="first discovery", systems=25, memories=12,
            habits=("Thorough system surveyor",),
        )

        events = MainDashboard._cockpit_ai_state_events(before, after)

        self.assertTrue(any("Mood changed: Curious" in event for event in events))
        self.assertTrue(any("Learned flight habit" in event for event in events))
        self.assertTrue(any("25/300 systems" in event for event in events))
        self.assertFalse(any("12/80 notable" in event for event in events))

    def test_ai_feed_reports_expeditions_and_relationship_stages(self):
        before = {
            "mood": "calm", "mood_reason": "systems nominal",
            "voice_stage": "familiar", "habits": (),
            "systems": 40, "species": 2, "ships": 1, "memories": 15,
            "limits": {"systems": 300, "species": 200, "ships": 30, "memories": 80},
            "expedition_id": None, "expedition_name": None, "expedition_jumps": 0,
        }
        after = dict(before)
        after.update(
            voice_stage="trusted", expedition_id="exp-1",
            expedition_name="Expedition 3309-01-01", expedition_jumps=50,
        )

        events = MainDashboard._cockpit_ai_state_events(before, after)

        self.assertTrue(any("Relationship evolved: Trusted" in event for event in events))
        self.assertTrue(any("Expedition log opened" in event for event in events))

    def test_ai_feed_reports_sparse_survey_awareness_milestones(self):
        before = {
            "mood": "calm", "mood_reason": "systems nominal",
            "voice_stage": "familiar", "habits": (),
            "systems": 40, "species": 2, "ships": 1, "memories": 15,
            "honks": 24, "fss_completed": 9, "dss_maps": 9, "signal_bodies": 9,
            "limits": {"systems": 300, "species": 200, "ships": 30, "memories": 80},
            "expedition_id": None, "expedition_name": None, "expedition_jumps": 0,
        }
        after = dict(before)
        after.update(honks=25, fss_completed=10, dss_maps=10, signal_bodies=10)

        events = MainDashboard._cockpit_ai_state_events(before, after)

        survey = next(event for event in events if event.startswith("Survey awareness:"))
        self.assertIn("25 system honks", survey)
        self.assertIn("10 full FSS surveys", survey)
        self.assertIn("10 DSS maps", survey)
        self.assertIn("10 signal-bearing bodies", survey)

    def test_ai_feed_announces_each_new_gameplay_domain_once(self):
        before = {
            "mood": "calm", "mood_reason": "systems nominal",
            "voice_stage": "familiar", "habits": (),
            "systems": 40, "species": 2, "ships": 1, "memories": 15,
            "awareness_domains": ("Missions",),
            "limits": {"systems": 300, "species": 200, "ships": 30, "memories": 80},
            "expedition_id": None, "expedition_name": None, "expedition_jumps": 0,
        }
        after = dict(before)
        after["awareness_domains"] = ("Missions", "Combat", "Engineering")

        events = MainDashboard._cockpit_ai_state_events(before, after)

        awareness = next(event for event in events if event.startswith("New operational awareness:"))
        self.assertIn("Combat", awareness)
        self.assertIn("Engineering", awareness)
        self.assertNotIn("Missions", awareness)


if __name__ == "__main__":
    unittest.main()
