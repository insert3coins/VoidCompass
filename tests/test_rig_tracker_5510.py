"""5.5.10: the Rig Tracker, after SrvSurvey's: the game logs nothing when a
mining rig goes down, so a hotkey marks it where you stand, and the overlay
points the way to each one, with how far and how long (the hold is the Cargo
overlay's)."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from voidcompass.core.overlay_registry import DEFAULT_OVERLAY_HOTKEYS, OVERLAY_HOTKEY_SPECS, OVERLAY_SPEC_BY_ATTR, TEXT_SIZE_KEYS
from voidcompass.dashboard.dashboard_rigs_mixin import DashboardRigsMixin
from voidcompass.overlays.rig_tracker import HERE_M, RigStore, bearing_deg, build_rig_model, collect_order, surface_distance_m

ROOT = Path(__file__).resolve().parents[1]
RADIUS = 2_400_000.0
BODY = "Synuefe XX-A d1-58 AB 3 a"


def store(test):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    return RigStore(str(Path(folder.name) / "rigs.json")), Path(folder.name) / "rigs.json"


class GeometryTests(unittest.TestCase):
    def test_distance_and_bearing_on_a_planet(self):
        metres_per_degree = RADIUS * 3.141592653589793 / 180
        self.assertAlmostEqual(surface_distance_m(0, 0, 1, 0, RADIUS), metres_per_degree, delta=1)
        self.assertAlmostEqual(bearing_deg(0, 0, 1, 0), 0, delta=.01)    # due north
        self.assertAlmostEqual(bearing_deg(0, 0, 0, 1), 90, delta=.01)   # due east
        self.assertAlmostEqual(bearing_deg(0, 0, -1, 0), 180, delta=.01)

    def test_collect_nearest_first_then_nearest_to_that(self):
        rigs = {1: {"lat": 0.3, "lon": 0}, 2: {"lat": 0.1, "lon": 0}, 3: {"lat": 0.2, "lon": 0}}
        self.assertEqual(collect_order((0, 0), rigs, RADIUS), [2, 3, 1])


class StoreTests(unittest.TestCase):
    def test_the_key_marks_then_collects(self):
        rigs, _path = store(self)
        self.assertEqual(rigs.mark(1, "Sys", BODY, 10, 20, now=1000), "placed")
        self.assertEqual(rigs.rigs("Sys", BODY, now=1000), {1: {"lat": 10.0, "lon": 20.0, "at": 1000.0}})
        self.assertEqual(rigs.mark(1, "Sys", BODY, 10.5, 20.5, now=2000), "collected")
        self.assertEqual(rigs.rigs("Sys", BODY, now=2000), {})

    def test_each_planet_its_own_and_one_rig_per_number(self):
        rigs, _path = store(self)
        rigs.mark(1, "Sys", BODY, 10, 20, now=1000)
        rigs.mark(2, "Sys", BODY, 11, 20, now=1000)
        self.assertEqual(rigs.rigs("Sys", "Another body", now=1000), {})
        rigs.mark(1, "Sys", "Another body", 1, 2, now=1100)
        self.assertEqual(set(rigs.rigs("Sys", BODY, now=1100)), {2}, "rig 1 went with you")
        self.assertEqual(set(rigs.rigs("Sys", "Another body", now=1100)), {1})

    def test_kept_across_restarts_and_forgotten_after_a_week(self):
        rigs, path = store(self)
        rigs.mark(3, "Sys", BODY, 10, 20, now=1000)
        from voidcompass.core import persistence_queue as pq
        pq.persistence_queue().flush(str(path), timeout=2)
        again = RigStore(str(path))
        self.assertEqual(set(again.rigs("Sys", BODY, now=2000)), {3})
        self.assertEqual(again.rigs("Sys", BODY, now=1000 + 8 * 86400), {})

    def test_forget_the_rigs_here(self):
        rigs, _path = store(self)
        rigs.mark(1, "Sys", BODY, 10, 20)
        self.assertTrue(rigs.clear("Sys", BODY))
        self.assertEqual(rigs.rigs("Sys", BODY), {})


class ModelTests(unittest.TestCase):
    def test_dials_point_the_way_from_where_you_face(self):
        rigs = {1: {"lat": 0.01, "lon": 0, "at": 0}, 4: {"lat": 0, "lon": 0.05, "at": 0}}
        model = build_rig_model(rigs, 0, 0, 90, RADIUS, BODY, now=600)
        slots = {row["slot"]: row for row in model["slots"]}
        self.assertEqual(len(model["slots"]), 6)
        self.assertFalse(slots[2]["tracked"])
        self.assertAlmostEqual(slots[1]["relative"], 270, delta=.5, msg="north, while facing east: to your left")
        self.assertAlmostEqual(slots[4]["relative"], 0, delta=.5, msg="east, while facing east: straight ahead")
        self.assertTrue(slots[1]["nearest"])
        self.assertNotIn("nearest", slots[4])
        self.assertEqual(slots[1]["age_s"], 600)
        self.assertEqual(model["order"], [1, 4])
        self.assertEqual(model["holds"], [], "how full the holds are only (5.5.11): the Cargo overlay lists them")

    def test_at_a_rig(self):
        model = build_rig_model({2: {"lat": 0, "lon": 0, "at": 0}}, 0.0001, 0, 0, RADIUS)
        self.assertLess(model["slots"][1]["distance_m"], HERE_M)
        self.assertTrue(model["slots"][1]["here"])

    def test_up_as_soon_as_the_rhino_is_out(self):
        model = build_rig_model({}, 0, 0, 0, RADIUS, BODY, in_rhino=True, hint="CTRL+ALT+1 AS YOU DEPLOY RIG 1")
        self.assertEqual((model["tracked"], model["order"], model["hint"]), (0, [], "CTRL+ALT+1 AS YOU DEPLOY RIG 1"))
        self.assertFalse(any(row["tracked"] for row in model["slots"]))
        once_down = build_rig_model({1: {"lat": 0, "lon": 0, "at": 0}}, 0, 0, 0, RADIUS, in_rhino=True, hint="x")
        self.assertEqual(once_down["hint"], "", "the reminder goes once a rig is down")

    def test_nothing_to_show_without_rigs_or_a_planet(self):
        self.assertIsNone(build_rig_model({}, 0, 0, 0, RADIUS))
        self.assertIsNone(build_rig_model({1: {"lat": 0, "lon": 0, "at": 0}}, None, None, None, None))


class Deck(DashboardRigsMixin):
    def __init__(self, folder):
        self.config = {"active_commander_name": "Tester"}
        self.on_planet, self.current_latitude, self.current_longitude = True, 0.0, 0.0
        self.current_planet_radius, self.current_heading = RADIUS, 0.0
        self.current_body_name, self.current_sys = BODY, "Synuefe XX-A d1-58"
        self.toast_hud = Mock()
        self.rig_tracker_hud = Mock()
        self._rig_store_instance, self._rig_store_key = RigStore(str(Path(folder) / "rigs.json")), "default"

    def rig_store(self):
        return self._rig_store_instance


class HotkeyTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Deck(folder.name)

    def test_deploy_then_collect_with_one_key(self):
        deck = self.deck()
        self.assertEqual(deck._rig_mark(1), "placed")
        deck.current_latitude = 0.01
        self.assertEqual(deck._rig_mark(2), "placed")
        title = deck.toast_hud.push.call_args.args[0]
        self.assertEqual(title, "RIG 2 DEPLOYED")
        self.assertIn("from rig 1", deck.toast_hud.push.call_args.args[1])
        model = deck.rig_tracker_hud.update.call_args.args[0]
        self.assertEqual(model["tracked"], 2)
        self.assertEqual(deck._rig_mark(1), "collected")
        self.assertEqual(deck.toast_hud.push.call_args.args[:2], ("RIG 1 COLLECTED", "1 still out"))

    def test_off_the_surface_it_says_so(self):
        deck = self.deck()
        deck.on_planet = False
        self.assertIsNone(deck._rig_mark(3))
        self.assertEqual(deck.toast_hud.push.call_args.kwargs["severity"], "warn")

    def test_launching_the_rhino_brings_it_up(self):
        deck = self.deck()
        deck._rig_update_overlay()
        self.assertIsNone(deck.rig_tracker_hud.update.call_args.args[0], "no rigs, not in the Rhino")
        deck.current_in_srv, deck.current_vehicle_name = True, "RHINO"
        deck.config["overlay_hotkey_rig_1"] = "Ctrl+Alt+1"
        deck._rig_update_overlay()
        model = deck.rig_tracker_hud.update.call_args.args[0]
        self.assertEqual(model["hint"], "CTRL+ALT+1 AS YOU DEPLOY RIG 1 · AGAIN AS YOU COLLECT IT")
        deck.current_vehicle_name = "SCARAB"
        deck._rig_update_overlay()
        self.assertIsNone(deck.rig_tracker_hud.update.call_args.args[0], "other SRVs don't deploy rigs")

    def test_the_overlay_hides_when_no_rigs_are_here(self):
        deck = self.deck()
        deck._rig_mark(1)
        deck.current_body_name = "Somewhere else"
        deck._rig_update_overlay()
        self.assertIsNone(deck.rig_tracker_hud.update.call_args.args[0])


class ApiTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Deck(folder.name)

    def test_read_the_rigs_and_mark_them_from_outside(self):
        deck = self.deck()
        self.assertEqual(deck.api_rig_mark(2)["done"], "placed")
        answer = deck.api_rigs()
        self.assertTrue(answer["on_surface"])
        self.assertEqual([row["slot"] for row in answer["rigs"]], [2])
        self.assertEqual(answer["body"], BODY)
        self.assertEqual(deck.api_rig_mark(2)["done"], "collected")

    def test_rigs_left_on_other_planets(self):
        deck = self.deck()
        deck.api_rig_mark(1)
        deck.current_body_name = "Elsewhere 2"
        self.assertEqual(deck.api_rigs()["elsewhere"], [{"system": "Synuefe XX-A d1-58", "body": BODY, "rigs": [1]}])

    def test_off_the_surface_it_refuses(self):
        from voidcompass.services.local_api import ApiError
        deck = self.deck()
        deck.on_planet = False
        with self.assertRaises(ApiError) as caught:
            deck.api_rig_mark(1)
        self.assertEqual(caught.exception.status, 409)
        self.assertFalse(deck.api_rigs()["on_surface"])

    def test_over_http(self):
        from http.client import HTTPConnection
        import json
        import socket
        from voidcompass.services.local_api import LocalApi
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        deck = self.deck()
        api = LocalApi(deck, version="test")
        self.assertTrue(api.configure(enabled=True, port=port))
        self.addCleanup(api.stop)

        def call(path, method="GET", body=None):
            connection = HTTPConnection("127.0.0.1", port, timeout=10)
            self.addCleanup(connection.close)
            payload = json.dumps(body).encode() if body is not None else b"{}"
            connection.request(method, f"/api/v1{path}", body=payload if method == "POST" else None,
                               headers={"Content-Type": "application/json"} if method == "POST" else {})
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))

        status, answer = call("/rigs/3", "POST")
        self.assertEqual((status, answer["done"]), (200, "placed"))
        self.assertEqual([row["slot"] for row in call("/rigs")[1]["rigs"]], [3])
        self.assertEqual(call("/rigs/7", "POST")[0], 404)
        self.assertEqual(call("/rigs/clear", "POST")[0], 400)
        status, answer = call("/rigs/clear", "POST", {"confirmed": True})
        self.assertEqual((status, answer["forgotten"], answer["rigs"]), (200, True, []))
        deck.on_planet = False
        self.assertEqual(call("/rigs/1", "POST")[0], 409)

    def test_the_routes_are_documented(self):
        from voidcompass.services.local_api import PROVIDER_CALLS
        self.assertTrue({"api_rigs", "api_rig_mark", "api_rigs_clear"} <= set(PROVIDER_CALLS))
        docs = (ROOT / "api.md").read_text(encoding="utf-8")
        for path in ("`/api/v1/rigs`", "`/api/v1/rigs/{n}`", "`/api/v1/rigs/clear`"):
            self.assertIn(path, docs)


class RegistrationTests(unittest.TestCase):
    def test_an_overlay_with_its_own_hotkeys(self):
        spec = OVERLAY_SPEC_BY_ATTR["rig_tracker_hud"]
        self.assertEqual((spec.overlay_id, spec.enabled_key, spec.default_enabled), ("rig-tracker", "rig_tracker_overlay_enabled", True))
        self.assertIn("rig_tracker_hud", TEXT_SIZE_KEYS)
        actions = {row[0] for row in OVERLAY_HOTKEY_SPECS}
        self.assertTrue({f"rig_{n}" for n in range(1, 7)} | {"rig_clear", "rig_tracker"} <= actions)
        self.assertEqual([DEFAULT_OVERLAY_HOTKEYS[f"overlay_hotkey_rig_{n}"] for n in range(1, 7)],
                         [f"Ctrl+Alt+{n}" for n in range(1, 7)])

    def test_kept_per_commander(self):
        from voidcompass.core.config import PROFILE_SETTINGS
        for key in ("rig_tracker_overlay_enabled", "rig_tracker_hud_x", "rig_tracker_hud_y", "rig_tracker_text_scale_percent",
                    "overlay_hotkey_rig_1", "overlay_hotkey_rig_6", "overlay_hotkey_rig_clear"):
            self.assertIn(key, PROFILE_SETTINGS)

    def test_its_page_follows_the_overlay_fit(self):
        page = (ROOT / "web" / "rig_tracker" / "app.js").read_text(encoding="utf-8")
        self.assertIn("VoidCompassOverlay.fitToWindow(root, 420", page)
        self.assertIn("VoidCompassOverlay.designHeight(root, 130)", page)
        host = (ROOT / "src" / "voidcompass" / "overlays" / "html_overlay_host.py").read_text(encoding="utf-8")
        self.assertIn('"/rig_tracker/index.html"', host)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('attr == "rig_tracker_hud"', dashboard)
        self.assertIn('action.startswith("rig_")', dashboard)


if __name__ == "__main__":
    unittest.main()
