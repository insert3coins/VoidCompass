"""5.5.1.6: Survey Operations' Codex flags, after SrvSurvey's bio panel.

A filled flag marks a species (or the variant being sampled) never logged in
the commander's Codex; an outline, one not logged in the current galactic
region. Matching uses the game's own identifiers, so it works in any game
language. Off by default (Overlay Studio > Survey Operations > Codex flags).
"""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.exploration import bio_values
from voidcompass.exploration.codex_index import CodexIndex, region_id, species_prefix
from voidcompass.overlays.survey_status_hud import SurveyStatusHUD, annotate_codex, build_survey_model

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
AURASUS = "$Codex_Ent_Bacterial_01_Name;"
AURASUS_EMERALD = "$Codex_Ent_Bacterial_01_G_Name;"
TECTONICAS = "$Codex_Ent_Stratum_07_Name;"


def codex(timestamp, entry, region, address=1, body=5):
    return {"timestamp": timestamp, "event": "CodexEntry", "Category": "$Codex_Category_Biology;",
            "Name": entry, "Region": f"$Codex_RegionName_{region};", "SystemAddress": address, "BodyID": body}


def index(*events):
    result = CodexIndex(None)
    for event in events:
        result.observe(event)
    return result


class CodexIndexTests(unittest.TestCase):
    def test_identifiers(self):
        self.assertEqual(region_id("$Codex_RegionName_18;"), 18)
        self.assertIsNone(region_id(""))
        self.assertEqual(species_prefix(AURASUS), "$Codex_Ent_Bacterial_01")

    def test_species_flags(self):
        record = index(codex("2026-08-01T00:00:00Z", AURASUS_EMERALD, 20))
        self.assertEqual(record.species_flag(AURASUS, 20), "", "any variant logged here counts")
        self.assertEqual(record.species_flag(AURASUS, 18), "region")
        self.assertEqual(record.species_flag(TECTONICAS, 20), "new")
        # Bacterium_10 must not borrow Bacterium_01's record.
        self.assertEqual(record.species_flag("$Codex_Ent_Bacterial_10_Name;", 20), "new")

    def test_a_variant_keeps_its_flag_on_the_body_it_was_first_logged(self):
        record = index(codex("2026-10-03T00:00:00Z", AURASUS_EMERALD, 18, address=7, body=3))
        self.assertEqual(record.variant_flag(AURASUS_EMERALD, 18, 7, 3), "new", "logging it wrote the entry")
        self.assertEqual(record.variant_flag(AURASUS_EMERALD, 18, 7, 4), "", "elsewhere it is known")
        record.observe(codex("2026-10-04T00:00:00Z", AURASUS_EMERALD, 20, address=9, body=1))
        self.assertEqual(record.variant_flag(AURASUS_EMERALD, 20, 9, 1), "region")
        self.assertEqual(record.variant_flag("$Codex_Ent_Bacterial_01_A_Name;", 20, 9, 1), "new")

    def test_imports_only_the_commanders_biology_once(self):
        lines = [
            {"timestamp": "2026-01-01T00:00:00Z", "event": "Commander", "Name": "Other", "FID": "F2"},
            codex("2026-01-01T00:01:00Z", TECTONICAS.replace("_Name;", "_F_Name;"), 18),
            {"timestamp": "2026-01-01T00:02:00Z", "event": "Commander", "Name": "Nyx Evera", "FID": "F1"},
            codex("2026-01-01T00:03:00Z", AURASUS_EMERALD, 18),
            {**codex("2026-01-01T00:04:00Z", "$Codex_Ent_L_Cry_IcCry_Pk_Name;", 18), "Category": "$Codex_Category_StellarBodies;"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "Journal.2026-01-01T000000.01.log").write_text(
                "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
            store = Path(folder) / "codex_index.json"
            record = CodexIndex(str(store))
            self.assertEqual(record.import_journals(folder, "Nyx Evera", "F1"), 1)
            self.assertEqual(record.import_journals(folder, "Nyx Evera", "F1"), 0, "unchanged files are skipped")
            record.flush(wait=True)
            self.assertEqual(CodexIndex(str(store)).species_flag(AURASUS, 18), "")
            self.assertEqual(CodexIndex(str(store)).species_flag(TECTONICAS, 18), "new")


class SurveyModelTests(unittest.TestCase):
    def body(self):
        return {
            "body_id": 5, "name": "Prai Preia 3 c", "planet_class": "Rocky body", "landable": True,
            "bio_count": 3, "genuses": [{"Genus_Localised": "Bacterium"}],
            "predicted_genuses": [
                {"name": "Bacterium", "species": [{"name": "Bacterium Aurasus", "key": AURASUS, "value": 1_000_000, "confirmed": True}]},
                {"name": "Stratum", "species": [
                    {"name": "Stratum Tectonicas", "key": TECTONICAS, "value": 19_000_000, "confirmed": True},
                    # An older cached prediction (no identifier): its name finds it.
                    {"name": "Stratum Paleas", "value": 1_300_000, "confirmed": True}]},
            ],
            "organic_scans": {"5|Tussock Ignis": {
                "species": "Tussock Ignis", "genus": "Tussock", "variant": "Tussock Ignis - Green",
                "variant_codex": "$Codex_Ent_Tussocks_07_F_Name;", "sample_idx": 1}},
        }

    def test_rows_carry_flags_only_when_asked(self):
        record = index(codex("2026-08-01T00:00:00Z", AURASUS_EMERALD, 20),
                       codex("2026-08-01T00:00:00Z", "$Codex_Ent_Stratum_02_A_Name;", 18))
        lookup = lambda kind, key, body: (record.variant_flag(key, 18, 1, body) if kind == "variant"
                                          else record.species_flag(key, 18))
        model = build_survey_model("Prai Preia", [self.body()], focused_body_id=5, scanned=1, total=1)
        rows = {row["name"]: row for row in model["rows"]}
        self.assertNotIn("codex", rows["Bacterium"])
        annotate_codex(model, lookup)
        self.assertEqual(rows["Bacterium"]["codex"], "region", "detected genus: its predicted species")
        self.assertEqual(rows["Stratum"]["codex_parts"], [{"text": "Tectonicas", "flag": "new"}, {"text": "Paleas", "flag": ""}])
        self.assertEqual(rows["Tussock Ignis"]["codex"], "new")

    def test_a_detected_genus_without_predictions_is_judged_as_a_whole(self):
        from voidcompass.overlays.survey_status_hud import _genus_species_keys

        body = {"body_id": 6, "name": "Prai Preia 4", "planet_class": "Icy body", "bio_count": 2,
                "genuses": [{"Genus_Localised": "Frutexa"}, {"Genus_Localised": "Tussock"}],
                "predicted_genuses": [{"name": "Crystalline Shards", "species": [{"name": "Crystalline Shards"}]}]}
        tussock = _genus_species_keys("Tussock")
        frutexa = _genus_species_keys("Frutexa")
        self.assertTrue(tussock and frutexa)
        record = index(codex("2026-08-01T00:00:00Z", tussock[0].replace("_Name;", "_A_Name;"), 14),
                       codex("2026-08-01T00:00:00Z", frutexa[0].replace("_Name;", "_A_Name;"), 20))
        model = build_survey_model("Prai Preia", [body], focused_body_id=6, scanned=1, total=1)
        annotate_codex(model, lambda kind, key, b: record.species_flag(key, 14))
        rows = {row["name"]: row for row in model["rows"]}
        self.assertEqual(rows["Frutexa"]["codex"], "region", "logged elsewhere, never here")
        self.assertEqual(rows["Tussock"]["codex"], "", "a Tussock is logged here: no claim either way")
        shards = rows["Crystalline Shards"]
        self.assertEqual((shards["codex"], shards.get("codex_parts")), ("new", None), "named once, flagged once")

    def test_identifiers_agree_with_the_codex_reference(self):
        """codexRef.json (SrvSurvey's Codex reference, packaged) lists every
        variant: each must start with its species' identifier, as the flags
        assume, and every catalogue species must be a real Codex entry."""
        from voidcompass.core.paths import resource_path
        from voidcompass.exploration import bio_requirements

        reference = json.loads(resource_path("data", "codexRef.json").read_text(encoding="utf-8"))
        variants = {}
        for entry in reference.values():
            if entry.get("category") == "$Codex_Category_Biology;":
                species = str(entry.get("english_name") or "").partition(" - ")[0].strip().casefold()
                variants.setdefault(species, []).append(entry["name"])
        for species_map in bio_requirements.CATALOG.values():
            for key, species in species_map.items():
                listed = variants.get(str(species.get("name") or "").casefold())
                if listed is None:
                    continue  # "Stratum Aranaemus": a misspelt duplicate of Araneamus
                with self.subTest(species=species.get("name")):
                    prefix = species_prefix(key)
                    self.assertTrue(all(name == key or name.startswith(prefix + "_") for name in listed))

    def test_genera_outside_the_catalogue_use_the_codex_reference(self):
        from voidcompass.overlays.survey_status_hud import _genus_species_keys

        self.assertEqual(_genus_species_keys("Bark Mounds"), ["$Codex_Ent_Cone_Name;"])
        self.assertEqual(_genus_species_keys("Amphora Plant"), ["$Codex_Ent_Vents_Name;"])
        body = {"body_id": 7, "name": "Prai Preia 5", "planet_class": "Rocky body", "bio_count": 1,
                "genuses": [{"Genus_Localised": "Bark Mounds"}]}
        model = build_survey_model("Prai Preia", [body], focused_body_id=7, scanned=1, total=1)
        annotate_codex(model, lambda kind, key, b: index().species_flag(key, 14))
        self.assertEqual(model["rows"][0]["codex"], "new")

    def test_the_overlay_follows_its_setting(self):
        hud = SurveyStatusHUD.__new__(SurveyStatusHUD)
        hud.config = {"survey_codex_flags": True}
        hud.codex_lookup = Mock(return_value="new")
        hud._suppressed = False
        hud._last_render_key = None
        hud._palette = {}
        hud._redraw = Mock()
        hud.show = Mock()
        hud.update("Prai Preia", 1, 1, [self.body()], {}, focused_body_id=5)
        self.assertTrue(any(row.get("codex") == "new" for row in hud._html_render_model["rows"]))
        hud.config["survey_codex_flags"] = False
        hud._last_render_key = None
        hud.update("Prai Preia", 1, 1, [self.body()], {}, focused_body_id=5)
        self.assertFalse(any(row.get("codex") for row in hud._html_render_model["rows"]))

    def test_predictions_carry_the_game_identifier(self):
        genera = bio_values.predict_genera("Rocky body", "Thin Ammonia", 170, 0.25, "")
        keys = [species.get("key") for genus in genera for species in genus.get("species") or ()]
        self.assertTrue(keys and all(str(key).startswith("$Codex_Ent_") for key in keys))


class WiringTests(unittest.TestCase):
    def test_off_by_default_per_profile_and_in_overlay_studio(self):
        self.assertIn("survey_codex_flags", config_module.PROFILE_BOOL_SETTINGS)
        source = (ROOT / "src/voidcompass/core/config.py").read_text(encoding="utf-8")
        self.assertIn('"survey_codex_flags": False', source)
        studio = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        survey = studio.split('data-studio-settings="survey_status_hud"', 1)[1].split("</section>", 1)[0]
        self.assertIn('data-overlay-option="survey_codex_flags"', survey)


class SurveyPageTests(unittest.TestCase):
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

    def test_flags_draw_beside_their_species(self):
        from tests.test_survey_planet_visuals import CLIENT_STUB

        page = self.browser.new_page(viewport={"width": 420, "height": 900})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/assets/overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=CLIENT_STUB)
            file = WEB / path.lstrip("/")
            return route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404, body="")

        page.route("http://survey.test/**", serve)
        page.goto("http://survey.test/survey/index.html")
        record = index(codex("2026-08-01T00:00:00Z", AURASUS_EMERALD, 20),
                       codex("2026-08-01T00:00:00Z", "$Codex_Ent_Stratum_02_A_Name;", 18))
        model = build_survey_model("Prai Preia", [SurveyModelTests().body()], focused_body_id=5, scanned=1, total=1)
        annotate_codex(model, lambda kind, key, body: (record.variant_flag(key, 18, 1, body) if kind == "variant"
                                                       else record.species_flag(key, 18)))
        page.evaluate("s => window.__surveyRender(s)", {"survey": model, "theme": {}, "effects": {"reduced_motion": True}})
        self.assertEqual(page.locator(".codex-flag.new").count(), 2, "Tectonicas and the Tussock variant")
        self.assertEqual(page.locator(".codex-flag.region").count(), 1, "Aurasus, not yet in this region")
        stratum = page.locator(".biological-name", has_text="Tectonicas").inner_text()
        self.assertEqual(stratum, "Stratum Tectonicas/Paleas")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
