"""5.6.3: Hatchling, the Games page's pocket pet. It lives in real time, is
fed by how you really play (live journal events only), hibernates when
neglected and can be brought back with medicine, is kept per commander,
and has an overlay."""

import json
import tempfile
import unittest
from pathlib import Path

from voidcompass.core import hatchling as pet_module
from voidcompass.core.hatchling import HIBERNATE_DAYS, act, advance, load_state, new_state, observe, view
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR, TEXT_SIZE_KEYS
from voidcompass.dashboard import dashboard_games_mixin as games_module
from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin
from voidcompass.overlays.hatchling_hud import build_hatchling_model

ROOT = Path(__file__).resolve().parents[1]
HOUR = 3600.0
DAY = 24 * HOUR


def hatched(species="larva", now=0.0, **extra):
    state = new_state()
    act(state, "hatch", {"species": species, "name": "Pip", **extra}, now)
    advance(state, now + HOUR)
    return state


class PetTests(unittest.TestCase):
    def test_an_egg_hatches_and_grows_up_in_real_time(self):
        state = new_state()
        self.assertEqual(act(state, "hatch", {"species": "bot", "name": "Bolt"}, 0.0), (True, ""))
        self.assertEqual(view(state, 60)["pet"]["stage"], "egg")
        self.assertEqual(view(state, 60)["pet"]["hatch_minutes"], 29)
        for when, stage in ((HOUR, "hatchling"), (2 * DAY, "juvenile")):
            pet = state["pet"]
            pet["needs"] = {need: 100.0 for need in pet["needs"]}
            self.assertEqual(view(state, when)["pet"]["stage"], stage)
        self.assertFalse(act(state, "hatch", {"species": "larva"}, 3 * DAY)[0], "one at a time")

    def test_needs_fall_by_the_hour_and_it_sleeps_when_spent(self):
        state = hatched()
        before = dict(state["pet"]["needs"])
        after = view(state, 7 * HOUR)["pet"]["needs"]
        self.assertLess(after["hunger"], before["hunger"])
        self.assertLess(after["mood"], before["mood"])
        state["pet"]["needs"]["energy"] = 6.0
        self.assertTrue(view(state, 9 * HOUR)["pet"]["asleep"], "it nods off by itself")

    def test_neglect_hibernates_it_and_medicine_brings_it_back(self):
        state = hatched("larva")
        shown = view(state, 6 * DAY)["pet"]
        self.assertTrue(shown["dormant"])
        self.assertEqual(shown["mood_word"], "HIBERNATING")
        self.assertEqual(shown["wants"], "REVIVE IT")
        changed, message = act(state, "revive", {}, 6 * DAY)
        self.assertFalse(changed)
        self.assertIn("Basic Medicines", message, "it says what to buy")
        observe(state, {"event": "MarketBuy", "Type": "basicmedicines", "Count": 2}, 6 * DAY + 60)
        self.assertEqual(act(state, "revive", {}, 6 * DAY + 120), (True, ""))
        shown = view(state, 6 * DAY + 180)["pet"]
        self.assertFalse(shown["dormant"])
        self.assertEqual(shown["needs"]["health"], 50)

    def test_a_week_hibernating_and_it_is_remembered(self):
        state = hatched("sample", kind="tubus")
        seen = view(state, 40 * DAY)
        self.assertIsNone(seen["pet"])
        self.assertEqual(seen["memorial"][-1]["name"], "Pip")
        self.assertEqual(seen["memorial"][-1]["species"], "sample")
        self.assertTrue(act(state, "hatch", {"species": "bot"}, 40 * DAY)[0], "a new egg can be chosen")
        self.assertEqual(HIBERNATE_DAYS, 7)

    def test_feeding_play_vent_and_lights(self):
        state = hatched("larva")
        pet = state["pet"]
        pet["needs"].update(hunger=40.0, clean=30.0, mood=40.0, energy=50.0)
        self.assertEqual(act(state, "feed", {"item": "foodcartridges"}, 2 * HOUR), (True, ""), "the ship's stores")
        self.assertGreater(pet["needs"]["hunger"], 40)
        self.assertFalse(act(state, "feed", {"item": "fish"}, 2 * HOUR)[0], "not in the larder")
        self.assertEqual(act(state, "vent", {}, 2 * HOUR), (True, ""))
        self.assertEqual(pet["needs"]["clean"], 100.0)
        mood = pet["needs"]["mood"]
        act(state, "play", {"game": "limpet", "won": True}, 2 * HOUR)
        self.assertGreater(pet["needs"]["mood"], mood)
        self.assertEqual(act(state, "lights", {}, 2 * HOUR), (True, ""))
        self.assertTrue(pet["asleep"])
        self.assertFalse(act(state, "feed", {"item": "foodcartridges"}, 2 * HOUR)[0], "asleep")
        self.assertEqual(pet["care"]["meals"], 1)

    def test_a_pat_cheers_it_now_and_then(self):
        state = hatched("bot")
        mood = state["pet"]["needs"]["mood"]
        self.assertEqual(act(state, "pet", {}, 2 * HOUR), (True, ""))
        self.assertEqual(state["pet"]["reaction"], "petted")
        self.assertGreater(state["pet"]["needs"]["mood"], mood)
        self.assertEqual(act(state, "pet", {}, 2 * HOUR + 30), (False, ""), "at most once in a while, and quietly")

    def test_each_species_eats_its_own_food(self):
        bot = hatched("bot")
        self.assertFalse(observe(bot, {"event": "MarketBuy", "Type": "coffee", "Count": 4}, 2 * HOUR), "a bot wants parts")
        self.assertTrue(observe(bot, {"event": "MarketBuy", "Type": "powerconverter", "Count": 1}, 2 * HOUR))
        larva = hatched("larva")
        observe(larva, {"event": "MarketBuy", "Type": "Coffee", "Count": 4}, 2 * HOUR)
        larder = {row["id"]: row["count"] for row in view(larva, 2 * HOUR)["pet"]["larder"]}
        self.assertEqual(larder["coffee"], 4, "buy Coffee and it gets coffee")

    def test_how_you_play_feeds_it(self):
        state = hatched("larva")
        pet = state["pet"]
        pet["needs"]["mood"] = 50.0
        observe(state, {"event": "FSSSignalDiscovered", "SignalName": "$Fixed_Event_Life_Ring;", "USSType": "$USS_Type_NonHuman;"}, 2 * HOUR)
        self.assertEqual(pet["reaction"], "excited", "a larva glows near Thargoid signals")
        excited = pet["needs"]["mood"]
        observe(state, {"event": "ApproachSettlement", "Name": "$Ancient:#index=2;", "Name_Localised": "Guardian Structure"}, 2 * HOUR)
        self.assertLess(pet["needs"]["mood"], excited, "and hates Guardian things")
        mood = pet["needs"]["mood"]
        observe(state, {"event": "Resurrect", "Option": "rebuy", "Cost": 1000}, 2 * HOUR)
        self.assertLessEqual(pet["needs"]["mood"], mood - 20, "a rebuy upsets it badly")
        self.assertEqual(pet["care"]["rebuys"], 1)
        observe(state, {"event": "CodexEntry", "IsNewEntry": True, "Name_Localised": "Stratum Tectonicas"}, 2 * HOUR)
        observe(state, {"event": "Scan", "ScanType": "Detailed", "WasDiscovered": False, "BodyName": "Col 1 A 1"}, 2 * HOUR)
        self.assertEqual((pet["care"]["codex"], pet["care"]["discoveries"]), (1, 1))
        observe(state, {"event": "Docked", "MarketID": 128, "StationName": "Vance Ring"}, 2 * HOUR)
        mood = pet["needs"]["mood"]
        # 5.6.4: every dock is acted out; only somewhere new is a treat.
        observe(state, {"event": "Docked", "MarketID": 128, "StationName": "Vance Ring"}, 2 * HOUR)
        self.assertEqual((pet["needs"]["mood"], pet["care"]["stations"]), (mood, 1), "only somewhere new")
        observe(state, {"event": "SupercruiseEntry"}, 3 * HOUR)
        mood = pet["needs"]["mood"]
        observe(state, {"event": "SupercruiseExit"}, 3 * HOUR + 20 * 60)
        self.assertLess(pet["needs"]["mood"], mood, "long supercruise bores it")
        pet["asleep"] = True
        energy = pet["needs"]["energy"]
        observe(state, {"event": "CarrierJump"}, 3 * HOUR + 21 * 60)
        self.assertGreater(pet["needs"]["energy"], energy, "it sleeps through a carrier jump")

    def test_how_it_was_raised_picks_its_adult_form(self):
        explorer = hatched("bot")
        explorer["pet"]["care"]["explored"] = 60
        battered = hatched("bot")
        battered["pet"]["care"]["rebuys"] = 5
        for state, form in ((explorer, "Pathfinder"), (battered, "Salvager")):
            pet = state["pet"]
            for hours in range(1, 80):
                pet["needs"] = {need: 100.0 for need in pet["needs"]}
                advance(state, HOUR + hours * HOUR)
            shown = view(state, 80 * HOUR)
            self.assertEqual((shown["pet"]["stage"], shown["pet"]["form_name"]), ("adult", form))
            self.assertEqual(shown["collection"][-1]["label"], form)

    def test_a_broken_file_is_a_fresh_start(self):
        self.assertEqual(load_state("{nope"), new_state())
        self.assertIsNone(load_state(json.dumps({"pet": {"species": "dragon"}}))["pet"])
        old = load_state(json.dumps({"pet": {"species": "bot", "name": "Old", "needs": {need: 50 for need in pet_module.NEEDS},
                                             "born": 0, "last": 0, "larder": {}, "care": {"meals": 2}}}))
        self.assertEqual(old["pet"]["care"]["meals"], 2)
        self.assertIn("rebuys", old["pet"]["care"], "missing fields are filled in")


class DeckTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = str(Path(folder.name) / "hatchling.json")
        self.published = []

        class Deck(DashboardGamesMixin):
            pass

        self.deck = Deck()
        self.deck.config = {}
        self.deck._hatchling_path = lambda: self.path
        self.deck._schedule_html_dashboard_publish = lambda immediate=False: self.published.append(immediate)
        self.updates = []
        self.deck.hatchling_hud = type("Hud", (), {"update_hatchling": lambda _self, model: self.updates.append(model)})()

    def act(self, act, **value):
        return self.deck._handle_games_command("action", {"game": "hatchling", "act": act, "value": value})

    def test_actions_are_saved_per_commander(self):
        self.assertTrue(self.act("hatch", species="sample", name="Moss", kind="fungoida"))
        saved = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.assertEqual((saved["pet"]["name"], saved["pet"]["kind"]), ("Moss", "fungoida"))
        self.assertTrue(self.published)
        self.assertEqual(self.updates[-1]["name"], "Moss", "the overlay hears of it at once")
        source = Path(games_module.__file__).read_text(encoding="utf-8")
        self.assertIn('get_profile_file(get_active_profile(getattr(self, "config", None) or {}), HATCHLING_FILE)', source)

    def test_why_nothing_happened_reaches_the_page(self):
        self.act("vent")
        live = self.deck._games_live("hatchling")
        self.assertIn("Nothing aboard", live["notice"]["text"])

    def test_only_live_journal_events_feed_it(self):
        self.act("hatch", species="larva")
        self.deck._hatchling_state()["pet"]["born"] -= 2 * HOUR
        self.deck._games_observe("MarketBuy", {"event": "MarketBuy", "Type": "fish", "Count": 3}, startup_replay=True)
        self.assertNotIn("fish", self.deck._hatchling_state()["pet"]["larder"], "a replayed history never feeds the pet")
        self.deck._games_observe("MarketBuy", {"event": "MarketBuy", "Type": "fish", "Count": 3})
        self.assertEqual(self.deck._hatchling_state()["pet"]["larder"]["fish"], 3)
        self.assertEqual(json.loads(Path(self.path).read_text(encoding="utf-8"))["pet"]["larder"]["fish"], 3)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("self._games_observe(ev, raw if isinstance(raw, dict) else d, startup_replay=startup_replay)", dashboard)

    def test_the_workspace_carries_the_pet_and_touchdowns_gravity(self):
        self.deck.current_body_id = 4
        self.deck.current_body_name = "Synuefe 4"
        self.deck.scan_items_by_id = {4: {"gravity_g": 2.41}}
        games = {game["id"]: game for game in self.deck._html_games_workspace()["games"]}
        self.assertEqual(games["touchdown"]["live"], {"body": "Synuefe 4", "gravity": 2.41})
        self.assertEqual(games["scarab-patrol"]["live"], games["touchdown"]["live"])
        self.assertIn("species", games["hatchling"]["live"])
        self.assertIsNone(games["rock-rats"]["live"])
        self.deck.scan_items_by_id = {4: {"gravity_g": None}}
        self.assertIsNone(self.deck._games_live("touchdown"), "away from a known world, the game makes one up")


class OverlayTests(unittest.TestCase):
    def test_the_overlay_is_registered_and_off_by_default(self):
        spec = OVERLAY_SPEC_BY_ATTR["hatchling_hud"]
        self.assertEqual((spec.overlay_id, spec.default_enabled), ("hatchling", False))
        self.assertEqual(TEXT_SIZE_KEYS["hatchling_hud"], "hatchling_text_scale_percent")
        page = (ROOT / "web" / "hatchling" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/assets/hatchling-art.js", page)
        self.assertIn("/assets/overlay-client.js", page)

    def test_its_model_shows_a_fresh_reaction_and_line_only(self):
        state = hatched("larva")
        observe(state, {"event": "ShieldState", "ShieldsUp": False}, 2 * HOUR)
        model = build_hatchling_model(view(state, 2 * HOUR), 2 * HOUR + 10)
        self.assertEqual(model["reaction"], "scared")
        self.assertIn("Shields down", model["line"])
        later = build_hatchling_model(view(state, 3 * HOUR), 3 * HOUR)
        self.assertEqual((later["reaction"], later["line"]), ("", ""))
        self.assertIsNone(build_hatchling_model(view(new_state(), 0), 0), "no pet, no overlay")



if __name__ == "__main__":
    unittest.main()
