"""5.6.4: the Hatchling's life on its own, on its game page and in its
overlay: it gets up to things by itself, plays its own little games, and
keeps still while it sleeps. It acts out what you're doing, finds toys on
your trips, learns tricks, grows a personality, dreams of where you've been,
dances to your music, has the Watcher's notice, and SNAP makes it a postcard.
It knows the world you're on, rides the SRV, misses you on foot, greets you
back, keeps a diary for the Captain's Log, earns outfits, and its overlay can
be the pet on its own. It chatters a little, in its own voice, never over
the Watcher. More of the journal reaches it (fights, missions, promotions,
a new ship, being paid, screenshots…), and its page can start again. It
dances to what your music sounds like. It comes along on your expeditions,
keeps a diary of each, earns a badge for every one finished together, and
has a card of its own in the trip's Void Wrapped."""

import base64
import os
import tempfile
import unittest
from io import BytesIO

from tests.test_hatchling_563 import HOUR, ROOT, hatched
from voidcompass.core import config as config_module
from voidcompass.core.hatchling import act, diary, observe, view, welcome
from voidcompass.overlays import watcher_lines
from voidcompass.overlays.hatchling_hud import build_hatchling_model, hatchling_overlay_options, hatchling_pet_window
from voidcompass.overlays.watcher_mind import IMPORTANCE, WatcherMind, thought_heading

PET_TOPICS = ("hatchling_toy", "hatchling_trick", "hatchling_scared", "hatchling_grown", "hatchling_idle", "hatchling_said")


class CharacterTests(unittest.TestCase):
    def test_it_acts_out_what_you_do_and_knows_where_you_are(self):
        state = hatched("larva")
        now = 2 * HOUR
        observe(state, {"event": "StartJump", "JumpType": "Hyperspace", "StarSystem": "Achenar"}, now)
        self.assertEqual(view(state, now)["pet"]["cue"]["kind"], "jump")
        observe(state, {"event": "StartJump", "JumpType": "Supercruise"}, now + 1)
        self.assertEqual(view(state, now + 1)["pet"]["cue"]["kind"], "jump", "supercruise charge isn't a jump")
        observe(state, {"event": "FSDJump", "StarSystem": "Achenar"}, now + 20)
        pet = view(state, now + 20)["pet"]
        self.assertEqual((pet["cue"]["kind"], pet["place"], pet["dreams"]), ("arrive", "supercruise", ["Achenar"]))
        observe(state, {"event": "Docked", "StationName": "Dawes Hub", "MarketID": 9}, now + 60)
        pet = view(state, now + 60)["pet"]
        self.assertEqual((pet["cue"]["kind"], pet["place"]), ("dock", "docked"))
        self.assertIsNone(view(state, now + 200)["pet"]["cue"], "a cue is only acted out while it's fresh")
        observe(state, {"event": "ShieldState", "ShieldsUp": False}, now + 300)
        self.assertEqual(view(state, now + 300)["pet"]["cue"]["kind"], "danger")
        observe(state, {"event": "Scan", "ScanType": "Detailed", "BodyName": "Achenar 3", "WasDiscovered": False}, now + 400)
        self.assertEqual(view(state, now + 400)["pet"]["cue"]["kind"], "discovery")

    def test_low_fuel_worries_it_until_you_refuel(self):
        state = hatched("bot")
        now = 2 * HOUR
        observe(state, {"event": "Loadout", "FuelCapacity": {"Main": 32.0, "Reserve": .5}}, now)
        observe(state, {"event": "FSDJump", "StarSystem": "Hip 1", "FuelLevel": 4.0}, now + 10)
        pet = view(state, now + 10)["pet"]
        self.assertEqual((pet["cue"]["kind"], pet["low_fuel"]), ("lowfuel", True))
        observe(state, {"event": "FuelScoop", "Scooped": 20.0, "Total": 24.0}, now + 60)
        pet = view(state, now + 60)["pet"]
        self.assertEqual((pet["cue"]["kind"], pet["low_fuel"]), ("scoop", False))

    def test_toys_from_your_trips_one_of_each(self):
        state = hatched("sample")
        now = 2 * HOUR
        self.assertTrue(observe(state, {"event": "MiningRefined", "Type_Localised": "Painite"}, now))
        observe(state, {"event": "MiningRefined", "Type_Localised": "Platinum"}, now + 60)
        observe(state, {"event": "Docked", "StationName": "Jameson Memorial", "MarketID": 128666762}, now + 120)
        observe(state, {"event": "CodexEntry", "Name": "$Codex_Ent_Guardian_Beacons_Name;", "Name_Localised": "Guardian Beacon",
                        "System": "Synuefe", "StarSystem": "Synuefe"}, now + 180)
        toys = view(state, now + 180)["pet"]["toys"]
        self.assertEqual([toy["kind"] for toy in toys], ["fragment", "model", "relic"])
        self.assertEqual(toys[0]["label"], "a chunk of Painite", "the same kind not again within the hour")
        self.assertEqual(state["pet"]["moment"]["kind"], "toy")
        observe(state, {"event": "MiningRefined", "Type_Localised": "Platinum"}, now + 2 * HOUR)
        self.assertEqual(view(state, now + 2 * HOUR)["pet"]["toys"][-1]["label"], "a chunk of Platinum")

    def test_tricks_favourites_and_personality(self):
        state = hatched("larva")
        now = 2 * HOUR
        for game in range(4):
            act(state, "play", {"game": "limpet", "won": True}, now + game * 60)
        pet = view(state, now + 300)["pet"]
        self.assertEqual((pet["tricks"], pet["favourite_game"]), (["spin"], "Catch the Limpet"))
        self.assertEqual(state["pet"]["moment"], {"kind": "trick", "at": now + 180, "trick": "spin"})
        state["pet"]["larder"]["coffee"] = 5
        act(state, "feed", {"item": "coffee"}, now + 400)
        self.assertEqual(view(state, now + 400)["pet"]["favourite_food"], "Coffee")
        self.assertEqual(view(state, now + 400)["pet"]["trait"], "", "still finding itself")
        for jump in range(70):
            observe(state, {"event": "FSDJump", "StarSystem": f"Sys {jump}"}, now + 500 + jump)
        pet = view(state, now + 600)["pet"]
        self.assertEqual(pet["trait"], "curious")
        self.assertEqual(len(pet["dreams"]), 5, "it dreams of the last few")

    def test_the_overlay_gets_its_character_and_your_music(self):
        state = hatched("bot")
        observe(state, {"event": "Docked", "StationName": "Dawes Hub", "MarketID": 9}, 2 * HOUR)
        model = build_hatchling_model(view(state, 2 * HOUR), 2 * HOUR, music=True)
        self.assertEqual((model["place"], model["music"], model["cue"]["kind"]), ("docked", True, "dock"))
        self.assertEqual(model["toys"][0]["kind"], "model")
        self.assertFalse(build_hatchling_model(view(state, 2 * HOUR), 2 * HOUR)["music"])


class ShipTests(unittest.TestCase):
    def test_the_world_the_srv_and_on_foot(self):
        state = hatched("larva")
        now = 2 * HOUR
        observe(state, {"event": "Touchdown", "PlayerControlled": True, "_world": {"body": "Col 1 A 2", "gravity": 2.6, "temp": 140}}, now)
        pet = view(state, now)["pet"]
        self.assertEqual((pet["place"], pet["cue"]["kind"], pet["world"]["gravity"], pet["world"]["temp"]), ("landed", "touchdown", 2.6, 140))
        observe(state, {"event": "LaunchSRV", "SRVType": "testbuggy"}, now + 10)
        self.assertEqual((view(state, now + 10)["pet"]["place"], view(state, now + 10)["pet"]["cue"]["kind"]), ("srv", "srv"))
        observe(state, {"event": "Disembark", "SRV": True, "OnPlanet": True}, now + 20)
        self.assertEqual(view(state, now + 20)["pet"]["cue"]["kind"], "srv", "stepping out of the SRV isn't leaving the ship")
        observe(state, {"event": "DockSRV"}, now + 30)
        observe(state, {"event": "Disembark", "SRV": False, "OnPlanet": True}, now + 40)
        pet = view(state, now + 40)["pet"]
        self.assertEqual((pet["place"], pet["cue"]["kind"]), ("away", "leave"))
        observe(state, {"event": "Embark", "SRV": False, "OnPlanet": True}, now + 50)
        pet = view(state, now + 50)["pet"]
        self.assertEqual((pet["place"], pet["cue"]["kind"]), ("landed", "welcome"))
        observe(state, {"event": "Liftoff", "PlayerControlled": True}, now + 60)
        self.assertIsNone(view(state, now + 60)["pet"]["world"], "off the ground, the world doesn't count")
        observe(state, {"event": "LeaveBody", "Body": "Col 1 A 2"}, now + 70)
        self.assertIsNone(state["pet"]["world"])

    def test_it_greets_you_after_time_away(self):
        state = hatched("bot")
        view(state, 2 * HOUR)
        self.assertFalse(welcome(state, 2 * HOUR + 3600), "an hour isn't long")
        self.assertTrue(welcome(state, 9 * HOUR))
        pet = view(state, 9 * HOUR)["pet"]
        self.assertEqual(pet["welcome"]["lines"][0], "You were away 6 hours.")
        self.assertEqual(pet["welcome"]["lines"][-1], "It missed you.")
        self.assertEqual(pet["cue"]["kind"], "welcome")
        self.assertIsNone(view(state, 9 * HOUR + 3600)["pet"]["welcome"], "shown for a while only")
        act(state, "welcomed", {}, 9 * HOUR + 10)
        self.assertIsNone(state["pet"]["welcome"])

    def test_outfits_are_earned_and_worn(self):
        state = hatched("larva")
        now = 2 * HOUR
        self.assertEqual(act(state, "wear", {"outfit": "visor"}, now), (False, "It hasn't earned that one yet."))
        state["pet"]["care"]["explored"] = 499
        observe(state, {"event": "FSDJump", "StarSystem": "Beagle Point"}, now + 1)
        pet = view(state, now + 1)["pet"]
        self.assertEqual([item["id"] for item in pet["outfits"] if item["earned"]], ["visor"])
        self.assertEqual(state["pet"]["moment"]["kind"], "outfit")
        self.assertEqual(act(state, "wear", {"outfit": "visor"}, now + 2), (True, ""))
        self.assertEqual(view(state, now + 2)["pet"]["outfit"], "visor")
        act(state, "wear", {"outfit": ""}, now + 3)
        self.assertEqual(view(state, now + 3)["pet"]["outfit"], "")

    def test_its_diary_for_the_captains_log(self):
        state = hatched("larva")
        observe(state, {"event": "MiningRefined", "Type_Localised": "Painite"}, 2 * HOUR)
        for game in range(4):
            act(state, "play", {"game": "thargon", "won": False}, 3 * HOUR + game)
        self.assertEqual(diary(state, 2 * HOUR - 1, 4 * HOUR), ["Found a chunk of Painite.", "Learned to flip."])
        self.assertEqual(diary(state, 3 * HOUR, 4 * HOUR), ["Learned to flip."])

        from voidcompass.dashboard.dashboard_flight_log_mixin import DashboardFlightLogMixin

        class Deck(DashboardFlightLogMixin):
            def _hatchling_state(self):
                return state

        import time as clock
        start = clock.strftime("%Y-%m-%dT%H:%M:%SZ", clock.gmtime(2 * HOUR - 60))
        end = clock.strftime("%Y-%m-%dT%H:%M:%SZ", clock.gmtime(4 * HOUR))
        logs = Deck()._flight_log_pet([{"id": start}, {"id": "other"}], [{"started": start, "ended": end}])
        self.assertEqual(logs[0]["pet"], {"name": "Pip", "lines": ["Found a chunk of Painite.", "Learned to flip."]})
        self.assertNotIn("pet", logs[1])


class PetOnlyTests(unittest.TestCase):
    def test_its_settings_and_window(self):
        self.assertIsNone(hatchling_pet_window({}), "the panel sizes itself")
        self.assertEqual(hatchling_pet_window({"hatchling_look": "pet"}), (294, 156))
        self.assertEqual(hatchling_pet_window({"hatchling_look": "pet", "hatchling_pet_size": "large", "hatchling_roam": "wide"}), (792, 224))
        options = hatchling_overlay_options({"hatchling_look": "PET", "hatchling_roam": "sideways", "hatchling_sounds": True})
        self.assertEqual((options["look"], options["roam"], options["sounds"], options["speech"]), ("pet", "short", True, True))
        for key in ("hatchling_look", "hatchling_pet_size", "hatchling_roam", "hatchling_needs", "hatchling_speech", "hatchling_glow", "hatchling_sounds"):
            self.assertIn(key, config_module.PROFILE_SETTINGS, key)

    def test_studio_has_them_and_saves_only_real_choices(self):
        import re
        html = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="hatchling_hud">(.*?)</section>', html, re.S).group(1)
        for key in ("hatchling_look", "hatchling_pet_size", "hatchling_roam", "hatchling_needs"):
            self.assertIn(f'data-studio-setting="{key}"', section)
        for key in ("hatchling_speech", "hatchling_glow", "hatchling_sounds"):
            self.assertIn(f'data-overlay-option="{key}"', section)
        from types import SimpleNamespace
        from unittest.mock import Mock

        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
        deck = SimpleNamespace(config={}, _persist_config=lambda: None, update_hud=lambda: None,
                               _schedule_html_dashboard_publish=lambda **kw: None, _hatchling_overlay_refresh=Mock(),
                               heartbeat_hud=None, galnet_ticker_hud=None, music_player_hud=None,
                               galaxy_minimap_hud=None, postcard_hud=None, station_info_hud=None,
                               contact_scope_hud=None, current_docked=False)
        HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_look": "pet", "hatchling_roam": "everywhere"})
        self.assertEqual((deck.config["hatchling_look"], deck.config["hatchling_roam"]), ("pet", "short"))
        self.assertTrue(HtmlOverlayStudioMixin._html_overlay_option_toggle(deck, "hatchling_sounds", True))
        self.assertTrue(deck.config["hatchling_sounds"])
        self.assertGreaterEqual(deck._hatchling_overlay_refresh.call_count, 2)

    def test_its_bridge_uses_the_strip(self):
        from voidcompass.overlays.html_hatchling_overlay import HtmlHatchlingBridge
        bridge = HtmlHatchlingBridge.__new__(HtmlHatchlingBridge)
        bridge.config = {"hatchling_look": "pet", "hatchling_pet_size": "small", "hatchling_roam": "still"}
        self.assertEqual(bridge._dimensions(), (109, 109))

    def test_the_watcher_side_comes_from_where_they_are(self):
        from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin

        class Mind:
            last_thought = {"text": "…", "at": 123.0}

        class Heartbeat:
            mind = Mind()

        class Deck(DashboardGamesMixin):
            heartbeat_hud = Heartbeat()
            config = {"heartbeat_hud_x": -400, "heartbeat_hud_y": 100, "hatchling_hud_x": 1660, "hatchling_hud_y": 860}

        self.assertEqual(Deck()._hatchling_watcher_seen(), {"at": 123.0, "side": [-1, -1], "weary": True})
        Deck.config = {**Deck.config, "heartbeat_overlay_enabled": False}
        self.assertIsNone(Deck()._hatchling_watcher_seen())


class JournalTests(unittest.TestCase):
    def cue(self, state, event, now):
        observe(state, event, now)
        return (view(state, now)["pet"]["cue"] or {}).get("kind")

    def test_more_of_your_day_reaches_it(self):
        state = hatched("bot")
        now = 2 * HOUR
        self.assertEqual(self.cue(state, {"event": "Bounty", "VictimFaction": "Pirates", "TotalReward": 50000}, now), "victory")
        self.assertEqual(state["pet"]["care"]["fights"], 1)
        self.assertEqual(self.cue(state, {"event": "MissionCompleted", "LocalisedName": "Deliver 8 units of Gold"}, now + 1), "mission")
        self.assertIn("Deliver 8 units of Gold", state["pet"]["log"][0]["text"])
        self.assertEqual(self.cue(state, {"event": "Promotion", "Explore": 5}, now + 2), "party")
        self.assertEqual(state["pet"]["care"]["ranks"], 1)
        self.assertEqual(self.cue(state, {"event": "ShipyardSwap", "ShipType": "krait_mkii", "ShipType_Localised": "Krait Mk II"}, now + 3), "newship")
        self.assertEqual(view(state, now + 3)["pet"]["ship"], "Krait Mk II")
        self.assertEqual(self.cue(state, {"event": "MultiSellExplorationData", "TotalEarnings": 9000000}, now + 4), "paid")
        self.assertEqual(self.cue(state, {"event": "Screenshot", "Filename": "x.bmp"}, now + 5), "pose")
        self.assertEqual(self.cue(state, {"event": "CommitCrime", "CrimeType": "collidedAtSpeedInNoFireZone"}, now + 6), "naughty")
        self.assertEqual(self.cue(state, {"event": "SAAScanComplete", "ProbesUsed": 4, "EfficiencyTarget": 6}, now + 7), "mapped")
        observe(state, {"event": "SAAScanComplete", "ProbesUsed": 9, "EfficiencyTarget": 6}, now + 8)
        self.assertEqual(view(state, now + 8)["pet"]["cue"]["at"], now + 7, "a wasteful map isn't cheered")
        observe(state, {"event": "Loadout", "Ship": "anaconda", "ShipName": "Wanderer", "FuelCapacity": {"Main": 32.0}}, now + 9)
        self.assertEqual(view(state, now + 9)["pet"]["ship"], "Wanderer", "your own name for it first")

    def test_a_larva_mourns_a_thargoid(self):
        state = hatched("larva")
        mood = state["pet"]["needs"]["mood"]
        observe(state, {"event": "FactionKillBond", "VictimFaction": "$faction_Thargoid;", "Reward": 80000}, 2 * HOUR)
        self.assertLess(state["pet"]["needs"]["mood"], mood)
        self.assertEqual(state["pet"]["reaction"], "distraught")

    def test_its_page_can_start_again(self):
        for setup in ("egg", "dormant"):
            with self.subTest(setup=setup):
                from voidcompass.core.hatchling import new_state
                state = new_state()
                act(state, "hatch", {"species": "sample", "name": "Moss"}, 0)
                if setup == "dormant":
                    view(state, 3 * 86400)
                    self.assertTrue(view(state, 3 * 86400 + 1)["pet"]["dormant"])
                self.assertEqual(act(state, "release", {}, 3 * 86400 + 2), (True, ""))
                self.assertIsNone(state["pet"])
                self.assertTrue(state["memorial"][-1]["released"])
        page = (ROOT / "web" / "games" / "hatchling" / "game.js").read_text(encoding="utf-8")
        self.assertIn('sure ? "SURE?" : "RESET"', page, "a second press lets it go")

    def test_it_has_words_for_them(self):
        from voidcompass.core import hatchling_chatter
        pet = {**view(hatched("bot"), 2 * HOUR)["pet"], "ship": "Krait Mk II"}
        for situation in ("victory", "mission", "sad", "party", "newship", "paid", "upgrade", "repaired", "phew", "boost",
                          "pose", "naughty", "rude", "fighter", "allfound", "mapped", "settlement"):
            self.assertTrue(hatchling_chatter._pool(pet, situation), situation)
        self.assertIn("I like the Krait Mk II.", hatchling_chatter._pool(pet, "idle"))


class MusicTests(unittest.TestCase):
    def test_the_levels_go_out_for_it_too(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_music.py").read_text(encoding="utf-8")
        self.assertIn('config.get("hatchling_overlay_enabled", False)', source)
        from voidcompass.overlays.html_hatchling_overlay import HtmlHatchlingBridge
        self.assertTrue(hasattr(HtmlHatchlingBridge, "levels"))
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("attach_html_hatchling_overlay(\n                    overlay, overlay_id, title, enabled_key, x_key, y_key, levels=self.music_levels,", dashboard)
        from voidcompass.core import hatchling_chatter
        self.assertTrue(hatchling_chatter._pool(view(hatched("bot"), 2 * HOUR)["pet"], "music"))


class ExpeditionTests(unittest.TestCase):
    def deck(self, state):
        import tempfile
        from tests.test_expeditions_561 import Deck as ExpeditionDeck
        from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin

        class Deck(DashboardGamesMixin, ExpeditionDeck):
            def _hatchling_state(self):
                return state

            def _hatchling_save(self):
                return True

        deck = Deck()
        deck.config = {}
        return deck

    def test_it_comes_along_and_earns_a_badge(self):
        import time
        from voidcompass.core.hatchling import trip_story
        state = hatched("larva", now=time.time() - 2 * HOUR)
        deck = self.deck(state)
        trip = deck.expedition_manager.create("Colonia run", start_system="Sol", destination="Colonia")
        deck.expedition_manager.set_status(trip["id"], "active")
        self.assertTrue(deck._hatchling_sync_trip())
        self.assertFalse(deck._hatchling_sync_trip(), "once")
        pet = view(state, time.time())["pet"]
        self.assertEqual(pet["trip"], {"name": "Colonia run", "to": "Colonia"})
        observe(state, {"event": "MiningRefined", "Type_Localised": "Painite"}, time.time())
        self.assertEqual(deck._hatchling_trip_view(trip["id"])["aboard"], True)
        deck._handle_expedition_command("status", {"expedition_id": trip["id"], "status": "completed"})
        pet = view(state, time.time())["pet"]
        self.assertIsNone(pet["trip"])
        self.assertEqual(pet["badges"][-1]["text"], "Travelled with you to Colonia")
        story = trip_story(state, trip["id"])
        self.assertEqual(story["lines"], ["Set off with you on Colonia run.", "Found a chunk of Painite.",
                                          "Finished Colonia run: travelled with you to Colonia."])
        self.assertEqual(deck._expedition_view(deck.expedition_manager.get(trip["id"]))["pet"]["badge"], "Travelled with you to Colonia")
        self.assertNotIn("kind", story, "the card's own kind stays 'hatchling'")
        journey = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard_journey_mixin.py").read_text(encoding="utf-8")
        self.assertIn('cards.insert(at, {**pet, "kind": "hatchling"})', journey)

    def test_a_trip_abandoned_is_no_badge(self):
        import time
        state = hatched("bot", now=time.time() - 2 * HOUR)
        deck = self.deck(state)
        trip = deck.expedition_manager.create("Short hop", start_system="Sol", destination="Achenar")
        deck.expedition_manager.set_status(trip["id"], "active")
        deck._hatchling_sync_trip()
        deck._handle_expedition_command("status", {"expedition_id": trip["id"], "status": "failed"})
        self.assertEqual(view(state, time.time())["pet"]["badges"], [])
        self.assertIsNone(view(state, time.time())["pet"]["trip"])

    def test_pausing_lets_it_step_off(self):
        import time
        state = hatched("sample", now=time.time() - 2 * HOUR)
        deck = self.deck(state)
        trip = deck.expedition_manager.create("Slow road", start_system="Sol", destination="Sag A*")
        deck.expedition_manager.set_status(trip["id"], "active")
        deck._hatchling_sync_trip()
        deck.expedition_manager.set_status(trip["id"], "paused")
        self.assertTrue(deck._hatchling_sync_trip())
        self.assertIsNone(state["pet"]["trip"])

    def test_it_has_a_card_in_the_trips_wrapped(self):
        import functools
        import http.server
        import json
        import threading
        from datetime import datetime

        from tests.test_journey_5510 import PAGE, events, journey
        from voidcompass.exploration import galactic_regions
        from voidcompass.exploration.void_wrapped import year_story
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        rows, sessions = journey()
        story = year_story(2026, {"rows": rows, "sessions": sessions, "region_of": galactic_regions.find_region, "events": events()},
                           "weary", "Tester")
        at = next(index for index, card in enumerate(story["cards"]) if card["kind"] == "verdict")
        story["cards"].insert(at, {"kind": "hatchling", "name": "Glim", "species": "larva", "sample_kind": "", "stage": "juvenile",
                                   "form": "", "lines": ["Set off with you on Colonia run.", "Found a chunk of Painite."],
                                   "moments": 2, "badge": "Travelled with you to Colonia"})
        art = (ROOT / "web" / "assets" / "hatchling-art.js").read_text(encoding="utf-8")
        page_html = (PAGE % json.dumps(story)).replace("<script type=\"module\">", f"<script>{art}</script><script type=\"module\">", 1)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/":
                    body = page_html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT / "web" / "dashboard")))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1300, "height": 1200}, reduced_motion="reduce")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
            page.wait_for_function("window.harnessReady === true")
            page.wait_for_selector("#wrapped-start:not([hidden])")
            page.click("#wrapped-start")
            for _ in range(at):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(40)
            page.wait_for_timeout(2500)
            self.assertIn("Along for the ride", page.inner_text("#wrapped-workspace"))
            self.shot = page.screenshot()
            self.assertEqual(errors, [])
            browser.close()


class LightTouchTests(unittest.TestCase):
    """The pet never weighs on the rest of the app (5.6.4)."""

    def test_its_overlay_draws_at_most_30_a_second(self):
        from voidcompass.overlays.hatchling_hud import hatchling_frame_rate
        self.assertEqual([hatchling_frame_rate(rate) for rate in (0, 60, 144, 30, 24, 15, "x")], [30, 30, 30, 30, 24, 15, 30])
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('"hatchling": hatchling_frame_rate(overlay_frame_rate(self.config))', source)

    def test_a_honk_is_one_cue_not_dozens(self):
        state = hatched("larva")
        now = 2 * HOUR
        noticed = [observe(state, {"event": "Scan", "ScanType": "AutoScan", "BodyName": f"Col 1 A {n}", "WasDiscovered": True}, now + n * .2)
                   for n in range(3)]
        observe(state, {"event": "Scan", "ScanType": "Detailed", "BodyName": "Col 1 A 9", "WasDiscovered": False}, now + 1)
        first = state["pet"]["cue"]["at"]
        for n in range(20):
            observe(state, {"event": "Scan", "ScanType": "Detailed", "BodyName": f"Col 1 B {n}", "WasDiscovered": False}, now + 2 + n * .3)
        self.assertEqual(state["pet"]["cue"]["at"], first, "the same reaction isn't restarted for every scan in a burst")
        observe(state, {"event": "Scan", "ScanType": "Detailed", "BodyName": "Col 1 C 1", "WasDiscovered": False}, now + 40)
        self.assertEqual(state["pet"]["cue"]["at"], now + 40, "later, a new one")

    def test_it_saves_once_for_a_burst_and_on_close(self):
        from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin

        class Root:
            def __init__(self):
                self.jobs = []

            def call_later(self, ms, callback):
                self.jobs.append(callback)
                return len(self.jobs)

            def cancel(self, job):
                self.jobs[job - 1] = None

        class Deck(DashboardGamesMixin):
            def __init__(self):
                self.root = Root()
                self.saves = 0

            def _hatchling_save(self):
                self.saves += 1
                return True

        deck = Deck()
        for _ in range(30):
            deck._hatchling_save_soon()
        self.assertEqual((deck.saves, len(deck.root.jobs)), (0, 1), "one save waiting for the whole burst")
        deck.root.jobs[0]()
        self.assertEqual(deck.saves, 1)
        deck._hatchling_save_soon()
        self.assertTrue(deck._hatchling_flush(), "closing writes what's waiting")
        self.assertEqual(deck.saves, 2)
        self.assertFalse(deck._hatchling_flush(), "nothing left")
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('flush_pet = getattr(self, "_hatchling_flush", None)', source)


class ChatterTests(unittest.TestCase):
    def setUp(self):
        import random
        from voidcompass.core import hatchling_chatter
        self.chatter = hatchling_chatter
        self.rng = random.Random(4)
        self.state = hatched("larva")

    def say(self, situation, now, mode="chatty", **extra):
        return self.chatter.chatter(self.state, view(self.state, now)["pet"], situation, now, mode, rng=self.rng, **extra)

    def test_a_few_words_rarely_and_never_over_the_watcher(self):
        now = 2 * HOUR
        self.assertIsNone(self.say("jump", now, watcher_busy=True), "the Watcher has the floor")
        self.assertIsNone(self.say("jump", now, mode="off"))
        said = self.say("jump", now, force=True)
        self.assertTrue(said)
        self.assertLessEqual(len(said.replace("hmm…", "").split()), 6, "six words at most")
        self.assertEqual(view(self.state, now + 2)["pet"]["chat"]["text"], said)
        self.assertIsNone(view(self.state, now + 30)["pet"]["chat"], "on screen for a few seconds")
        self.assertIsNone(self.say("dock", now + 30, force=False), "not again so soon")
        quiet = [self.say("idle", now + 400 * step, mode="quiet") for step in range(1, 40)]
        self.assertLess(sum(1 for line in quiet if line), 12, "quiet is quiet")

    def test_each_kind_talks_its_own_way(self):
        import random
        self.assertTrue(self.chatter.voiced("bot", "Where are we?", random.Random(1)).endswith("."))
        self.assertTrue(self.chatter.voiced("sample", "Lights! People!", random.Random(1)).startswith("…l"))
        asleep = hatched("bot")
        asleep["pet"]["asleep"] = True
        self.assertIsNone(self.chatter.chatter(asleep, view(asleep, 2 * HOUR)["pet"], "idle", 2 * HOUR, "chatty", force=True))

    def test_lines_needing_what_it_hasnt_got_are_skipped(self):
        pet = view(self.state, 2 * HOUR)["pet"]
        lines = self.chatter._pool(pet, "idle")
        self.assertFalse(any("{" in line for line in lines))
        self.assertFalse(any("Painite" in line for line in lines))
        observe(self.state, {"event": "MiningRefined", "Type_Localised": "Painite"}, 2 * HOUR)
        lines = self.chatter._pool(view(self.state, 2 * HOUR)["pet"], "idle")
        self.assertTrue(any("chunk of Painite" in line for line in lines), "it talks about its toy")

    def test_the_deck_asks_on_a_cue_and_the_watcher_may_pick_it_up(self):
        from unittest.mock import patch

        from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin

        class Mind:
            last_thought = None
            showing = False

            def current(self):
                return {"text": "…"} if self.showing else None

        class Heartbeat:
            def __init__(self):
                self.mind = Mind()
                self.notes = []

            def note(self, kind, fields=None):
                self.notes.append((kind, fields))

        import time
        # The deck runs on the real clock: a pet hatched an hour ago.
        state = hatched("larva", now=time.time() - 2 * HOUR)

        class Deck(DashboardGamesMixin):
            config = {"hatchling_chatter": "chatty"}
            heartbeat_hud = Heartbeat()

            def _hatchling_state(self):
                return state

        deck = Deck()
        always = {"chatty": {"gap": 0.0, "cue": 1.0, "idle": 1.0}}
        with patch("voidcompass.core.hatchling_chatter.random.random", return_value=0.0),                 patch.dict(self.chatter.MODES, always):
            deck.heartbeat_hud.mind.showing = True
            self.assertIsNone(deck._hatchling_chat("dock"))
            deck.heartbeat_hud.mind.showing = False
            said = deck._hatchling_chat("dock")
        self.assertTrue(said)
        self.assertEqual(deck.heartbeat_hud.notes[-1][0], "hatchling_said")

    def test_chatter_is_a_studio_choice(self):
        import re
        html = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="hatchling_hud">(.*?)</section>', html, re.S).group(1)
        self.assertIn('data-studio-setting="hatchling_chatter"', section)
        self.assertEqual(hatchling_overlay_options({})["chatter"], "quiet")
        self.assertEqual(hatchling_overlay_options({"hatchling_chatter": "loud"})["chatter"], "quiet")
        self.assertIn("hatchling_chatter", config_module.PROFILE_SETTINGS)


class WatcherTests(unittest.TestCase):
    def test_the_watcher_has_words_for_it(self):
        for topic in PET_TOPICS:
            self.assertIn(topic, IMPORTANCE)
            self.assertEqual(thought_heading(topic), ("", "THE HATCHLING"))
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)
        mind = WatcherMind(memory_path=None)
        thought = mind.note("hatchling_trick", {"name": "Pip", "trick": "spin"})
        self.assertIn("spin", thought["text"], "every trick line names the trick")
        self.assertIsNone(mind.note("hatchling_unknown", {"name": "Pip"}))

    def test_the_deck_tells_it_each_moment_once(self):
        from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin

        class Heartbeat:
            def __init__(self):
                self.notes = []

            def note(self, kind, fields=None):
                self.notes.append((kind, fields))

        class Deck(DashboardGamesMixin):
            def __init__(self, state):
                self.heartbeat_hud = Heartbeat()
                self._state = state

            def _hatchling_state(self):
                return self._state

        state = hatched("larva")
        deck = Deck(state)
        observe(state, {"event": "MiningRefined", "Type_Localised": "Painite"}, 2 * HOUR)
        deck._hatchling_watcher()
        deck._hatchling_watcher()
        self.assertEqual(deck.heartbeat_hud.notes, [("hatchling_toy", {"name": "Pip", "toy": "a chunk of Painite"})])


class SnapTests(unittest.TestCase):
    def test_snap_saves_the_pod_as_a_postcard(self):
        from PIL import Image

        from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin
        from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin

        with tempfile.TemporaryDirectory() as folder:
            class Deck(DashboardGamesMixin, DashboardKeepsakesMixin):
                def __init__(self):
                    self.config = {"postcards_path": folder}
                    self.current_sys = "Shinrarta Dezhra"
                    self._state = hatched("bot")

                def _hatchling_state(self):
                    return self._state

            picture = BytesIO()
            Image.new("RGB", (1080, 632), "#123040").save(picture, "PNG")
            answer = Deck()._postcard_design_save({"mode": "snap", "png": base64.b64encode(picture.getvalue()).decode()})
            self.assertTrue(answer["ok"], answer)
            saved = [name for name in os.listdir(folder) if name.endswith(".png")]
            self.assertEqual(len(saved), 1)
            self.assertIn("Shinrarta Dezhra", saved[0])
            self.assertFalse(Deck()._postcard_design_save({"mode": "snap", "png": "bm90IGEgcGljdHVyZQ=="})["ok"])


class LifeTests(unittest.TestCase):
    """It gets up to things on its own, on its game page and in its overlay."""

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

    def open(self, path, width, height):
        from urllib.parse import urlsplit
        web = ROOT / "web"
        stub = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
                " window.renderPet = options.render; return {rerender() {}}; }};")
        page = self.browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            file = web / urlsplit(route.request.url).path.lstrip("/")
            if not file.is_file():
                return route.fulfill(status=404, body="")
            if file.name == "overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + stub)
            return route.fulfill(path=str(file))

        page.route("http://h.test/**", serve)
        page.goto(f"http://h.test/{path}")
        return page, errors

    def run_every_act(self, page, hook, species_acts):
        acts = page.evaluate(f"{hook}.acts()")
        for name in ("keepy", "tower", "tag", "stars", "doze", "rumble", "sulk", "sneeze", "chase", "wander", "hum"):
            self.assertIn(name, acts)
        for name in acts:
            if name in species_acts:
                continue
            page.evaluate(f"n => {hook}.play(n)", name)
            page.wait_for_timeout(120)
            self.assertEqual(page.evaluate(f"{hook}.state().life.act"), name, name)

    def test_the_game_page_pet_plays_on_its_own(self):
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("window.cabinet.card()")
        page.wait_for_function("window.hatchling.state().life.act !== ''", timeout=9000)
        self.run_every_act(page, "window.hatchling", {"scan", "sway", "dance"})
        page.wait_for_timeout(600)
        self.assertEqual(errors, [])
        page.close()

    def test_the_overlay_pet_plays_on_its_own(self):
        state = hatched("larva")
        model = build_hatchling_model(view(state, 3 * HOUR), 3 * HOUR + 700)
        page, errors = self.open("hatchling/index.html", 250, 200)
        page.wait_for_function("typeof window.renderPet === 'function'")
        page.evaluate("m => renderPet({theme: {}, effects: {text_scale: 1}, hatchling: m})", model)
        page.wait_for_function("window.hatchlingOverlay.state().life && window.hatchlingOverlay.state().life.act !== ''", timeout=9000)
        self.run_every_act(page, "window.hatchlingOverlay", {"scan", "sway", "dance"})
        page.wait_for_timeout(600)
        self.assertEqual(errors, [])
        page.close()

    def live_pet(self, page, **extra):
        pet = {"name": "Glim", "species": "larva", "species_name": "Thargoid larva", "kind": "", "kind_name": "", "stage": "juvenile",
               "form": "", "form_name": "", "age_hours": 41, "needs": {"hunger": 74, "mood": 91, "clean": 62, "health": 96, "energy": 58},
               "food_label": "HUNGER", "asleep": False, "sick": False, "dormant": False, "mood_word": "HAPPY", "wants": "", "mess": 0,
               "larder": [], "medicine": "x", "stores_hours": 6, "reaction": "", "reaction_at": 0, "log": [], "toys": [], "tricks": [],
               "dreams": [], "place": "space", "music": False, "cue": None, **extra}
        page.evaluate("p => window.cabinet.live({pet: p})", pet)

    def test_it_acts_out_cues_dances_and_dreams(self):
        import time
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("window.cabinet.card()")
        self.live_pet(page, cue={"kind": "jump", "at": time.time()})
        page.wait_for_function("window.hatchling.state().life.act === 'brace'", timeout=3000)
        self.live_pet(page, cue={"kind": "scoop", "at": time.time() + 1})
        page.wait_for_function("window.hatchling.state().life.shades", timeout=3000)
        self.live_pet(page, cue={"kind": "dock", "at": time.time() - 120})
        page.wait_for_timeout(200)
        self.assertNotEqual(page.evaluate("window.hatchling.state().life.act"), "peek", "a stale cue isn't acted out")
        self.live_pet(page, music=True)
        page.wait_for_function("window.hatchling.state().life.act === 'dance'", timeout=3000)
        self.live_pet(page, asleep=True, dreams=["Colonia"])
        page.wait_for_function("window.hatchling.state().life.dream.startsWith('COLONIA')", timeout=9000)
        self.assertEqual(errors, [])
        page.close()

    def test_snap_sends_the_pod_to_the_deck(self):
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("""() => { window.snapped = null; window.addEventListener('message', (event) => {
          if (event.data && event.data.type === 'snap') window.snapped = event.data.png.length; }); }""")
        page.evaluate("window.cabinet.card()")
        page.wait_for_timeout(200)
        page.keyboard.press("Digit6")
        page.wait_for_function("window.snapped > 1000", timeout=3000)
        self.assertEqual(errors, [])
        page.close()

    def test_pet_only_overlay(self):
        from voidcompass.overlays.hatchling_hud import hatchling_overlay_options as options_for
        config = {"hatchling_look": "pet", "hatchling_needs": "always", "hatchling_speech": False}
        model = build_hatchling_model(view(hatched("bot"), 3 * HOUR), 3 * HOUR, options=options_for(config))
        model["wants"] = "POWER"
        width, height = hatchling_pet_window(config)
        page, errors = self.open("hatchling/index.html", width, height)
        page.wait_for_function("typeof window.renderPet === 'function'")
        page.evaluate("m => renderPet({theme: {}, effects: {text_scale: 1}, hatchling: m})", model)
        page.wait_for_timeout(400)
        self.assertEqual(page.evaluate("window.hatchlingOverlay.state().look"), "pet")
        self.assertTrue(page.evaluate("document.getElementById('hatchling').classList.contains('pet-mode')"))
        self.assertTrue(page.evaluate("getComputedStyle(document.querySelector('.content')).display === 'none'"))
        drawn = page.evaluate("""() => { const c = document.getElementById('roam');
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let lit = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) lit += 1; return lit; }""")
        self.assertGreater(drawn, 500, "the pet is drawn on its strip")
        self.assertEqual(errors, [])
        page.close()

    def test_on_the_ground_it_feels_the_world(self):
        import time
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("window.cabinet.card()")
        self.live_pet(page, place="landed", world={"body": "X", "gravity": 4.0, "temp": 120})
        page.wait_for_timeout(150)
        self.assertAlmostEqual(page.evaluate("window.hatchling.state().life.heavy"), .55, places=2)
        self.live_pet(page, place="srv", world={"body": "X", "gravity": .25, "temp": 300}, cue={"kind": "srv", "at": time.time()})
        page.wait_for_function("window.hatchling.state().life.act === 'bumpy'", timeout=3000)
        self.assertAlmostEqual(page.evaluate("window.hatchling.state().life.heavy"), 1.8, places=2)
        self.live_pet(page, place="away", cue={"kind": "leave", "at": time.time() + 1})
        page.wait_for_function("window.hatchling.state().life.act === 'miss'", timeout=3000)
        self.live_pet(page, place="landed", cue={"kind": "welcome", "at": time.time() + 2})
        page.wait_for_function("window.hatchling.state().life.act === 'welcome'", timeout=3000)
        self.live_pet(page, watcher={"at": time.time() + 3, "side": [1, -1], "weary": True})
        # It waits for the welcome to finish, then goes to sit by the Watcher.
        page.wait_for_function("window.hatchling.state().life.act === 'company'", timeout=6000)
        self.assertEqual(errors, [])
        page.close()

    def test_the_welcome_card_and_outfits_ask_the_deck(self):
        import time
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("""() => { window.asked = []; window.addEventListener('message', (event) => {
          if (event.data && event.data.type === 'action') window.asked.push([event.data.action, event.data.value]); }); }""")
        page.evaluate("window.cabinet.card()")
        self.live_pet(page, welcome={"at": time.time(), "hours": 6, "lines": ["You were away 6 hours.", "It missed you."]},
                      outfits=[{"id": "visor", "label": "Scanner visor", "earned": True, "how": ""}], outfit="")
        page.wait_for_timeout(200)
        page.keyboard.press("Digit8")
        page.wait_for_function("window.asked.some(([action]) => action === 'welcomed')", timeout=3000)
        page.wait_for_timeout(4200)
        page.keyboard.press("Digit7")
        page.wait_for_function("window.asked.some(([action, value]) => action === 'wear' && value.outfit === 'visor')", timeout=3000)
        self.assertEqual(errors, [])
        page.close()

    def test_its_words_show_in_a_bubble(self):
        import time
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("window.cabinet.card()")
        self.live_pet(page, chat={"text": "Ooh. New star!", "at": time.time()})
        page.wait_for_function("window.hatchling.state().life.chat === 'Ooh. New star!'", timeout=3000)
        self.live_pet(page, chat={"text": "Old news", "at": time.time() - 60})
        page.wait_for_timeout(200)
        self.assertEqual(page.evaluate("window.hatchling.state().life.chat"), "Ooh. New star!", "stale words aren't shown")
        self.assertEqual(errors, [])
        page.close()

    def test_reset_takes_two_presses(self):
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("""() => { window.asked = []; window.addEventListener('message', (event) => {
          if (event.data && event.data.type === 'action') window.asked.push(event.data.action); }); }""")
        page.evaluate("window.cabinet.card()")
        page.wait_for_timeout(200)
        page.keyboard.press("Digit9")
        page.wait_for_timeout(200)
        self.assertNotIn("release", page.evaluate("window.asked"), "one press only asks")
        page.keyboard.press("Digit9")
        page.wait_for_function("window.asked.includes('release')", timeout=3000)
        self.assertEqual(errors, [])
        page.close()

    def test_new_moments_are_acted_out(self):
        import time
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.cabinet && window.hatchling")
        page.evaluate("window.cabinet.card()")
        for offset, (kind, act_name) in enumerate((("party", "party"), ("paid", "coins"), ("newship", "inspect"), ("pose", "pose"),
                                                   ("naughty", "gasp"), ("victory", "cheer"))):
            self.live_pet(page, cue={"kind": kind, "at": time.time() + offset})
            page.wait_for_function(f"window.hatchling.state().life.act === '{act_name}'", timeout=3000)
        self.assertEqual(errors, [])
        page.close()

    def test_its_dance_follows_the_music(self):
        music = {
            "bounce": "n => Array.from({length: 32}, (_, b) => b < 4 ? (n % 5 === 0 ? 240 : 90) : 60)",
            "sway": "n => Array.from({length: 32}, () => 30)",
            "robot": "n => Array.from({length: 32}, (_, b) => b < 4 ? (n % 4 === 0 ? 255 : 170) : 190)",
        }
        for style, pattern in music.items():
            with self.subTest(style=style):
                page, errors = self.open("games/hatchling/index.html", 600, 675)
                page.wait_for_function("window.cabinet && window.hatchling")
                page.evaluate("window.cabinet.card()")
                self.live_pet(page, music=True, species="bot")
                page.evaluate(f"""() => {{ const pattern = {pattern}; let n = 0;
                  setInterval(() => window.postMessage({{source: 'voidcompass-deck', type: 'levels', bands: pattern(n++), playing: true}}, '*'), 100); }}""")
                page.wait_for_function(f"window.hatchling.state().life.dance === '{style}'", timeout=10000)
                self.assertEqual(errors, [])
                page.close()

    def test_music_doesnt_take_over(self):
        # Five minutes of music, run quickly in the page: a set when it starts,
        # the odd one after, and its other things in between.
        page, errors = self.open("games/hatchling/index.html", 600, 675)
        page.wait_for_function("window.HatchlingLife")
        share = page.evaluate("""() => {
          const life = HatchlingLife.create({size: 100, range: 100, top: 100});
          const pet = {name: "Glim", species: "larva", stage: "juvenile", needs: {hunger: 74, mood: 90, clean: 90, health: 96, energy: 70},
            toys: [], tricks: [], dreams: [], place: "space", music: true, traits: {}};
          let dancing = 0, first = "";
          for (let step = 0; step < 60 * 300; step += 1) {
            if (step % 6 === 0) life.hear(Array.from({length: 32}, (_, b) => b < 4 ? (step / 6 % 5 === 0 ? 230 : 90) : 80), true);
            life.step(1 / 60, pet);
            if (step === 30) first = life.state().act;
            if (life.state().act === "dance") dancing += 1;
          }
          return {first, share: dancing / (60 * 300)};
        }""")
        self.assertEqual(share["first"], "dance", "a set when the music starts")
        self.assertLess(share["share"], .35)
        self.assertEqual(errors, [])
        page.close()

    def test_its_words_follow_the_overlay_text_size(self):
        model = build_hatchling_model(view(hatched("larva"), 3 * HOUR), 3 * HOUR)
        page, errors = self.open("hatchling/index.html", 375, 300)
        page.wait_for_function("typeof window.renderPet === 'function'")
        page.evaluate("m => renderPet({theme: {}, effects: {text_scale: 1.5}, hatchling: m})", model)
        page.wait_for_function("window.hatchlingOverlay.state().life && window.hatchlingOverlay.state().life.text === 1.5", timeout=3000)
        self.assertEqual(errors, [])
        page.close()

    def test_listening_is_one_loop_not_a_storm(self):
        # A request out used to let every frame start another loop: dozens of
        # level requests a second, slowing the overlay server and every overlay.
        model = {**build_hatchling_model(view(hatched("larva"), 3 * HOUR), 3 * HOUR, music=True), "music": True}
        page, errors = self.open("hatchling/index.html", 250, 200)
        asked = []

        def slow_live(route):
            asked.append(1)
            import time as clock
            clock.sleep(.15)
            route.fulfill(content_type="application/json", body='{"playing": true, "bands": [' + ",".join(["90"] * 32) + "]}")

        page.route("http://h.test/api/live**", slow_live)
        page.wait_for_function("typeof window.renderPet === 'function'")
        page.evaluate("m => renderPet({theme: {}, effects: {text_scale: 1}, hatchling: m})", model)
        page.wait_for_timeout(3000)
        self.assertLessEqual(len(asked), 14, f"{len(asked)} requests in 3 s")
        self.assertGreaterEqual(len(asked), 5, "it still listens")
        self.assertEqual(errors, [])
        page.close()

    def test_the_overlay_hears_it_too(self):
        model = {**build_hatchling_model(view(hatched("larva"), 3 * HOUR), 3 * HOUR, music=True), "music": True}
        page, errors = self.open("hatchling/index.html", 250, 200)
        page.route("http://h.test/api/live**", lambda route: route.fulfill(
            content_type="application/json", body='{"playing": true, "bands": [' + ",".join(["30"] * 32) + "]}"))
        page.wait_for_function("typeof window.renderPet === 'function'")
        page.evaluate("m => renderPet({theme: {}, effects: {text_scale: 1}, hatchling: m})", model)
        page.wait_for_function("window.hatchlingOverlay.state().life && window.hatchlingOverlay.state().life.dance === 'sway'", timeout=10000)
        self.assertEqual(errors, [])
        page.close()

    def test_a_sleeping_pet_stays_put(self):
        model = {**build_hatchling_model(view(hatched("bot"), 2 * HOUR), 2 * HOUR), "asleep": True}
        page, errors = self.open("hatchling/index.html", 250, 200)
        page.wait_for_function("typeof window.renderPet === 'function'")
        page.evaluate("m => renderPet({theme: {}, effects: {text_scale: 1}, hatchling: m})", model)
        page.wait_for_timeout(4500)
        self.assertEqual(page.evaluate("window.hatchlingOverlay.state().life.act"), "")
        self.assertEqual(errors, [])
        page.close()



if __name__ == "__main__":
    unittest.main()
