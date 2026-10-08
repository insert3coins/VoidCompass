"""5.5.3.1: body data EDDiscovery shows that Void Compass dropped or hid —
Human, Guardian, Thargoid and Other signals, the value breakdown and the
discovery record, and each body's scan facts."""

import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from voidcompass.core.journal_watcher import site_signals
from voidcompass.exploration.stellar_cartography import build_orrery
from voidcompass.overlays.survey_status_hud import build_survey_model

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

SIGNALS = [
    {"Type": "$SAA_SignalType_Biological;", "Count": 2},
    {"Type": "$SAA_SignalType_Human;", "Type_Localised": "Human", "Count": 3},
    {"Type": "$SAA_SignalType_Guardian;", "Count": 1},
    {"Type": "$SAA_SignalType_Other;", "Count": 1},
]


def planet(**extra):
    return {
        "body_id": 4, "name": "Prai 4", "planet_class": "High metal content body", "landable": True,
        "is_star": False, "mass": 0.5, "radius": 3_200_000, "surface_temp": 212.4,
        "surface_pressure": 15_198.75, "axial_tilt": 0.35, "tidal_lock": True, "orbital_inclination": 1.25,
        "semi_major_axis": 2.99e11, "eccentricity": .02, "orbital_period": 86400 * 30,
        "volcanism": "minor rocky magma volcanism",
        "atmosphere_composition": [{"Name": "CarbonDioxide", "Percent": 96.5}, {"Name": "Nitrogen", "Percent": 3.5}],
        "composition": {"Ice": 0.0, "Rock": 0.68, "Metal": 0.32},
        "rings": [{"Name": "Prai 4 A Ring", "RingClass": "eRingClass_MetalRich", "InnerRad": 5.0e6, "OuterRad": 9.5e6}],
        "reward": 21_000, "dss_reward": 95_000, "dss_reward_plain": 76_000,
        "was_discovered": True, "was_mapped": False, "was_footfalled": True, "sites": {"human": 3, "guardian": 1},
        **extra,
    }


class SignalTests(unittest.TestCase):
    def test_the_journal_keeps_settlement_and_site_signals(self):
        self.assertEqual(site_signals(SIGNALS), {"human": 3, "guardian": 1, "other": 1})
        self.assertEqual(site_signals([]), {})

    def test_survey_rows_carry_them(self):
        model = build_survey_model("Prai", [planet()], scanned=1, total=1)
        row = model["rows"][0]
        self.assertEqual(row["sites"], {"human": 3, "guardian": 1})
        self.assertTrue(row["priority"], "a body with sites is worth a row")


class OrreryTests(unittest.TestCase):
    def body(self):
        orrery = build_orrery([planet()], None, [])
        return next(row for row in orrery["bodies"] if row["kind"] == "planet")

    def test_value_breakdown_and_record(self):
        body = self.body()
        self.assertEqual(body["values"], {"scan": 21_000, "mapped": 95_000, "mapped_plain": 76_000})
        self.assertEqual((body["was_discovered"], body["was_mapped"], body["was_footfalled"]), (True, False, True))

    def test_scan_facts(self):
        facts = self.body()["facts"]
        self.assertAlmostEqual(facts["pressure_atm"], .15, places=2)
        self.assertAlmostEqual(facts["axial_tilt_deg"], 20.05, places=1)
        self.assertTrue(facts["tidal_lock"])
        self.assertEqual(facts["radius_km"], 3200.0)
        self.assertEqual(facts["atmosphere_composition"][0], {"name": "CarbonDioxide", "percent": 96.5})
        self.assertEqual(facts["composition"], {"Rock": 68.0, "Metal": 32.0}, "nothing for an empty share")
        self.assertEqual(facts["rings"], [{"name": "Prai 4 A Ring", "class": "Metal Rich", "width_km": 4500,
                                           "inner_km": 5000, "outer_km": 9500, "mass_mt": None, "belt": False}])

    def test_everything_else_the_scan_gives(self):
        body = build_orrery([planet(periapsis=159.1, ascending_node=-52.2, mean_anomaly=291.7,
                                    scan_type="Detailed", dss_probes_used=5, dss_efficiency_target=6,
                                    value_table={"base": 1000, "first_mapped": 9000},
                                    radius=7_000_000, eccentricity=.97,
                                    genuses=[{"Genus_Localised": "Bacterium"}],
                                    organic_scans={"4|x": {"species": "Bacterium Acies", "variant": "Bacterium Acies - White",
                                                           "is_complete": True}})], None, [])["bodies"]
        facts = next(row for row in body if row["kind"] == "planet")["facts"]
        self.assertEqual((facts["periapsis_deg"], facts["ascending_node_deg"], facts["mean_anomaly_deg"]), (159.1, -52.2, 291.7))
        self.assertEqual(facts["scan_type"], "Detailed")
        self.assertEqual(facts["dss"], {"probes": 5, "target": 6, "efficient": True})
        self.assertEqual(facts["value_table"], {"base": 1000, "first_mapped": 9000})
        self.assertIn("Large landable: 7,000 km", facts["notes"])
        self.assertIn("High eccentricity: 0.970", facts["notes"])
        self.assertIn("Ringed landable", facts["notes"])
        self.assertIn("Volcanism", facts["notes"])
        self.assertEqual(facts["genera"], ["Bacterium"])
        self.assertEqual(facts["organics"], [{"name": "Bacterium Acies - White", "state": "analysed"}])

    def test_stars_get_their_class_and_circumstellar_zones(self):
        from voidcompass.exploration.stellar_cartography import circumstellar_zones

        star = {"body_id": 0, "name": "Candiaei", "is_star": True, "star_type": "K", "subclass": 3,
                "luminosity": "Vab", "radius": 531_496_000, "surface_temp": 4724, "mass": .664,
                "age_my": 2300, "absolute_magnitude": 6.29, "distance_to_arrival": 0}
        facts = build_orrery([star], None, [])["bodies"][0]["facts"]
        self.assertEqual(facts["classification"], "K3Vab")
        self.assertAlmostEqual(facts["radius_sr"], .764, places=3)
        zones = facts["zones"]
        # EDDiscovery's bands for this star (checked against its HabZones).
        self.assertEqual(zones["habitable"], [199, 398])
        self.assertEqual(zones["earth_like"], [251, 384])
        self.assertEqual(zones["icy_from"], 879)
        self.assertEqual(circumstellar_zones(None, 4000), {})


class CodexOnBodyTests(unittest.TestCase):
    def test_codex_entries_logged_on_a_body_by_name(self):
        from voidcompass.exploration import bio_reference
        from voidcompass.exploration.codex_index import CodexIndex

        index = CodexIndex(None)
        for stamp, entry, body in (("2026-08-01T00:00:00Z", "$Codex_Ent_Bacterial_04_Tellurium_Name;", 7),
                                   ("2026-08-01T00:01:00Z", "$Codex_Ent_Bacterial_04_Tellurium_Name;", 7),
                                   ("2026-08-01T00:02:00Z", "$Codex_Ent_Bacterial_01_G_Name;", 8)):
            index.observe({"timestamp": stamp, "event": "CodexEntry", "Category": "$Codex_Category_Biology;",
                           "Name": entry, "Region": "$Codex_RegionName_18;", "SystemAddress": 42, "BodyID": body})
        self.assertEqual(index.entries_on(42, 7), ["$Codex_Ent_Bacterial_04_Tellurium_Name;"])
        self.assertEqual(bio_reference.english_name("$Codex_Ent_Bacterial_04_Tellurium_Name;"), "Bacterium Acies - White")


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

    def test_survey_shows_site_badges(self):
        from tests.test_survey_planet_visuals import CLIENT_STUB

        page = self.browser.new_page(viewport={"width": 420, "height": 900})
        self.addCleanup(page.close)

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/assets/overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=CLIENT_STUB)
            file = WEB / path.lstrip("/")
            return route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404, body="")

        page.route("http://survey.test/**", serve)
        page.goto("http://survey.test/survey/index.html")
        model = build_survey_model("Prai", [planet(bio_count=1)], focused_body_id=4, scanned=1, total=1)
        page.evaluate("s => window.__surveyRender(s)", {"survey": model, "theme": {}, "effects": {"reduced_motion": True}})
        badges = page.locator(".badge.site").all_inner_texts()
        self.assertEqual(badges, ["GUARDIAN 1", "HUMAN 3"])
        self.assertIn("212 K", page.locator(".target-temperature").inner_text())

    def test_navigation_hud_shows_sites_only_when_found(self):
        from tests.test_navigation_state_visuals import SHIP_ART, hud_snapshot, hud_state

        page = self.browser.new_page(viewport={"width": 500, "height": 326})
        self.addCleanup(page.close)

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = SHIP_ART / path[len("/ship-art/"):] if path.startswith("/ship-art/") else WEB / path.lstrip("/")
            route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        page.route("http://nav.test/**", serve)
        page.goto("http://nav.test/navigation_hud/index.html")
        snapshot = hud_snapshot(hud_state("SUPERCRUISE"))
        page.evaluate("s => render(s)", snapshot)
        self.assertTrue(page.locator("#survey-signal-sites").is_hidden())
        snapshot["survey"]["signals"].update({"sites": 4, "sites_detail": {"human": 3, "guardian": 1}})
        page.evaluate("s => render(s)", snapshot)
        chip = page.locator("#survey-signal-sites")
        self.assertTrue(chip.is_visible())
        self.assertEqual(chip.locator("em").inner_text(), "4")
        self.assertEqual(chip.get_attribute("title"), "Settlements and sites: Human 3 · Guardian 1")


if __name__ == "__main__":
    unittest.main()
