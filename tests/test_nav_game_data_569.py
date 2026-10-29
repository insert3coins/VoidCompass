"""5.6.9: the Navigation HUD's scenes drawn from the game's own data.

The FSD cooldown counts down to FSD READY once its length has been measured
(tests/test_jump_clock_569.py learns it); a carrier's departure fills the rail
from the request to the jump; the pad you were cleared to stays with you in
the hangar; your locked target flies its own hull with its scanned shields and
hull; the power distributor's pips sit on the ship's portrait; and the body you
are at is drawn as your scan has it, rings and atmosphere only if it has them.
"""

import unittest

from tests import test_navigation_scene as scene_tests
from tests.test_navigation_state_visuals import hud_state
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.dashboard_hud_pages_mixin import DashboardHudPagesMixin
from voidcompass.overlays.hud import TacticalHUD
from voidcompass.services import carrier_tracker
from voidcompass.services.carrier_tracker import CarrierTracker


def deck():
    dashboard = MainDashboard.__new__(MainDashboard)
    dashboard.config = {"ground_target_lat": 0, "ground_target_lon": 0, "ground_target_active": False,
                        "ground_popup_enabled": False}
    dashboard._reset_profile_runtime_state("Commander", "F1")
    dashboard.batch_mode = True
    dashboard.heartbeat_hud = None
    dashboard.mining_window = None
    dashboard._perf_spike = lambda *_args, **_kwargs: None
    return dashboard


class GameDataTests(unittest.TestCase):
    def test_the_carrier_remembers_when_its_jump_was_asked_for(self):
        tracker = CarrierTracker.__new__(CarrierTracker)
        tracker.carrier_data = {}
        tracker._handle_jump_request({"timestamp": "2026-10-30T10:00:00Z", "DepartureTime": "2026-10-30T10:15:10Z",
                                      "SystemName": "Colonia"})
        self.assertEqual(tracker.carrier_data["jump_requested_time"], "2026-10-30T10:00:00Z")
        self.assertIn("jump_requested_time", carrier_tracker._PERSIST_KEYS)
        tracker._handle_jump_cancelled({"timestamp": "2026-10-30T10:01:00Z"})
        self.assertIsNone(tracker.carrier_data["jump_requested_time"])
        travel = {"state": "carrier_preparing", "carrier_schedule": {
            "departure_epoch": 1000.5, "requested_epoch": 100.0, "carrier_type": "SquadronCarrier"}}
        self.assertEqual(TacticalHUD._carrier_clock(travel), {"departure": 1000500, "requested": 100000, "squadron": True})
        self.assertIsNone(TacticalHUD._carrier_clock({**travel, "state": "ready"}))

    def test_the_pad_stays_with_you_until_you_leave(self):
        dashboard = deck()
        dashboard._observe_navigation_docking_state("DockingGranted", {"LandingPad": 7, "StationName": "Jameson Memorial",
                                                                       "StationType": "Orbis"}, {})
        for event in ("Docked", "CarrierJump"):
            dashboard._observe_navigation_docking_state(event, {}, {})
            self.assertEqual(dashboard._navigation_pad["pad"], 7, event)
        dashboard._observe_navigation_docking_state("Undocked", {}, {})
        self.assertIsNone(dashboard._navigation_pad)

    def test_the_body_you_are_at_as_the_scan_has_it(self):
        dashboard = deck()
        dashboard.scan_items_by_id = {3: {"planet_class": "Icy body", "rings": [{}, {}], "atmosphere_type": "Thin Neon",
                                          "radius": 1500000.0}}
        dashboard.current_body_id = 3
        self.assertEqual(dashboard._navigation_body_form(), {"kind": "ice", "rings": 2, "radius_km": 1500, "atmosphere": True})
        dashboard.current_body_id = None
        dashboard.current_body_name = "Sol 5"
        dashboard.scan_items = [{"name": "Sol 5", "planet_class": "Sudarsky class I gas giant", "radius": 7e7}]
        self.assertEqual(dashboard._navigation_body_form()["kind"], "gas")
        self.assertTrue(dashboard._navigation_body_form()["atmosphere"], "a giant is all atmosphere")
        dashboard.scan_items = [{"name": "Sol 5", "planet_class": "High metal content body", "atmosphere": ""}]
        self.assertEqual((dashboard._navigation_body_form()["kind"], dashboard._navigation_body_form()["atmosphere"]),
                         ("metal", False))
        dashboard.scan_items = [{"name": "Sol 5", "star_type": "G"}]
        self.assertIsNone(dashboard._navigation_body_form(), "a star isn't a world to land on")

    def test_your_target_as_far_as_it_is_scanned_and_the_hud_hears_of_it(self):
        dashboard = deck()
        self.assertIsNone(dashboard._navigation_combat_target())
        dashboard._hud_target = {"symbol": "anaconda", "stage": 3, "shields": 40.0, "hull": 90.0, "legal_status": "Wanted"}
        self.assertEqual(dashboard._navigation_combat_target(),
                         {"symbol": "anaconda", "stage": 3, "shields": 40.0, "hull": 90.0, "wanted": True})

        class Pages(DashboardHudPagesMixin):
            refreshed = 0

            def update_hud(self):
                self.refreshed += 1
        pages = Pages()
        raw = {"TargetLocked": True, "Ship": "anaconda", "ScanStage": 2, "ShieldHealth": 50.0, "HullHealth": 100.0}
        pages._hud_pages_observe("ShipTargeted", raw)
        pages._hud_pages_observe("ShipTargeted", raw)
        self.assertEqual(pages.refreshed, 1, "only a change refreshes the HUD")

    def test_the_power_distributor_is_read_from_status(self):
        dashboard = deck()
        dashboard._apply_status_update({"Flags": dashboard._STATUS_IN_MAIN_SHIP, "Pips": [4, 8, 0]})
        self.assertEqual(dashboard.current_pips, [4, 8, 0])
        dashboard._apply_status_update({"Flags": 0, "Flags2": 1})
        self.assertIsNone(dashboard.current_pips, "on foot there is no distributor")


class GameDataHudTests(unittest.TestCase):
    open = scene_tests.NavigationSceneBrowserTests.open
    render = scene_tests.NavigationSceneBrowserTests.render
    controlled_frame = scene_tests.NavigationSceneBrowserTests.controlled_frame

    @classmethod
    def setUpClass(cls):
        scene_tests.NavigationSceneBrowserTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        scene_tests.NavigationSceneBrowserTests.tearDownClass.__func__(cls)

    def show(self, page, label, clocks=None, **dynamics):
        now = page.evaluate("Date.now()")
        state = hud_state(label, **dynamics)
        for field, fields in (clocks or {}).items():
            state[field] = {key: now + value if isinstance(value, int) and key in {"start", "ready", "departure", "requested"} else value
                            for key, value in fields.items()}
        self.render(page, state)
        return page.locator("#instrument-readout").text_content()

    def test_the_cooldown_counts_to_fsd_ready_once_measured(self):
        page = self.open()
        text = self.show(page, "FSD COOLDOWN", {"cooldown_clock": {"after": "hyperspace", "start": -4000, "ready": 6500, "exact": True}})
        self.assertEqual(text, "FSD READY IN 7")
        self.assertEqual(page.locator("#instrument").get_attribute("data-instrument"), "cooldown")
        text = self.show(page, "FSD COOLDOWN", {"cooldown_clock": {"after": "other", "start": -4000, "ready": None, "exact": False}})
        self.assertEqual(text, "FSD COOLDOWN")
        self.assertIn("unmeasured", page.locator("#instrument").get_attribute("class"))

    def test_a_carrier_counts_to_its_departure_and_its_lockdown(self):
        page = self.open()
        self.assertEqual(self.show(page, "CARRIER PREPARING", {"carrier_clock": {"departure": 720500, "requested": -180000}}),
                         "JUMP IN 12:01")
        self.assertRegex(page.evaluate("document.getElementById('instrument-fill').style.transition"), r"transform \d+ms linear")
        self.assertEqual(self.show(page, "CARRIER LOCKDOWN", {"carrier_clock": {"departure": 150500, "requested": -750000}}),
                         "LOCKDOWN 2:31")

    def test_the_pad_shows_docked_but_not_in_flight(self):
        page = self.open()
        self.assertEqual(self.show(page, "DOCKED", landing_pad=7), "PAD 07")
        self.assertEqual(self.show(page, "FLIGHT", landing_pad=7), "")

    def test_your_target_flies_its_own_hull(self):
        page = self.open()
        self.show(page, "COMBAT")
        plain = self.controlled_frame(page, 1.37)["deck"]
        self.show(page, "COMBAT", target={"symbol": "anaconda", "stage": 3, "shields": 40, "hull": 80, "wanted": True})
        self.assertEqual(page.evaluate("navigationScene.state.targetKey"), "anaconda")
        self.assertNotEqual(self.controlled_frame(page, 1.37)["deck"], plain)

    def test_the_body_and_the_distributor_are_drawn_from_the_game(self):
        page = self.open()
        self.show(page, "ORBITAL APPROACH")
        plain = self.controlled_frame(page, 1.37)["deck"]
        self.show(page, "ORBITAL APPROACH", body={"kind": "gas", "rings": 2, "atmosphere": True, "radius_km": 60000})
        self.assertIn("gas2a", page.evaluate("navigationScene.state.identity"))
        self.assertNotEqual(self.controlled_frame(page, 1.37)["deck"], plain)
        # The distributor sits on the ship's portrait, clear of the hologram.
        self.show(page, "FLIGHT")
        self.assertTrue(page.locator("#vehicle-pips").is_hidden())
        self.show(page, "FLIGHT", pips=[8, 0, 3])
        columns = page.evaluate("[...document.querySelectorAll('#vehicle-pips b')].map(b => [...b.children].map(i => i.className))")
        self.assertEqual(columns, [["full"] * 4, [""] * 4, ["full", "half", "", ""]])
        self.assertTrue(page.evaluate("document.querySelector('.holo-bay').contains(document.getElementById('vehicle-pips'))"))
        self.show(page, "FLIGHT", pips=[8, 0, 3], in_main_ship=False)
        self.assertTrue(page.locator("#vehicle-pips").is_hidden(), "on foot or in the SRV there is no distributor")

    def test_the_new_scenes_stay_cheap_to_draw(self):
        page = self.open()
        worst = []
        cases = (
            ("FSD COOLDOWN", {"cooldown_clock": {"after": "hyperspace", "start": -2000, "ready": 8000, "exact": True}}, {"pips": [4, 4, 4]}),
            ("CARRIER LOCKDOWN", {"carrier_clock": {"departure": 120000, "requested": -600000}}, {}),
            ("COMBAT", None, {"target": {"symbol": "anaconda", "stage": 3, "shields": 40, "hull": 80, "wanted": True}, "pips": [2, 4, 6]}),
            ("ORBITAL APPROACH", None, {"body": {"kind": "gas", "rings": 3, "atmosphere": True, "radius_km": 60000}}),
            ("DSS 2/5", None, {"body": {"kind": "ice", "rings": 1, "atmosphere": False, "radius_km": 900}}),
        )
        for label, clocks, dynamics in cases:
            self.show(page, label, clocks, **dynamics)
            page.wait_for_timeout(600)
            cost = page.evaluate("""() => new Promise((resolve, reject) => {
              const scene = navigationScene, draw = scene.draw, samples = [];
              const timeout = setTimeout(() => { scene.draw = draw; reject(Error('no frames')); }, 5000);
              scene.draw = function(now) {
                const start = performance.now();
                draw.call(this, now);
                samples.push(performance.now() - start);
                if (samples.length === 30) {
                  scene.draw = draw; clearTimeout(timeout);
                  samples.sort((a, b) => a - b);
                  resolve(samples[Math.ceil(samples.length * .9) - 1]);
                }
              };
            })""")
            worst.append((label, cost))
        self.assertLess(max(cost for _, cost in worst), 4.0, worst)


if __name__ == "__main__":
    unittest.main()
