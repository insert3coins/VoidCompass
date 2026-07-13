import unittest

from dashboard import MainDashboard


class DashboardVoiceTests(unittest.TestCase):
    def _app(self, route=None):
        app = MainDashboard.__new__(MainDashboard)
        app.route_list = list(route or [])
        app.spoken = []
        app._speak = lambda text, **kwargs: app.spoken.append((text, kwargs)) or True
        return app

    def test_live_jump_announces_entered_system(self):
        app = self._app()

        self.assertTrue(app._announce_system_arrival("Shinrarta Dezhra"))
        self.assertEqual(app.spoken[0][0], "Entered system. Shinrarta Dezhra.")
        self.assertEqual(app.spoken[0][1]["category"], "navigation")

    def test_route_arrival_replaces_generic_system_callout(self):
        app = self._app(["Sol", "Achenar"])

        app._announce_system_arrival("Sol")
        self.assertEqual(len(app.spoken), 1)
        self.assertIn("Waypoint 1 of 2 reached", app.spoken[0][0])

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


if __name__ == "__main__":
    unittest.main()
