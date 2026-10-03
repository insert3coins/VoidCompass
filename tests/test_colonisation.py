"""5.5.2 Colonisation: the catalogue, the Raven Colonial client, colony state,
the Construction Needs overlay model, journal sync (never during replay, never
without a key) and the Colonisation tab's snapshot and commands."""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.colonisation import catalogue
from voidcompass.colonisation.colony import ColonyState
from voidcompass.colonisation.views import overlay_model, project_rows
from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPEC_BY_ATTR
from voidcompass.dashboard.dashboard_colonisation_mixin import DashboardColonisationMixin
from voidcompass.dashboard.html_colonisation import HtmlColonisationMixin
from voidcompass.services.raven_colonial import RavenColonialClient, RavenError, _text_value

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SITE = "Orbital Construction Site: Nyx Gate"
DEPOT = {"event": "ColonisationConstructionDepot", "MarketID": 3900, "ConstructionProgress": 0.25,
         "ConstructionComplete": False, "ConstructionFailed": False,
         "ResourcesRequired": [
             {"Name": "$LiquidOxygen_Name;", "RequiredAmount": 1000, "ProvidedAmount": 400},
             {"Name": "$Steel_Name;", "RequiredAmount": 500, "ProvidedAmount": 500},
             {"Name": "$Water_Name;", "RequiredAmount": 200, "ProvidedAmount": 50},
         ]}
DOCKED_SITE = {"event": "Docked", "StationName": SITE, "StationType": "SpaceConstructionDepot", "MarketID": 3900,
               "SystemAddress": 77, "StarSystem": "Nyx", "StationServices": ["dock", "colonisationcontribution"],
               "StationFaction": {"Name": "Nyx Pioneers"}}
DOCKED_FC = {"event": "Docked", "StationName": "K7Q-1HT", "StationType": "FleetCarrier", "MarketID": 5500,
             "SystemAddress": 77, "StarSystem": "Nyx", "StationServices": ["dock", "carriermanagement"]}


def project(build_id="b1", **extra):
    row = {"buildId": build_id, "buildName": "Nyx Gate", "buildType": "dual_truss", "systemName": "Nyx",
           "systemAddress": 77, "marketId": 3900, "maxNeed": 1700,
           "commodities": {"liquidoxygen": 600, "water": 150, "steel": 0},
           "commanders": {"Nyx Evera": ["liquidoxygen"], "Payden": ["water"]},
           "linkedFC": [{"marketId": 5500, "name": "K7Q-1HT"}]}
    row.update(extra)
    return row


class CatalogueTests(unittest.TestCase):
    def test_commodity_ids_names_and_categories(self):
        self.assertEqual(catalogue.commodity_id("$LiquidOxygen_Name;"), "liquidoxygen")
        self.assertEqual(catalogue.commodity_id("LiquidOxygen"), "liquidoxygen")
        self.assertEqual(catalogue.commodity_name("liquidoxygen"), "Liquid oxygen")
        self.assertEqual(catalogue.commodity_category("steel"), "Metals")
        self.assertGreaterEqual(len(catalogue.commodities()), 50)
        self.assertGreaterEqual(len(catalogue.build_types()), 50)

    def test_build_types_and_sites(self):
        self.assertEqual(catalogue.build_type_for("Demeter")["buildType"], "demeter")
        self.assertIsNone(catalogue.build_type_for(""))
        self.assertEqual(catalogue.build_type_label("fc_loading"), "Fleet carrier loading")
        self.assertTrue(catalogue.is_construction_site(SITE, ["colonisationcontribution"]))
        self.assertFalse(catalogue.is_construction_site(SITE, ["dock"]), "a finished site keeps its name a while")
        self.assertFalse(catalogue.is_construction_site("Jameson Memorial", ["colonisationcontribution"]))
        self.assertTrue(catalogue.is_primary_port_site("System Colonisation Ship"))
        self.assertEqual(catalogue.default_project_name(SITE), "Nyx Gate")
        self.assertEqual(catalogue.default_project_name("System Colonisation Ship"), "Primary port")

    def test_depot_needs_and_cargo_match(self):
        needs = catalogue.depot_needs(DEPOT["ResourcesRequired"])
        self.assertEqual(needs, {"liquidoxygen": 600, "steel": 0, "water": 150})
        self.assertEqual(catalogue.depot_total(DEPOT["ResourcesRequired"]), 1700)
        demeter = catalogue.build_type_for("demeter")
        self.assertEqual(catalogue.match_by_cargo({key: value - 1 for key, value in demeter["cargo"].items()})["buildType"], "demeter")


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self.ok, self.reason = status, 200 <= status < 300, ""
        self.content = b"" if body is None else json.dumps(body).encode()
        self.text = self.content.decode()

    def json(self):
        return json.loads(self.text)


class ClientTests(unittest.TestCase):
    def client(self, *responses):
        session = Mock()
        session.request.side_effect = list(responses)
        return RavenColonialClient("secret", base_url="https://rc.test", session=session), session

    def test_keyed_calls_carry_the_key_and_reads_do_not(self):
        client, session = self.client(FakeResponse(body=[]), FakeResponse(body={"buildId": "b1"}))
        client.active_projects("Nyx Evera")
        client.contribute("b1", "Nyx Evera", {"steel": 4})
        first, second = session.request.call_args_list
        self.assertEqual(first.args[:2], ("GET", "https://rc.test/api/cmdr/Nyx%20Evera/active"))
        self.assertNotIn("rcc-key", first.kwargs["headers"])
        self.assertEqual(second.args[0], "POST")
        self.assertEqual(second.kwargs["headers"]["rcc-key"], "secret")
        self.assertEqual(second.kwargs["json"], {"steel": 4})
        self.assertTrue(first.kwargs["headers"]["User-Agent"].startswith("VoidCompass/"))

    def test_errors_and_key_checks(self):
        client, _session = self.client(FakeResponse(500, {"error": "boom"}), FakeResponse(401), FakeResponse(body={"displayName": "Nyx Evera"}))
        with self.assertRaises(RavenError):
            client.project("b1")
        self.assertIsNone(client.commander_for_key("wrong"))
        self.assertEqual(client.commander_for_key("right"), "Nyx Evera")
        self.assertIsNone(_text_value('""'))
        self.assertEqual(_text_value('"b1"'), "b1")


class ColonyStateTests(unittest.TestCase):
    def test_sync_needs_and_carriers(self):
        state = ColonyState(None)
        state.apply_sync(projects=[project(), project("b2", buildName="Nyx Farm", systemAddress=78, marketId=3901)],
                         primary="b2", hidden=["b1"],
                         carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {"LiquidOxygen": 300}}])
        self.assertEqual(state.primary_build_id, "b2")
        self.assertEqual([row["buildId"] for row in state.visible_projects()], ["b2"])
        self.assertEqual(state.project_at(77, 3900)["buildId"], "b1")
        self.assertEqual(state.carrier_cargo(), {"liquidoxygen": 300})
        needs = state.needs([project()], "nyx evera")
        self.assertEqual(needs["commodities"]["liquidoxygen"], 600)
        self.assertEqual((needs["assigned_me"], needs["assigned_others"]), ({"liquidoxygen"}, {"water"}))
        state.apply_sync(primary="missing")
        self.assertIsNone(state.primary_build_id, "a primary that is not one of our projects is dropped")
        self.assertTrue(state.apply_carrier_cargo(5500, {"steel": 9}))
        self.assertFalse(state.apply_carrier_cargo(1, {"steel": 9}))

    def test_saved_and_reloaded(self):
        import tempfile
        from voidcompass.core.persistence_queue import flush_persistence

        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = str(Path(folder.name) / "colony.json")
        state = ColonyState(path)
        state.apply_sync(projects=[project()], primary="b1", hidden=[], carriers=[])
        flush_persistence(path)
        again = ColonyState(path)
        self.assertEqual((again.primary_build_id, again.projects[0]["buildName"]), ("b1", "Nyx Gate"))


class OverlayModelTests(unittest.TestCase):
    def state(self):
        state = ColonyState(None)
        state.apply_sync(projects=[project()], carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {"liquidoxygen": 600, "water": 150}}])
        return state

    def test_away_names_the_system_unless_the_project_does(self):
        state = ColonyState(None)
        state.apply_sync(projects=[project(buildName="Pioneer Gate")])
        self.assertEqual(overlay_model(state, "Nyx Evera", current_address=12)["subheader"], "Nyx")
        self.assertEqual(overlay_model(state, "Nyx Evera", current_address=77)["subheader"], "")
        state.apply_sync(projects=[project()])
        self.assertEqual(overlay_model(state, "Nyx Evera", current_address=12)["subheader"], "", "Nyx Gate already says Nyx")

    def test_at_a_tracked_site(self):
        state = self.state()
        state.last_depot = DEPOT
        docked = {"station_name": SITE, "station_type": "SpaceConstructionDepot", "market_id": 3900,
                  "system_address": 77, "services": ["colonisationcontribution"]}
        model = overlay_model(state, "Nyx Evera", docked=docked, current_address=77,
                              ship_cargo=[{"Name": "water", "Count": 150}], capacity=400)
        self.assertTrue(model["at_site"])
        self.assertEqual(model["header"], "Nyx Gate · Coriolis Starport (Tier 2)")
        rows = {row["id"]: row for row in model["groups"][0]["rows"]}
        self.assertEqual(set(rows), {"liquidoxygen", "water"}, "covered needs are left out")
        self.assertEqual((rows["water"]["check"], rows["liquidoxygen"]["check"]), ("ship", "fc"))
        self.assertEqual(rows["water"]["fc"], 150)
        self.assertEqual((rows["liquidoxygen"]["assigned"], rows["water"]["assigned"]), ("me", "others"))
        self.assertEqual((model["remaining"], model["trips"]), (750, 2))
        self.assertEqual(model["carriers"]["deficit"], 0)

    def test_away_groups_by_category_and_folds_what_carriers_cover(self):
        model = overlay_model(self.state(), "Nyx Evera", current_address=12, capacity=0)
        groups = {group["name"]: group for group in model["groups"]}
        self.assertTrue(groups["Chemicals"]["collapsed"])
        self.assertFalse(groups["Chemicals"]["rows"])
        self.assertIsNone(model["trips"])
        self.assertIsNone(overlay_model(ColonyState(None), "Nyx Evera"), "nothing to show without projects")

    def test_an_untracked_site_and_a_finished_one(self):
        state = ColonyState(None)
        state.last_depot = DEPOT
        docked = {"station_name": SITE, "station_type": "", "market_id": 3900, "system_address": 77,
                  "services": ["colonisationcontribution"]}
        model = overlay_model(state, "Nyx Evera", docked=docked)
        self.assertEqual(model["warnings"], ["Untracked project"])
        self.assertEqual(model["remaining"], 750)
        state.last_depot = {**DEPOT, "ConstructionComplete": True}
        self.assertTrue(overlay_model(state, "Nyx Evera", docked=docked)["complete"])

    def test_project_rows(self):
        rows = project_rows(self.state(), capacity=100)
        self.assertEqual(rows[0]["remaining"], 750)
        self.assertEqual(rows[0]["trips"], 8)
        self.assertAlmostEqual(rows[0]["progress"], round(1 - 750 / 1700, 4))


class SyncWorker:
    def submit(self, call, on_done=None, on_error=None):
        try:
            result = call()
        except Exception as exc:
            on_error and on_error(exc)
        else:
            on_done and on_done(result)

    def shutdown(self):
        pass


class Deck(DashboardColonisationMixin, HtmlColonisationMixin):
    def __init__(self, key="secret", sync=True):
        self.config = {"raven_api_key": key, "raven_sync_enabled": sync}
        self.cmdr_name = "Nyx Evera"
        self.colony = ColonyState(None)
        self.raven = Mock(spec=RavenColonialClient)
        self.raven.active_projects.return_value = []
        self.raven.primary.return_value = ""
        self.raven.hidden_ids.return_value = []
        self.raven.commander_carriers.return_value = []
        self.raven_worker = SyncWorker()
        self.colony_needs_hud = Mock()
        self._colony_market = None
        self._colony_market_seen = False
        self._colony_docked = None
        self.current_gui_focus = 0
        self.current_cargo_inventory = []
        self.colonisation_projects = {}
        self._transient = {}
        self._schedule_html_dashboard_publish = Mock()

    def _ui_post(self, callback, *args, key=None):
        callback(*args)

    def _active_cargo_capacity(self):
        return 400

    def _html_profile_transient(self, key, default):
        return self._transient.setdefault(key, default)


class JournalSyncTests(unittest.TestCase):
    def play(self, deck, replay=False):
        deck.colony.apply_sync(projects=[project()], carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {}}])
        deck.raven.reset_mock()
        deck.raven.project.return_value = project(commodities={"liquidoxygen": 590, "water": 150})
        deck.raven.supply_carrier.return_value = {"steel": 20}
        for event in (DOCKED_SITE, DEPOT,
                      {"event": "ColonisationContribution", "MarketID": 3900,
                       "Contributions": [{"Name": "$LiquidOxygen_Name;", "Amount": 10}]},
                      {"event": "Undocked"}, DOCKED_FC,
                      {"event": "CargoTransfer", "Transfers": [{"Type": "steel", "Count": 20, "Direction": "tocarrier"}]}):
            deck._colony_observe(event["event"], event, startup_replay=replay)

    def test_nothing_is_sent_while_replaying(self):
        deck = Deck()
        self.play(deck, replay=True)
        self.assertEqual(deck.raven.method_calls, [])

    def test_nothing_is_sent_without_a_key_or_with_sync_off(self):
        for deck in (Deck(key=""), Deck(sync=False)):
            self.play(deck)
            self.assertEqual(deck.raven.method_calls, [])

    def test_live_play_publishes_deliveries_and_carrier_cargo(self):
        deck = Deck()
        self.play(deck)
        deck.raven.contribute.assert_called_once_with("b1", "Nyx Evera", {"liquidoxygen": 10})
        deck.raven.project.assert_called_with("b1")
        self.assertEqual(deck.colony.project("b1")["commodities"]["liquidoxygen"], 590)
        deck.raven.update_project.assert_any_call("b1", {"factionName": "Nyx Pioneers"})
        deck.raven.supply_carrier.assert_called_once_with(5500, {"steel": 20})
        self.assertEqual(deck.colony.carriers["5500"]["cargo"], {"steel": 20})
        self.assertEqual(deck.colony.pending, 0)

    def test_a_changed_depot_updates_the_project(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project(commodities={"liquidoxygen": 900})])
        deck._colony_observe("Docked", DOCKED_SITE)
        deck.raven.update_project.reset_mock()
        deck._colony_observe("ColonisationConstructionDepot", DEPOT)
        build_id, fields = deck.raven.update_project.call_args.args
        self.assertEqual(build_id, "b1")
        self.assertEqual(fields["commodities"], {"liquidoxygen": 600, "steel": 0, "water": 150})
        self.assertEqual(fields["maxNeed"], 1700)

    def test_failures_show_on_the_tab(self):
        deck = Deck()
        deck.raven.active_projects.side_effect = RavenError("HTTP 503: down")
        deck._colony_refresh()
        self.assertIn("HTTP 503", deck.colony.sync_error)
        self.assertEqual(deck.colony.pending, 0)

    def test_overlay_shows_at_the_site_and_hides_on_maps(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project()])
        deck._colony_observe("Docked", DOCKED_SITE, startup_replay=True)
        deck._colony_observe("ColonisationConstructionDepot", DEPOT, startup_replay=True)
        model = deck.colony_needs_hud.update.call_args.args[0]
        self.assertTrue(model["at_site"])
        deck.current_gui_focus = 6
        deck._colony_update_overlay()
        deck.colony_needs_hud.clear.assert_called()
        deck._colony_observe("Undocked", {"event": "Undocked"})
        deck.current_gui_focus = 1
        deck.colony_needs_hud.reset_mock()
        deck._colony_update_overlay()
        deck.colony_needs_hud.update.assert_called_once()
        deck.config["colony_show_on_right_panel"] = False
        deck._colony_update_overlay()
        deck.colony_needs_hud.clear.assert_called_once()


class WorkspaceTests(unittest.TestCase):
    def test_snapshot_is_complete_and_serialisable(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project()], primary="b1",
                               carriers=[{"marketId": 5500, "name": "K7Q-1HT", "displayName": "Nyx Haul", "cargo": {"liquidoxygen": 100}}])
        deck.current_cargo_inventory = [{"Name": "water", "Count": 40}]
        deck._colony_observe("Docked", DOCKED_SITE, startup_replay=True)
        deck._colony_observe("ColonisationConstructionDepot", DEPOT, startup_replay=True)
        data = deck._html_colonisation_workspace()
        json.dumps(data)
        self.assertTrue(data["raven"]["active"])
        self.assertEqual(data["selected"]["build_id"], "b1")
        self.assertTrue(data["selected"]["member"])
        rows = {row["id"]: row for group in data["selected"]["groups"] for row in group["rows"]}
        self.assertEqual((rows["liquidoxygen"]["fc"], rows["water"]["ship"]), (100, 40))
        self.assertTrue(rows["liquidoxygen"]["mine"])
        self.assertTrue(data["site"]["tracked"])
        self.assertTrue(data["site"]["depot_known"])
        self.assertEqual(data["carriers"][0]["cargo_total"], 100)

    def test_commands(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project()])
        deck.raven.set_hidden_ids.return_value = ["b1"]
        self.assertTrue(deck._handle_colonisation_command("toggle_visible", {"build_id": "b1"}))
        deck.raven.set_hidden_ids.assert_called_once_with("Nyx Evera", ["b1"])
        self.assertEqual(deck.colony.hidden_ids, ["b1"])
        deck.raven.complete_project.reset_mock()
        deck._handle_colonisation_command("complete", {"build_id": "b1"})
        deck.raven.complete_project.assert_not_called()
        deck._handle_colonisation_command("assign", {"build_id": "b1", "commodity": "$Water_Name;"})
        deck.raven.assign.assert_called_once_with("b1", "Nyx Evera", "water")

        local = Deck(key="")
        local.colony.apply_sync(projects=[project()])
        self.assertTrue(local._handle_colonisation_command("set_primary", {"build_id": "b1"}))
        self.assertIn("Settings > Integrations", local._colony_ui_state()["error"])
        self.assertEqual(local.raven.method_calls, [])

    def test_create_project_from_the_docked_site(self):
        deck = Deck()
        deck._colony_observe("Docked", DOCKED_SITE, startup_replay=True)
        deck._colony_observe("ColonisationConstructionDepot", DEPOT, startup_replay=True)
        deck.raven.create_project.return_value = {"buildId": "new", "buildName": "Nyx Gate"}
        deck._handle_colonisation_command("create_project", {"name": "Nyx Gate", "layout": "Demeter", "body_id": "-1"})
        sent = deck.raven.create_project.call_args.args[0]
        self.assertEqual((sent["buildType"], sent["marketId"], sent["systemAddress"]), ("demeter", 3900, 77))
        self.assertEqual(sent["commodities"]["liquidoxygen"], 600)
        self.assertEqual(sent["commanders"], {"Nyx Evera": []})
        self.assertEqual(deck._colony_ui_state()["selected"], "new")

    def test_system_sites_round_trip(self):
        deck = Deck()
        deck.raven.system.return_value = {"name": "Nyx", "architect": "Nyx Evera", "bodies": [{"num": 3, "name": "Nyx 3"}],
                                          "sites": [{"id": "s1", "name": "Gate", "bodyNum": 3, "buildType": "demeter", "status": "plan"}]}
        deck._handle_colonisation_command("architect_load", {"system": "Nyx"})
        model = deck._colony_ui_state()["architect"]
        self.assertEqual(model["sites"][0]["body"], "Nyx 3")
        deck.raven.update_system.return_value = deck.raven.system.return_value
        deck._handle_colonisation_command("architect_save", {
            "architect": "Nyx Evera", "reserve": "major", "open": True, "delete": ["s0"],
            "sites": [{"id": "s1", "name": "Gate", "body_num": "3", "build_type": "Demeter", "status": "build"},
                      {"id": "", "name": "", "status": "plan"}]})
        system, put = deck.raven.update_system.call_args.args
        self.assertEqual(system, "Nyx")
        self.assertEqual(put["update"], [{"id": "s1", "name": "Gate", "bodyNum": 3, "buildType": "demeter", "status": "build"}])
        self.assertEqual((put["delete"], put["reserveLevel"], put["open"]), (["s0"], "major", True))


class WiringTests(unittest.TestCase):
    def test_registered_profile_aware_and_themed(self):
        spec = OVERLAY_SPEC_BY_ATTR["colony_needs_hud"]
        self.assertEqual((spec.overlay_id, spec.hotkey_action), ("colony-needs", "colony_needs"))
        self.assertIn("colony_needs", [row[0] for row in OVERLAY_HOTKEY_SPECS])
        for key in ("colony_needs_overlay_enabled", "raven_sync_enabled", "raven_share_ship_cargo", "colony_show_carriers",
                    "colony_carrier_delta", "colony_collapse_covered", "colony_highlight_almost", "colony_show_on_right_panel"):
            self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS)
        for key in ("raven_api_key", "overlay_hotkey_colony_needs"):
            self.assertIn(key, config_module.PROFILE_TEXT_SETTINGS)
        for key in ("colony_needs_hud_x", "colony_needs_hud_y"):
            self.assertIn(key, config_module.PROFILE_VALUE_SETTINGS)
        self.assertIn("'colony_needs_hud'", (ROOT / "src/voidcompass/core/theme_state.py").read_text(encoding="utf-8"))
        deck = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="colonisation"', deck)
        self.assertIn('data-studio-settings="colony_needs_hud"', deck)
        self.assertIn('href="colonisation.css"', deck)
        css = (WEB / "colony_needs" / "styles.css").read_text(encoding="utf-8")
        self.assertNotRegex("\n".join(css.split("}", 1)[1:]), r"#[0-9a-fA-F]{6}")
        self.assertNotIn("<style", (WEB / "colony_needs" / "index.html").read_text(encoding="utf-8"))
        self.assertNotRegex((WEB / "dashboard" / "colonisation.css").read_text(encoding="utf-8"), r"#[0-9a-fA-F]{3,6}\b")

    def test_studio_options_refresh_the_overlay(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {}
        for name in ("_persist_config", "_schedule_html_dashboard_publish", "_colony_update_overlay"):
            setattr(studio, name, Mock())
        self.assertTrue(studio._html_overlay_option_toggle("colony_carrier_delta", True))
        self.assertTrue(studio.config["colony_carrier_delta"])
        studio._colony_update_overlay.assert_called_once()

    def test_raven_settings_are_saved_from_integrations(self):
        source = (ROOT / "src/voidcompass/dashboard/html_dashboard.py").read_text(encoding="utf-8")
        for key in ("raven_api_key", "raven_sync_enabled", "raven_share_ship_cargo"):
            self.assertIn(f'"{key}"', source)
        script = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('settingGroup("RAVEN COLONIAL"', script)
        self.assertIn('data-ws-op="test_raven"', script)


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open(self, url, width=420):
        page = self.browser.new_page(viewport={"width": width, "height": 600})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8")
                              + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: o => {"
                              " window.__render = o.render; window.__height = o.contentHeight; }};")
            elif path.name == "blank.html":
                route.fulfill(content_type="text/html", body="<!doctype html><div id='colonisation-workspace'></div>")
            elif path.is_file():
                route.fulfill(path=str(path), content_type="application/javascript" if path.suffix == ".js" else None)
            else:
                route.fulfill(status=404, body="")

        page.route("http://colony.test/**", serve)
        page.goto(url)
        return page

    def test_overlay_renders_the_needs(self):
        page = self.open("http://colony.test/colony_needs/index.html")
        page.wait_for_selector("#needs", state="attached")
        state = ColonyState(None)
        state.apply_sync(projects=[project()], carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {"liquidoxygen": 100}}])
        model = overlay_model(state, "Nyx Evera", current_address=12, ship_cargo=[{"Name": "water", "Count": 20}], capacity=400)
        page.evaluate("m => __render({needs: m, theme: {}, effects: {reduced_motion: true}})", model)
        self.assertEqual(page.locator("#needs-title").inner_text(), "NYX GATE · CORIOLIS STARPORT (TIER 2)")
        self.assertEqual(page.locator(".need-row").count(), 2)
        self.assertIn("750 REMAINING", page.locator("#needs-footer").inner_text())
        self.assertIn("1 FC", page.locator("#head-fc").inner_text())
        self.assertGreater(page.evaluate("__height()"), 80)
        page.evaluate("() => __render({needs: null, theme: {}, effects: {}})")
        self.assertIn("empty", page.locator("#needs").get_attribute("class"))

    def test_tab_renders_every_view(self):
        deck = Deck()
        deck.colony.apply_sync(projects=[project()], primary="b1",
                               carriers=[{"marketId": 5500, "name": "K7Q-1HT", "cargo": {"liquidoxygen": 100}}])
        deck.colonisation_projects = {3900: {"site_name": "Nyx Gate", "system_name": "Nyx", "progress": 0.25,
                                             "resources": [{"name": "Steel", "required": 500, "provided": 100}],
                                             "activity": [{"type": "Delivery", "detail": "Steel x10"}]}}
        deck._colony_observe("Docked", DOCKED_SITE, startup_replay=True)
        deck._colony_observe("ColonisationConstructionDepot", DEPOT, startup_replay=True)
        deck._colony_ui_state()["architect"] = deck._colony_architect_model(
            {"name": "Nyx", "bodies": [{"num": 3, "name": "Nyx 3"}],
             "sites": [{"id": "s1", "name": "Gate", "bodyNum": 3, "buildType": "demeter", "status": "plan"}]}, "Nyx")
        data = json.loads(json.dumps(deck._html_colonisation_workspace()))
        page = self.open("http://colony.test/blank.html")
        result = page.evaluate("""async (data) => {
          const m = await import('/dashboard/colonisation.js');
          const sent = [];
          const ui = {byId: (id) => document.getElementById(id), command: (...args) => { sent.push(args[1]); },
                      escapeHtml: (v) => String(v ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)};
          const root = document.getElementById('colonisation-workspace');
          const out = {};
          const draw = () => m.renderColonisation(data, ui);
          draw();
          for (const view of ['projects', 'site', 'carriers', 'architect', 'journal']) {
            const tab = root.querySelector(`[data-co-view="${view}"]`);
            m.handleColonisationClick({target: tab, preventDefault() {}}, ui, draw);
            out[view] = {text: root.innerText, wide: document.documentElement.scrollWidth > innerWidth + 1};
          }
          m.handleColonisationClick({target: root.querySelector('[data-co-view="architect"]'), preventDefault() {}}, ui, draw);
          m.handleColonisationClick({target: root.querySelector('[data-co-add-site]'), preventDefault() {}}, ui, draw);
          out.siteRows = root.querySelectorAll('.co-sites tbody tr[data-index]').length;
          out.selectedType = root.querySelector('.co-sites [data-co-site="build_type"]').value;
          m.handleColonisationClick({target: root.querySelector('[data-co-view="projects"]'), preventDefault() {}}, ui, draw);
          m.handleColonisationClick({target: root.querySelector('[data-co-op="assign"], [data-co-op="unassign"]'), preventDefault() {}}, ui, draw);
          out.sent = sent;
          return out;
        }""", data)
        self.assertIn("RAVEN COLONIAL · NYX EVERA", result["projects"]["text"])
        self.assertIn("Liquid oxygen", result["projects"]["text"])
        self.assertIn("Tracked", result["site"]["text"])
        self.assertIn("K7Q-1HT", result["carriers"]["text"])
        self.assertIn("SAVE TO RAVEN", result["architect"]["text"])
        self.assertIn("Nyx Gate", result["journal"]["text"])
        self.assertEqual(result["siteRows"], 2)
        self.assertEqual(result["selectedType"], "demeter")
        self.assertEqual(result["sent"][-1]["operation"], "unassign")
        self.assertEqual(result["sent"][-1]["commodity"], "liquidoxygen")


if __name__ == "__main__":
    unittest.main()
