"""5.6.1: Expeditions. Mission Control rebuilt as the Expeditions page: legs
Spansh plots, the data at risk, supplies, a streak (with Ironman), progress by
distance, a community expedition imported, a Nav HUD page, Void Wrapped and a
replay for the trip, and the Watcher's milestones."""

import os
import re
import tempfile
import unittest
from pathlib import Path

from voidcompass.dashboard.dashboard_expedition_mixin import DashboardExpeditionMixin
from voidcompass.exploration import expedition_plan as plan
from voidcompass.exploration.expedition_manager import ExpeditionManager
from voidcompass.exploration.void_wrapped import _trip_words
from voidcompass.overlays import hud_pages, watcher_lines
from voidcompass.overlays.watcher_mind import IMPORTANCE

ROOT = Path(__file__).resolve().parents[1]
SGR_A = [25.21875, -20.90625, 25899.96875]


def jump(system, pos, dist, at="2099-01-01T10:00:00Z", **extra):
    return {"event": "FSDJump", "StarSystem": system, "StarPos": pos, "JumpDist": dist, "timestamp": at, **extra}


class Deck(DashboardExpeditionMixin):
    def __init__(self):
        self.expedition_manager = ExpeditionManager(os.path.join(tempfile.mkdtemp(), "expeditions.json"))
        self.config = {}
        self.current_sys, self.current_coords = "Sol", [0.0, 0.0, 0.0]
        self.companion_state = {"loadout": {"MaxJumpRange": 62.3, "Modules": [{"Item": "int_dronecontrol_repair_size3"}]},
                                "unsold_exploration_cr": 150_000_000}
        self.current_cargo_inventory = [{"Name": "drones", "Count": 2}]
        self.engineer_materials = {"raw": {"iron": 40, "nickel": 25}}
        self.notes = []
        deck = self

        class Heartbeat:
            def note(self, topic, fields):
                deck.notes.append((topic, fields))

        self.heartbeat_hud = Heartbeat()

    def _galaxy_minimap_position(self):
        return self.current_coords

    def add_event_feed_entry(self, *args, **kwargs):
        pass

    def _schedule_html_dashboard_publish(self, immediate=False):
        pass


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = ExpeditionManager(os.path.join(tempfile.mkdtemp(), "expeditions.json"))
        self.expedition = self.manager.create("Colonia run", start_system="Sol", destination="Colonia", return_system="Sol",
                                              start_pos=[0, 0, 0])

    def test_a_new_expedition_has_its_destination_and_the_way_home(self):
        legs = self.manager.get(self.expedition["id"])["legs"]
        self.assertEqual([(leg["system"], leg["kind"]) for leg in legs], [("Colonia", "destination"), ("Sol", "home")])
        self.manager.add_leg(self.expedition["id"], "Sagittarius A*")
        self.assertEqual([leg["system"] for leg in self.manager.get(self.expedition["id"])["legs"]],
                         ["Sagittarius A*", "Colonia", "Sol"], "a stop goes before the destination")

    def test_legs_are_reached_and_the_streak_counts(self):
        manager, eid = self.manager, self.expedition["id"]
        result = manager.observe_event(jump("Colonia", [-9530.5, -910.28, 19808.13], 50), event_uid="a")
        self.assertIn("set_out", result["milestones"])
        self.assertTrue(manager.get(eid)["legs"][0]["reached"])
        stats = manager.get(eid)["stats"]
        self.assertEqual((stats["streak_jumps"], stats["start_pos"]), (1, [0.0, 0.0, 0.0]), "where it was created")
        manager.observe_event({"event": "HullDamage", "Health": .2, "PlayerPilot": True, "timestamp": "2099-01-01T11:00:00Z"},
                              event_uid="b")
        self.assertEqual(manager.get(eid)["stats"]["streak_jumps"], 0, "a hull scare ends the streak")
        self.assertEqual(manager.get(eid)["stats"]["scares"], 1)

    def test_ironman_fails_on_a_death(self):
        manager, eid = self.manager, self.expedition["id"]
        manager.set_ironman(eid, True)
        manager.observe_event({"event": "Died", "timestamp": "2099-01-01T11:00:00Z"}, event_uid="c")
        self.assertEqual(manager.get(eid)["status"], "failed")
        self.assertIsNone(manager.active())

    def test_old_saves_load_with_the_new_fields(self):
        self.manager.flush(wait=True)
        again = ExpeditionManager(self.manager.path)
        row = again.get(self.expedition["id"])
        self.assertEqual((row["ironman"], row["day_notes"], len(row["legs"])), (False, {}, 2))

    def test_a_pilgrimage_objective_is_met_at_the_place(self):
        eid = self.expedition["id"]
        self.manager.add_objective(eid, "pilgrimage", target="core")
        self.manager.observe_event(jump("Near the core", [25, -20, 25500], 40), event_uid="d")
        objective = self.manager.get(eid)["objectives"][0]
        self.assertEqual(objective["status"], "complete")


class PlanTests(unittest.TestCase):
    def test_progress_by_distance(self):
        legs = [{"coords": [0, 0, 100], "reached": "x"}, {"coords": [0, 0, 300]}]
        progress = plan.path_progress([0, 0, 0], legs, [0, 0, 150])
        self.assertEqual((progress["total_ly"], progress["to_go_ly"], progress["share"]), (300.0, 150.0, .5))

    def test_a_neutron_chain_with_nothing_to_scoop(self):
        rows = [{"system": str(n), "neutron": True, "jumps": 1} for n in range(5)] + [{"system": "x", "neutron": False, "jumps": 3}]
        self.assertEqual(plan.fuel_runs(rows), [{"from": "0", "to": "4", "jumps": 5}])
        self.assertEqual(plan.fuel_runs(rows[:3]), [], "three in a row is fine")

    def test_imports_a_list_a_csv_or_a_spansh_link(self):
        self.assertEqual([row["name"] for row in plan.parse_import("1. Sol\n2) Colonia\n- Beagle Point")["systems"]],
                         ["Sol", "Colonia", "Beagle Point"])
        csv = plan.parse_import("System,x,y,z\nSol,0,0,0\nColonia,-9530,-910,19808")["systems"]
        self.assertEqual(csv[1]["coords"], [-9530.0, -910.0, 19808.0])
        self.assertEqual(plan.parse_import("https://spansh.co.uk/plotter/results/1A2B3C4D-1111-2222-3333-444455556666")["spansh_job"],
                         "1A2B3C4D-1111-2222-3333-444455556666")

    def test_eta_at_your_own_pace(self):
        times = [i * 90.0 for i in range(40)]
        measured = plan.pace(times, [50.0] * 40, [3 * 3600])
        self.assertEqual(measured["jumps_per_hour"], 40.0)
        self.assertEqual(plan.eta(4000, measured), {"jumps": 80, "hours": 2.0, "sessions": 1})

    def test_supplies_say_what_is_low_and_what_you_can_make(self):
        supplies = plan.supplies({"hull_percent": 62, "afmu_installed": True, "afmu_ammo": 120,
                                  "injections": {"basic": 0, "standard": 0, "premium": 0}}, limpets=2, repair_controller=True,
                                 raw_materials={"iron": 25, "nickel": 30})
        self.assertEqual(supplies["low"], ["Hull", "AFMU", "Limpets", "FSD injections"])
        limpets = next(row for row in supplies["rows"] if row["name"] == "Limpets")
        self.assertIn("8 more", limpets["detail"])


class DeckTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        manager = self.deck.expedition_manager
        self.expedition = manager.create("Colonia run", start_system="Sol", destination="Colonia", return_system="Sol",
                                         start_pos=[0, 0, 0])
        legs = manager.get(self.expedition["id"])["legs"]
        manager.update_leg(self.expedition["id"], legs[0]["id"], coords=[-9530.5, -910.28, 19808.13])
        manager.update_leg(self.expedition["id"], legs[1]["id"], coords=[0, 0, 0])

    def test_the_page_follows_the_active_trip(self):
        data = self.deck._html_expedition_workspace()
        live = data["expeditions"][0]["live"]
        self.assertGreater(live["progress"]["total_ly"], 40000)
        self.assertTrue(live["risk"]["over"], "150 M CR aboard, past the 100 M CR line")
        self.assertIn("Limpets", live["supplies"]["low"])

    def test_the_hud_page(self):
        page = self.deck._hud_page_expedition()
        self.assertEqual(page["id"], "expedition")
        self.assertIn("LY TO GO", page["blocks"][0]["value"])
        self.assertIn("expedition", hud_pages.PAGES)
        self.assertEqual(hud_pages.hold_page("nav", {}, {"expedition": True}, 0, list(hud_pages.PAGES)), "expedition",
                         "on an expedition its page stands in for NAV")

    def test_milestones_reach_the_watcher(self):
        manager = self.deck.expedition_manager
        result = manager.observe_event(jump("Wregoe", [-1000, 0, 2000], 60), event_uid="x")
        self.deck._expedition_after_event(result, "FSDJump")
        topics = [topic for topic, _fields in self.deck.notes]
        self.assertIn("expedition_set_out", topics)
        self.assertIn("expedition_risk", topics)

    def test_commands(self):
        eid = self.expedition["id"]
        self.assertTrue(self.deck._handle_expedition_command("day_note", {"expedition_id": eid, "day": "2026-10-23", "text": "Long day"}))
        self.assertTrue(self.deck._handle_expedition_command("import", {"expedition_id": eid, "text": "Sol\nColonia\nBeagle Point"}))
        self.assertEqual([leg["kind"] for leg in self.deck.expedition_manager.get(eid)["legs"]], ["stop", "stop", "destination", "home"])
        self.assertIsNone(self.deck._handle_expedition_command("status", {}), "the older commands are answered elsewhere")


class WrappedTests(unittest.TestCase):
    def test_a_trip_is_told_in_its_own_words(self):
        self.assertEqual(_trip_words("You flew far this year. The Year of Long Roads."), "You flew far this trip. The Voyage of Long Roads.")
        self.assertEqual(_trip_words("40,000 light years"), "40,000 light years", "light years stay light years")


class LinesTests(unittest.TestCase):
    def test_every_expedition_topic_has_ten_lines_a_nature(self):
        for topic in (name for name in IMPORTANCE if name.startswith("expedition_")):
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)


class PageTests(unittest.TestCase):
    def test_on_the_rail_and_in_the_api(self):
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="mission" aria-label="Expeditions"', page)
        names = re.findall(r'class="nav-item[^"]*" data-page="[^"]+" aria-label="([^"]+)"', page)
        self.assertEqual(names[:3], ["Dashboard", "Expeditions", "Explore &amp; Survey"])
        api = (ROOT / "api.md").read_text(encoding="utf-8")
        self.assertIn("`/api/v1/expedition`", api)
        self.assertIn("`/api/v1/expeditions`", api)


class PageLayoutTests(unittest.TestCase):
    """Laid out again after it cut names short: nothing clips, and the waypoint
    route borrowed from Explore keeps Explore's look here too."""

    def test_nothing_is_cut_short(self):
        css = (ROOT / "web" / "dashboard" / "expeditions.css").read_text(encoding="utf-8")
        self.assertNotIn("ellipsis", css)
        self.assertNotIn("nowrap", css)
        script = (ROOT / "web" / "dashboard" / "expeditions.js").read_text(encoding="utf-8")
        for marker in ("function tripBar", "function voyage", 'class="ex-next"', 'class="ex-legs"', "more</b>"):
            self.assertIn(marker, script)

    def test_the_route_cards_are_styled_on_both_pages(self):
        css = (ROOT / "web" / "dashboard" / "explore.css").read_text(encoding="utf-8")
        for name in (".waypoint-row", ".route-system", ".neutron-form", ".route-add-form"):
            self.assertNotRegex(css, rf"(?m)^#explore-workspace {re.escape(name)}", name)
            self.assertIn(f":is(#explore-workspace, #mission-workspace) {name}", css)

    def test_its_own_place_on_the_rail(self):
        app = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('["mission", "EXPEDITIONS"]', app)


if __name__ == "__main__":
    unittest.main()
