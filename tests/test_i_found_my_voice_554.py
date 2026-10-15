"""5.5.4, "I Found My Voice": the Watcher's voice (Piper, the HAL model), how
it finds it, what it learns of how you play, your home system, achievements
in their own overlay, the minimap's region names, echoes for every flight
style, Updates on its own Settings page, Inara, and removing carriers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import random
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from voidcompass.core import config as config_module, home_anchor
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR, OVERLAY_HOTKEY_SPECS
from voidcompass.overlays import (
    galaxy_minimap_hud, watcher_habits, watcher_idle, watcher_lines, watcher_lore, watcher_mind, watcher_voice_lore,
)
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD
from voidcompass.overlays.toast_hud import AchievementHUD, ToastHUD
from voidcompass.overlays.watcher_mind import WatcherMind
from voidcompass.services import carrier_tracker, inara
from voidcompass.voice import voice_assets, watcher_voice

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
BANNED = re.compile(r"\bdave\b|daisy|afraid i can't|marvin|thargoid|guardian|raxxla|dark wheel", re.I)


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SettingsRegisteredTests(unittest.TestCase):
    """New settings live in the PROFILE tuples (per commander)."""

    def test_every_new_setting_is_per_commander(self):
        for key in ("watcher_voice_speed", "watcher_voice_level", "home_system", "inara_api_key", "inara_cmdr_name",
                    "overlay_hotkey_achievements"):
            self.assertIn(key, config_module.PROFILE_TEXT_SETTINGS, key)
        for key in ("watcher_voice_enabled", "inara_upload_enabled", "achievement_overlay_enabled"):
            self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS, key)
        for key in ("watcher_voice_volume", "home_system_pos", "galaxy_minimap_region_text_percent",
                    "achievement_hud_x", "achievement_hud_y"):
            self.assertIn(key, config_module.PROFILE_VALUE_SETTINGS, key)


# -- the voice -----------------------------------------------------------------
class SpeakingTests(unittest.TestCase):
    def test_words_said_as_they_should_be_heard(self):
        said = watcher_voice.speakable("⟦Hatchooe⟧ is 12 ly away · CMDR [[sad|fine]], 30 T aboard at 21 °C")
        self.assertEqual(said, "Hatchooe is 12 light years away, Commander fine, 30 tonnes aboard at 21 degrees")

    def test_volume_and_loudness(self):
        self.assertEqual(watcher_voice.volume_gain(50), .5)
        self.assertEqual(watcher_voice.volume_gain("x"), .8)
        self.assertEqual(watcher_voice.volume_gain(250), 1.0)
        step = 22050 // watcher_voice.ENVELOPE_HZ
        levels = watcher_voice.envelope([0] * step + [1000] * step, 22050)
        self.assertEqual(levels, [0.0, 1.0])

    def test_newest_line_wins_and_close_is_instant(self):
        played = []
        speaker = watcher_voice.WatcherSpeaker(tempfile.mkdtemp(), player=played.append)
        speaker._start_worker = lambda: None  # nothing runs: only the queue is checked
        speaker.say("First thought.", key=1)
        speaker.say("Second thought.", key=2)
        self.assertEqual(speaker._pending["text"], "Second thought.")
        speaker._live = {"key": 2, "start": 0, "duration": 1, "envelope": []}
        proc = Mock()
        speaker._proc = proc
        speaker.close()
        self.assertEqual(played, [None], "playback stopped at once")
        proc.kill.assert_called_once()
        self.assertIsNone(speaker._pending)
        self.assertFalse(speaker.say("After close."), "nothing is said once closed")

    def test_shutdown_stops_the_voice_first(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        on_close = source.split("    def on_close(self):", 1)[1].split("\n    def ", 1)[0]
        self.assertLess(on_close.index("_watcher_voice_close()"), on_close.index("html_runtime"))


class VoiceDownloadTests(unittest.TestCase):
    def fixture(self, base, tamper=False):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("piper/piper.exe", b"engine")
            bundle.writestr("piper/espeak-ng-data/en", b"data")
        files = {"engine": archive.getvalue(), "hal.onnx": b"model", "hal.onnx.json": b"{}"}
        sha = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        if tamper:
            files["hal.onnx"] = b"something else"

        def opener(url):
            name = url.rsplit("/", 1)[-1]
            self.fetched.append(name)
            return io.BytesIO(files["engine"] if name.endswith(".zip") else files[name])
        engine = dict(voice_assets.ENGINE, sha256=sha["engine"], size=len(files["engine"]))
        model = tuple({"name": name, "sha256": sha[name], "size": len(files[name])} for name in ("hal.onnx", "hal.onnx.json"))
        return opener, engine, model

    def run_download(self, base, tamper=False):
        self.fetched = []
        opener, engine, model = self.fixture(base, tamper)
        with patch.object(voice_assets, "ENGINE", engine), patch.object(voice_assets, "MODEL_FILES", model):
            download = voice_assets.VoiceDownload(base, opener=opener)
            done = []
            download.start(done.append)
            download._thread.join(10)
            return download.state(), voice_assets.installed(base), done

    def test_downloads_checks_and_installs(self):
        base = tempfile.mkdtemp()
        state, ready, done = self.run_download(base)
        self.assertEqual(state["stage"], "done", state)
        self.assertTrue(ready)
        # Into models/, as the repo keeps it (5.5.4).
        self.assertTrue((Path(base) / "models" / "piper" / "piper.exe").is_file())
        self.assertTrue((Path(base) / "models" / "piper" / "espeak-ng-data" / "en").is_file())
        self.assertTrue((Path(base) / "models" / "hal9000" / "hal.onnx").is_file())
        self.assertFalse((Path(base) / "models" / ".engine-unpack").exists())
        self.assertEqual(done[0]["stage"], "done")
        (Path(base) / "models" / "hal9000" / "README.md").write_text("model card", encoding="utf-8")
        self.assertTrue(voice_assets.remove(base))
        self.assertFalse((Path(base) / "models" / "hal9000" / "hal.onnx").exists())
        self.assertFalse((Path(base) / "models" / "piper").exists())
        self.assertTrue((Path(base) / "models" / "hal9000" / "README.md").exists(), "only what the download brought")

    def test_a_model_already_in_place_is_not_fetched_again(self):
        base = tempfile.mkdtemp()
        folder = Path(base) / "models" / "hal9000"
        folder.mkdir(parents=True)
        (folder / "hal.onnx").write_bytes(b"model")
        (folder / "hal.onnx.json").write_bytes(b"{}")
        state, ready, _done = self.run_download(base)
        self.assertEqual(state["stage"], "done", state)
        self.assertTrue(ready)
        self.assertEqual(self.fetched, ["piper_windows_amd64.zip"], "a source checkout only needs the engine")

    def test_a_file_that_doesnt_match_its_checksum_is_refused(self):
        base = tempfile.mkdtemp()
        state, ready, _done = self.run_download(base, tamper=True)
        self.assertEqual(state["stage"], "failed")
        self.assertIn("checksum", state["error"])
        self.assertFalse(ready)
        self.assertFalse((Path(base) / "models" / "hal9000" / "hal.onnx").exists())

    def test_the_model_comes_from_our_repo_and_is_never_bundled(self):
        self.assertTrue(voice_assets.MODEL_URL.startswith("https://raw.githubusercontent.com/insert3coins/VoidCompass/"))
        build = (ROOT / "tools" / "build.py").read_text(encoding="utf-8")
        self.assertNotIn("models", build)
        self.assertIn("voice/", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("Douglas Rain", voice_assets.RIGHTS_NOTICE)


# -- finding its voice -------------------------------------------------------------
class FindingItsVoiceTests(unittest.TestCase):
    def test_a_word_then_whole_thoughts_over_an_hour(self):
        text = "Another jump, Commander. The stars here are older. I like them."
        self.assertEqual(watcher_voice_lore.spoken_part(text, 0), "Another...")
        self.assertEqual(watcher_voice_lore.spoken_part(text, 1), "Another jump, Commander. The...")
        self.assertEqual(watcher_voice_lore.spoken_part(text, 2), "Another jump, Commander.")
        self.assertEqual(watcher_voice_lore.spoken_part(text, 4), text)

    def test_hello_first_then_the_story_of_its_voice(self):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "off"}, clock, random.Random(1))
        mind.observe("LoadGame", {})
        self.assertIsNone(mind.find_voice(), "not until its voice is on")
        mind.voice_active = True
        clock.now += 30
        self.assertEqual(mind.find_voice()["text"], "Hello.")
        heard = ["hello"]
        for _ in range(120):
            clock.now += 60
            thought = mind.find_voice()
            if thought:
                heard.append(thought["key"] if "key" in thought else thought["text"])
        self.assertEqual(len(watcher_voice_lore.voice_memory(mind.memory)["told"]), len(watcher_voice_lore.PASSAGES))
        self.assertTrue(watcher_voice_lore.found(mind.memory))
        self.assertEqual(watcher_mind.thought_heading("voice_found", "Hello."), ("memory", "THE SWITCH · 1 OF 8"))

    def test_its_own_words(self):
        for _id, _minutes, words in watcher_voice_lore.PASSAGES:
            self.assertNotRegex(words, BANNED)
        for bank in (watcher_habits.NORMAL, watcher_habits.WEARY):
            for lines in bank.values():
                for line in lines:
                    self.assertNotRegex(line, BANNED)

    def test_voice_level_and_the_typing_follows_the_voice(self):
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.config = {"watcher_voice_level": "important"}
        hud.mind = SimpleNamespace(voice_active=True)
        hud.voice_listener = lambda words, key: True
        self.assertFalse(hud._speaks({"topic": "arrival", "importance": 0}))
        self.assertTrue(hud._speaks({"topic": "died", "importance": 3}))
        self.assertTrue(hud._speaks({"topic": "voice_found", "importance": 0}), "finding its voice is always said")
        hud.mind.voice_active = False
        self.assertFalse(hud._speaks({"topic": "died", "importance": 3}))
        page = (WEB / "heartbeat" / "app.js").read_text(encoding="utf-8")
        self.assertIn("thought.voice_full", page)
        self.assertIn("orb.voice?.(", page)


# -- what it learns -----------------------------------------------------------------
class HabitTests(unittest.TestCase):
    def test_it_counts_how_you_play_and_marks_milestones(self):
        memory = {}
        milestones = []
        for index in range(100):
            mark = watcher_habits.observe(memory, "FSDJump", {"JumpDist": 30, "StarClass": "K"})
            if mark:
                milestones.append(mark)
        self.assertEqual(milestones, [("jumps", 10), ("jumps", 50), ("jumps", 100)])
        watcher_habits.observe(memory, "MarketSell", {"Type": "gold", "Type_Localised": "Gold", "Count": 200,
                                                      "SellPrice": 60000, "AvgPricePaid": 50000})
        row = watcher_habits.habits(memory)
        self.assertEqual(row["profit"], 2_000_000)
        self.assertEqual(row["best"], ["Gold", 2_000_000])
        known = watcher_habits.fields(memory)
        self.assertEqual(known["flight"]["star"], "K-class stars")
        self.assertEqual(known["trade"]["sold"], "Gold")

    def test_how_it_speaks_depends_on_how_well_it_knows_you(self):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, clock, random.Random(3))
        for _ in range(30):
            watcher_habits.observe(mind.memory, "FSDJump", {"JumpDist": 30, "StarClass": "K"})
        stranger = watcher_habits.choices(mind.memory, 0, random.Random(1))[0]
        self.assertEqual(stranger[0], "habit_flight")
        self.assertIn("t0", stranger[1])
        friend = watcher_habits.choices(mind.memory, 3, random.Random(1))[0]
        self.assertIn("t2", friend[1])
        bank = watcher_lines.NORMAL["habit_flight"]
        self.assertTrue(any(line.startswith("{t0}") for line in bank) and any(line.startswith("{t2}") for line in bank))
        thought = mind.consider("habit_flight", stranger[1], force=True)
        self.assertNotIn("{", thought["text"])
        heard = mind.memory["said"][-2][0]
        both = list(bank) + list(watcher_lines.WEARY["habit_flight"])  # the default nature is weary
        template = next(line for line in both if f"habit_flight:{__import__('zlib').crc32(line.encode('utf-8')):08x}" == heard)
        self.assertTrue(template.startswith("{t0}"), "a stranger hears a stranger's words")

    def test_its_memory_of_you_survives_a_restart(self):
        path = Path(tempfile.mkdtemp()) / "watcher_memory.json"
        mind = WatcherMind(path, {}, Clock())
        watcher_habits.observe(mind.memory, "FSDJump", {"JumpDist": 30})
        watcher_voice_lore.add_minutes(mind.memory, 12)
        mind.memory["postcards"] = [{"system": "Sol"}]
        mind.save()
        again = WatcherMind(path, {}, Clock())
        self.assertEqual(watcher_habits.habits(again.memory)["jumps"], 1)
        self.assertEqual(watcher_voice_lore.minutes(again.memory), 12)
        self.assertEqual(again.memory["postcards"], [{"system": "Sol"}], "kept postcards were lost on restart before")

    def test_the_page_shows_what_it_knows(self):
        memory = {}
        for _ in range(25):
            watcher_habits.observe(memory, "FSDJump", {"JumpDist": 20, "StarClass": "M"})
        summary = watcher_habits.summary(memory, 1)
        self.assertEqual(summary["facts"][0], {"label": "JUMPS", "value": "25 · 500 LY"})
        page = (WEB / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        for needed in ("WHAT IT KNOWS OF YOU", 'data-watcher-tab="settings"', 'data-watcher-tab="voice"',
                       "TEST THE VOICE", "watcher-voice-rights"):
            self.assertIn(needed, page)


# -- home --------------------------------------------------------------------------
class HomeTests(unittest.TestCase):
    COLONIA = [-9530.5, -910.28, 19808.125]

    def test_sol_unless_set_and_found(self):
        self.assertEqual(home_anchor.home({})["name"], "Sol")
        self.assertEqual(home_anchor.home({"home_system": "Colonia"})["name"], "Sol", "not found yet: still Sol")
        custom = home_anchor.home({"home_system": "Colonia", "home_system_pos": self.COLONIA})
        self.assertTrue(custom["custom"])
        self.assertAlmostEqual(home_anchor.distance(self.COLONIA, {"home_system": "Colonia", "home_system_pos": self.COLONIA}), 0)
        rows = [["t", "Sol", 0, 0, 0], ["t", "Colonia", *self.COLONIA]]
        self.assertEqual(home_anchor.from_history(rows, "colonia"), self.COLONIA)

    def test_the_watcher_and_the_minimap_measure_from_home(self):
        home = {"name": "Colonia", "pos": self.COLONIA, "custom": True}
        near = watcher_idle.Surroundings()
        near.observe("FSDJump", {"StarSystem": "Ratraii", "StarPos": [-9520.0, -910.0, 19800.0], "StarClass": "K"})
        topics = dict(near.choices(0, random.Random(1), {"home": home}))
        self.assertEqual(topics["idle_home_away"]["home"], "Colonia")
        self.assertTrue(all("{home}" in line or "Sol" not in line for line in watcher_lines.NORMAL["idle_far"]))
        model = galaxy_minimap_hud.build_minimap_model([], position=[-9520.0, -910.0, 19800.0], system="Ratraii", home=home)
        self.assertTrue(model["home"]["custom"])
        self.assertLess(model["here"]["from_home"], 20)
        page = (WEB / "galaxy_minimap" / "app.js").read_text(encoding="utf-8")
        self.assertIn("here.from_home", page)


# -- achievements in their own overlay -------------------------------------------------
class AchievementOverlayTests(unittest.TestCase):
    def test_its_own_overlay_switch_and_place(self):
        spec = OVERLAY_SPEC_BY_ATTR["achievement_hud"]
        self.assertEqual((spec.enabled_key, spec.x_key, spec.y_key),
                         ("achievement_overlay_enabled", "achievement_hud_x", "achievement_hud_y"))
        self.assertIn("overlay_hotkey_achievements", [row[1] for row in OVERLAY_HOTKEY_SPECS])
        self.assertEqual((AchievementHUD.X_KEY, ToastHUD.X_KEY), ("achievement_hud_x", "toast_hud_x"))

    def test_unlocks_go_to_the_achievements_overlay_only(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        deck = MainDashboard.__new__(MainDashboard)
        deck.config = {}
        deck.heartbeat_hud = None
        deck.toast_hud = Mock()
        deck.achievement_hud = Mock()
        deck.add_event_feed_entry = Mock()
        deck._schedule_html_dashboard_publish = Mock()
        deck._ui_post = lambda callback, *args, **kwargs: callback(*args)
        deck._on_achievement_unlocked({"title": "Star Hopper", "points": 100})
        deck.achievement_hud.push.assert_called_once()
        deck.toast_hud.push.assert_not_called()
        deck.achievement_hud = None
        deck._on_achievement_unlocked({"title": "Star Hopper", "points": 100})
        deck.toast_hud.push.assert_not_called()

    def test_settings_no_longer_duplicate_the_switch(self):
        source = (WEB / "dashboard" / "app.js").read_bytes().decode("utf-8")
        self.assertNotIn('key: "achievement_notifications_enabled"', source)
        self.assertIn('data-studio-settings="achievement_hud"', (WEB / "dashboard" / "index.html").read_text(encoding="utf-8"))


# -- minimap region names ------------------------------------------------------------
class RegionNameSizeTests(unittest.TestCase):
    def test_their_own_size(self):
        self.assertEqual(galaxy_minimap_hud.minimap_options({"galaxy_minimap_region_text_percent": "150"})["region_text"], 150)
        self.assertEqual(galaxy_minimap_hud.minimap_options({})["region_text"], 0)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-studio-setting="galaxy_minimap_region_text_percent"', html)
        self.assertIn("model.options?.region_text", (WEB / "galaxy_minimap" / "app.js").read_text(encoding="utf-8"))


# -- echoes for everyone ----------------------------------------------------------------
class EchoTests(unittest.TestCase):
    def test_every_flight_style_can_find_them(self):
        self.assertEqual(watcher_lore.echo_for("Docked", {"StationType": "MegaShip"}), "lore_great_ship")
        self.assertEqual(watcher_lore.echo_for("JetConeBoost", {}), "lore_neutron")
        self.assertEqual(watcher_lore.echo_for("Scan", {"StarType": "N"}), "lore_neutron")
        self.assertEqual(watcher_lore.echo_for("TechnologyBroker", {"BrokerType": "guardian"}), "lore_builders")
        self.assertEqual(watcher_lore.echo_for("MaterialCollected", {"Name": "guardian_sentinel_weaponparts"}), "lore_builders")
        self.assertEqual(watcher_lore.echo_for("MaterialCollected", {"Name": "tg_causticshard"}), "lore_sound")
        self.assertEqual(watcher_lore.echo_for("FactionKillBond", {"VictimFaction": "$faction_Thargoid;"}), "lore_sound")
        self.assertEqual(watcher_lore.distance_echoes(25_000), ["lore_far"])
        self.assertEqual(watcher_lore.distance_echoes(60_000), ["lore_far", "lore_core"])

    def test_a_trader_far_from_anywhere_still_hears_the_far_echo(self):
        mind = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, Clock(), random.Random(2))
        mind.observe("LoadGame", {})
        watcher_habits.habits(mind.memory)["ly"] = 19_995.0
        mind.observe("FSDJump", {"StarSystem": "Sol", "StarPos": [0, 0, 0], "JumpDist": 10})
        self.assertIn("lore_far", mind.memory["echoes"])

    def test_the_page_says_it_will_surface_anyway(self):
        memory = {"lore": [[row[0], 1.0] for row in watcher_lore.FRAGMENTS if row[5] < len(watcher_lore.CHAPTERS)],
                  "afterword": 1.0}
        page = watcher_lore.page(memory, 999, 400, now=1_800_000_000.0)
        xi = next(chapter for chapter in page["chapters"] if chapter["numeral"] == "XI")
        self.assertTrue(any(line.startswith("Or it surfaces anyway") for line in xi["unlock"]), xi["unlock"])


# -- updates ------------------------------------------------------------------------
class UpdatesPageTests(unittest.TestCase):
    def test_its_own_settings_page(self):
        source = (WEB / "dashboard" / "app.js").read_bytes().decode("utf-8")
        self.assertIn('{id: "updates", title: "Updates"', source)
        updates = source.split('if (id === "updates") {', 1)[1].split("\n  }", 1)[0]
        self.assertIn("data-update-check", updates)
        diagnostics = source.split('const rebuildPanel = ', 1)[1].split("function settingsHealthDetail", 1)[0]
        self.assertNotIn('settingGroup("UPDATES"', diagnostics)


# -- inara --------------------------------------------------------------------------
class FakeSession:
    def __init__(self, header_status=200):
        self.sent = []
        self.header_status = header_status

    def post(self, url, json=None, timeout=None, headers=None):
        self.sent.append(json)
        status = self.header_status

        class Reply:
            def raise_for_status(self):
                pass

            def json(self):
                return {"header": {"eventStatus": status, "eventStatusText": "Invalid API key"},
                        "events": [{"eventStatus": 200} for _ in json["events"]]}
        return Reply()


class InaraTests(unittest.TestCase):
    def uploader(self, status=200):
        clock = Clock(10_000.0)
        config = {"inara_upload_enabled": True, "inara_api_key": "key", "active_commander_name": "insert3coins",
                  "active_commander_fid": "F104074"}
        session = FakeSession(status)
        up = inara.InaraUploader(config, "5.5.4", session=session, clock=clock)
        up.flush = lambda force=False, _flush=up.flush: _flush(force=True)
        return up, session, clock

    def test_journal_to_inara(self):
        events = inara.map_event("FSDJump", {"StarSystem": "Sol", "StarPos": [0, 0, 0], "JumpDist": 8.21},
                                 {"ship_type": "panthermkii", "ship_id": 110})
        self.assertEqual(events, [("addCommanderTravelFSDJump", {"starsystemName": "Sol", "starsystemCoords": [0, 0, 0],
                                                                 "jumpDistance": 8.21, "isTaxiShuttle": False,
                                                                 "shipType": "panthermkii", "shipGameID": 110})])
        materials = inara.map_event("Materials", {"Raw": [{"Name": "iron", "Count": 30}], "Encoded": [{"Name": "shieldsoakanalysis", "Count": 2}]})
        self.assertEqual(materials[0][0], "setCommanderInventoryMaterials")
        self.assertEqual(len(materials[0][1]), 2)
        self.assertEqual(inara.map_event("Died", {}), [], "a death with nobody named isn't sent")

    def test_live_game_only(self):
        self.assertTrue(inara.live_game("4.2.1.0"))
        self.assertFalse(inara.live_game("3.8.0.404"))
        self.assertFalse(inara.live_game("4.1.0.100 beta"))

    def test_polite_batches_once_each(self):
        up, session, _clock = self.uploader()
        stamp = now_stamp()
        up.observe("Rank", {"timestamp": stamp, "Combat": 3})
        up.observe("Progress", {"timestamp": stamp, "Combat": 40})
        up.observe("Rank", {"timestamp": stamp, "Combat": 3})
        self.assertEqual(up.pending(), 1, "ranks and progress go together, and once")
        up.observe("Docked", {"timestamp": stamp, "StarSystem": "Sol", "StationName": "Abraham Lincoln", "MarketID": 1})
        up._send(up._queue[:])  # what flush would send, on this thread
        header = session.sent[0]["header"]
        self.assertEqual((header["appName"], header["appVersion"], header["APIkey"], header["commanderName"]),
                         ("VoidCompass", "5.5.4", "key", "insert3coins"))
        ranks = next(row for row in session.sent[0]["events"] if row["eventName"] == "setCommanderRankPilot")
        self.assertEqual(ranks["eventData"], [{"rankName": "combat", "rankValue": 3, "rankProgress": .4}])

    def test_old_and_startup_travel_stay_home(self):
        up, _session, _clock = self.uploader()
        self.assertEqual(up.observe("FSDJump", {"timestamp": "2020-01-01T00:00:00Z", "StarSystem": "Sol"}), 0)
        self.assertEqual(up.observe("FSDJump", {"timestamp": now_stamp(), "StarSystem": "Sol"}, startup=True), 0)
        self.assertEqual(up.observe("LoadGame", {"timestamp": now_stamp(), "Credits": 5}, startup=True), 1)

    def test_a_rejected_key_stops_uploads(self):
        up, _session, _clock = self.uploader(status=400)
        up.observe("Rank", {"timestamp": now_stamp(), "Combat": 3})
        up._send(up._queue[:])
        self.assertFalse(up.enabled())
        self.assertEqual(up.stats["status"], "rejected")
        up.reset_block()
        self.assertTrue(up.enabled())

    def test_settings_and_the_feed(self):
        source = (WEB / "dashboard" / "app.js").read_bytes().decode("utf-8")
        self.assertIn('settingGroup("INARA"', source)
        self.assertIn('data-ws-op="test_inara"', source)
        deck = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("self.inara.set_log_callback", deck)
        self.assertTrue((ROOT / "inara.md").is_file())


# -- carriers -----------------------------------------------------------------------
class CarrierRemovalTests(unittest.TestCase):
    def tracker(self):
        queue = SimpleNamespace(submit_json=lambda *args, **kwargs: None)
        patcher = patch.object(carrier_tracker, "persistence_queue", return_value=queue)
        patcher.start()
        self.addCleanup(patcher.stop)
        tracker = carrier_tracker.CarrierTracker()
        tracker.set_config({"carrier_state_file": str(Path(tempfile.mkdtemp()) / "carriers.json")})
        for carrier_id, kind in ((1, "FleetCarrier"), (2, "SquadronCarrier")):
            tracker.process_event({"event": "CarrierStats", "timestamp": "2026-10-01T10:00:00Z", "CarrierID": carrier_id,
                                   "CarrierType": kind, "Callsign": f"ABC-{carrier_id}"})
        return tracker

    def ids(self, tracker):
        return [row["carrier_id"] for row in tracker.carriers()]

    def test_remove_and_stay_removed(self):
        tracker = self.tracker()
        self.assertTrue(tracker.remove_carrier(1))
        self.assertEqual(self.ids(tracker), [2])
        tracker.process_event({"event": "CarrierStats", "timestamp": "2026-10-01T12:00:00Z", "CarrierID": 1,
                               "CarrierType": "FleetCarrier"})
        self.assertEqual(self.ids(tracker), [2], "an older event doesn't bring it back")

    def test_scrapped_and_left_behind_go_by_themselves(self):
        tracker = self.tracker()
        tracker.process_event({"event": "LeftSquadron", "timestamp": "2026-10-02T10:00:00Z"})
        self.assertEqual(self.ids(tracker), [1])
        tracker.process_event({"event": "CarrierDecommission", "timestamp": "2026-10-03T10:00:00Z", "CarrierID": 1,
                               "ScrapTime": 4_000_000_000})
        self.assertEqual(self.ids(tracker), [1], "not yet scrapped")
        tracker.process_event({"event": "CarrierCancelDecommission", "timestamp": "2026-10-04T10:00:00Z", "CarrierID": 1})
        self.assertIsNone(tracker.carriers()[0]["decommission_at"])
        tracker.process_event({"event": "CarrierDecommission", "timestamp": "2026-10-05T10:00:00Z", "CarrierID": 1,
                               "ScrapTime": 1_000})
        self.assertEqual(self.ids(tracker), [])
        tracker.process_event({"event": "CarrierBuy", "timestamp": "2026-10-10T10:00:00Z", "CarrierID": 1,
                               "CarrierType": "FleetCarrier", "Callsign": "NEW-111"})
        self.assertEqual(self.ids(tracker), [1], "a carrier bought again shows again")

    def test_the_page_asks_twice(self):
        source = (WEB / "dashboard" / "app.js").read_bytes().decode("utf-8")
        self.assertIn('data-ws-op="remove_carrier"', source)
        self.assertIn("PRESS AGAIN TO REMOVE", source)


if __name__ == "__main__":
    unittest.main()
