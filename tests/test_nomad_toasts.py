import unittest

from voidcompass.dashboard.dashboard import MainDashboard


class NomadToastTests(unittest.TestCase):
    def _dashboard(self):
        app = MainDashboard.__new__(MainDashboard)
        app.is_first_load = False
        app.current_vehicle_name = ""
        app._last_surface_vehicle_name = ""
        app._vehicle_name_by_id = {}
        app.toasts = []
        app._push_live_toast = lambda *args, **kwargs: app.toasts.append((args, kwargs))
        return app

    def test_embark_uses_nomad_name_remembered_by_vehicle_id(self):
        app = self._dashboard()
        app._vehicle_name_by_id[42] = "NOMAD"

        app._handle_live_journal_toast(
            "Embark", {"SRV": True, "ID": 42}, {"SRV": True, "ID": 42}
        )

        self.assertEqual(app.toasts[-1][0][:2], ("EMBARKED", "NOMAD"))

    def test_embark_keeps_ordinary_srv_label(self):
        app = self._dashboard()

        app._handle_live_journal_toast(
            "Embark", {"SRV": True, "ID": 7}, {"SRV": True, "ID": 7}
        )

        self.assertEqual(app.toasts[-1][0][:2], ("EMBARKED", "SRV"))

    def test_nomad_destruction_uses_remembered_vehicle_name(self):
        app = self._dashboard()
        app.current_vehicle_name = "NOMAD"

        app._handle_live_journal_toast("SRVDestroyed", {}, {})

        self.assertEqual(app.toasts[-1][0][0], "NOMAD DESTROYED")


if __name__ == "__main__":
    unittest.main()
