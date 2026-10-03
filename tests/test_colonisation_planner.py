"""5.5.2.1 Colonisation: the system planner (a port of Raven Colonial's
website model, checked against the website's own numbers), its draft and
save, sending your scans as a system's bodies, the station identifier, and
the rest of the website's features (markets, stats, nexus, carriers)."""

import base64
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from tests.test_colonisation import Deck, FakeResponse, project
from voidcompass.colonisation import identifier, planner
from voidcompass.colonisation.system_journal import SystemJournal
from voidcompass.colonisation.views import overlay_model
from voidcompass.colonisation.colony import ColonyState
from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS
from voidcompass.services.raven_colonial import RavenColonialClient

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "colonisation_planner_parity.json").read_text(encoding="utf-8"))


def close(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9
    return a == b


class PlannerParityTests(unittest.TestCase):
    """The expected values come from RavenColonialWeb's own model."""

    def test_every_figure_matches_the_website(self):
        for name, raw in FIXTURE["systems"].items():
            for key, expected in FIXTURE["expected"][name].items():
                if key == "snapshot":
                    snap = planner.snapshot(copy.deepcopy(raw))
                    self.assertTrue(close({"score": snap["score"], "tierPoints": snap["tierPoints"], "sumEffects": snap["sumEffects"]}, expected), name)
                    continue
                incomplete, buff = (part == "true" for part in key.split("|"))
                model = planner.build_model(copy.deepcopy(raw), incomplete, buff)
                with self.subTest(system=name, mode=key):
                    for field in ("score", "tier_points", "tax_count", "effects", "unlocks"):
                        self.assertTrue(close(model[field], expected[field]), (field, model[field], expected[field]))
                    self.assertEqual(list(model["economies"].items()), list(expected["economies"].items()))
                    for mine, theirs in zip(model["sites"], expected["sites"]):
                        self.assertEqual(mine["primary_economy"], theirs["primary"], mine["name"])
                        self.assertTrue(close(mine["economies"], theirs["economies"]), mine["name"])
                        self.assertEqual(mine["calc_needs"], theirs["calc_needs"], mine["name"])
                        self.assertEqual(mine["parent_link"], theirs["parent"], mine["name"])
                        links = mine["links"]["economies"] if mine["links"] else None
                        self.assertEqual(list((links or {}).items()), list((theirs["links"] or {}).items()), mine["name"])

    def test_site_types_and_helpers(self):
        self.assertEqual(planner.site_type("dual_truss")["displayName2"], "Coriolis Starport")
        self.assertEqual(planner.site_type("no_truss?")["displayName2"], "Coriolis Starport", "a trailing ? still matches")
        self.assertEqual(planner.site_type("nonsense")["buildClass"], "unknown")
        self.assertEqual(planner.build_type_name("dual_truss"), "Coriolis (dual_truss)")
        self.assertEqual(planner.build_type_name("demeter"), "Space Farm installation (demeter)")
        self.assertEqual(planner.apply_tax(2, 3, 1), 5)
        self.assertEqual(planner.apply_tax(3, 6, 2), 18)
        self.assertEqual(planner.predict_surface_slots({"type": "rb", "features": ["landable", "geo"], "radius": 2000, "gravity": 0.3, "temp": 200}), 3)
        self.assertEqual(planner.predict_surface_slots({"type": "gg", "features": [], "radius": 70000}), 0)
        rows = {"dual_truss": planner.site_type("dual_truss"), "demeter": planner.site_type("demeter")}
        model = planner.build_model({"name": "Nyx", "bodies": [], "sites": []})
        self.assertFalse(planner.type_validity(model, rows["dual_truss"])["valid"], "a Coriolis needs Tier 2 points")
        self.assertTrue(planner.type_validity(model, rows["demeter"])["valid"])


NYX = {
    "name": "Nyx", "id64": 77, "v": 6, "rev": 4, "architect": "Nyx Evera", "reserveLevel": "major", "open": False,
    "bodies": [{"num": 0, "name": "Nyx", "type": "st", "parents": [], "features": [], "distLS": 0},
               {"num": 3, "name": "Nyx 3", "type": "elw", "parents": [0], "features": ["bio", "landable"], "distLS": 900,
                "radius": 5000, "gravity": 1, "temp": 280}],
    "sites": [{"id": "s1", "name": "Gate", "bodyNum": 3, "buildType": "dual_truss", "status": "complete", "buildId": "b9", "marketId": 3900},
              {"id": "s2", "name": "Farm", "bodyNum": 3, "buildType": "demeter", "status": "plan", "buildId": None, "marketId": None}],
    "revs": [{"rev": 4, "cmdr": "Nyx Evera", "time": "2026-10-01T00:00:00Z"}], "savedNames": [],
}


class PlannerDraftTests(unittest.TestCase):
    def loaded(self):
        deck = Deck()
        deck.raven.system.return_value = copy.deepcopy(NYX)
        deck.raven.system_snapshot.return_value = None
        deck._handle_colonisation_command("planner_load", {"system": "Nyx"})
        return deck

    def test_load_checks_the_architects_snapshot(self):
        deck = self.loaded()
        snap = deck._planner_snapshot()
        self.assertTrue(snap["loaded"])
        self.assertTrue(snap["can_edit"])
        self.assertEqual([site["name"] for site in snap["sites"]], ["Gate", "Farm"])
        # Our own system with no snapshot yet: one is saved, as the website does.
        deck.raven.save_system_snapshot.assert_called_once()
        id64, saved = deck.raven.save_system_snapshot.call_args.args
        self.assertEqual((id64, saved["score"]), (77, planner.snapshot(NYX)["score"]))

    def test_edits_recalculate_and_save_sends_full_sites(self):
        deck = self.loaded()
        before = deck._planner_snapshot()["model"]["score"]
        deck._handle_colonisation_command("planner_site", {"id": "s2", "field": "status", "value": "complete"})
        after = deck._planner_snapshot()
        self.assertGreater(after["model"]["score"], before)
        self.assertTrue(after["dirty"])
        deck._handle_colonisation_command("planner_add", {})
        deck._handle_colonisation_command("planner_move", {"id": "s2", "to": 0})
        deck._handle_colonisation_command("planner_remove", {"id": "s1"})
        deck._handle_colonisation_command("planner_field", {"field": "reserveLevel", "value": "low"})
        deck.raven.update_system.return_value = copy.deepcopy(NYX)
        deck._handle_colonisation_command("planner_save", {})
        system, put = deck.raven.update_system.call_args.args
        self.assertEqual(system, "77")
        self.assertEqual(put["delete"], ["s1"])
        self.assertEqual(put["orderIDs"][0], "s2")
        updated = {site["id"]: site for site in put["update"]}
        self.assertEqual(updated["s2"]["status"], "complete")
        self.assertIn("buildId", updated["s2"], "the full site goes back, so project links survive")
        self.assertEqual(put["reserveLevel"], "low")
        self.assertEqual(put["snapshot"]["architect"], "Nyx Evera")
        self.assertNotIn("architect", put, "unchanged fields are left out")
        self.assertFalse(deck._planner_snapshot()["dirty"], "the saved system replaces the draft")

    def test_someone_elses_system_saves_only_as_a_named_copy(self):
        deck = Deck()
        deck.raven.system.return_value = {**copy.deepcopy(NYX), "architect": "Payden"}
        deck._handle_colonisation_command("planner_load", {"system": "Nyx"})
        deck.raven.save_system_snapshot.assert_not_called()
        self.assertFalse(deck._planner_snapshot()["can_edit"])
        deck._handle_colonisation_command("planner_site", {"id": "s2", "field": "name", "value": "Big Farm"})
        deck._handle_colonisation_command("planner_save", {})
        deck.raven.update_system.assert_not_called()
        self.assertIn("named copy", deck._colony_ui_state()["error"])
        deck.raven.update_system.return_value = copy.deepcopy(NYX)
        deck._handle_colonisation_command("planner_save", {"save_name": "my idea"})
        self.assertEqual(deck.raven.update_system.call_args.args[1]["saveName"], "my idea")

    def test_cut_line_and_options(self):
        deck = self.loaded()
        deck._handle_colonisation_command("planner_cut", {"index": 1})
        deck._handle_colonisation_command("planner_option", {"field": "use_incomplete", "value": True})
        model = deck._planner_snapshot()
        self.assertTrue(model["model"]["use_incomplete"])
        self.assertEqual([site["in_calc"] for site in model["sites"]], [True, False])
        self.assertTrue(deck.config["colony_planner_include_planned"])

    def test_start_project_from_a_planned_site(self):
        deck = self.loaded()
        deck.raven.create_project_from_site.return_value = {"buildId": "new", "buildName": "Farm"}
        deck._handle_colonisation_command("planner_start_project", {"id": "s2"})
        deck.raven.create_project_from_site.assert_called_once_with(77, "s2", "demeter")
        self.assertEqual(deck._colony_ui_state()["selected"], "new")

    def test_nothing_without_a_key(self):
        deck = Deck(key="")
        deck._handle_colonisation_command("planner_load", {"system": "Nyx"})
        self.assertEqual([call for call in deck.raven.method_calls if call[0] != "set_commander"], [])


def scan(body_id, name, **fields):
    return {"event": "Scan", "SystemAddress": 77, "StarSystem": "Nyx", "BodyID": body_id, "BodyName": name, **fields}


class SystemJournalTests(unittest.TestCase):
    def journal(self):
        journal = SystemJournal()
        for raw in (
            {"event": "FSDJump", "SystemAddress": 77, "StarSystem": "Nyx"},
            {"event": "FSSDiscoveryScan", "SystemAddress": 77, "BodyCount": 3, "Progress": 0.4},
            scan(0, "Nyx", StarType="DA", DistanceFromArrivalLS=0, Radius=7000000,
                 Rings=[{"Name": "Nyx A Belt", "RingClass": "eRingClass_MetalRich", "InnerRad": 299792458 * 20}]),
            scan(1, "Nyx 1", PlanetClass="Sudarsky class I gas giant", DistanceFromArrivalLS=500, Parents=[{"Star": 0}],
                 Radius=70000000, SurfaceGravity=20, Rings=[{"Name": "Nyx 1 A Ring"}]),
            scan(2, "Nyx 1 a", PlanetClass="Rocky body", DistanceFromArrivalLS=501, Parents=[{"Planet": 1}, {"Star": 0}],
                 TidalLock=True, Landable=True, Volcanism="minor silicate magma", TerraformState="Terraformable",
                 SurfaceGravity=1.96, SurfaceTemperature=300, Radius=2000000, AtmosphereType="None"),
            {"event": "FSSBodySignals", "SystemAddress": 77, "BodyID": 2, "Signals": [{"Type": "$SAA_SignalType_Geological;", "Count": 2}]},
            {"event": "FSSSignalDiscovered", "SystemAddress": 77, "SignalName": "Gate Hub", "SignalType": "StationCoriolis", "IsStation": True},
            {"event": "FSSSignalDiscovered", "SystemAddress": 77, "SignalName": "K7Q-1HT", "SignalType": "FleetCarrier"},
            {"event": "FSSAllBodiesFound", "SystemAddress": 77, "Count": 3},
        ):
            journal.observe(raw["event"], raw)
        return journal

    def test_bodies_in_raven_form(self):
        journal = self.journal()
        self.assertTrue(journal.ready_to_upload())
        bods = {bod["num"]: bod for bod in journal.raven_bodies()}
        self.assertEqual(bods[0]["type"], "wd", "white dwarfs are white dwarfs (not black holes)")
        self.assertEqual(bods[1]["type"], "gg")
        self.assertEqual(bods[1]["subType"], "Class I gas giant")
        self.assertIn("rings", bods[1]["features"])
        self.assertEqual(bods[2]["parents"], [1, 0])
        self.assertEqual(set(bods[2]["features"]), {"tidal", "geo", "volcanism", "terraformable", "landable"})
        self.assertAlmostEqual(bods[2]["gravity"], 0.2, places=2)
        self.assertEqual(bods[2]["radius"], 2000)
        belt = next(bod for bod in journal.raven_bodies() if bod["type"] == "ac")
        self.assertEqual((belt["num"], belt["subType"], belt["parents"]), (100000, "Metal Rich", [0]))
        self.assertAlmostEqual(belt["distLS"], 20)
        order = [bod["num"] for bod in journal.raven_bodies()]
        self.assertLess(order.index(100000), order.index(1), "the belt sits before bodies further out")

    def test_a_jump_starts_over(self):
        journal = self.journal()
        journal.observe("FSDJump", {"SystemAddress": 88, "StarSystem": "Elsewhere"})
        self.assertEqual((journal.scans, journal.honk, journal.name), ({}, None, "Elsewhere"))
        self.assertFalse(journal.observe("Scan", scan(5, "Nyx 5", PlanetClass="Icy body")), "another system's scans are ignored")

    def test_upload_sends_your_scans(self):
        deck = Deck()
        deck.raven.system.return_value = copy.deepcopy(NYX)
        deck._handle_colonisation_command("planner_load", {"system": "Nyx"})
        deck.colony_journal = self.journal()
        self.assertTrue(deck._planner_snapshot()["journal"]["ready"])
        deck.raven.update_system_bodies.return_value = deck.colony_journal.raven_bodies()
        deck._handle_colonisation_command("planner_upload_bodies", {})
        address, bodies = deck.raven.update_system_bodies.call_args.args
        self.assertEqual(address, 77)
        self.assertEqual(len(bodies), 4)


class IdentifierTests(unittest.TestCase):
    def state(self, bodies=4):
        deck = Deck()
        system = copy.deepcopy(NYX)
        system["bodies"] = [{"num": num, "name": name, "type": "rb", "parents": [], "features": []}
                            for num, name in ((0, "Nyx"), (1, "Nyx 1"), (2, "Nyx 1 a"), (100000, "Nyx A Belt"))][:bodies]
        state = deck._planner_from_system(system)
        return state

    def test_walks_the_phases(self):
        journal = SystemJournalTests().journal()
        state = self.state(bodies=2)
        identifier.start(state)
        self.assertEqual(identifier.step(state, journal)["phase"], "bodies", "Raven has too few bodies")
        state = self.state()
        identifier.start(state)
        ident = identifier.step(state, journal)
        self.assertEqual(ident["phase"], "orbitals", "the Coriolis signal needs its body")
        gate = next(site for site in state["sites"] if site["name"] == "Gate Hub")
        self.assertEqual((gate["buildType"], gate["status"], gate["bodyNum"]), ("no_truss?", "complete", -1))
        self.assertEqual(state["sites"].index(gate), 2, "new sites go in above the cut line")
        self.assertNotIn("K7Q-1HT", [site["name"] for site in state["sites"]], "carriers are not stations")
        identifier.on_destination(state, journal, {"System": 77, "Body": 9, "Name": "Gate Hub"})
        self.assertEqual(state["identify"]["pending"], gate["id"])
        identifier.on_destination(state, journal, {"System": 77, "Body": 1, "Name": "Nyx 1"})
        self.assertEqual(gate["bodyNum"], 1)
        self.assertEqual(identifier.step(state, journal)["phase"], "surface")
        identifier.on_destination(state, journal, {"System": 77, "Body": 2, "Name": "Hobbs Landing"})
        settlement = next(site for site in state["sites"] if site["name"] == "Hobbs Landing")
        self.assertEqual((settlement["bodyNum"], settlement["buildType"]), (2, "settlement?"))
        self.assertEqual(identifier.finish(state)["phase"], "done")
        self.assertIn(gate["id"], state["dirty"])

    def test_docking_identifies_outposts(self):
        state = self.state()
        state["sites"].append({"id": "o1", "name": "Vesta Post", "bodyNum": 1, "buildType": "outpost?", "status": "plan"})
        identifier.apply_docked(state, {"StationName": "Vesta Post", "MarketID": 42, "StationType": "Outpost",
                                        "LandingPads": {"Small": 4, "Medium": 1, "Large": 0}})
        site = state["sites"][-1]
        self.assertEqual((site["buildType"], site["marketId"], site["status"]), ("vesta", 42, "complete"))
        state["sites"].append({"id": "o2", "name": "Tech Post", "bodyNum": 1, "buildType": "", "status": "plan"})
        identifier.apply_docked(state, {"StationName": "Tech Post", "MarketID": 43, "StationType": "Outpost",
                                        "LandingPads": {"Small": 2, "Medium": 1}, "StationEconomy": "$economy_HighTech;",
                                        "StationEconomies": [{"Name": "$economy_HighTech;", "Proportion": 1.0}]})
        self.assertEqual(state["sites"][-1]["buildType"], "prometheus")


class ExtrasTests(unittest.TestCase):
    def deck(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project(), project("b2", buildName="Farm", architectName="Nyx Evera")],
                               carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {}}])
        deck.current_sys = "Nyx"
        return deck

    def test_market_finder(self):
        deck = self.deck()
        deck.raven.find_markets.return_value = {"preparedAt": "now", "markets": [
            {"stationName": "Galileo", "systemName": "Sol", "distance": 12, "distanceToArrival": 500, "padSize": "large",
             "supplies": {"liquidoxygen": 9000, "water": 10}},
            {"stationName": "Far Away", "systemName": "Sirius", "distance": 8, "distanceToArrival": 50, "padSize": "large",
             "supplies": {"water": 500}}]}
        deck._handle_colonisation_command("markets_find", {"build_id": "b1", "max_distance": "5000", "ship_size": "huge"})
        options = deck.raven.find_markets.call_args.args[0]
        self.assertEqual(options["commodities"], {"liquidoxygen": 600, "water": 150})
        self.assertEqual((options["maxDistance"], options["shipSize"], options["refSystem"]), (1000, "large", "Nyx"))
        markets = deck._colony_ui_state()["markets"]["markets"]
        self.assertEqual([row["station"] for row in markets], ["Galileo", "Far Away"], "most needs covered first")

    def test_project_actions(self):
        deck = self.deck()
        assigned = deck._colony_assignments("Nyx Evera")
        self.assertEqual({(row["build_id"], row["id"], row["need"]) for row in assigned},
                         {("b1", "liquidoxygen", 600), ("b2", "liquidoxygen", 600)})
        deck._handle_colonisation_command("project_delete", {"build_id": "b2"})
        deck.raven.delete_project.assert_not_called()
        deck._handle_colonisation_command("project_delete", {"build_id": "b2", "confirmed": True})
        deck.raven.delete_project.assert_called_once_with("b2")
        deck._handle_colonisation_command("project_ready", {"build_id": "b1", "commodity": "Water", "ready": True})
        deck.raven.set_ready.assert_called_once_with("b1", ["water"], True)
        deck.raven.project_stats.return_value = {"totalCargo": 120, "totalDeliveries": 3, "cmdrs": {"a": 20, "b": 100},
                                                 "stats": [{"time": "t", "countCargo": 120, "countDeliveries": 3}]}
        deck._handle_colonisation_command("project_stats", {"build_id": "b1"})
        stats = deck._colony_ui_state()["stats"]["b1"]
        self.assertEqual([row["name"] for row in stats["cmdrs"]], ["b", "a"])
        deck.raven.create_fc_loading_project.return_value = {"buildId": "fc1"}
        deck._handle_colonisation_command("project_fc_loading", {"name": "Stock up"})
        deck.raven.create_fc_loading_project.assert_called_once_with("Stock up")
        deck._handle_colonisation_command("save_details", {"build_id": "b1", "discord": "https://discord.com/x"})
        self.assertEqual(deck.raven.update_project.call_args.args[1], {"discordLink": "https://discord.com/x"})

    def test_carrier_actions(self):
        deck = self.deck()
        deck.raven.set_carrier_cargo.return_value = {"steel": 400}
        deck._handle_colonisation_command("carrier_cargo", {"market_id": "5500", "cargo": {"Steel": "400", "water": "-3"}})
        deck.raven.set_carrier_cargo.assert_called_once_with(5500, {"steel": 400, "water": 0})
        self.assertEqual(deck.colony.carriers["5500"]["cargo"], {"steel": 400})
        deck.raven.find_carriers.return_value = [{"market_id": 7, "name": "ABC-123"}]
        deck._handle_colonisation_command("carrier_search", {"name": "AB"})
        deck.raven.find_carriers.assert_not_called()
        deck._handle_colonisation_command("carrier_search", {"name": "ABC"})
        self.assertEqual(deck._colony_ui_state()["carrier_search"]["results"][0]["name"], "ABC-123")
        deck.raven.carrier.return_value = None
        deck._handle_colonisation_command("carrier_link_found", {"market_id": "7"})
        deck.raven.check_carrier.assert_called_once_with(7)
        deck.raven.link_carrier.assert_called_once_with("Nyx Evera", 7)

    def test_nexus_and_stats(self):
        deck = self.deck()
        deck.raven.create_nexus.return_value = {"id": "n1", "name": "Road", "owner": "Nyx Evera", "systems": [], "cmdrs": ["Nyx Evera"]}
        deck._handle_colonisation_command("nexus_create", {"name": "Road"})
        self.assertTrue(deck._html_colonisation_workspace()["nexus"]["mine"])
        deck.raven.update_nexus.return_value = {"id": "n1", "name": "Road", "owner": "Nyx Evera", "systems": [{"name": "Sol"}]}
        deck._handle_colonisation_command("nexus_set", {"field": "systems", "value": ["Sol", " ", "Nyx"]})
        deck.raven.update_nexus.assert_called_once_with("n1", "setSystems", ["Sol", "Nyx"])
        deck._handle_colonisation_command("nexus_set", {"field": "open", "value": False})
        self.assertEqual(deck.raven.update_nexus.call_args.args[1:], ("setPrivate", False))
        deck.raven.global_stats.return_value = {"topContributors7d": {"a": 5, "b": 9}, "topSystemScores": {"830": {"X": "y"}, "12": {"Z": "w"}}}
        deck._handle_colonisation_command("stats_load", {})
        stats = deck._colony_ui_state()["global_stats"]
        self.assertEqual([row["name"] for row in stats["contributors"]], ["b", "a"])
        self.assertEqual(stats["systems"][0], {"score": 830, "system": "X", "architect": "y"})


class ClientAndWiringTests(unittest.TestCase):
    def test_keyed_calls_name_the_commander(self):
        session = Mock()
        session.request.return_value = FakeResponse(body={})
        client = RavenColonialClient("secret", base_url="https://rc.test", session=session)
        client.set_commander("Nyx Evera")
        client.delete_project("b1")
        headers = session.request.call_args.kwargs["headers"]
        self.assertEqual(base64.b64decode(headers["rcc-cmdr0"]).decode(), "Nyx Evera")
        client.global_stats()
        self.assertNotIn("rcc-cmdr0", session.request.call_args.kwargs["headers"])
        with self.assertRaises(ValueError):
            client.update_nexus("n1", "setEverything", 1)

    def test_settings_hotkeys_and_overlay_options(self):
        for key in ("colony_inline_carriers", "colony_hide_other_overlays", "colony_planner_include_planned", "colony_planner_buff_nerf"):
            self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS)
        for key in ("overlay_hotkey_colony_refresh", "overlay_hotkey_colony_fold"):
            self.assertIn(key, config_module.PROFILE_TEXT_SETTINGS)
        actions = [row[0] for row in OVERLAY_HOTKEY_SPECS]
        self.assertIn("colony_refresh", actions)
        self.assertIn("colony_fold", actions)
        studio = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for key in ("colony_inline_carriers", "colony_hide_other_overlays"):
            self.assertIn(f'data-overlay-option="{key}"', studio)

    def test_fold_hotkey_and_inline_column(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project()], carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {"liquidoxygen": 600, "water": 150}}])
        deck.current_gui_focus = 1
        deck._colony_update_overlay()
        folded = deck.colony_needs_hud.update.call_args.args[0]
        self.assertTrue(folded["groups"][0]["collapsed"])
        deck._colony_toggle_fold()
        self.assertFalse(deck.colony_needs_hud.update.call_args.args[0]["groups"][0]["collapsed"])
        state = ColonyState(None)
        state.apply_sync(projects=[project()], carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {"water": 10}}])
        self.assertTrue(overlay_model(state, "Nyx Evera", current_address=12, options={"colony_inline_carriers": True})["columns"]["inline"])

    def test_hide_other_overlays_while_colonising(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
        from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {"colony_hide_other_overlays": True, "overlay_hide_on_maps": True}
        studio.current_gui_focus = 0
        studio._colony_overlay_showing = True
        self.addCleanup(HtmlOverlayServer.set_overrides, hidden=set())
        studio._apply_map_overlay_hiding()
        hidden = HtmlOverlayServer.overlays_hidden
        self.assertIn("survey", " ".join(hidden))
        self.assertNotIn("colony-needs", hidden)
        self.assertNotIn("navigation", hidden)
        studio._colony_overlay_showing = False
        studio._apply_map_overlay_hiding()
        self.assertEqual(HtmlOverlayServer.overlays_hidden, frozenset())


if __name__ == "__main__":
    unittest.main()
