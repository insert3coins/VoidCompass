"""The companion on watch writes the postcard, and its authorship travels with it."""
import copy
import random
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from PIL import Image

from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays import aster_postcards, postcard_picture
from voidcompass.overlays.aster_mind import AsterMind
from voidcompass.overlays.watcher_mind import WatcherMind
from voidcompass.overlays.postcards import caption_text, postcard_card
from tests import test_postcard_editor_563 as editor_fixture
from tests import test_postcards_5537 as overlay_fixture

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ARTIFACTS = Path(tempfile.gettempdir()) / "voidcompass-aster-checks"
RAW = {"timestamp": "2026-11-04T05:10:00Z", "Filename": "shot.png", "System": "Sol", "Body": "Sol 3"}


class AsterPostcardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.deck = DashboardKeepsakesMixin()
        self.deck.config = {"companion_identity": "aster", "aster_thoughts": "occasional", "aster_humour": "dry",
                            "heartbeat_thoughts": "off", "screenshot_captions": True,
                            "screenshots_path": str(self.root), "postcards_path": str(self.root / "cards")}
        self.deck.current_coords, self.deck.current_sys, self.deck.hud_flight_state = [0, 0, 0], "Sol", "LANDED"
        self.deck.scan_items = [{"name": "Sol 3", "planet_class": "Earthlike body", "was_discovered": False}]
        self.deck.postcard_hud = None
        self.deck._ui_post = lambda callback, *args, key=None, **kwargs: callback(*args, **kwargs)
        self.deck.heartbeat_hud = SimpleNamespace(mind=AsterMind(None, self.deck.config, rng=random.Random(5)))

    def capture(self):
        with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.threading.Thread") as worker:
            card = self.deck._postcard_observe("Screenshot", RAW)
        return card, worker

    def test_live_card_and_saved_memory_follow_selected_companion(self):
        card, _ = self.capture()
        self.assertEqual(card["signed"], "Aster")
        self.assertTrue(card["note"])
        self.assertEqual(self.deck.heartbeat_hud.mind.memory["postcards"][-1][1], "Sol 3")
        self.assertEqual(self.deck._html_postcards_workspace()["note_author"], "Aster")
        self.deck.config.update(companion_identity="watcher", heartbeat_thoughts="occasional")
        self.deck.heartbeat_hud.mind = WatcherMind(None, self.deck.config)
        watcher, _ = self.capture()
        self.assertEqual(watcher["signed"], "the Watcher")
        self.assertNotEqual(card["note"], watcher["note"])
        self.assertEqual(self.deck._html_postcards_workspace()["note_author"], "The Watcher")
        self.assertEqual(card["signed"], "Aster", "a switch cannot reattribute an existing card")

    def test_own_none_and_disabled_companion_choices_remain_independent(self):
        self.deck.config["aster_thoughts"] = "off"
        self.assertEqual(self.capture()[0]["note"], "")
        self.deck.config.update(aster_thoughts="rare", heartbeat_overlay_enabled=False)
        self.assertEqual(self.capture()[0]["note"], "")
        self.deck.config.update(heartbeat_overlay_enabled=True, postcard_note_mode="none")
        self.assertEqual(self.capture()[0]["note"], "")
        self.deck.config.update(postcard_note_mode="own", postcard_note_text="Our own voyage.", postcard_signature="Crew",
                                aster_thoughts="off")
        own = self.capture()[0]
        self.assertEqual((own["note"], own["signed"]), ("Our own voyage.", "Crew"))
        self.assertIn('"Our own voyage." (Crew)', caption_text(own))
        self.deck.config.update(postcard_note_mode="watcher", aster_thoughts="rare")
        self.assertEqual(self.capture()[0]["signed"], "Aster", "old automatic-mode token follows active identity")

    def test_plain_and_dry_context_notes_use_known_fields_only(self):
        cases = (({"facts": ["First footfall"]}, None, "", "first"),
                 ({"kind": "Water world"}, None, "", "rare"),
                 ({"region": "Outer Arm"}, 23000, "", "far"),
                 ({}, 100, "", "home"), ({}, None, "LANDED", "landed"),
                 ({}, None, "DOCKED", "docked"), ({"kind": "Black hole"}, None, "", "star"))
        for restrained in (False, True):
            for values, distance, state, moment in cases:
                with self.subTest(restrained=restrained, moment=moment):
                    card = {**postcard_card(RAW), **values}
                    rng = random.Random(2)
                    with patch.object(rng, "random", return_value=0.):
                        note = aster_postcards.postcard_note(card, restrained=restrained, from_sol=distance, state=state, rng=rng)
                    fields = {"place": "Sol 3", "kind": str(card.get("kind", "")).lower(),
                              "region": card.get("region", ""), "far": f"{distance:,.0f}" if distance is not None else ""}
                    bank = aster_postcards.PLAIN[moment] + (() if restrained else aster_postcards.DRY[moment])
                    self.assertIn(note, [line.format(**fields) for line in bank])
                    self.assertNotIn("{", note)
                    self.assertFalse(any(spoiler in note for spoiler in ("Mara", "Iven", "eleven days")))
        bare = postcard_card({})
        for seed in range(20):
            note = aster_postcards.postcard_note(bare, rng=random.Random(seed))
            self.assertTrue(note)
            self.assertNotIn("{", note)

    def test_station_foot_notes_describe_port_rather_than_a_surface(self):
        card = postcard_card({"System": "Sol"}, state="ONFOOT", station="Galileo")
        rng = random.Random(2)
        with patch.object(rng, "random", return_value=0.):
            note = aster_postcards.postcard_note(card, restrained=True, state="ONFOOT", rng=rng)
        self.assertIn(note, aster_postcards.PLAIN["docked"])

    def test_postcard_wording_cycle_survives_restart_and_a_change_of_place(self):
        path = self.root / "aster_memory.json"
        config = self.deck.config
        mind = AsterMind(path, config, rng=random.Random(2))
        self.deck.heartbeat_hud.mind = mind
        lines = []
        for index in range(12):
            if index == 5:
                mind.save()
                mind = AsterMind(path, config, rng=random.Random(9))
                self.deck.heartbeat_hud.mind = mind
            place = "Altair" if index < 5 else "Achenar"
            card = postcard_card({"System": place})
            note = self.deck._postcard_companion_note(card, None, "")
            lines.append(note.replace(place, "{place}"))
        self.assertEqual(set(lines), set(aster_postcards.PLAIN["any"] + aster_postcards.DRY["any"]))
        again = self.deck._postcard_companion_note(postcard_card({"System": "Achenar"}), None, "").replace("Achenar", "{place}")
        self.assertNotEqual(again, lines[-1], "no immediate repeat at the cycle boundary")

    def test_preview_changes_author_and_tone_without_consuming_live_rotation(self):
        mind = self.deck.heartbeat_hud.mind
        before = copy.deepcopy(mind.memory)
        captures = []
        real = postcard_picture.render_postcard
        def render(card, *args, **kwargs):
            captures.append(dict(card))
            return real(card, *args, **kwargs)
        with patch.object(postcard_picture, "render_postcard", side_effect=render):
            first = self.deck._postcard_preview_png()
            self.assertEqual(self.deck._postcard_preview_png(), first)
            self.assertEqual(len(captures), 1)
            self.assertEqual(captures[-1]["signed"], "Aster")
            key = self.deck._postcard_preview_key()
            self.deck.config["aster_humour"] = "off"
            self.assertNotEqual(self.deck._postcard_preview_key(), key)
            self.deck._postcard_preview_png()
            self.deck.config.update(companion_identity="watcher", heartbeat_thoughts="rare")
            watcher = self.deck._postcard_preview_png()
            self.assertEqual(captures[-1]["signed"], "the Watcher")
            self.assertNotEqual(first, watcher)
            self.deck.config["heartbeat_thoughts"] = "off"
            self.deck._postcard_preview_png()
            self.assertEqual(captures[-1]["note"], "")
        self.assertEqual(mind.memory, before)
        ARTIFACTS.mkdir(exist_ok=True)
        (ARTIFACTS / "aster-postcard-preview.png").write_bytes(first)
        (ARTIFACTS / "watcher-postcard-preview.png").write_bytes(watcher)

    def test_author_survives_background_save_caption_and_editor_after_switch(self):
        Image.new("RGB", (640, 360), (20, 60, 100)).save(self.root / "shot.png")
        card, worker = self.capture()
        pending = worker.call_args
        self.deck.config.update(companion_identity="watcher", heartbeat_thoughts="rare")
        self.deck.heartbeat_hud.mind = WatcherMind(None, self.deck.config)
        self.deck._postcard_develop(card, str(self.root), False, True, time.time(), sleep=lambda _: None,
                                    keep=True, palette={})
        saved = next((self.root / "cards").glob("*.png"))
        kept, settings, photo = postcard_picture.kept_card(str(saved))
        self.assertEqual((kept["note"], kept["signed"]), (card["note"], "Aster"))
        self.assertIn('(Aster)', (self.root / "shot.txt").read_text(encoding="utf-8"))
        self.assertNotIn('the Watcher', (self.root / "shot.txt").read_text(encoding="utf-8"))
        self.assertEqual(pending.kwargs["args"][0]["signed"], "Aster")
        row = self.deck.postcard_album().rows()[0]
        self.assertTrue(self.deck._postcard_edit_open(row["id"]))
        self.assertEqual(self.deck._postcard_editing["info"]["signed"], "Aster")

    def test_outgoing_mind_cannot_consume_another_companions_note_or_memory(self):
        outgoing = WatcherMind(None, {})
        before = copy.deepcopy(outgoing.memory)
        self.deck.heartbeat_hud.mind = outgoing
        card, _ = self.capture()
        self.assertEqual(card["signed"], "Aster")
        self.assertEqual(outgoing.memory, before)

    def test_legacy_and_own_signatures_are_preserved_in_text_captions(self):
        card = postcard_card(RAW, note="A view worth keeping.")
        self.assertIn('(the Watcher)', caption_text(card))
        card["signed"] = "CMDR Jeff"
        self.assertIn('(CMDR Jeff)', caption_text(card))


class AsterPostcardPageTests(unittest.TestCase):
    setUpClass = classmethod(editor_fixture.EditorPageTests.setUpClass.__func__)
    tearDownClass = classmethod(editor_fixture.EditorPageTests.tearDownClass.__func__)
    open_page = editor_fixture.EditorPageTests.open_page

    def test_studio_author_switches_and_saved_aster_signature_opens_in_editor(self):
        page = self.open_page(1)
        row = self.album.rows()[0]
        path = self.album.path(row["id"])
        card, settings, photo = postcard_picture.kept_card(path)
        card.update(note="A place in the voyage account.", signed="Aster")
        postcard_picture.keep_card(path, card, photo, settings)
        self.deck.config.update(companion_identity="aster", aster_thoughts="occasional")
        self.deck._postcard_album_cache = None
        self.publish("postcards")
        page.click('[data-pc-tab="studio"]')
        select = '[data-postcard-setting="postcard_note_mode"]'
        page.wait_for_function("document.querySelector('[data-postcard-setting=postcard_note_mode]')?.options[0].text === \"Aster's\"")
        self.assertEqual(page.input_value(select), "watcher")
        self.deck.config["companion_identity"] = "watcher"
        self.publish("postcards")
        page.wait_for_function("document.querySelector('[data-postcard-setting=postcard_note_mode]')?.options[0].text === \"The Watcher's\"")
        page.click('[data-pc-tab="album"]')
        page.locator('[data-postcard]').first.click()
        page.click('#pc-edit')
        page.wait_for_function("window.voidcompassPostcardEditor.state() !== null")
        layers = page.evaluate("window.voidcompassPostcardEditor.state().design.layers")
        self.assertEqual(next(layer["text"] for layer in layers if layer.get("role") == "signed"), "— Aster")

    def test_overlay_keeps_each_cards_original_signature_when_stacked(self):
        page = self.browser.new_page(viewport={"width": 380, "height": 520})
        self.addCleanup(page.close)
        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + overlay_fixture.STUB)
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")
        page.route("http://postcard.test/**", serve)
        page.goto("http://postcard.test/postcards/index.html?token=t&overlay=postcards")
        page.wait_for_function("Boolean(window.renderCards)")
        aster = {**postcard_card(RAW, now=1, note="A scenic use of archival space."), "signed": "Aster"}
        watcher = {**postcard_card(RAW, now=2, note="Another place. I keep them all."), "signed": "the Watcher"}
        render = "cards => renderCards({theme: {}, effects: {text_scale: 1}, postcards: {cards, options: {size: 'standard'}}})"
        page.evaluate(render, [aster])
        self.assertEqual(page.locator('.signed').all_text_contents(), ["Aster"])
        page.evaluate(render, [watcher, aster])
        self.assertEqual(page.locator('.signed').all_text_contents(), ["the Watcher", "Aster"])


if __name__ == "__main__":
    unittest.main()
