"""5.5.12: the Mining page, rebuilt for asteroid and Rhino mining: the record
read from the journals, what mined cargo has sold for, Rhino ground from
Spansh, and the page itself."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from voidcompass.dashboard.html_mining import HtmlMiningMixin, material_grounds, mining_prices
from voidcompass.mining.mining_data import GROUND_SPANSH, search_spansh_grounds
from voidcompass.mining.mining_record import MiningRecord, material_name, read_journal

ROOT = Path(__file__).resolve().parents[1]


def line(when, event, **fields):
    return json.dumps({"timestamp": f"2026-09-0{when[0]}T{when[1:]}Z", "event": event, **fields})


SESSION = [
    line("110:00:00", "Commander", Name="Tester", FID="F1"),
    line("110:00:01", "Location", StarSystem="Ba Po", Body="Ba Po C 3"),
    # In the ship, in a ring: a tonne a refine.
    line("110:01:00", "SupercruiseExit", StarSystem="Ba Po", Body="Ba Po 1 A Ring"),
    line("110:02:00", "LaunchDrone", Type="Prospector"),
    line("110:02:10", "ProspectedAsteroid", Materials=[{"Name": "Platinum", "Proportion": 31.5}, {"Name": "palladium", "Proportion": 12.0}],
         Content="$AsteroidMaterialContent_High;", Content_Localised="Material Content: High", Remaining=100.0),
    line("110:02:20", "ProspectedAsteroid", Materials=[{"Name": "Platinum", "Proportion": 40.25}], MotherlodeMaterial="Painite",
         Content_Localised="Material Content: Low", Remaining=100.0),
    line("110:03:00", "MiningRefined", Type="$platinum_name;", Type_Localised="Platinum"),
    line("110:03:10", "MiningRefined", Type="$platinum_name;", Type_Localised="Platinum"),
    line("110:03:20", "AsteroidCracked", Body="Ba Po 1 A Ring"),
    line("110:04:00", "LaunchDrone", Type="Collection"),
    # Out in the Rhino on Ba Po C 3: tonnes from the hold climbing.
    line("110:10:00", "Touchdown", Body="Ba Po C 3", PlayerControlled=True),
    line("110:11:00", "LaunchSRV", SRVType="mev_rhino", SRVType_Localised="SRV Rhino"),
    line("110:11:01", "Cargo", Vessel="SRV", Count=0),
    line("110:12:00", "MiningRefined", Type="$platinum_name;", Type_Localised="Platinum"),
    line("110:12:01", "MiningRefined", Type="$platinum_name;", Type_Localised="Platinum"),
    line("110:12:02", "Cargo", Vessel="SRV", Count=4),
    line("110:13:00", "MiningRefined", Type="$rhodplumsite_name;", Type_Localised="Rhodplumsite"),
    line("110:13:01", "Cargo", Vessel="SRV", Count=6),
    line("110:13:02", "Cargo", Vessel="SRV", Count=5),        # a wobble, not new cargo
    line("110:13:03", "Cargo", Vessel="SRV", Count=8),
    line("110:14:00", "CargoTransfer", Transfers=[{"Type": "platinum", "Count": 8, "Direction": "toship"}]),
    line("110:14:01", "Cargo", Vessel="SRV", Count=0),
    line("110:15:00", "MiningRefined", Type="$platinum_name;", Type_Localised="Platinum"),
    line("110:15:01", "Cargo", Vessel="SRV", Count=3),
    line("110:16:00", "DockSRV", SRVType="mev_rhino"),
    line("110:17:00", "SAASignalsFound", BodyName="Ba Po 1 A Ring", Signals=[{"Type": "Platinum", "Count": 2}]),
]


def journals(test, files):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    for name, lines in files.items():
        (Path(folder.name) / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder.name


class RecordTests(unittest.TestCase):
    def test_ship_and_rhino_counted_their_own_ways(self):
        path = journals(self, {"Journal.2026-09-01T100000.01.log": SESSION})
        summary = MiningRecord().summary(path)
        self.assertEqual(summary["ship_t"], 2, "a tonne for each refine in the ship")
        self.assertEqual(summary["rhino_t"], 11, "4 + 2 + 2 (not the wobble) + 3 after unloading")
        self.assertEqual(summary["deployments"], 1)
        self.assertEqual(summary["pulses"], 4)
        materials = {row["name"]: row for row in summary["materials"]}
        self.assertEqual(materials["Platinum"]["ship"], 2)
        # The Rhino's 11 t shared by pulses: 3 of 4 platinum, 1 rhodplumsite.
        self.assertEqual((materials["Platinum"]["rhino"], materials["Rhodplumsite"]["rhino"]), (8, 3))

    def test_rocks_limpets_and_scans(self):
        path = journals(self, {"Journal.2026-09-01T100000.01.log": SESSION})
        summary = MiningRecord().summary(path)
        self.assertEqual(summary["prospected"], 2)
        self.assertEqual(summary["content"], {"High": 1, "Low": 1})
        self.assertEqual(summary["best"][0], {"name": "Platinum", "percent": 40.2})
        self.assertIn({"name": "Palladium", "percent": 12.0}, summary["best"], "a lower-case journal name is tidied")
        self.assertEqual(summary["motherlodes"], [{"name": "Painite", "count": 1}])
        self.assertEqual(summary["cracked"], 1)
        self.assertEqual(summary["limpets"], {"Prospector": 1, "Collection": 1})
        self.assertEqual(summary["rings_scanned"], 1)
        self.assertEqual(summary["days"], 1)

    def test_where_and_when(self):
        path = journals(self, {"Journal.2026-09-01T100000.01.log": SESSION})
        summary = MiningRecord().summary(path)
        places = {(row["mode"], row["body"]): row["tonnes"] for row in summary["places"]}
        self.assertEqual(places, {("ship", "Ba Po 1 A Ring"): 2, ("rhino", "Ba Po C 3"): 11})
        self.assertEqual(summary["months"], [{"month": "2026-09", "ship": 2, "rhino": 11}])

    def test_only_this_commander(self):
        other = [line("209:00:00", "Commander", Name="Someone", FID="F9"),
                 line("209:01:00", "MiningRefined", Type="$gold_name;", Type_Localised="Gold")]
        path = journals(self, {"Journal.2026-09-01T100000.01.log": SESSION, "Journal.2026-09-02T090000.01.log": other})
        self.assertEqual(MiningRecord().summary(path, "Tester", "F1")["ship_t"], 2)
        self.assertEqual(MiningRecord().summary(path)["ship_t"], 3)

    def test_each_file_read_once(self):
        path = journals(self, {"Journal.2026-09-01T100000.01.log": SESSION})
        record = MiningRecord()
        record.summary(path)
        with patch("voidcompass.mining.mining_record.read_journal") as again:
            record.summary(path)
        again.assert_not_called()

    def test_a_lost_rhino_still_counts(self):
        lines = SESSION[:16] + [line("110:30:00", "SRVDestroyed", ID=7)]
        summary = read_journal(journals(self, {"Journal.2026-09-01T100000.01.log": lines}) + "/Journal.2026-09-01T100000.01.log")
        self.assertEqual(round(sum(summary["rhino"].values())), 4)

    def test_material_names(self):
        self.assertEqual(material_name("opal"), "Void Opals")
        self.assertEqual(material_name("lowtemperaturediamond"), "Low Temperature Diamonds")
        self.assertEqual(material_name("periclasedunite"), "Periclase Dunite")
        self.assertEqual(material_name("$x;", "Rhodplumsite"), "Rhodplumsite")


class PriceTests(unittest.TestCase):
    def test_what_mined_cargo_fetched(self):
        trades = [
            {"ts": 1789000000, "commodity": "platinum", "count": 100, "price": 200_000, "total": 20_000_000},
            {"ts": 1790000000, "commodity": "platinum", "count": 50, "price": 260_000, "total": 13_000_000},
            {"ts": 1791500000, "commodity": "periclasedunite", "name": "Periclase Dunite", "count": 10, "price": 1_000_000, "total": 10_000_000},
            {"ts": 1790600000, "commodity": "hnshockmount", "count": 3, "price": 5000, "total": 15000},
        ]
        out = mining_prices(trades)
        platinum = out["prices"]["Platinum"]
        self.assertEqual((platinum["sold_t"], platinum["avg"], platinum["best"], platinum["last"]), (150, 220_000, 260_000, 260_000))
        self.assertIn("Periclase Dunite", out["prices"])
        self.assertNotIn("Hnshockmount", out["prices"], "salvage isn't mining")
        self.assertEqual(out["total"], 43_000_000)
        self.assertEqual([row["month"] for row in out["months"]], ["2026-09", "2026-10"])


class GroundTests(unittest.TestCase):
    def test_where_a_material_turns_up(self):
        grounds = material_grounds()["Platinum"]
        self.assertEqual(grounds, sorted(grounds, key=lambda row: (-row["pct"], -row["median"])))
        self.assertTrue(all(row["searchable"] == (row["ground"] in GROUND_SPANSH) for row in grounds))

    def test_spansh_is_asked_for_landable_planets_of_that_ground(self):
        reply = Mock()
        reply.json.return_value = {"results": [{"system_name": "Wolf 562", "name": "Wolf 562 B 4", "volcanism_type": "Major Metallic Magma",
                                                "gravity": 1.2, "distance": 9.8, "distance_to_arrival": 88, "id64": 123}]}
        with patch("voidcompass.mining.mining_data.requests.post", return_value=reply) as post:
            rows = search_spansh_grounds("Sol", "rock 80%+ [metallic magma]", 150, max_gravity=1.5, max_ls=5000)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["reference_system"], "Sol")
        self.assertEqual(payload["filters"]["subtype"], {"value": ["Rocky body"]})
        self.assertIn("Major Metallic Magma", payload["filters"]["volcanism_type"]["value"])
        self.assertEqual(payload["filters"]["is_landable"], {"value": True})
        self.assertEqual(payload["filters"]["gravity"], {"min": 0, "max": 1.5})
        self.assertEqual(payload["filters"]["distance"], {"min": 0, "max": 150.0})
        self.assertEqual(rows[0]["body_name"], "Wolf 562 B 4")
        with self.assertRaises(ValueError):
            search_spansh_grounds("Sol", "gas giant")


class Deck(HtmlMiningMixin):
    def __init__(self, **state):
        self.config = {"active_commander_name": "Tester"}
        self.published = 0
        self.__dict__.update(state)

    def _html_profile_transient(self, attribute, defaults):
        state = getattr(self, attribute, None)
        if not isinstance(state, dict):
            state = {"profile": "p", **defaults}
            setattr(self, attribute, state)
        return state

    def _schedule_html_dashboard_publish(self, immediate=False):
        self.published += 1


class PageDataTests(unittest.TestCase):
    def test_what_you_are_doing(self):
        self.assertEqual(Deck(current_in_srv=True, _rig_in_rhino=lambda: True)._mining_where()["mode"], "rhino")
        field = Deck(current_asteroid_field_kind="ring", current_local_space_name="Ba Po 1 A Ring")._mining_where()
        self.assertEqual((field["mode"], field["field_name"]), ("field", "Ba Po 1 A Ring"))
        docked = Deck(current_docked=True, current_station_name="Jameson Memorial")._mining_where()
        self.assertEqual((docked["mode"], docked["station"]), ("docked", "Jameson Memorial"))
        self.assertEqual(Deck()._mining_where()["mode"], "flight")

    def test_the_haul_and_its_worth(self):
        deck = Deck(current_cargo_vessel="SRV", current_cargo_inventory=[{"Name": "rhodplumsite", "Count": 12}],
                    _cargo_inventory_by_hold={"Ship": [{"Name": "platinum", "Count": 100}, {"Name": "drones", "Count": 40},
                                                       {"Name": "hnshockmount", "Count": 2}]})
        haul, limpets = deck._mining_haul({"Platinum": {"avg": 200_000}})
        self.assertEqual(limpets, 40)
        rows = {row["name"]: row for row in haul}
        self.assertEqual((rows["Platinum"]["ship"], rows["Platinum"]["value"], rows["Platinum"]["source"]), (100, 20_000_000, "yours"))
        self.assertEqual((rows["Rhodplumsite"]["rhino"], rows["Rhodplumsite"]["source"]), (12, "typical"), "the sheet's usual price")
        self.assertFalse(rows["Hnshockmount"]["mined"])
        self.assertEqual(haul[-1]["name"], "Hnshockmount", "what wasn't mined goes last")

    def test_the_page_operations(self):
        deck = Deck(_rig_clear_here=lambda: True)
        self.assertTrue(deck._html_mining_operation("forget_rigs", {}))
        self.assertIsNone(deck._html_mining_operation("save_plan", {}), "the run's own operations pass through")
        self.assertFalse(deck._html_mining_operation("ground_search", {"reference": "Sol", "ground": "lava"}))
        self.assertFalse(deck._html_mining_operation("ground_copy", {"result_index": 3}))

    def test_done_with_a_search(self):
        deck = Deck()
        deck._html_profile_transient("_html_mining_tool_state", {}).update(ring_generation=1, ring_status="ready",
                                                                           ring_detail="Found 2", ring_results=[{"system": "A"}])
        deck._html_profile_transient("_html_mining_ground", {}).update(generation=1, status="working", detail="Looking",
                                                                       results=[{"system": "B"}], ground="icy")
        deck._html_profile_transient("_html_mining_sell", {}).update(generation=1, commodity="Platinum", results=[{"x": 1}], nearest=[{"x": 2}])
        for operation in ("ring_clear", "ground_clear", "sell_clear"):
            self.assertTrue(deck._html_mining_operation(operation, {}))
        rings, ground, sell = deck._html_mining_tool_state, deck._html_mining_ground, deck._html_mining_sell
        self.assertEqual((rings["ring_results"], rings["ring_detail"]), ([], ""))
        self.assertEqual((ground["results"], ground["status"], ground["detail"]), ([], "ready", ""))
        self.assertEqual((sell["commodity"], sell["results"], sell["nearest"]), ("", [], []))
        self.assertTrue(all(state.get("generation", state.get("ring_generation")) != 1 for state in (rings, ground, sell)),
                        "a search still running is dropped when it answers")

    def test_the_record_is_read_in_the_background(self):
        deck = Deck(_ui_post=lambda fn, key=None: fn())
        deck.config["journal_path"] = journals(self, {"Journal.2026-09-01T100000.01.log": SESSION})
        first = deck._mining_record_view()
        self.assertIn(first["status"], ("reading", "ready"))
        for _ in range(100):
            if deck._html_mining_record["status"] == "ready":
                break
            time.sleep(.05)
        view = deck._mining_record_view()
        self.assertEqual(view["summary"]["rhino_t"], 11)

    def test_in_the_local_api(self):
        from voidcompass.services.local_api import PROVIDER_CALLS
        self.assertIn("api_mining_record", PROVIDER_CALLS)
        self.assertIn("`/api/v1/mining/record`", (ROOT / "api.md").read_text(encoding="utf-8"))


class WiringTests(unittest.TestCase):
    def test_the_deck_uses_the_new_page(self):
        app = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('from "./mining.js"', app)
        self.assertIn("renderMining(data, WORKSHOP_UI)", app)
        self.assertNotIn("RUN DIRECTIVE", app, "the old page is gone")
        self.assertIn('href="mining.css"', (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8"))
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn("**self._mining_extras()", source)
        self.assertIn("self._html_mining_operation(operation, payload)", source)


def sample():
    record = {"first": 1779154700, "last": 1792274739, "days": 40, "ship_t": 12026, "rhino_t": 4568, "pulses": 5325, "deployments": 33,
              "materials": [{"name": "Platinum", "ship": 10994, "rhino": 2649}, {"name": "Rhodplumsite", "ship": 0, "rhino": 683}],
              "months": [{"month": "2026-05", "ship": 1111, "rhino": 0}, {"month": "2026-09", "ship": 661, "rhino": 4079}],
              "places": [{"mode": "rhino", "system": "Ba Po", "body": "Ba Po C 3", "tonnes": 2688, "last": 1789779937}],
              "prospected": 811, "content": {"High": 97, "Medium": 288, "Low": 426}, "best": [{"name": "Platinum", "percent": 66.7}],
              "motherlodes": [{"name": "Platinum", "count": 4}], "cracked": 4, "limpets": {"Prospector": 862}, "rings_scanned": 158}
    return {
        "active": True, "system": "Ba Po", "plan": {"target": "Platinum", "minimum": 25, "cargo_goal": 0, "method": "laser"},
        "readiness": {"ship": "Type-9 Heavy", "cargo_capacity": 256, "equipment": {"refinery": True, "laser": False}, "missing": ["Mining laser"]},
        "session": {"mode": "asteroid", "duration": 600, "prospected": 3, "refined_t": 20, "tons_per_hour": 90, "hit_rate": 66,
                    "current": {"decision": "MINE", "target": "Platinum", "target_percent": 33, "content": "Material Content: High",
                                "remaining": 100, "materials": [{"name": "Platinum", "percent": 33}]},
                    "prospects": [{"decision": "MINE", "target_percent": 33, "refined": 8}, {"decision": "SKIP", "target_percent": 0}],
                    "yield": [{"name": "Platinum", "count": 20}]},
        "history": [{"started": 1790000000000, "system": "Vetta", "refined": 212, "duration": 7200, "tons_per_hour": 106}],
        "ring_scans": [{"system": "Ba Po", "body": "Ba Po 1 A Ring", "signals": [{"name": "Platinum", "count": 2}]}],
        "surface_scans": [], "bookmarks": [{"id": 3, "system": "Ba Po", "body": "Ba Po 1 A Ring", "material": "Platinum"}], "missions": [],
        "tools": {"ring_results": [{"system": "Ba Po", "body": "Ba Po 1 A Ring", "material": "Platinum", "hotspots": 2, "distance": 0}]},
        "where": {"system": "Ba Po", "body": "Ba Po C 3", "mode": "rhino"},
        "holds": [{"name": "RHINO", "used": 52, "capacity": 72, "free": 20}, {"name": "SHIP", "used": 256, "capacity": 256, "free": 0}],
        "limpets": 40, "haul": [{"name": "Platinum", "ship": 100, "rhino": 0, "mined": True, "each": 200000, "source": "yours", "value": 2e7}],
        "income": {"total": 2.7e9, "months": [{"month": "2026-05", "credits": 1e8}, {"month": "2026-09", "credits": 2.2e9}],
                   "prices": [{"name": "Platinum", "sold_t": 11250, "credits": 2.5e9, "avg": 224000, "best": 333000, "last": 55000, "last_at": 1790000000}]},
        "record": {"status": "ready", "summary": record, "at": 1790000000},
        "rigs": {"body": "Ba Po C 3", "rigs": [{"slot": 1, "distance_m": 1500, "relative": 90, "age_s": 600}, {"slot": 2, "distance_m": 10, "here": True, "age_s": 60}],
                 "collect_order": [2, 1], "elsewhere": []},
        "ground": {"ground_label": "Metal-Rich World", "gravity": 0.3, "ground_sample": 114,
                   "expected_materials": [{"material": "Platinum", "pct": 46.5, "median": 58337}]},
        "sites": [{"name": "Site 3", "materials": ["Platinum"], "estimate": "Estimated 900 t left"}],
        "material_grounds": {"Platinum": [{"ground": "metal-rich", "label": "Metal-Rich World", "pct": 46.5, "median": 58337, "searchable": True}]},
        "grounds": [{"key": "metal-rich", "label": "Metal-Rich World"}], "ring_materials": ["Platinum"], "surface_materials": ["Platinum"],
        "finder": {"results": [{"system": "Wolf 562", "body": "Wolf 562 B 4", "gravity": 1.2, "distance": 9.8}]},
        "sell": {"commodity": "Platinum", "radius": 50, "results": [{"station": "Jameson Memorial", "system": "Shinrarta Dezhra", "price": 281044, "stock": 4000}]},
        "sell_radius": 50,
    }


class PageRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        from tests.test_dashboard_overview_visuals import overview_state
        cls.overview = overview_state()
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.errors, self.sent = [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        web = ROOT / "web"
        harness = """
          window.__mining = (data) => { document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.dataset.pageName === 'mining'));
            currentPage = 'mining'; model.workspace = {page: 'mining', ready: true, data}; workspaceFingerprints.mining = ''; renderWorkspace(model); };
          window.__render = (data) => { model = data; applyTheme(data.theme || {}); document.body.classList.add('ready');
            document.getElementById('boot').hidden = true; renderDashboard(data); };"""

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                return route.fulfill(content_type="application/json", body='{"closing":true}')
            if path == "/api/command":
                self.sent.append(json.loads(route.request.post_data or "{}"))
                return route.fulfill(content_type="application/json", body='{"accepted":true}')
            if path == "/api/snapshot":
                return route.fulfill(content_type="application/json", body=json.dumps(self.overview))
            file = web / path.lstrip("/")
            if path == "/dashboard/app.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + harness)
            if file.is_file():
                return route.fulfill(path=str(file))
            route.fulfill(status=404, body="")

        self.page.route("http://mining.test/**", serve)
        self.page.goto("http://mining.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__mining)")
        self.page.evaluate("data => window.__render(data)", self.overview)

    def tearDown(self):
        self.page.close()

    def fits(self):
        return self.page.evaluate("() => { const p = document.querySelector('.page[data-page-name=\"mining\"]'); return p.scrollWidth <= p.clientWidth + 1; }")

    def test_every_tab_in_both_kinds_of_mining(self):
        rhino = sample()
        ring = {**sample(), "where": {"system": "Ba Po", "mode": "field", "field": "ring", "field_name": "Ba Po 1 A Ring"}}
        for width in (1400, 980):
            self.page.set_viewport_size({"width": width, "height": 900})
            for name, data in (("rhino", rhino), ("ring", ring)):
                self.page.evaluate("data => window.__mining(data)", data)
                for tab in ("live", "find", "sell", "record"):
                    with self.subTest(width=width, mode=name, tab=tab):
                        self.page.click(f'[data-mine-op="view"][data-view="{tab}"]')
                        self.assertTrue(self.fits())
                        self.assertTrue(self.page.locator("#mining-workspace .mn-panel").count())
        self.page.click('[data-mine-op="view"][data-view="live"]')
        self.page.evaluate("data => window.__mining(data)", rhino)
        self.assertIn("RIGS ON BA PO C 3", self.page.inner_text("#mining-workspace"))
        self.page.evaluate("data => window.__mining(data)", ring)
        self.assertIn("THIS ROCK", self.page.inner_text("#mining-workspace"))
        self.assertFalse(self.errors, self.errors)

    def test_live_data_never_pulls_a_dropdown_out_from_under_you(self):
        data = sample()
        data["session"]["started"] = 1_790_000_000_000
        self.page.evaluate("data => window.__mining(data)", data)
        self.page.click('[data-mine-op="view"][data-view="find"]')
        self.page.focus('[data-mine-form="ground"] select[name="material"]')
        self.page.evaluate("() => { window.__picked = document.querySelector('[data-mine-form=\"ground\"] select[name=\"material\"]'); }")
        moved = json.loads(json.dumps(data))
        moved["rigs"]["rigs"][0]["distance_m"] = 1400       # the Rhino drove on
        moved["holds"][0]["used"] = 53
        self.page.evaluate("data => window.__mining(data)", moved)
        self.assertTrue(self.page.evaluate("() => window.__picked.isConnected"), "the open box was redrawn away")
        self.assertFalse(self.page.evaluate(
            "() => Boolean(document.querySelector('#mining-workspace [data-refresh-on-change]'))"),
            "nothing on the page opts out of the focus guard")

    def test_the_same_picture_is_not_redrawn(self):
        data = sample()
        data["session"]["started"] = 1_790_000_000_000
        self.page.evaluate("data => window.__mining(data)", data)
        self.page.click('[data-mine-op="view"][data-view="record"]')
        self.page.evaluate("() => { window.__chart = document.querySelector('#mining-workspace svg'); }")
        later = json.loads(json.dumps(data))
        later["session"]["duration"] = 4321                 # only the run's clock moved on
        self.page.evaluate("data => window.__mining(data)", later)
        self.assertTrue(self.page.evaluate("() => window.__chart.isConnected"), "a tooltip would vanish")
        clock = self.page.inner_text('.mn-status time[data-mn-live="1"]')
        self.assertRegex(clock, r"^\d+:\d\d:\d\d$", "the tick fills the running clock")

    def test_each_search_can_be_cleared(self):
        self.page.evaluate("data => window.__mining(data)", sample())
        self.page.click('[data-mine-op="view"][data-view="find"]')
        self.page.fill('[data-mine-form="rings"] input[name="range"]', "80")
        self.page.dispatch_event('[data-mine-form="rings"] input[name="range"]', "input")
        self.page.click('[data-mine-op="ring_clear"]')
        self.page.click('[data-mine-op="ground_clear"]')
        self.page.click('[data-mine-op="view"][data-view="sell"]')
        self.page.click('[data-mine-op="sell_clear"]')
        self.page.wait_for_timeout(200)
        ops = [row.get("operation") for row in self.sent if row.get("page") == "mining"]
        self.assertEqual(ops, ["ring_clear", "ground_clear", "sell_clear"])
        self.page.click('[data-mine-op="view"][data-view="find"]')
        self.assertEqual(self.page.input_value('[data-mine-form="rings"] input[name="range"]'), "300", "the form starts afresh")
        self.assertFalse(self.errors, self.errors)

    def test_an_empty_page_still_draws(self):
        self.page.evaluate("data => window.__mining(data)", {})
        for tab in ("live", "find", "sell", "record"):
            self.page.click(f'[data-mine-op="view"][data-view="{tab}"]')
        self.assertFalse(self.errors, self.errors)

    def test_buttons_send_what_the_deck_expects(self):
        self.page.evaluate("data => window.__mining(data)", sample())
        self.page.click('[data-mine-op="view"][data-view="find"]')
        self.page.click('[data-mine-form="rings"] button[type="submit"]')
        self.page.click('[data-mine-op="ring_bookmark"]')
        self.page.click('[data-mine-op="delete_bookmark"]')     # asks first
        self.page.click('[data-mine-op="delete_bookmark"]')
        self.page.click('[data-mine-op="view"][data-view="sell"]')
        self.page.click('[data-mine-op="sell_search"]')
        self.page.wait_for_timeout(200)
        sent = [(row.get("operation"), row) for row in self.sent if row.get("page") == "mining"]
        ops = [op for op, _ in sent]
        self.assertEqual(ops, ["ring_search", "ring_bookmark", "delete_bookmark", "sell_search"])
        self.assertEqual(sent[0][1]["reference"], "Ba Po")
        self.assertEqual(sent[1][1]["result_index"], "0")
        self.assertEqual((sent[2][1]["bookmark_id"], sent[2][1]["confirmed"]), ("3", True))
        self.assertEqual((sent[3][1]["commodity"], sent[3][1]["amount"]), ("Platinum", "100"))
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
