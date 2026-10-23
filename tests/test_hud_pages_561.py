"""5.6.1: the Navigation HUD's pages show everything the overlays they stand
in for showed. What's in the hold under each hold bar, every row of every list
(the HUD grows to fit), warnings over any page, and the pages in A to Z order.

CoverageTests is the check that keeps it so: every overlay a page covers has
a test here that builds the page from a busy model and finds each fact the
overlay would show. A new entry in COVERS without one fails.
"""

import re
import unittest
from pathlib import Path

from tests import test_hud_pages_5517 as earlier
from voidcompass.core import config as config_module
from voidcompass.overlays import hud_pages as hp
from voidcompass.overlays.cargo_hud import build_cargo_model
from voidcompass.overlays.prospector_hud import build_prospector_model

ROOT = Path(__file__).resolve().parents[1]

HOLD = [{"Name": "platinum", "Name_Localised": "Platinum", "Count": 104}, {"Name": "gold", "Count": 10},
        {"Name": "painite", "Count": 6, "MissionID": 77}, {"Name": "slaves", "Count": 2, "Stolen": 2},
        {"Name": "osmium", "Count": 1}]
ROCK = {"Content": "$AsteroidMaterialContent_Low;", "Remaining": 100.0, "MiningType": "Asteroid",
        "Materials": [{"Name": name, "Proportion": share} for name, share in
                      (("Platinum", 28.3), ("Gold", 17.7), ("Indite", 7.1), ("Silver", 6.0), ("Praseodymium", 4.2),
                       ("Samarium", 3.9), ("Bertrandite", 3.1), ("Gallite", 2.4), ("Coltan", 1.9), ("Uraninite", 1.2))]}


def text_of(page):
    """Every word a page puts on screen."""
    words = []
    for block in (page or {}).get("blocks") or ():
        words += [str(block.get(key) or "") for key in ("title", "value", "sub", "text", "label", "distance", "detail")]
        for item in block.get("items") or ():
            words += [str(item.get(key) or "") for key in ("label", "value", "name", "detail")]
    return " | ".join(words).upper()


def every_list(page):
    return [block for block in page["blocks"] if block["type"] == "list"]


class OrderTests(unittest.TestCase):
    def test_nav_first_then_a_to_z(self):
        self.assertEqual(hp.PAGES[0], "nav")
        self.assertEqual(list(hp.PAGES[1:]), sorted(hp.PAGES[1:]))

    def test_studio_lists_the_pages_a_to_z_with_the_cargo_switch(self):
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        names = re.findall(r'studio-page-switch"><span><b>([^<]+)</b>', page)
        self.assertIn("Cargo", names)
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.assertEqual(len(names), len(hp.PAGES))


class CargoTests(unittest.TestCase):
    def test_no_page_hides_the_cargo_overlay(self):
        self.assertNotIn("cargo_hud", hp.covered_overlays({"hud_pages": "auto"}))
        self.assertTrue(earlier.Deck({"cargo_overlay_enabled": True, "hud_pages": "manual"})._overlay_enabled("cargo_hud"))

    def test_the_hold_heaviest_first_every_item_marked(self):
        block = hp.hold_list(build_cargo_model(HOLD, 523))
        self.assertEqual([item["name"] for item in block["items"]], ["Platinum", "Gold", "Painite", "Slaves", "Osmium"])
        self.assertEqual(block["more"], 0)
        self.assertEqual(block["columns"], 2, "two columns once it's long")
        marks = {item["name"]: (item["detail"], item["tone"]) for item in block["items"]}
        self.assertEqual(marks["Painite"], ("MISSION", "accent"))
        self.assertEqual(marks["Slaves"], ("STOLEN", "red"))
        self.assertIsNone(hp.hold_list(build_cargo_model([], 64)), "an empty hold lists nothing")

    def test_the_cargo_switch_turns_the_lists_off(self):
        self.assertIn("hud_hold_lists", config_module.PROFILE_SETTINGS)
        deck = earlier.Deck({})
        self.assertEqual([title for title, _model in deck._hud_hold_contents(("IN THE HOLD", HOLD))], ["IN THE HOLD"])
        deck.config["hud_hold_lists"] = False
        self.assertEqual(deck._hud_hold_contents(("IN THE HOLD", HOLD)), ())

    def test_each_page_with_a_hold_bar_lists_the_hold(self):
        cargo = build_cargo_model(HOLD, 523)
        contents = (("IN THE HOLD", cargo),)
        pages = {
            "mining": hp.mining_page(build_prospector_model(ROCK), cargo, contents),
            "trade": hp.trade_page({"hop": 1, "hops": 2, "phase": "sell", "station": "A", "action": "Sell"}, cargo, contents),
            "station": hp.station_page({"station": "Jameson Memorial"}, None, (("ABOARD", cargo),)),
            "rhino": hp.rhino_page({"slots": [], "order": []}, (), contents=(("IN THE RHINO", cargo),)),
        }
        for name, page in pages.items():
            with self.subTest(page=name):
                self.assertIn("OSMIUM", text_of(page), "the lightest item is there too")


class MiningTests(unittest.TestCase):
    def test_the_rock_says_what_it_is(self):
        page = hp.mining_page(build_prospector_model(ROCK, {"Platinum": 6, "Gold": 2}), build_cargo_model(HOLD, 523))
        hero = page["blocks"][0]
        self.assertEqual((hero["title"], hero["value"]), ("LOW CONTENT", "PLATINUM 28.3%"))
        self.assertIn("100% LEFT", hero["sub"])
        refined = every_list(page)[0]
        self.assertEqual(refined["title"], "REFINED FROM THIS ROCK · 8 T")
        motherlode = hp.mining_page(build_prospector_model({**ROCK, "MotherlodeMaterial": "Painite"}))
        self.assertEqual(motherlode["blocks"][0]["value"], "MOTHERLODE · PAINITE")

    def test_three_materials_one_column(self):
        page = hp.mining_page(build_prospector_model({**ROCK, "Materials": ROCK["Materials"][:3]}))
        self.assertEqual(page["blocks"][1]["columns"], 1)


class AlertTests(unittest.TestCase):
    def test_heavy_gravity_then_the_rigs(self):
        self.assertEqual(hp.alert_line(("Col 1 A", 4.2)), {"text": "HEAVY GRAVITY · 4.20 G · COL 1 A", "tone": "red"})
        rigs = {"too_far": [{"slot": 3, "distance": 4200}], "ready": [1]}
        self.assertEqual(hp.alert_line(None, rigs)["text"], "RIG 3 4.2 KM AWAY · LOST AT 5 KM")
        self.assertEqual(hp.alert_line(None, {"too_far": [], "ready": [1, 4]}),
                         {"text": "COLLECT RIG 1, 4", "tone": "accent"})
        self.assertIsNone(hp.alert_line(None, {"too_far": [], "ready": []}))

    def test_only_a_live_approach_while_flying_and_not_on_the_planet_page(self):
        deck = earlier.Deck({})
        deck.current_body_id, deck.current_body_name = 3, "Col 1 A"
        deck._hud_heavy_body = ("Col 1 A", 4.2)
        self.assertEqual(deck._hud_pages_alert("nav")["tone"], "red", "a pinned NAV page still warns")
        self.assertIsNone(deck._hud_pages_alert("planet"), "the Planet page already says so")
        deck.current_landed = True
        self.assertIsNone(deck._hud_pages_alert("nav"), "down safely: nothing to warn about")
        deck.current_landed = False
        deck.current_body_name = "Col 1 B"
        self.assertIsNone(deck._hud_pages_alert("nav"), "a different body")


def _contacts():
    rows = [{"kind": "megaship", "label": "Megaship", "name": "Gnosis", "threat": 0, "count": 1},
            {"kind": "combat", "label": "Conflict zone", "name": "Conflict Zone [High]", "threat": 3, "count": 4},
            {"kind": "res", "label": "Resource site", "name": "Resource Extraction Site [Hazardous]", "threat": 2, "count": 1},
            {"kind": "installation", "label": "Installation", "name": "Defence Installation", "threat": 0, "count": 1}]
    return {"rows": rows, "more": 0, "groups": [{"kind": "megaship", "name": "MEGASHIP", "count": 1}]}


class CoverageTests(unittest.TestCase):
    """Each covered overlay's facts, found on the page that covers it."""

    def check_prospector_hud(self):
        model = build_prospector_model(ROCK, {"Platinum": 6, "Gold": 2})
        page = hp.mining_page(model)
        return page, ["LOW", "100% LEFT"] + [row["name"] for row in model["materials"]] + ["PLATINUM", "GOLD", "8 T"]

    def check_planet_materials_hud(self):
        materials = [{"name": f"Mat {n}", "percent": 20.0 - n} for n in range(12)]
        page = hp.planet_page("X 1", {"short_body": "1", "details": {"gravity": 0.4}, "materials": materials})
        return page, [row["name"] for row in materials]

    def check_gravity_warning_hud(self):
        page = hp.planet_page("X 1", {"short_body": "1", "details": {"gravity": 4.2}}, threshold=3.0)
        return page, ["4.20 G", "HEAVY GRAVITY"]

    def check_ground_popup(self):
        page = hp.planet_page("X 1", {"short_body": "1"}, {"state": "OK", "label": "Vein", "distance_m": 2500,
                                                          "heading_delta": 20, "direction": "RIGHT 20°"})
        return page, ["VEIN", "2.5 KM"]

    def check_colony_needs_hud(self):
        rows = [{"name": f"Commodity {n}", "need": 100 + n, "ship": 0} for n in range(20)]
        page = hp.colony_page({"header": "Site", "remaining": 3000, "groups": [{"rows": rows}]})
        return page, [row["name"] for row in rows]

    def check_contact_scope_hud(self):
        page = hp.survey_page({"system": "X", "rows": []}, _contacts())
        return page, [row["name"] for row in _contacts()["rows"]] + ["×4"]

    def check_station_info_hud(self):
        model = {"station": "Jameson Memorial", "pads": "L 8", "type": "ORBIS", "authority": "Federation", "economies": "Industrial 60%",
                 "distance": "512 Ls",
                 "core_services": [{"label": label, "available": True} for label in ("REFUEL", "REPAIR", "REARM", "OUTFITTING")],
                 "exploration_services": [{"label": label, "available": True} for label in
                                          ("UNIVERSAL CARTOGRAPHICS", "VISTA GENOMICS", "SEARCH & RESCUE", "COLONISATION")],
                 "special_services": ["SHIPYARD", "TECH BROKER", "MATERIAL TRADER", "BLACK MARKET", "ENGINEER"],
                 "data_rows": [{"label": "EXPLORATION", "value": "4.2 M CR", "available": True, "service": "CARTOGRAPHICS"}]}
        page = hp.station_page(model)
        return page, ["REFUEL", "OUTFITTING", "VISTA GENOMICS", "COLONISATION", "ENGINEER", "BLACK MARKET",
                      "INDUSTRIAL 60%", "512 LS", "EXPLORATION", "4.2 M CR"]

    def check_rig_tracker_hud(self):
        model = {"slots": [{"slot": 1, "tracked": True, "distance_m": 4200.0, "here": False},
                           {"slot": 2, "tracked": True, "distance_m": 10.0, "here": True, "age_s": 300}], "order": [1, 2]}
        page = hp.rhino_page(model, [{"name": "RHINO", "used": 20, "capacity": 72, "free": 52}])
        return page, ["RIG 1", "LOST AT 5 KM", "COLLECT RIG 2", "20 / 72 T"]

    def check_jump_info_hud(self):
        lines = [{"tone": "text", "items": [{"label": f"FACT {n}", "value": f"V{n}"} for n in range(9)]}]
        page = hp.jump_page({"phase": "charging", "system": "Colonia", "route": {}, "lines": lines})
        return page, ["COLONIA"] + [f"FACT {n}" for n in range(9)]

    def check_survey_status_hud(self):
        rows = [{"name": f"X {n}", "bio_count": 2, "max_value": 1_000_000 * n} for n in range(1, 6)]
        page = hp.survey_page({"system": "X", "scanned": 5, "total": 9, "total_known": True, "rows": rows})
        return page, ["5 OF 9 BODIES", "10 BIO"] + [str(n) for n in range(1, 6)]

    def check_carrier_hud(self):
        page = hp.carrier_page({"name": "Void Ark", "callsign": "X9Z-1TT", "location": "Sol", "fuel": 500.0, "fuel_capacity": 1000.0,
                                "fuel_ratio": .5, "cargo": 1200, "free": 23000})
        return page, ["VOID ARK", "X9Z-1TT", "SOL", "500 / 1,000 T", "1,200 T", "23,000 T"]

    def check_trade_route_hud(self):
        page = hp.trade_page({"hop": 1, "hops": 3, "phase": "buy", "action": "Buy 720 t Gold", "station": "Ray Gateway",
                              "system": "Diaguandri", "distance": 12.0, "expected": 2_000_000, "warnings": ["Large pad only"]})
        return page, ["RAY GATEWAY", "DIAGUANDRI", "BUY 720 T GOLD", "2.0 M CR", "LARGE PAD ONLY"]

    def check_powerplay_hud(self):
        page = hp.powerplay_page({"active": True, "power": "Aisling Duval", "rank": 42, "cycle_merits": 1200,
                                  "objective": {"title": "Deliver", "current": 3, "target": 10}})
        return page, ["AISLING DUVAL", "RANK 42", "1,200 MERITS", "DELIVER", "3 / 10"]

    def check_expedition_hud(self):
        from tests.test_overlay_text_fit_5539 import EXPEDITION_SAMPLE
        page = hp.expedition_page(*EXPEDITION_SAMPLE)
        return page, ["DISTANT WORLDS 3: THE LONG WAY ROUND TO BEAGLE POINT", "37,780 LY TO GO", "42%", "27,500 LY",
                      "THE CRYSTAL ARCHES BY THE CANYON WALL", "EOL PROU LW-L C8-306 4 A", "17.5 KM", "BEARING 092°", "ALT 1.2 KM",
                      "1.23 BN CR", "1,287 JUMPS", "61 H", "64%", "NO STAR TO SCOOP: 6 NEUTRON JUMPS FROM SHINRARTA DEZHRA JAMESON MEMORIAL",
                      "LIMPETS", "FSD INJECTIONS", "AFMU AMMO", "IRONMAN · ONE LIFE"]

    def test_every_covered_overlay_has_a_check(self):
        covered = {attr for attrs in hp.COVERS.values() for attr in attrs}
        checks = {name[len("check_"):] for name in dir(self) if name.startswith("check_")}
        self.assertEqual(covered - checks, set(), "a page covers an overlay this test doesn't check")

    def test_each_page_shows_what_its_overlay_did(self):
        covered = {attr for attrs in hp.COVERS.values() for attr in attrs}
        for attr in sorted(covered):
            page, facts = getattr(self, f"check_{attr}")()
            shown = text_of(page)
            for fact in facts:
                with self.subTest(overlay=attr, fact=fact):
                    self.assertIn(str(fact).upper(), shown)
            for block in every_list(page):
                with self.subTest(overlay=attr, list=block["title"]):
                    self.assertEqual(block["more"], 0, "the HUD grows to fit: no +N MORE")


class AlertRenderTests(unittest.TestCase):
    """The alert line in the HUD, over NAV as well as a page."""

    setUpClass = classmethod(earlier.PageRenderTests.setUpClass.__func__)
    tearDownClass = classmethod(earlier.PageRenderTests.tearDownClass.__func__)
    open = earlier.PageRenderTests.open
    render = earlier.PageRenderTests.render
    page_snapshot = earlier.PageRenderTests.page_snapshot

    def test_the_alert_shows_on_nav_and_goes(self):
        page = self.open()
        snapshot = self.page_snapshot(None, active="nav", mode="manual")
        snapshot["pages"]["alert"] = {"text": "HEAVY GRAVITY · 4.20 G · COL 1 A", "tone": "red"}
        self.render(page, snapshot)
        state = page.evaluate("""() => ({shown: !dom['page-alert'].hidden, text: dom['page-alert'].textContent,
          alerting: dom.hud.classList.contains('alerting'), route: getComputedStyle(dom['route-block']).gridRowStart})""")
        self.assertEqual(state, {"shown": True, "text": "HEAVY GRAVITY · 4.20 G · COL 1 A", "alerting": True, "route": "4"})
        snapshot["pages"]["alert"] = None
        self.render(page, snapshot)
        self.assertTrue(page.evaluate("dom['page-alert'].hidden && !dom.hud.classList.contains('alerting')"))

    def test_a_long_hold_in_two_columns_all_shown(self):
        page = self.open()
        cargo = build_cargo_model([{"Name": f"item{n}", "Count": 30 - n} for n in range(14)], 523)
        mining = hp.mining_page(build_prospector_model(ROCK), cargo, (("IN THE HOLD", cargo),))
        self.render(page, self.page_snapshot(mining, active="mining"))
        result = page.evaluate("""() => ({rows: [...document.querySelectorAll('.pg-list[data-columns="2"] li')].filter((li) => !li.hidden).length,
          more: document.querySelectorAll('.pg-more').length, over: dom['page-body'].scrollHeight - dom['page-body'].clientHeight})""")
        self.assertEqual(result, {"rows": 14, "more": 0, "over": 0})


if __name__ == "__main__":
    unittest.main()
