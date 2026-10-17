"""5.5.3.7: Postcards. Take a screenshot in game and a Polaroid of it slides
in: the picture you just took (developing, as an instant photo does) with
"Greetings from…" lettering over it, a handwritten note from the Watcher in
its nature's voice, what the journal knows of the place (its kind, gravity,
firsts, life, how far from Sol), where you were and what you were doing, and
the date in Elite's calendar. Shots taken in a run stack. With Settings >
Caption files, the card's words are saved beside the picture; with Save
postcards as pictures, the card itself, in the postcards folder in Void
Compass's own folder."""

import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from tests.test_galaxy_minimap_5537 import FakeRoot
from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR
from voidcompass.core.screenshot_handler import ScreenshotHandler
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays.html_postcard_overlay import HtmlPostcardBridge
from voidcompass.overlays.postcard_hud import PostcardHUD
from voidcompass.overlays.postcards import (
    MAX_STACK, STACK_S, caption_text, doing, find_screenshot, make_thumbnail, postcard_card, postcard_options,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LANDED = {"timestamp": "2026-10-11T20:14:00Z", "event": "Screenshot", "Filename": "\\ED_Pictures\\Screenshot_0003.bmp",
          "Width": 1920, "Height": 1080, "System": "Hatchooe", "Body": "Hatchooe AB 3",
          "Latitude": 12.34567, "Longitude": -45.678, "Heading": 120, "Altitude": 4.2}


def bitmap(path, size=(1920, 1080)):
    from PIL import Image
    Image.new("RGB", size, (20, 60, 120)).save(path, "BMP")
    return path


class CardTests(unittest.TestCase):
    def test_a_card_says_where_what_and_when(self):
        card = postcard_card(LANDED, state="LANDED", serial=1, now=5)
        self.assertEqual((card["title"], card["place"], card["doing"]), ("Hatchooe AB 3", "Hatchooe", "Landed"))
        self.assertEqual(card["coordinates"], "12.3457° N · 45.6780° W")
        self.assertEqual(card["date"], "11 OCT 3312", "Elite's calendar: 1,286 years on")
        self.assertRegex(card["time"], r"^\d\d:\d\d$")
        self.assertEqual(card["file"], "Screenshot_0003.bmp")
        self.assertFalse(card["photo"])

    def test_it_never_says_the_same_thing_twice(self):
        docked = postcard_card({"timestamp": "2026-10-11T20:00:00Z", "System": "Colonia", "Body": "Jaques Station",
                                "Filename": "\\ED_Pictures\\HighResScreenshot_0001.bmp"},
                               state="DOCKED", station="Jaques Station")
        self.assertEqual((docked["title"], docked["doing"], docked["place"]), ("Jaques Station", "Docked", "Colonia"))
        self.assertTrue(docked["high_res"])
        star = postcard_card({"timestamp": "2026-10-11T20:00:00Z", "System": "Sol", "Body": "Sol"}, state="SUPERCRUISE")
        self.assertEqual((star["title"], star["place"], star["doing"]), ("Sol", "", "In supercruise"))

    def test_what_you_were_doing(self):
        self.assertEqual(doing("ONFOOT"), "On foot")
        self.assertEqual(doing("SRV"), "Driving the SRV")
        self.assertEqual(doing("SCARAB"), "In the Scarab")
        self.assertEqual(doing("DOCKED", station="Jameson Memorial"), "Docked at Jameson Memorial")
        self.assertEqual(doing("TAXI"), "Riding a taxi")
        self.assertEqual(doing(""), "In flight")

    def test_the_caption_in_words(self):
        text = caption_text(postcard_card(LANDED, state="LANDED"))
        self.assertEqual(text.splitlines()[:3], ["Greetings from Hatchooe AB 3", "Hatchooe", "Landed"])
        self.assertIn("11 OCT 3312", text)

    def test_options_stay_within_their_choices(self):
        self.assertEqual(postcard_options({}), {"hold": 10, "photo": True, "size": "standard", "facts": True, "note": True,
                                                "doing": True, "style": "polaroid", "greeting": "Greetings from",
                                                # 5.5.4: the note's words, and your own themes.
                                                "note_mode": "watcher", "note_text": "", "signature": "", "theme": None,
                                            "postmark": True, "sizes": {"lettering": 1.0, "note": 1.0, "details": 1.0}})
        self.assertEqual(postcard_options({"postcard_style": "Airmail"})["style"], "airmail")
        self.assertEqual(postcard_options({"postcard_style": "neon"})["style"], "polaroid")
        self.assertEqual(postcard_options({"postcard_hold_s": 7, "postcard_size": "huge"})["hold"], 10)


class PhotoTests(unittest.TestCase):
    def test_the_bmp_or_the_png_the_converter_made(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(find_screenshot(folder, "Screenshot_0003.bmp"))
            bmp = bitmap(os.path.join(folder, "Screenshot_0003.bmp"))
            self.assertEqual(find_screenshot(folder, "Screenshot_0003.bmp"), bmp)
            os.remove(bmp)
            old = os.path.join(folder, "Sol_2025.png")
            Path(old).write_bytes(b"x")
            os.utime(old, (time.time() - 3600, time.time() - 3600))
            new = os.path.join(folder, "Hatchooe_2026-10-11_20-14-00.png")
            Path(new).write_bytes(b"x")
            self.assertEqual(find_screenshot(folder, "Screenshot_0003.bmp", time.time()), new, "the one just written")

    def test_a_small_jpeg_for_the_card(self):
        with tempfile.TemporaryDirectory() as folder:
            jpeg = make_thumbnail(bitmap(os.path.join(folder, "shot.bmp"), (3840, 2160)))
            from PIL import Image
            import io
            with Image.open(io.BytesIO(jpeg)) as image:
                self.assertEqual((image.format, image.size), ("JPEG", (640, 360)))
            Path(folder, "half.bmp").write_bytes(b"BM\x00\x00")
            self.assertIsNone(make_thumbnail(os.path.join(folder, "half.bmp")), "still being written: try again")


class HudTests(unittest.TestCase):
    def test_cards_stack_then_go_away(self):
        root = FakeRoot()
        hud = PostcardHUD(root, {"postcard_hold_s": 6})
        hud.post(postcard_card(LANDED, serial=1, now=1), now=1000)
        self.assertTrue(hud.visible)
        self.assertEqual([job[0] for job in root.jobs.values()], [6000])
        for serial in range(2, 7):
            hud.post(postcard_card(LANDED, serial=serial, now=serial), now=1000 + serial)
        cards = hud._html_render_model["cards"]
        self.assertEqual(len(cards), MAX_STACK)
        self.assertTrue(cards[0]["id"].endswith("-6"), "the newest on top")
        self.assertEqual(len(root.jobs), 1, "one timer, restarted")
        next(iter(root.jobs.values()))[1]()
        self.assertFalse(hud.visible)
        # A while later, a new run starts its own stack.
        hud.post(postcard_card(LANDED, serial=7, now=7), now=1006 + STACK_S + 1)
        self.assertEqual(len(hud._html_render_model["cards"]), 1)

    def test_the_photo_arrives_and_is_served_by_id(self):
        hud = PostcardHUD(FakeRoot(), {})
        card = postcard_card(LANDED, serial=1, now=1)
        hud.post(card)
        self.assertTrue(hud.attach_photo(card["id"], b"jpeg"))
        self.assertTrue(hud._html_render_model["cards"][0]["photo"])
        self.assertFalse(hud.attach_photo("someone-else", b"jpeg"))
        bridge = HtmlPostcardBridge.__new__(HtmlPostcardBridge)
        bridge.overlay = hud
        self.assertEqual(bridge._file(f"photo-{card['id']}"), (b"jpeg", "image/jpeg"))
        self.assertIsNone(bridge._file("photo-nope"))
        self.assertIsNone(bridge._file("../secrets"))


class DashboardTests(unittest.TestCase):
    def deck(self, folder, **config):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {"screenshots_path": folder, **config}
        deck.postcard_hud = PostcardHUD(FakeRoot(), deck.config)
        deck.hud_flight_state = "LANDED"
        deck.current_sys, deck.current_station_name, deck.current_body_name = "Hatchooe", None, "Hatchooe AB 3"
        deck.posted = []
        deck._ui_post = lambda callback, *args, key=None: callback(*args)
        deck.screenshots = None
        return deck

    def test_live_only(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = self.deck(folder)
            self.assertIsNone(deck._postcard_observe("Screenshot", LANDED, startup_replay=True))
            self.assertIsNone(deck._postcard_observe("FSDJump", {}))
            self.assertFalse(deck.postcard_hud.visible)

    def test_the_picture_reaches_the_card_and_the_caption_its_side(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = self.deck(folder, screenshot_captions=True)
            bitmap(os.path.join(folder, "Screenshot_0003.bmp"))
            card = postcard_card(LANDED, state="LANDED", serial=1, now=1)
            deck.postcard_hud.post(card)
            path, photo = deck._postcard_develop(card, folder, True, True, time.time(), sleep=lambda s: None)
            self.assertTrue(photo)
            self.assertTrue(deck.postcard_hud._html_render_model["cards"][0]["photo"])
            caption = Path(folder, "Screenshot_0003.txt").read_text(encoding="utf-8")
            self.assertTrue(caption.startswith("Greetings from Hatchooe AB 3\nHatchooe\nLanded\n"))

    def test_with_the_converter_the_caption_follows_the_png(self):
        with tempfile.TemporaryDirectory() as folder:
            config = {"screenshots_enabled": False, "screenshots_path": folder}
            handler = ScreenshotHandler(config, get_system_name_cb=lambda: "Hatchooe")
            self.addCleanup(handler.stop)
            deck = self.deck(folder, screenshot_captions=True, screenshots_enabled=True)
            deck.screenshots = handler
            bitmap(os.path.join(folder, "Screenshot_0003.bmp"))
            card = postcard_card(LANDED, state="LANDED", serial=1, now=1)
            deck._postcard_develop(card, folder, False, True, time.time(), sleep=lambda s: None)
            self.assertFalse(Path(folder, "Screenshot_0003.txt").exists(), "not beside a BMP about to go")
            handler.process_folder(folder)
            pngs = [name for name in os.listdir(folder) if name.endswith(".png")]
            self.assertEqual(len(pngs), 1)
            beside = Path(folder, pngs[0][:-4] + ".txt")
            self.assertTrue(beside.read_text(encoding="utf-8").startswith("Greetings from Hatchooe AB 3"))


class DepthTests(unittest.TestCase):
    """Postcards from space: "Greetings from…", the journal's facts and the
    Watcher's note (5.5.3.7, the user's picks)."""

    def test_what_the_journal_knows(self):
        from voidcompass.overlays.postcards import body_kind, postcard_facts
        water = {"planet_class": "Water world", "terraformable": True, "landable": True, "gravity_g": 1.0213,
                 "was_discovered": False, "bio_count": 3}
        self.assertEqual(postcard_facts(water, 57904.4),
                         ["Water world", "Terraformable", "1.02 G", "First discovered", "3 biological signals",
                          "57,904 ly from Sol"])
        self.assertEqual(postcard_facts({"planet_class": "Rocky body", "landable": True, "gravity_g": .3,
                                         "first_footfall": True, "was_discovered": False}),
                         ["Rocky world", "0.30 G", "First footfall"], "a footfall says more than a discovery")
        for star, kind in (("K", "Class K star"), ("N", "Neutron star"), ("DA", "White dwarf"), ("H", "Black hole"),
                           ("SupermassiveBlackHole", "Supermassive black hole"), ("TTS", "T Tauri star")):
            self.assertEqual(body_kind({"star_type": star}), kind)
        self.assertEqual(body_kind({"planet_class": "Earthlike body"}), "Earth-like world")
        self.assertEqual(body_kind({"planet_class": "Sudarsky class II gas giant"}), "Class II gas giant")
        self.assertEqual(postcard_facts(None), [])

    def test_the_watcher_writes_in_its_own_voice(self):
        import random
        from voidcompass.overlays.watcher_postcards import NOTES, moments, postcard_note
        card = postcard_card(LANDED, state="LANDED", region="Outer Scutum-Centaurus Arm", kind="Water world",
                             facts=["Water world", "First discovered"])
        self.assertEqual(moments(card, 57904, "LANDED"), ["first", "rare", "far", "landed"])
        for nature, bank in NOTES.items():
            with self.subTest(nature=nature):
                note = postcard_note(card, nature, 57904, "LANDED", rng=random.Random(1))
                every = [line for lines in bank.values() for line in lines]
                self.assertTrue(note)
                self.assertNotIn("{", note, "every field filled")
                self.assertTrue(any(note.startswith(line.split("{")[0][:12]) for line in every))
        # Lines needing a field that isn't there are never used.
        bare = postcard_card({"timestamp": "2026-10-11T20:00:00Z"}, state="")
        for seed in range(30):
            self.assertNotIn("{", postcard_note(bare, "curious", rng=random.Random(seed)))
        # Not the same line twice while there are others.
        recent = [postcard_note(bare, "stoic", rng=random.Random(0))]
        self.assertNotEqual(postcard_note(bare, "stoic", rng=random.Random(0), recent=recent), recent[0])

    def test_facts_and_the_note_can_be_turned_off(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.postcard_hud = None
        deck.scan_items = [{"name": "Hatchooe AB 3", "planet_class": "Water world", "was_discovered": False}]
        deck.current_coords, deck.current_sys, deck.hud_flight_state = [-9530.5, -910.3, 19808.1], "Hatchooe", "LANDED"
        cards = {}
        for facts, note in ((True, True), (False, True), (True, False), (False, False)):
            deck.config = {"screenshot_captions": True, "postcard_facts": facts, "postcard_note": note,
                           "heartbeat_overlay_enabled": True, "heartbeat_thoughts": "rare"}
            with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.threading.Thread"):
                cards[facts, note] = deck._postcard_observe("Screenshot", LANDED)
        self.assertIn("Water world", cards[True, True]["facts"])
        self.assertTrue(cards[True, True]["note"])
        self.assertEqual(cards[False, True]["facts"], [])
        self.assertTrue(cards[False, True]["note"], "the note still knows the moment")
        self.assertEqual(cards[True, False]["note"], "")
        for card in cards.values():
            self.assertEqual(card["title"], "Hatchooe AB 3", "the place's name, always")
        deck.config = {"postcard_doing": False, "screenshot_captions": True}
        with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.threading.Thread"):
            quiet = deck._postcard_observe("Screenshot", LANDED)
        self.assertEqual(quiet["doing"], "", "no 'Landed', no 'In supercruise'")
        self.assertEqual(quiet["coordinates"], "12.3457° N · 45.6780° W", "where the picture is stays")
        # The Watcher's note is its own (and may say "Landed." itself).
        self.assertNotIn("Landed", caption_text({**quiet, "note": ""}))
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        # 5.5.4: the Watcher's note became a choice (the Watcher's, your own words, none).
        for key in ("postcard_facts", "postcard_note_mode", "postcard_doing"):
            self.assertIn(f'"{key}"', page, "on the Postcards page")
            self.assertIn(key, config_module.PROFILE_SETTINGS)

    def test_no_note_when_the_watcher_is_off(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        card = postcard_card(LANDED, state="LANDED")
        deck.config = {"heartbeat_overlay_enabled": True, "heartbeat_thoughts": "rare", "heartbeat_personality": "stoic"}
        self.assertTrue(deck._postcard_watcher_note(card, 100.0, "LANDED"))
        deck.config["heartbeat_thoughts"] = "off"
        self.assertEqual(deck._postcard_watcher_note(card, 100.0, "LANDED"), "")
        deck.config = {"heartbeat_overlay_enabled": False}
        self.assertEqual(deck._postcard_watcher_note(card, 100.0, "LANDED"), "")

    def test_the_card_knows_the_body_from_this_systems_scans(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.scan_items = [{"name": "Hatchooe AB 3", "body_id": 7, "planet_class": "Water world", "was_discovered": False}]
        deck.body_scan_data = {7: {"landable": True, "gravity_g": 1.02}}
        found = deck._postcard_body("hatchooe ab 3")
        self.assertEqual((found["planet_class"], found["landable"], found["gravity_g"]), ("Water world", True, 1.02))
        self.assertIsNone(deck._postcard_body("Somewhere else"))

    def test_open_postcards(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        with tempfile.TemporaryDirectory() as app, \
                patch("voidcompass.dashboard.dashboard_keepsakes_mixin.application_dir", return_value=Path(app)), \
                patch("voidcompass.dashboard.dashboard_keepsakes_mixin.open_path", return_value=True) as opened:
            self.assertTrue(Deck().open_postcards_folder())
            self.assertEqual(opened.call_args.args[0], os.path.join(app, "postcards"))
            self.assertTrue(os.path.isdir(os.path.join(app, "postcards")), "made on the first visit")
        app_js = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('data-command="open_postcards"', app_js)
        runtime = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"open_postcards"', runtime)


class StyleTests(unittest.TestCase):
    """Four looks, in the overlay and saved postcards alike (5.5.3.7)."""

    def test_every_style_draws(self):
        from voidcompass.overlays.postcard_picture import card_colours, open_picture, render_postcard
        from voidcompass.overlays.postcards import STYLES
        self.assertEqual(STYLES, ("polaroid", "airmail", "holo", "vintage"))
        with tempfile.TemporaryDirectory() as folder:
            picture = open_picture(bitmap(os.path.join(folder, "shot.bmp")))
        card = postcard_card(LANDED, state="LANDED", facts=["Water world"], note="Noted.")
        palette = {"text": "#dce8ef", "bg": "#070b10", "accent": "#00d1ff", "panel": "#0d141c", "orange": "#ff7a18"}
        papers = set()
        for style in STYLES:
            with self.subTest(style=style):
                image = render_postcard(card, picture, palette, style=style)
                self.assertEqual(image.mode, "RGBA")
                papers.add(card_colours(palette, style)["paper"])
        self.assertEqual(len(papers), 4, "each its own paper")
        self.assertEqual(card_colours(palette, "holo")["greet"], (0, 209, 255), "Holo in the theme's accent")

    def test_the_overlay_and_studio_offer_them(self):
        css = (WEB / "postcards" / "styles.css").read_text(encoding="utf-8")
        for style in ("airmail", "holo", "vintage"):
            self.assertIn(f'.card[data-style="{style}"]', css)
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('data-postcard-style=', page, "chosen on the Postcards page")
        self.assertIn("postcard_style", config_module.PROFILE_SETTINGS)


class FolderTests(unittest.TestCase):
    def test_the_postcard_folder_is_yours_to_choose(self):
        from voidcompass.dashboard.dashboard_keepsakes_mixin import postcards_folder
        with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.application_dir", return_value=Path("C:/VC")):
            self.assertEqual(postcards_folder({}), str(Path("C:/VC") / "postcards"), "empty: Void Compass's own folder")
        self.assertEqual(postcards_folder({"postcards_path": "D:/Shots/Cards"}), "D:/Shots/Cards")
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as chosen:
            class Deck(DashboardKeepsakesMixin):
                pass
            deck = Deck()
            deck.config = {"postcards_path": chosen, "postcard_style": "vintage"}
            deck.postcard_hud = None
            deck._ui_post = lambda callback, *args, key=None: callback(*args)
            bitmap(os.path.join(folder, "Screenshot_0003.bmp"))
            card = postcard_card(LANDED, state="LANDED")
            deck._postcard_develop(card, folder, False, False, time.time(), sleep=lambda s: None, keep=True)
            # The picture, and (5.5.4) the hidden .cards folder that lets it be edited.
            self.assertEqual([name for name in os.listdir(chosen) if name.endswith(".png")].__len__(), 1)
            self.assertTrue(os.path.isdir(os.path.join(chosen, ".cards")))
        self.assertIn("postcards_path", config_module.PROFILE_SETTINGS)
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('data-postcard-setting="postcards_path"', page)
        self.assertIn("data-postcard-browse", page)
        self.assertIn("Made even with the Postcards overlay off", page)


class PictureTests(unittest.TestCase):
    """Settings > Save postcards as pictures: the card drawn into a PNG."""

    def test_the_postcard_as_a_picture(self):
        from voidcompass.overlays.postcard_picture import open_picture, render_postcard
        with tempfile.TemporaryDirectory() as folder:
            picture = open_picture(bitmap(os.path.join(folder, "shot.bmp")))
        card = postcard_card(LANDED, state="LANDED")
        image = render_postcard(card, picture, {"text": "#dce8ef", "yellow": "#ffd166", "bg": "#070b10"})
        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 1280, "full width, not the overlay's thumbnail")
        self.assertEqual(image.getpixel((0, 0))[3], 0, "on a transparent ground")
        caption_only = render_postcard(card, None)
        self.assertLess(caption_only.height, image.height, "no picture: the greeting on the paper instead")

    def test_saved_in_the_apps_own_postcards_folder(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as app:
            class Deck(DashboardKeepsakesMixin):
                pass
            deck = Deck()
            deck.config = {"screenshots_path": folder}
            deck.postcard_hud = None
            deck._ui_post = lambda callback, *args, key=None: callback(*args)
            bitmap(os.path.join(folder, "Screenshot_0003.bmp"))
            card = postcard_card({**LANDED, "Body": "Hatchooe AB 3: a/b?"}, state="LANDED")
            with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.application_dir", return_value=Path(app)):
                deck._postcard_develop(card, folder, False, False, time.time(), sleep=lambda s: None, keep=True)
            self.assertFalse(os.path.exists(os.path.join(folder, "Postcards")), "not among the game's screenshots")
            saved = [name for name in os.listdir(os.path.join(app, "postcards")) if name != ".cards"]
            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0].startswith("Postcard - Hatchooe AB 3 ab - "), saved[0])
            self.assertTrue(saved[0].endswith(".png"))
            # With the overlay off, the setting alone makes postcards.
            deck.config["screenshot_postcards"] = True
            with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.threading.Thread") as thread:
                self.assertIsNotNone(deck._postcard_observe("Screenshot", LANDED))
                self.assertTrue(thread.call_args.kwargs["kwargs"]["keep"])

    def test_it_is_a_setting(self):
        self.assertIn("screenshot_postcards", config_module.PROFILE_SETTINGS)
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('"screenshot_postcards"', page)


class RegistrationTests(unittest.TestCase):
    def test_a_managed_overlay_on_by_default(self):
        spec = OVERLAY_SPEC_BY_ATTR["postcard_hud"]
        self.assertEqual((spec.overlay_id, spec.default_enabled, spec.hotkey_key), ("postcards", True, "overlay_hotkey_postcards"))

    def test_every_setting_follows_the_commander(self):
        for key in ("postcard_overlay_enabled", "postcard_hud_x", "postcard_hud_y", "postcard_hold_s",
                    "postcard_photo", "postcard_size", "overlay_hotkey_postcards", "screenshot_captions"):
            with self.subTest(key=key):
                self.assertIn(key, config_module.PROFILE_SETTINGS)

    def test_studio_and_settings_offer_the_options(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        for marker in ('data-studio-settings="postcard_hud"', 'data-studio-setting="postcard_hold_s"',
                       'data-studio-setting="postcard_size"', 'data-overlay-option="postcard_photo"'):
            self.assertIn(marker, html)
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('"screenshot_captions"', page, "caption files are on the Postcards page, not an overlay option")


STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderCards = options.render; window.cardsHeight = options.contentHeight; return {rerender() {}}; }};")


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

    def test_cards_arrive_once_develop_and_stack(self):
        with tempfile.TemporaryDirectory() as folder:
            jpeg = make_thumbnail(bitmap(os.path.join(folder, "shot.bmp")))
        page = self.browser.new_page(viewport={"width": 380, "height": 420})
        self.addCleanup(page.close)
        asked = []

        def serve(route):
            parsed = urlsplit(route.request.url)
            if parsed.path == "/api/file":
                asked.append(parsed.query)
                route.fulfill(body=jpeg, content_type="image/jpeg")
                return
            file = WEB / parsed.path.lstrip("/")
            if not file.is_file():
                route.fulfill(status=404, body="")
            elif file.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(file))
        page.route("http://pc.test/**", serve)
        page.goto("http://pc.test/postcards/index.html?token=t&overlay=postcards")
        page.wait_for_function("Boolean(window.renderCards)")
        first = {**postcard_card(LANDED, state="LANDED", serial=1, now=1), "photo": True}
        render = "data => renderCards({theme: {}, effects: {text_scale: 1}, postcards: data})"
        page.evaluate(render, {"cards": [first], "options": {"photo": True, "size": "standard"}})
        page.wait_for_selector(".card.top .photo img.developing")
        self.assertEqual(page.inner_text(".card.top .photo .greeting-place"), "HATCHOOE AB 3")
        self.assertEqual(page.inner_text(".card.top .note"), "Landed", "no Watcher note: what you were doing")
        self.assertIn("name=photo-", asked[0])
        # Republished: the same card stays (no second arrival, no second request).
        page.evaluate(render, {"cards": [first], "options": {"photo": True, "size": "standard"}})
        self.assertEqual(len(asked), 1)
        second = {**postcard_card(LANDED, state="ONFOOT", serial=2, now=2), "photo": False}
        page.evaluate(render, {"cards": [second, first], "options": {"photo": True, "size": "standard"}})
        self.assertEqual(page.eval_on_selector_all(".card", "cards => cards.map(c => c.className)"),
                         ["card top postmarked", "card postmarked behind"])
        self.assertEqual(page.inner_text(".card.top .note"), "On foot")
        self.assertGreater(page.evaluate("window.cardsHeight()"), 250)
        page.evaluate(render, {"cards": [second], "options": {"photo": False, "size": "small"}})
        self.assertIn("no-photo", page.get_attribute(".card.top", "class"))
        # 5.5.4: the postmark beside the note takes a little room.
        self.assertLess(page.evaluate("window.cardsHeight()"), 215, "a caption-only card is short")
        page.evaluate(render, {"cards": [], "options": {}})
        self.assertIn("empty", page.get_attribute("#postcards", "class"))


if __name__ == "__main__":
    unittest.main()
