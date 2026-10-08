"""5.5.3: the Explore survey board learns who discovered each body (EDSM's
bodies reply, keyed by BodyID) and each body's strongest Codex flag."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.overlays.survey_status_hud import body_codex_flag


class BodyDiscoveryTests(unittest.TestCase):
    def test_discoverers_are_kept_per_body_for_the_current_system(self):
        app = MainDashboard.__new__(MainDashboard)
        app.current_sys = "Prai Preia"
        app._ui_post = lambda callback, key=None: callback()
        app._refresh_html_workspace = Mock()
        replies = []
        app.edsm = SimpleNamespace(fetch_system_bodies=lambda name, callback: replies.append(callback))
        self.assertTrue(app._fetch_body_discovery("Prai Preia"))
        self.assertFalse(app._fetch_body_discovery("Prai Preia"), "asked once per system")
        replies[0]({"bodies": [
            {"bodyId": 3, "name": "Prai Preia 3", "discovery": {"commander": "Hale", "date": "2024-03-01 10:00:00"}},
            {"bodyId": 4, "name": "Prai Preia 4"},
        ]})
        self.assertEqual(app._edsm_body_discovery["bodies"], {"3": {"by": "Hale", "at": "2024-03-01 10:00:00"}})
        app._refresh_html_workspace.assert_called_once()
        # A reply for a system already left is dropped.
        app.current_sys = "Elsewhere"
        app._fetch_body_discovery("Prai Preia 2")
        replies[-1]({"bodies": [{"bodyId": 1, "discovery": {"commander": "X"}}]})
        self.assertEqual(app._edsm_body_discovery["bodies"], {}, "never filled in for another system")

    def test_a_body_carries_its_strongest_codex_flag(self):
        item = {"body_id": 5, "bio_count": 2, "genuses": [{"Genus_Localised": "Bacterium"}],
                "predicted_genuses": [{"name": "Bacterium", "species": [
                    {"name": "Bacterium Aurasus", "key": "$Codex_Ent_Bacterial_01_Name;", "confirmed": True}]}]}
        self.assertEqual(body_codex_flag(item, lambda kind, key, body: "region"), "region")
        self.assertEqual(body_codex_flag(item, lambda kind, key, body: ""), "")
        self.assertEqual(body_codex_flag(item, None), "")


if __name__ == "__main__":
    unittest.main()
