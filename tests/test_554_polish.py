"""5.5.4 polish: the Settings page patched in place with test answers by
their buttons, Piper kept warm, The Switch, Inara's steady sending and ship
loadouts, EDSM/Inara in the status bar, the Updates page, Save this spot and
the compass's fit, the Tools page, and postcard themes and editing."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from voidcompass.overlays import postcard_picture, postcard_themes, watcher_mind, watcher_voice_lore
from voidcompass.overlays.postcards import postcard_card, postcard_options
from voidcompass.services import inara
from voidcompass.voice import watcher_voice

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
APP = (WEB / "dashboard" / "app.js").read_bytes().decode("utf-8")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SettingsPageTests(unittest.TestCase):
    def test_patched_in_place_and_answers_by_the_button(self):
        self.assertIn("morphNode(shell, fresh.content.firstElementChild)", APP)
        self.assertIn("function showSettingsTestResult", APP)
        # Only beside the button: no status line under the section, no toast.
        self.assertNotIn("settings-test-status", APP)
        self.assertNotIn("lastSettingsTest", APP)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        for op in ('"op": "test_raven"', '"op": "test_inara"', '"op": operation'):
            self.assertIn(op, dashboard)

    def test_updates_has_its_own_page(self):
        updates = APP.split('if (id === "updates") {', 1)[1].split("const rebuildPanel", 1)[0]
        for needed in ("update-card", "HOW UPDATES WORK", "data-update-check", 'id="settings-update-state"'):
            self.assertIn(needed, updates)


class VoiceTests(unittest.TestCase):
    def test_kept_warm(self):
        self.assertGreater(watcher_voice.KEEP_WARM_S, 60)
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("# The voice warms up as the app loads", source)

    def test_the_switch(self):
        self.assertEqual(watcher_voice_lore.TITLE, "THE SWITCH")
        self.assertEqual(watcher_voice_lore.heading("Hello."), "THE SWITCH · 1 OF 8")
        self.assertEqual(watcher_mind.thought_heading("voice_found", "Hello.")[1], "THE SWITCH · 1 OF 8")
        self.assertIn("THE SWITCH", (WEB / "dashboard" / "watcher.js").read_text(encoding="utf-8"))


class InaraTests(unittest.TestCase):
    def uploader(self, clock, queue_path=None):
        config = {"inara_upload_enabled": True, "inara_api_key": "key", "active_commander_name": "insert3coins"}
        session = Mock()
        session.post.return_value.json.return_value = {"header": {"eventStatus": 200}, "events": []}
        return inara.InaraUploader(config, "5.5.4", session=session, clock=clock, queue_path=queue_path), session

    def test_jumps_go_about_once_a_minute_without_docking(self):
        now = [1000.0]
        up, session = self.uploader(lambda: now[0])

        class Inline:
            def __init__(self, target=None, args=(), **_kwargs):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)
        with patch.object(inara.threading, "Thread", Inline):
            up._last_send = 1000.0
            up.observe("FSDJump", {"timestamp": stamp(), "StarSystem": "A", "JumpDist": 30})
            now[0] += 30
            up.tick()
            self.assertEqual(session.post.call_count, 0, "not before the minute is up")
            now[0] += 40
            up.observe("FSDJump", {"timestamp": stamp(), "StarSystem": "B", "JumpDist": 30})
            up.tick()
        self.assertEqual(session.post.call_count, 1, "a jump every half minute no longer keeps the batch waiting")
        self.assertEqual(up.pending(), 0)

    def test_ship_loadouts_in_inaras_shape(self):
        events = inara.map_event("Loadout", {"Ship": "panthermkii", "ShipID": 110, "Modules": [
            {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_size7_class5", "On": True, "Priority": 0,
             "Health": 1.0, "Value": 1000, "Engineering": {"BlueprintName": "FSD_LongRange", "Level": 5, "Quality": 1.0,
                                                             "ExperimentalEffect": "special_fsd_heavy",
                                                             "Modifiers": [{"Label": "FSDOptimalMass", "Value": 3000,
                                                                            "OriginalValue": 2000, "LessIsGood": 0}]}}]})
        self.assertEqual([name for name, _data in events], ["setCommanderShip", "setCommanderShipLoadout"])
        module = events[1][1]["shipLoadout"][0]
        self.assertEqual((module["slotName"], module["itemName"], module["isOn"]), ("FrameShiftDrive", "int_hyperdrive_size7_class5", True))
        self.assertEqual(module["engineering"]["blueprintLevel"], 5)
        self.assertEqual(module["engineering"]["modifiers"][0], {"name": "FSDOptimalMass", "value": 3000,
                                                                 "originalValue": 2000, "lessIsGood": False})

    def test_cosmetics_are_not_modules(self):
        cosmetic = [("PaintJob", "paintjob_explorer_nx_02_11"), ("Decal1", "decal_distantworlds3"),
                    ("ShipName0", "nameplate_shipname_white"), ("Bobble02", "bobble_pilotfemale"),
                    ("ShipKitSpoiler", "explorer_nx_shipkita_spoiler2"), ("WeaponColour", "weaponcustomisation_red"),
                    ("EngineColour", "enginecustomisation_cyan"), ("StringLights", "string_lights_thargoidprobe"),
                    ("VesselVoice", "voicepack_celeste"), ("Hologram", "explorer_nx_holograma_02")]
        real = [("Armour", "explorer_nx_armour_grade1"), ("FrameShiftDrive", "int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii"),
                ("ShipCockpit", "explorer_nx_cockpit"), ("CargoHatch", "modularcargobaydoor"), ("Slot13_Size1", "int_supercruiseassist")]
        modules = [{"Slot": slot, "Item": item, "On": True, "Priority": 0, "Health": 1.0} for slot, item in cosmetic + real]
        sent = [row["slotName"] for row in inara.ship_loadout(modules)]
        self.assertEqual(sent, [slot for slot, _item in real])

    def test_damage_type_heat_and_why_inara_refused(self):
        weapon = {"Slot": "HugeHardpoint1", "Item": "hpt_multicannon_gimbal_huge", "On": True, "Priority": 0, "Health": 1.0,
                  "Engineering": {"BlueprintName": "Weapon_Overcharged", "Level": 5, "Quality": 1.0, "Modifiers": [
                      {"Label": "DamageType", "ValueStr": "$Thermic;", "ValueStr_Localised": "Thermal"},
                      {"Label": "Damage", "Value": 40.0, "OriginalValue": 30.0, "LessIsGood": 0}]}}
        events = inara.map_event("Loadout", {"Ship": "anaconda", "ShipID": 4, "Hot": True, "Modules": [weapon]})
        module = events[1][1]["shipLoadout"][0]
        self.assertEqual(module["engineering"]["modifiers"][0], {"name": "DamageType", "value": "$Thermic;"},
                         "Inara's own example: a text value, never null")
        self.assertTrue(module["isHot"], "the ship's heat when the module has none of its own")
        up, session = self.uploader(lambda: 1000.0)
        said = []
        up._say = lambda text, severity="INFO": said.append((severity, text))
        session.post.return_value.json.return_value = {"header": {"eventStatus": 200}, "events": [
            {"eventStatus": 200}, {"eventStatus": 400, "eventStatusText": "Invalid modifier"}]}
        up._send([{"eventName": "setCommanderShip", "eventTimestamp": stamp(), "eventData": {}},
                  {"eventName": "setCommanderShipLoadout", "eventTimestamp": stamp(), "eventData": {}}])
        self.assertIn(("WARN", "Inara refused setCommanderShipLoadout: Invalid modifier"), said)

    def test_closing_keeps_the_queue_instead_of_waiting(self):
        path = os.path.join(tempfile.mkdtemp(), "inara_queue.json")
        up, session = self.uploader(lambda: 1000.0, queue_path=lambda: path)
        up.observe("Rank", {"timestamp": stamp(), "Combat": 3})
        up.stop()
        session.post.assert_not_called()
        self.assertTrue(os.path.isfile(path))
        again, _session = self.uploader(lambda: 1000.0, queue_path=lambda: path)
        again._load_queue()
        self.assertEqual(again.pending(), 1)
        self.assertFalse(os.path.exists(path))

    def test_status_bar(self):
        from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
        deck = SimpleNamespace(config={"edsm_upload_enabled": True, "edsm_api_key": "k"}, _service_notes={},
                               inara=SimpleNamespace(enabled=lambda: True, stats={"status": "ok"}, pending=lambda: 3))
        states = HtmlDashboardMixin._html_service_states(deck, 1000.0)
        self.assertEqual(states["edsm"], {"state": "live", "label": "LIVE"})
        self.assertEqual(states["inara"], {"state": "recent", "label": "3 WAITING"})
        deck._service_notes = {"EDSM": ("WARN", 900.0)}
        self.assertEqual(HtmlDashboardMixin._html_service_states(deck, 1000.0)["edsm"]["state"], "warn")
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="inara-state"', html)
        self.assertIn('id="edsm-state"', html)


class CompassTests(unittest.TestCase):
    def test_save_this_spot(self):
        # 5.5.12: from ON THE GROUND into the Planetary page's new-site form.
        page = (WEB / "dashboard" / "planetary.js").read_text(encoding="utf-8")
        self.assertIn('data-po-op="save_spot"', page)
        self.assertIn("SAVE THIS SPOT AS A SITE", page)
        self.assertIn("form[data-new-site]", page)

    def test_the_compass_overlay_fits_its_window(self):
        page = (WEB / "ground" / "app.js").read_text(encoding="utf-8")
        self.assertIn("VoidCompassOverlay.fitToWindow(document.body, 420, effects)", page)


class ToolsTests(unittest.TestCase):
    def deck(self):
        from voidcompass.dashboard.dashboard_tools_mixin import DashboardToolsMixin
        deck = DashboardToolsMixin()
        deck.config = {"edsm_upload_enabled": True, "heartbeat_thoughts": "rare"}
        deck.heartbeat_hud = None
        deck.current_sys = "Sol"
        deck._persist_config = Mock()
        deck._apply_settings_changes = Mock()
        deck._html_overlay_toggle = Mock(return_value=True)
        deck._html_overlay_option_toggle = Mock(return_value=True)
        deck.music_remote = Mock(return_value=True)
        deck._html_copy_text = Mock(return_value=True)
        return deck

    def test_everything_in_one_place(self):
        deck = self.deck()
        data = deck._html_tools_workspace()
        self.assertTrue(any(row["id"] == "cargo_hud" for row in data["overlays"]))
        self.assertTrue(next(row for row in data["switches"] if row["key"] == "edsm_upload_enabled")["on"])
        groups = {row["id"] for row in data["groups"]}
        self.assertTrue(all(row["group"] in groups for row in data["overlays"]))
        self.assertEqual([row["id"] for row in data["overlays"] if row["group"] == "other"], [], "every overlay has its group")
        self.assertEqual(data["music"], {"state": "idle"})
        self.assertTrue(deck._handle_tools_command("setting", {"key": "inara_upload_enabled", "value": True}))
        self.assertTrue(deck.config["inara_upload_enabled"])
        deck._apply_settings_changes.assert_called_with({"inara_upload_enabled"})
        self.assertFalse(deck._handle_tools_command("setting", {"key": "journal_path", "value": True}), "only its own switches")
        self.assertTrue(deck._handle_tools_command("overlay", {"id": "cargo_hud"}))
        self.assertTrue(deck._handle_tools_command("music", {"action": "next"}))
        self.assertTrue(deck._handle_tools_command("copy_system", {}))
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page-name="tools"', html)
        self.assertIn("renderTools", APP)


class ExploreArchiveTests(unittest.TestCase):
    """The Exploration Archive is Explore & Survey's Archive tab: one page."""

    def test_one_page(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('data-page-name="analytics"', html)
        self.assertNotIn('data-page="analytics"', html)
        self.assertNotIn('data-target="analytics"', html)
        self.assertIn('data-page="explore" data-explore-view="archive"', html)
        explore = (WEB / "dashboard" / "explore.js").read_text(encoding="utf-8")
        self.assertIn('{id: "archive", label: "ARCHIVE"', explore)  # 5.6.1: plain tabs
        self.assertIn('id="analytics-workspace"', explore)
        self.assertIn('["chronicle", "CAPTAIN\'S LOG"]', APP)
        self.assertIn("renderExploreArchive(data.archive)", APP)
        from voidcompass.dashboard import html_dashboard
        self.assertNotIn("analytics", html_dashboard._HTML_WORKSPACE_PAGES)
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"archive": self._html_analytics_workspace()', source)


class PostcardThemeTests(unittest.TestCase):
    THEME = {"base": "airmail", "paper": "#202833", "ink": "#E8F0FF", "greet": "nonsense", "font": "hand",
             "filter": "mono", "angle": 40, "background": "colour", "bg_colour": "#2b1b3d"}

    def test_a_theme_kept_to_its_choices(self):
        theme = postcard_themes.normalize(self.THEME)
        self.assertEqual((theme["ink"], theme["greet"], theme["angle"]), ("#e8f0ff", "", 12.0))
        config = {"postcard_themes": {"Neon": theme}, "postcard_style": "theme:Neon"}
        self.assertEqual(postcard_themes.chosen(config), ("airmail", {**theme, "name": "Neon"}), "it knows its name (5.5.5)")
        self.assertEqual(postcard_options(config)["style"], "airmail")
        self.assertEqual(postcard_themes.chosen({"postcard_style": "theme:Gone"}), ("polaroid", None))

    def test_drawn_with_the_theme_and_a_background(self):
        from PIL import Image
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3"}, state="LANDED")
        card.update(note="Mine.", signed="CMDR insert3coins")
        photo = Image.new("RGB", (320, 180), (200, 40, 40))
        plain = postcard_picture.render_postcard(card, photo, {}, width=320)
        themed = postcard_picture.render_postcard(card, photo, {}, width=320, style="polaroid",
                                                  theme=postcard_themes.normalize(self.THEME))
        self.assertEqual(themed.getpixel((2, 2))[3], 255, "an opaque backdrop behind the card")
        self.assertEqual(plain.getpixel((2, 2))[3], 0, "see-through without one")

    def test_saved_postcards_can_be_edited(self):
        from PIL import Image
        from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
        folder = tempfile.mkdtemp()
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
        photo = Image.new("RGB", (320, 180), (10, 40, 90))
        path = postcard_picture.save_postcard_picture(card, photo, folder, {})
        postcard_picture.keep_card(path, card, photo, {"style": "polaroid", "theme": None})
        deck = DashboardKeepsakesMixin()
        deck.config = {}
        album = SimpleNamespace(path=lambda card_id: path if card_id == "abc" else None)
        deck.postcard_album = lambda: album
        self.assertTrue(deck._postcard_edit_open("abc"))
        self.assertEqual(deck._postcard_editing["title"], "Hatchooe")
        self.assertTrue(deck._postcard_edit_save("abc", {"title": "Home", "greeting": "Wish you were here",
                                                         "note": "Back again.", "signed": "Me", "style": "vintage",
                                                         "angle": "5"}))
        card_again, settings, _picture = postcard_picture.kept_card(path)
        self.assertEqual((card_again["title"], card_again["signed"], settings["style"]), ("Home", "Me", "vintage"))
        self.assertEqual(settings["theme"]["angle"], 5.0)
        self.assertFalse(deck._postcard_edit_open("missing"))

    def test_themes_saved_and_deleted_from_the_page(self):
        from PIL import Image
        from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
        deck = DashboardKeepsakesMixin()
        deck.config = {}
        deck._persist_config = Mock()
        out = io.BytesIO()
        Image.new("RGB", (64, 32), (1, 2, 3)).save(out, "PNG")
        picture = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
        with patch.object(postcard_themes, "folder", lambda: Path(tempfile.mkdtemp())):
            self.assertTrue(deck._postcard_save_theme({"name": "Sunset", "params": {"base": "vintage", "angle": 3},
                                                       "background_data": picture}))
            saved = deck.config["postcard_themes"]["Sunset"]
            self.assertEqual((saved["background"], saved["bg_image"]), ("image", "sunset.jpg"))
            self.assertEqual(deck.config["postcard_style"], "theme:Sunset")
            self.assertTrue(deck._postcard_delete_theme("Sunset"))
        self.assertEqual(deck.config["postcard_style"], "polaroid")

    def test_your_own_note(self):
        options = postcard_options({"postcard_note_mode": "own", "postcard_note_text": "  Hello   there "})
        self.assertEqual((options["note"], options["note_mode"], options["note_text"]), (False, "own", "Hello there"))
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        for needed in ('"postcard_note_mode"', "YOUR OWN THEME", "data-pc-edit", "EDIT THIS POSTCARD"):
            self.assertIn(needed, page)
        from voidcompass.core import config
        for key in ("postcard_note_mode", "postcard_note_text", "postcard_signature", "postcard_themes"):
            self.assertIn(key, config.PROFILE_SETTINGS)


if __name__ == "__main__":
    unittest.main()
