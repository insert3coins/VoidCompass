"""5.6.1, Part 5: places along the way. Bookmarks grown into places, surface
stops and guidance, finds kept with a click, pictures that find their place,
files in and out, and EDAstro's points of interest near the route."""

import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_expeditions_561 import Deck
from voidcompass.exploration import expedition_plan
from voidcompass.exploration.expedition_manager import ExpeditionManager
from voidcompass.overlays import hud_pages, watcher_lines
from voidcompass.services import gec_catalog

ROOT = Path(__file__).resolve().parents[1]
WHEN = "2099-01-01T10:00:00Z"


def event(name, at=WHEN, **fields):
    return {"event": name, "timestamp": at, **fields}


class ImportTests(unittest.TestCase):
    def test_a_csv_with_landing_sites(self):
        parsed = expedition_plan.parse_import("System,Body,Latitude,Longitude,Name,Notes,x,y,z\n"
                                              "Colonia,Colonia 4 a,12.5,-40.1,The Arch,big rock,-9530.5,-910.28,19808.13\n"
                                              "Colonia,Colonia 4 a,13.5,-41.1,The Other Arch,,,,\n"
                                              "Sol,,,,,,0,0,0\n")
        rows = parsed["systems"]
        self.assertEqual([(row["name"], row["body"], row["lat"], row["title"]) for row in rows],
                         [("Colonia", "Colonia 4 a", 12.5, "The Arch"), ("Colonia", "Colonia 4 a", 13.5, "The Other Arch"), ("Sol", "", None, "")],
                         "two sites on one planet are two places")
        self.assertEqual(rows[0]["coords"], [-9530.5, -910.28, 19808.13])

    def test_json_lists_edastro_shapes_and_our_own_file(self):
        rows = expedition_plan.parse_import(json.dumps([{"galMapSearch": "Athaip WR-H d11-7577", "name": "The Ammonia Lyceum",
                                                         "coordinates": [334.9, -55.4, 23014.3], "summary": "Nested moon"}]))["systems"]
        self.assertEqual((rows[0]["name"], rows[0]["title"], rows[0]["note"]), ("Athaip WR-H d11-7577", "The Ammonia Lyceum", "Nested moon"))
        own = expedition_plan.parse_import(json.dumps({"format": "voidcompass-expedition", "expedition": {"name": "X"}}))
        self.assertEqual(own["payload"]["expedition"]["name"], "X")
        self.assertEqual(len(expedition_plan.parse_import('{"waypoints": ["Sol", "Achenar"]}')["systems"]), 2)

    def test_bad_coordinates_are_dropped(self):
        row = expedition_plan.parse_import("System,Body,Latitude,Longitude\nSol,Earth,95,200\n")["systems"][0]
        self.assertEqual((row["lat"], row["lon"]), (None, None))

    def test_the_saved_csv_reads_back(self):
        text = expedition_plan.places_csv([{"system": "Sol", "body": "Earth", "lat": 51.5, "lon": -0.12, "kind": "surface",
                                            "title": "London, sort of", "note": "home", "coords": [0, 0, 0]}])
        row = expedition_plan.parse_import(text)["systems"][0]
        self.assertEqual((row["name"], row["body"], row["lat"], row["lon"], row["title"], row["note"], row["coords"]),
                         ("Sol", "Earth", 51.5, -0.12, "London, sort of", "home", [0.0, 0.0, 0.0]))


class GuidanceTests(unittest.TestCase):
    def test_bearing_distance_and_turn(self):
        target = expedition_plan.surface_target(0, 0, 0, 0, 1, 1_000_000)
        self.assertEqual((target["bearing"], target["turn"]), (90, 90))
        self.assertAlmostEqual(target["distance_m"], 1_000_000 * math.pi / 180, delta=1)
        self.assertEqual(expedition_plan.surface_target(0, 0, 180, 0, -1, 1_000_000)["turn"], 90, "heading south, west is to your right")
        self.assertTrue(expedition_plan.surface_target(10, 10, None, 10.0001, 10, 1_000_000)["arrived"])
        self.assertIsNone(expedition_plan.surface_target(None, 0, 0, 0, 0))

    def test_near_the_route_in_the_order_you_pass(self):
        rows = expedition_plan.near_route([{"id": 1, "coords": [80, 30, 0]}, {"id": 2, "coords": [20, -40, 0]}, {"id": 3, "coords": [50, 500, 0]}],
                                          [[0, 0, 0], [100, 0, 0]], 100)
        self.assertEqual([(row["id"], row["off_ly"], row["along_ly"]) for row in rows], [(2, 40.0, 20.0), (1, 30.0, 80.0)])


class ManagerPlaceTests(unittest.TestCase):
    def setUp(self):
        self.manager = ExpeditionManager(os.path.join(tempfile.mkdtemp(), "expeditions.json"))
        self.eid = self.manager.create("Bio loop", start_system="Sol", start_pos=[0, 0, 0])["id"]

    def test_old_bookmarks_load_as_places(self):
        with open(self.manager.path, "w", encoding="utf-8") as handle:
            json.dump({"bookmarks": [{"id": "a", "kind": "Field Note", "system": "Sol", "body": "Earth", "title": "Earth"},
                                     {"id": "b", "kind": "POI", "system": "Achenar", "title": "Achenar"}]}, handle)
        again = ExpeditionManager(self.manager.path)
        self.assertEqual({row["id"]: row["kind"] for row in again.bookmarks()}, {"a": "planet", "b": "poi"})

    def test_a_surface_stop_waits_for_its_spot(self):
        place = self.manager.add_bookmark("surface", "Colonia", "Colonia 4 a", "The Arch", expedition_id=self.eid, lat=10, lon=20, radius=1_000_000)
        self.assertEqual(place["kind"], "surface")
        self.assertTrue(self.manager.place_to_route(self.eid, place["id"]))
        self.assertFalse(self.manager.place_to_route(self.eid, place["id"]), "on the route once")
        leg = self.manager.get(self.eid)["legs"][0]
        self.assertEqual((leg["body"], leg["lat"], leg["place_id"]), ("Colonia 4 a", 10.0, place["id"]))
        self.manager.observe_event(event("FSDJump", StarSystem="Colonia", StarPos=[1, 0, 0], JumpDist=1), event_uid="1")
        self.assertIsNone(self.manager.get(self.eid)["legs"][0]["reached"], "the system isn't the spot")
        self.manager.observe_event(event("ApproachBody", StarSystem="Colonia", Body="Colonia 4 a"), event_uid="2")
        self.assertIsNone(self.manager.get(self.eid)["legs"][0]["reached"], "nor is the planet")
        result = self.manager.visit_near("Colonia", "Colonia 4 a", 10.001, 20.0, 1_000_000)
        self.assertEqual((result["legs"], result["places"]), (["The Arch"], ["The Arch"]))
        self.assertTrue(self.manager.get(self.eid)["legs"][0]["reached"])

    def test_a_planet_stop_is_reached_on_approach(self):
        self.manager.add_leg(self.eid, "Colonia", body="Colonia 2")
        self.manager.observe_event(event("ApproachBody", StarSystem="Colonia", Body="Colonia 2"), event_uid="3")
        self.assertTrue(self.manager.get(self.eid)["legs"][0]["reached"])

    def test_screenshots_find_their_place(self):
        near = self.manager.add_bookmark("surface", "Colonia", "Colonia 4 a", "The Arch", expedition_id=self.eid, lat=10, lon=20, radius=1_000_000)
        far = self.manager.add_bookmark("surface", "Colonia", "Colonia 4 a", "Elsewhere", expedition_id=self.eid, lat=-40, lon=20, radius=1_000_000)
        self.manager.observe_event(event("Screenshot", System="Colonia", Body="Colonia 4 a", Latitude=10.01, Longitude=20.0,
                                         Filename="\\ED_Pictures\\Screenshot_0001.bmp"), event_uid="4")
        shots = {row["id"]: row["shots"] for row in self.manager.bookmarks()}
        self.assertEqual(shots[near["id"]][0]["file"], "Screenshot_0001.bmp")
        self.assertEqual(shots[far["id"]], [])

    def test_finds_are_offered_and_kept(self):
        self.manager.observe_event(event("Scan", StarSystem="Colonia", BodyName="Colonia 3", PlanetClass="Earthlike body",
                                         WasDiscovered=False, SystemAddress=1, BodyID=3), event_uid="5")
        self.manager.observe_event(event("CodexEntry", System="Colonia", Name_Localised="Green Gas Giant", Category_Localised="Astronomical",
                                         IsNewEntry=True, EntryID=1), event_uid="6")
        finds = self.manager.get(self.eid)["finds"]
        self.assertEqual([find["kind"] for find in finds], ["valuable", "codex"])
        self.assertIn("first discovered", finds[0]["detail"])
        kept = self.manager.keep_find(self.eid, finds[0]["id"])
        self.assertEqual((kept["kind"], kept["body"]), ("planet", "Colonia 3"))
        self.assertTrue(kept["found"])
        self.assertTrue(self.manager.keep_find(self.eid, finds[1]["id"], dismiss=True))
        self.assertEqual([find["state"] for find in self.manager.get(self.eid)["finds"]], ["kept", "dismissed"])

    def test_visit_every_place_on_the_list(self):
        self.manager.add_objective(self.eid, "places_all")
        first = self.manager.add_bookmark("planet", "Colonia", "Colonia 2", "A", expedition_id=self.eid)
        self.manager.add_bookmark("system", "Sol", title="B", expedition_id=self.eid)
        self.manager.refresh_place_objectives(self.eid)
        objective = self.manager.get(self.eid)["objectives"][0]
        self.assertEqual((objective["progress"], objective["count"]), (0, 2))
        self.manager.update_bookmark(first["id"], status="visited")
        self.manager.observe_event(event("FSDJump", StarSystem="Sol", StarPos=[0, 0, 0], JumpDist=1), event_uid="7")
        self.assertEqual(self.manager.get(self.eid)["objectives"][0]["status"], "complete")

    def test_an_imported_landing_site_is_a_place_and_a_stop(self):
        rows = expedition_plan.parse_import("System,Body,Latitude,Longitude,Name\nColonia,Colonia 4 a,12.5,-40.1,The Arch\nSol,,,,\n")["systems"]
        self.manager.replace_legs(self.eid, rows)
        legs = self.manager.get(self.eid)["legs"]
        places = self.manager.bookmarks(self.eid)
        self.assertEqual(len(places), 1)
        self.assertEqual((legs[0]["place_id"], legs[0]["lat"], legs[1]["place_id"]), (places[0]["id"], 12.5, ""))


class ExampleTests(unittest.TestCase):
    """Distant Worlds 3 as an example, added once per commander, paused."""

    def test_added_once_and_paused(self):
        path = os.path.join(tempfile.mkdtemp(), "expeditions.json")
        self.assertEqual(ExpeditionManager(path).expeditions(), [], "only the deck asks for examples")
        manager = ExpeditionManager(path, examples=True)
        rows = manager.expeditions()
        self.assertEqual(len(rows), 1)
        example = rows[0]
        self.assertEqual((example["status"], example["example"], manager.active()), ("paused", "distant_worlds_3", None))
        legs = example["legs"]
        self.assertEqual(len(legs), 16)
        self.assertEqual((legs[3]["system"], legs[3]["body"], legs[3]["lat"]), ("Beagle Point", "Beagle Point 2", -59.57))
        self.assertTrue(all(leg["body"].startswith(leg["system"]) for leg in legs), "body names as the journal writes them")
        self.assertTrue(all(leg["coords"] for leg in legs), "every stop placed, no lookups needed")
        self.assertEqual((legs[-1]["kind"], legs[-1]["system"]), ("destination", "Stuemeae EG-Y d4548"))
        self.assertEqual(len(manager.bookmarks(example["id"])), 16)
        self.assertEqual(example["objectives"][0]["count"], 16)
        manager.flush(wait=True)
        manager.delete(example["id"])
        manager.flush(wait=True)
        self.assertEqual(ExpeditionManager(path, examples=True).expeditions(), [], "deleted stays deleted")
        self.assertEqual(ExpeditionManager(path).add_example("distant_worlds_3")["name"], "Distant Worlds 3 (example)")

    def test_every_example_is_well_formed(self):
        from voidcompass.exploration.expedition_examples import EXAMPLES
        self.assertEqual([key for key, example in EXAMPLES.items() if example.get("seed")], ["distant_worlds_3"], "only DW3 seeds")
        manager = ExpeditionManager(os.path.join(tempfile.mkdtemp(), "expeditions.json"))
        for key, example in EXAMPLES.items():
            with self.subTest(example=key):
                self.assertTrue(example["source_url"].startswith("https://") and example["credit"])
                for stop in example["stops"]:
                    self.assertTrue(stop["coords"] and len(stop["coords"]) == 3, stop["title"])
                    if stop["body"]:
                        self.assertTrue(stop["body"].startswith(stop["name"] + " "), stop["body"])
                    if stop["lat"] is not None:
                        self.assertTrue(-90 <= stop["lat"] <= 90 and -180 <= stop["lon"] <= 180, stop["title"])
                added = manager.add_example(key)
                self.assertEqual((added["status"], len(added["legs"])), ("paused", len(example["stops"])))
                self.assertEqual(added["legs"][-1]["kind"], "destination")
        self.assertIsNone(manager.active(), "examples never start themselves")

    def test_the_new_form_lists_them_a_to_z(self):
        names = [row["name"] for row in Deck()._expedition_examples()]
        self.assertEqual(names, ["Distant Worlds (example)", "Distant Worlds 2 (example)", "Distant Worlds 3 (example)",
                                 "A Grand Day Out (example)"])

    def test_resumed_it_is_flown(self):
        manager = ExpeditionManager(os.path.join(tempfile.mkdtemp(), "expeditions.json"), examples=True)
        eid = manager.expeditions()[0]["id"]
        manager.set_status(eid, "active")
        manager.observe_event(event("Touchdown", StarSystem="Spoihaae XE-X d2-9", Body="Spoihaae XE-X d2-9 A 1",
                                    Latitude=1.0, Longitude=2.0), event_uid="t")
        self.assertTrue(manager.get(eid)["legs"][0]["reached"], "a stop with no landing site is reached on the body")


class CatalogTests(unittest.TestCase):
    FEED = [{"id": 10, "name": "The Ammonia Lyceum", "type": "Sights and Scenery", "galMapSearch": "Athaip WR-H d11-7577",
             "coordinates": [334.9, -55.4, 23014.3], "summary": "Nested moon", "rating": "4.5", "poiUrl": "https://edastro.com/gec/view/10"},
            {"id": 11, "name": "Nowhere", "galMapSearch": "X"}]

    def test_fetched_once_a_day_and_cached(self):
        calls = []
        now = [1_000_000.0]
        path = os.path.join(tempfile.mkdtemp(), "cache", "gec.json")

        def fetch():
            calls.append(1)
            return self.FEED

        catalog = gec_catalog.GecCatalog(path, fetch=fetch, clock=lambda: now[0])
        self.assertEqual(catalog.rows(refresh=False), [], "nothing cached yet")
        catalog._refresh()  # the background thread's work, run here
        self.assertEqual(len(catalog.rows(refresh=False)), 1, "no coordinates, no point")
        self.assertEqual(catalog.rows(refresh=False)[0]["rating"], 4.5)
        now[0] += 3600
        catalog.rows()
        self.assertEqual(len(calls), 1, "an hour later, no fetch")
        again = gec_catalog.GecCatalog(path, fetch=fetch, clock=lambda: now[0])
        self.assertEqual(again.rows(refresh=False)[0]["system"], "Athaip WR-H d11-7577", "read from the cache")

    def test_credited_and_never_bundled(self):
        self.assertIn("CC BY-NC-SA 3.0", gec_catalog.CREDIT)
        self.assertFalse(list(ROOT.glob("data/*gec*")), "fetched at runtime, never shipped")


class DeckPlaceTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        self.eid = self.deck.expedition_manager.create("Bio loop", start_system="Sol", destination="Colonia", start_pos=[0, 0, 0])["id"]

    def test_mark_this_place_keeps_the_spot(self):
        deck = self.deck
        deck.on_planet, deck.current_body_name = True, "Sol 3"
        deck.current_latitude, deck.current_longitude, deck.current_planet_radius = 51.5, -0.12, 6_371_000.0
        place = deck._expedition_mark_here()
        self.assertEqual((place["kind"], place["body"], place["lat"], place["expedition_id"]), ("surface", "Sol 3", 51.5, self.eid))
        self.assertIn("expedition_marked", [topic for topic, _fields in deck.notes])
        deck.on_planet = False
        self.assertEqual(deck._expedition_mark_here()["kind"], "system", "in space, the system")

    def test_the_hud_points_the_way(self):
        deck = self.deck
        deck.expedition_manager.add_leg(self.eid, "Sol", body="Sol 3", lat=0, lon=1, radius=1_000_000, note="The Spot", index=0)
        deck.current_sys, deck.on_planet, deck.current_body_name = "Sol", True, "Sol 3"
        deck.current_latitude, deck.current_longitude, deck.current_heading, deck.current_planet_radius = 0.0, 0.0, 0.0, 1_000_000.0
        deck.current_altitude_m = 500.0
        page = deck._hud_page_expedition()
        compass = next(block for block in page["blocks"] if block["type"] == "compass")
        self.assertEqual((compass["label"], compass["relative"], compass["distance"]), ("THE SPOT", 90, "17.5 KM"))
        self.assertIn("BEARING 090°", compass["detail"])

    def test_points_of_interest_near_the_route_and_links(self):
        deck = self.deck
        deck.expedition_manager.update_leg(self.eid, deck.expedition_manager.get(self.eid)["legs"][0]["id"], coords=[400, 0, 23000])

        class Catalog:
            error = ""

            def rows(self, refresh=True):
                return [gec_catalog.compact(CatalogTests.FEED[0])]

        deck._gec = Catalog()
        view = deck._expedition_view(deck.expedition_manager.get(self.eid))
        self.assertEqual([row["name"] for row in view["nearby"]["rows"]], ["The Ammonia Lyceum"])
        self.assertTrue(deck._handle_expedition_command("add_poi", {"expedition_id": self.eid, "poi_id": 10, "route": True}))
        view = deck._expedition_view(deck.expedition_manager.get(self.eid))
        self.assertTrue(view["nearby"]["rows"][0]["kept"])
        self.assertEqual(view["places"][0]["source"], "edastro:10")
        self.assertTrue(view["places"][0]["on_route"])
        self.assertFalse(deck._handle_expedition_command("open_link", {"url": "https://evil.example/"}))
        deck.config["expedition_gec_enabled"] = False
        self.assertIsNone(deck._expedition_view(deck.expedition_manager.get(self.eid))["nearby"], "off: nothing fetched")

    def test_the_watcher_has_words_for_places(self):
        for topic in ("expedition_marked", "expedition_place_reached"):
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)

    def test_the_page_has_its_places(self):
        script = (ROOT / "web" / "dashboard" / "expeditions.js").read_text(encoding="utf-8")
        for marker in ('["places", "PLACES"]', "LOAD A FILE", "WORTH SEEING NEAR YOUR ROUTE", "KEEP THESE?", "GUIDE ME", "nearby.credit"):
            self.assertIn(marker, script)
        css = (ROOT / "web" / "dashboard" / "expeditions.css").read_text(encoding="utf-8")
        self.assertNotIn("ellipsis", css)


if __name__ == "__main__":
    unittest.main()
