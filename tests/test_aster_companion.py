"""5.7.4: Aster's independent persona, paced story, profile settings and shared voice assets."""
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from voidcompass.core import companions, config
from voidcompass.overlays import aster_lines, aster_lore, watcher_copilot, watcher_ship, watcher_mind
from voidcompass.overlays.aster_mind import AsterMind
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD, _memory_path, orb_size
from voidcompass.overlays.watcher_mind import WatcherMind
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.dashboard.dashboard_watcher_listen_mixin import DashboardWatcherListenMixin
from voidcompass.voice import voice_assets, watcher_voice


class Clock:
    now = 1800000000.
    def __call__(self):
        return self.now


class AsterMindTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.config = {"companion_identity": "aster", "aster_thoughts": "chatty"}
        self.mind = AsterMind(None, self.config, clock=self.clock, rng=random.Random(2))

    def test_all_greetings_and_capabilities_cycle_without_repeats(self):
        for phrase, pool in (("Hello Aster", aster_lines.GREETINGS), ("Aster, what can you do?", aster_lines.CAPABILITIES)):
            answers = []
            for _ in pool:
                self.assertTrue(self.mind.talk(phrase))
                answers.append(self.mind.thought["text"])
            self.assertEqual(set(answers), set(pool))
            self.assertEqual(len(answers), len(set(answers)))
        self.assertEqual(len(aster_lines.GREETINGS), 50)
        self.assertEqual(len(aster_lines.CAPABILITIES), 10)

    def test_active_address_preserves_commands_and_asteroid(self):
        self.assertEqual(companions.addressed("Aster, open the galaxy map", "aster"), "open the galaxy map")
        self.assertEqual(companions.addressed("Hey Aster: open the system map", "aster"), "open the system map")
        self.assertEqual(companions.addressed("asteroid prices", "aster"), "asteroid prices")
        self.mind.lookup_provider = lambda words: ["We are in Sol."]
        self.mind.talk("Aster, where are we?")
        self.assertEqual(self.mind.thought["text"], "We are in Sol.")
        self.assertEqual(self.mind.spoken_words(self.mind.thought), "We are in Sol.")

    def test_own_replies_cover_shared_action_outcomes(self):
        self.assertTrue(set(watcher_ship.REPLIES) <= set(aster_lines.COMMANDS))
        self.assertTrue(set(watcher_copilot.REPLIES) <= set(aster_lines.COMMANDS))
        self.assertIn(watcher_ship.reply("focus_failed", self.mind.random), aster_lines.COMMANDS["focus_failed"])
        self.assertIn(watcher_copilot.reply("plain", self.mind.random), aster_lines.COMMANDS["plain"])

    def test_original_story_only_in_order_with_settling_spacing_and_danger(self):
        self.mind.session_start()
        self.mind.memory["hours"] = 500
        self.assertIsNone(self.mind.remember())
        self.clock.now += aster_lore.SETTLE_S + 1
        waited_days = 0
        for row in aster_lore.PASSAGES:
            thought = self.mind.remember()
            # Chapters VII and VIII also wait real days after the chapter before.
            while thought is None and waited_days < 10:
                self.clock.now += 86400
                waited_days += 1
                thought = self.mind.remember()
            self.assertEqual(thought["text"], row[5])
            self.assertTrue(thought["heading"].startswith("HANDOVER"), thought["heading"])
            self.assertIsNone(self.mind.remember(), "not twice in one quiet period")
            self.clock.now += aster_lore.GAP_S + 1
        self.assertEqual(waited_days, 5, "two days before chapter VII, three before VIII")
        self.assertIsNone(self.mind.remember())
        self.assertTrue(aster_lore.page(self.mind.memory, 500)["complete"])
        self.assertEqual(len(aster_lore.PASSAGES), 48)
        self.assertEqual(len(aster_lore.CHAPTERS), 8)
        fresh = AsterMind(None, self.config, clock=self.clock)
        fresh.session_start(); fresh.memory["hours"] = 500
        self.clock.now += aster_lore.SETTLE_S + 1
        fresh._in_danger = True
        self.assertIsNone(fresh.remember())

    def test_story_gates_have_event_and_time_alternatives_and_no_spoilers(self):
        story = aster_lore.STORY
        page = aster_lore.page({}, 0)
        self.assertTrue(all(row["title"] == "Unopened" and not row["told"] and not row["account"] for row in page["chapters"]))
        self.assertTrue(all(row["unlock"] for row in page["chapters"]), "every unopened chapter says how it opens")
        for index, chapter in enumerate(aster_lore.CHAPTERS):
            gate = chapter["gate"]
            if not gate:
                continue
            start = chapter["hours"][0]
            self.assertFalse(story.gate_met({}, index, start))
            self.assertTrue(story.gate_met({"aster_marks": {gate["signals"][0]: gate["count"]}}, index, start))
            self.assertTrue(story.gate_met({}, index, start + story.grace_hours), "time alone opens every chapter")
        self.mind.observe("FSDJump", {"StarSystem": "Sol"})
        self.mind.observe("FSDJump", {"StarSystem": "Achenar"})
        self.mind.observe("FSDJump", {"StarSystem": "Sol"})
        self.mind.observe("Docked", {"StationName": "Galileo"})
        self.mind.observe("MarketSell", {})
        self.assertEqual(self.mind.memory["aster_marks"], {"jump": 3, "return": 1, "arrival": 1, "delivery": 1})
        self.mind.observe("Shutdown", {})
        self.assertFalse(self.mind.memory.get("echoes"), "no echo before its chapter is heard")
        # Aster writes its own watch notes at shutdown, never the Watcher's dreams.
        self.assertIn(self.mind.memory["dreams"][-1]["text"].split(": ")[0].split(".")[0],
                      " ".join(self.mind.persona.keepsakes.NOTES))
        self.assertIsNone(self.mind.find_voice())
        self.assertIsNone(self.mind.pending_question())

    def test_restraint_and_frequency_are_independent(self):
        self.config.update(heartbeat_thoughts="off", aster_thoughts="chatty", aster_humour="off")
        self.assertIsNotNone(self.mind.consider("quiet", force=True))
        self.assertIn(self.mind.thought["text"], aster_lines.RESTRAINED_EVENTS["quiet"])
        self.config["aster_thoughts"] = "off"
        self.assertIsNone(self.mind.consider("quiet", force=True))

    def test_every_shutdown_report_separates_completed_jumps_from_its_farewell(self):
        for humour in ("dry", "off"):
            with self.subTest(humour=humour):
                mind = AsterMind(None, dict(self.config, aster_humour=humour), clock=self.clock, rng=random.Random(2))
                mind.observe("LoadGame")
                self.clock.now += 7200
                mind.observe("Shutdown")
                variants = aster_lines.event_lines("sign_off", humour == "off")
                heard = []
                for _ in variants:
                    thought = mind.note("sign_off", {"summary": "19 jumps", "hours": "2h 00m"})
                    self.assertEqual(thought["topic"], "sign_off")
                    # The summary has no punctuation of its own. Aster must
                    # finish its sentence before starting the farewell.
                    self.assertIn("19 jumps. ", thought["text"])
                    self.assertRegex(thought["text"], r"(?:record|manifest|session|account): 19 jumps\.")
                    self.assertIn("19 jumps. ", mind.spoken_words(thought))
                    heard.append(thought["text"])
                self.assertEqual(len(heard), len(set(heard)))

    def test_shutdown_uses_captains_log_totals_and_saves_the_report_immediately(self):
        from voidcompass.dashboard.dashboard import MainDashboard

        for humour in ("dry", "off"):
            for counts in ({"jumps": 19}, {"jumps": 19, "first_discoveries": 2, "biology_sales": 500000}, {"jumps": 0}):
                with self.subTest(humour=humour, counts=counts), tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "aster_memory.json"
                    mind = AsterMind(path, dict(self.config, aster_humour=humour), clock=self.clock, rng=random.Random(4))
                    mind.observe("LoadGame")
                    self.clock.now += 7200
                    mind.observe("Shutdown")
                    session = {"started": "2026-11-04T01:00:00Z", "ended": "2026-11-04T03:00:00Z", **counts}
                    note = Mock(wraps=mind.note)
                    deck = SimpleNamespace(heartbeat_hud=SimpleNamespace(note=note),
                                           captains_log=SimpleNamespace(sessions=lambda: [session]),
                                           nav_route_entries=[{"StarSystem": "A different itinerary"}],
                                           route_remaining_jumps=777)
                    MainDashboard._watcher_sign_off(deck)
                    expected = watcher_mind.session_summary(session)
                    self.assertEqual(note.call_args.args, ("sign_off", {"summary": expected, "hours": "2h 00m"}))
                    thought = mind.thought
                    self.assertNotIn("777", thought["text"])
                    if expected:
                        self.assertEqual(thought["topic"], "sign_off")
                        self.assertIn(expected + ". ", thought["text"])
                    else:
                        self.assertEqual(thought["topic"], "sign_off_quiet")
                        self.assertNotIn("jumps", thought["text"])
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(saved["log"][-1][1:], [thought["topic"], thought["text"]])
                    self.assertEqual(saved["aster_event_last"][thought["topic"]], saved["said"][-2][0])

    def test_minor_remarks_exhaust_the_bank_then_keep_quiet(self):
        heard = []
        for _ in aster_lines.EVENTS['quiet']:
            heard.append(self.mind.consider('quiet', force=True)['text'])
            self.clock.now += 600
        self.assertEqual(len(heard), len(set(heard)))
        self.assertIsNone(self.mind.consider('quiet', force=True))
        self.clock.now += 3 * 86400 + 1
        self.assertIsNotNone(self.mind.consider('quiet', force=True))
        # Necessary warnings still speak even when every wording has been used.
        for _ in range(len(aster_lines.EVENTS['danger']) + 1):
            self.assertIsNotNone(self.mind.consider('danger', force=True))
            self.clock.now += 1

    def test_old_headlines_and_idle_topics_do_not_keep_returning(self):
        self.assertIsNotNone(self.mind.consider('idle_galnet', {'headline': 'An old report'}, force=True))
        self.clock.now += 3600
        self.assertIsNone(self.mind.consider('idle_galnet', {'headline': 'An old report'}, force=True))
        self.assertIsNotNone(self.mind.consider('idle_galnet', {'headline': 'A different report'}, force=True))
        self.assertIsNotNone(self.mind.consider('idle_self', force=True))
        self.clock.now += 1200
        self.assertIsNone(self.mind.consider('idle_self'))

    def test_command_wording_rotates_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'aster_memory.json'
            mind = AsterMind(path, self.config, clock=self.clock, rng=random.Random(3))
            first = watcher_copilot.reply('music_next', mind.random)
            mind.save()
            resumed = AsterMind(path, self.config, clock=self.clock, rng=random.Random(3))
            cycle = [first] + [watcher_copilot.reply('music_next', resumed.random) for _ in range(len(aster_lines.COMMANDS['music_next']) - 1)]
            self.assertEqual(len(cycle), len(set(cycle)))
            self.assertNotEqual(watcher_copilot.reply('music_next', resumed.random), cycle[-1])
        self.assertTrue(self.mind.talk("Hello Aster"), "direct replies work with idle thoughts disabled")

    def test_separate_files_survive_switch_and_inactive_hours_do_not_grow(self):
        with tempfile.TemporaryDirectory() as folder, patch("voidcompass.core.config.get_profile_file", side_effect=lambda profile, filename: str(Path(folder) / filename)):
            settings = {"active_profile": "cmdr", "companion_identity": "watcher", "heartbeat_thoughts": "off"}
            path = _memory_path(settings)
            old = WatcherMind(path, settings, clock=self.clock)
            old.memory["lore"] = [["watcher-only", self.clock.now]]
            old.save()
            original = Path(path).read_bytes()
            settings["companion_identity"] = "aster"
            aster = companions.create_mind(_memory_path(settings), settings, clock=self.clock)
            self.assertIsInstance(aster, AsterMind)
            self.assertFalse(aster.memory["lore"])
            aster.memory["lore"] = [[aster_lore.PASSAGES[0][0], self.clock.now]]
            aster.save()
            self.clock.now += 99999
            self.assertEqual(Path(path).read_bytes(), original)
            reloaded = companions.create_mind(_memory_path(settings), settings, clock=self.clock)
            self.assertEqual(reloaded.memory["hours"], 0)
            self.assertEqual(reloaded.memory["lore"], aster.memory["lore"])

    def test_edited_conversation_aliases_keep_their_default_phrase_policy(self):
        from voidcompass.core import voice_commands
        self.config["watcher_ship_commands"] = voice_commands.validate({"app_greeting": {
            "name": "Officer greeting", "phrase": "report for duty", "aliases": ["good watch"], "keep_defaults": False}})
        self.mind.talk("Aster, good watch")
        self.assertIn(self.mind.thought["text"], aster_lines.GREETINGS)
        self.mind.talk("Hello Aster")
        self.assertNotIn(self.mind.thought["text"], aster_lines.GREETINGS)

    def test_live_hud_switch_saves_old_mind_and_preserves_providers(self):
        with tempfile.TemporaryDirectory() as folder, patch("voidcompass.core.config.get_profile_file", side_effect=lambda profile, filename: str(Path(folder) / filename)):
            settings = {"companion_identity": "watcher"}
            hud = HeartbeatHUD.__new__(HeartbeatHUD)
            hud.config = settings
            hud._mind_path = _memory_path(settings)
            hud.mind = WatcherMind(hud._mind_path, settings, clock=self.clock)
            lookup, action = Mock(), Mock()
            hud.mind.lookup_provider, hud.mind.action_provider = lookup, action
            hud.companion_listener = Mock()
            hud.mind.memory["lore"] = [["old-watcher-story", self.clock.now]]
            settings["companion_identity"] = "aster"
            hud._check_profile()
            self.assertIsInstance(hud.mind, AsterMind)
            self.assertIs(hud.mind.lookup_provider, lookup)
            self.assertIs(hud.mind.action_provider, action)
            self.assertEqual(json.loads((Path(folder) / "watcher_memory.json").read_text())["lore"][0][0], "old-watcher-story")
            self.assertFalse(hud.mind.memory["lore"])
            hud.companion_listener.assert_called_once()

    def test_studio_refresh_keeps_aster_behaviour_settings(self):
        from voidcompass.overlays.watcher_mind import frequency
        self.config.update(heartbeat_thoughts="off", aster_thoughts="rare")
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.config, hud.mind = self.config, self.mind
        hud._mind_path = _memory_path(self.config)
        hud._redraw = Mock()
        hud.sync_html_window = Mock()
        hud.apply_settings()
        hud.sync_html_window.assert_called_once()
        self.assertEqual(frequency(hud.mind.config), "rare")
        self.assertIsNone(hud.mind.consider("quiet"))

    def test_preferred_address_is_used_throughout_reports_and_pronounced(self):
        self.mind._session_start = self.clock.now
        self.mind.memory["name"] = {"known": "J_F", "call": "name", "spoken": "Jeff"}
        with patch.object(self.mind.random.source, "choice", side_effect=lambda rows: rows[0]):
            first = self.mind.consider("greet_away", force=True)
            second = self.mind.consider("greet_soon", force=True)
        self.assertEqual(first["text"], "Welcome back, J_F. Ready to resume the watch.")
        self.assertEqual(self.mind.spoken_words(first), "Welcome back, Jeff. Ready to resume the watch.")
        self.assertEqual(second["text"], "Ready to continue, J_F.")
        self.assertEqual(self.mind.spoken_words(second), "Ready to continue, Jeff.")

    def test_profile_keys_and_size_fallbacks(self):
        for name in ("companion_identity", "aster_thoughts", "aster_humour", "aster_hud_accent", "aster_voice_speed", "aster_voice_level"):
            self.assertIn(name, config.PROFILE_TEXT_SETTINGS)
        for name in ("aster_voice_enabled", "aster_hud_motion"):
            self.assertIn(name, config.PROFILE_BOOL_SETTINGS)
        for name in ("aster_voice_volume", "aster_hud_size"):
            self.assertIn(name, config.PROFILE_VALUE_SETTINGS)
        self.assertEqual(orb_size({"companion_identity": "aster"}), 144)
        self.assertEqual(orb_size({"companion_identity": "aster", "aster_hud_size": 192}), 192)
        self.assertEqual(companions.identity({"companion_identity": "bad"}), "watcher")


class SwitchTests(unittest.TestCase):
    def test_switch_closes_old_workers_and_rejects_late_hearing(self):
        class Deck(DashboardWatcherVoiceMixin, DashboardWatcherListenMixin):
            config = {"companion_identity": "watcher"}
            _persist_config = Mock()
            _schedule_html_dashboard_publish = Mock()
            _watcher_mind_watch = Mock()
            def _ui_post(self, action, **kwargs):
                self.posted = action
        deck = Deck()
        deck.config = dict(deck.config)
        speaker = deck._watcher_voice = Mock()
        listener = deck._watcher_listen = Mock()
        deck._watcher_listen_heard("hello")
        # Explicit source token captures both profile and generation.
        from voidcompass.core.config import get_active_profile
        token = (get_active_profile(deck.config), "watcher", 0)
        deck._watcher_listen_heard("hello", token)
        self.assertTrue(deck._companion_switch("aster"))
        self.assertEqual(deck.config['aster_hud_size'], deck.config['heartbeat_orb_size'])
        mind = Mock()
        deck.heartbeat_hud = SimpleNamespace(mind=mind)
        deck.posted()
        mind.talk.assert_not_called()
        speaker.close.assert_called_once()
        listener.close.assert_called_once()
        self.assertFalse(deck._companion_switch("bogus"))

    def test_warm_engine_is_replaced_when_model_changes(self):
        settings = {"companion_identity": "watcher"}
        speaker = watcher_voice.WatcherSpeaker(settings=lambda: settings, player=lambda path: None)
        first, second = Mock(), Mock()
        first.poll.return_value = None
        second.poll.return_value = None
        with patch.object(voice_assets, "installed", return_value=True), patch.object(watcher_voice.subprocess, "Popen", side_effect=[first, second]) as popen:
            self.assertIs(speaker._ensure_engine(), first)
            self.assertIs(speaker._ensure_engine(), first)
            settings["companion_identity"] = "aster"
            self.assertIs(speaker._ensure_engine(), second)
            first.kill.assert_called_once()
            self.assertIn("jarvis", popen.call_args.args[0][2])
        speaker.close()


class DualVoiceAssetsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("piper/piper.exe", b"engine")
        self.files = {"piper_windows_amd64.zip": archive.getvalue(), "hal.onnx": b"watcher", "hal.onnx.json": b"{}", "aster.onnx": b"aster", "aster.onnx.json": b"{}"}
        def rows(names):
            return tuple({"name": name, "sha256": hashlib.sha256(self.files[name]).hexdigest(), "size": len(self.files[name])} for name in names)
        self.engine = dict(voice_assets.ENGINE, **rows(("piper_windows_amd64.zip",))[0])
        self.watcher = rows(("hal.onnx", "hal.onnx.json"))
        self.aster = rows(("aster.onnx", "aster.onnx.json"))
        for name, value in (("ENGINE", self.engine), ("MODEL_FILES", self.watcher), ("ASTER_MODEL_FILES", self.aster)):
            patcher = patch.object(voice_assets, name, value); patcher.start(); self.addCleanup(patcher.stop)
        self.fetched = []

    def opener(self, url):
        name = url.rsplit("/", 1)[-1]
        self.fetched.append(name)
        return io.BytesIO(self.files[name])

    def download(self, model):
        job = voice_assets.VoiceDownload(self.base, opener=self.opener, model=model)
        job._run(None)
        return job

    def test_independent_receipts_one_engine_and_safe_removal(self):
        self.assertEqual(self.download("watcher").state()["stage"], "done")
        self.assertEqual(self.download("aster").state()["stage"], "done")
        self.assertEqual(self.fetched.count("piper_windows_amd64.zip"), 1)
        self.assertTrue(voice_assets.installed(self.base))
        self.assertTrue(voice_assets.installed(self.base, "aster"))
        card = self.base / "models/jarvis/MODEL_CARD.md"; card.write_text("source")
        self.assertTrue(voice_assets.remove(self.base, "aster"))
        self.assertTrue(voice_assets.installed(self.base))
        self.assertTrue(voice_assets.engine_exe(self.base).is_file())
        self.assertTrue(card.exists())
        self.assertTrue(voice_assets.remove(self.base))
        self.assertFalse(voice_assets.engine_exe(self.base).exists())

    def test_local_pair_is_adopted_after_checking_and_cancel_never_receipts(self):
        folder = voice_assets.model_path(self.base, "aster").parent; folder.mkdir(parents=True)
        for row in self.aster:
            (folder / row["name"]).write_bytes(self.files[row["name"]])
        self.assertEqual(self.download("aster").state()["stage"], "done")
        self.assertEqual(self.fetched, ["piper_windows_amd64.zip"])
        job = voice_assets.VoiceDownload(self.base, opener=self.opener, model="aster")
        job.cancel(); job._run(None)
        self.assertEqual(job.state()["stage"], "cancelled")
        self.assertTrue(voice_assets.installed(self.base, "aster"), "cancelling before work preserves an existing receipt")

    def test_corrupt_model_is_not_installed(self):
        self.files["aster.onnx"] = b"corrupt"
        job = self.download("aster")
        self.assertEqual(job.state()["stage"], "failed")
        self.assertIn("checksum", job.state()["error"])
        self.assertFalse(voice_assets.installed(self.base, "aster"))
        self.assertFalse(list(self.base.glob("**/*.part")))

    def test_overlapping_model_downloads_serialize_the_shared_engine(self):
        entered, release = threading.Event(), threading.Event()
        original = self.opener
        def blocked(url):
            if url.endswith(".zip"):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release download")
            return original(url)
        first = voice_assets.VoiceDownload(self.base, opener=blocked)
        second = voice_assets.VoiceDownload(self.base, opener=self.opener, model="aster")
        first.start()
        self.assertTrue(entered.wait(5))
        second.start()
        release.set()
        first._thread.join(5); second._thread.join(5)
        self.assertEqual(first.state()["stage"], "done")
        self.assertEqual(second.state()["stage"], "done")
        self.assertEqual(self.fetched.count("piper_windows_amd64.zip"), 1)
        self.assertTrue(voice_assets.installed(self.base))
        self.assertTrue(voice_assets.installed(self.base, "aster"))


class AsterServerAssetsTests(unittest.TestCase):
    def test_real_dashboard_serves_both_modules_and_their_shared_three_dependencies(self):
        from urllib.request import urlopen
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
        root = Path(__file__).resolve().parents[1]
        server = HtmlDashboardServer(root / "web/dashboard")
        self.addCleanup(server.stop)
        for path in ("/assets/aster-companion.js", "/assets/aster-3d.js", "/assets/companion-caption.js", "/galactic_map/vendor/three.module.min.js", "/galactic_map/vendor/three.core.min.js"):
            with self.subTest(path=path), urlopen(server.origin + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("javascript", response.headers["Content-Type"])
                self.assertGreater(len(response.read()), 100)


class CompanionDisplayFixTests(unittest.TestCase):
    def test_selected_settings_identity_and_model_manifest_match_current_files(self):
        settings = companions.settings({"companion_identity": "watcher"}, "aster")
        self.assertEqual(companions.identity(settings), "aster")
        self.assertEqual(dict(settings)["companion_identity"], "aster")
        root = Path(__file__).resolve().parents[1]
        self.assertTrue(voice_assets.ASTER_MODEL_URL.endswith("models/jarvis/onnx/"))
        self.assertEqual(voice_assets.model_path(root, "aster").parent, root / "models/jarvis/onnx")
        for row in voice_assets.ASTER_MODEL_FILES:
            path = root / "models/jarvis/onnx" / row["name"]
            self.assertEqual(len(row["sha256"]), 64)
            self.assertEqual(path.stat().st_size, row["size"])
            self.assertEqual(voice_assets.sha256_of(path), row["sha256"])
        self.assertEqual(voice_assets._receipt(root, "aster"), root / "models/jarvis/installed.json")

    def test_studio_controls_are_one_look_for_the_whole_crew_and_resize_live_window(self):
        from tests.test_heartbeat_orb import _Studio
        studio = _Studio()
        studio.config.update(companion_identity="aster", aster_hud_size=144, aster_hud_liveliness="standard")
        self.assertTrue(studio._html_overlay_settings_save({"companion_size": "192", "companion_accent": "brass", "companion_liveliness": "alive", "companion_focus": "expressive"}))
        self.assertEqual(studio.config["aster_hud_size"], 192)
        self.assertEqual(studio.config["heartbeat_orb_size"], 192)
        self.assertEqual(studio.config["aster_hud_accent"], "brass")
        self.assertEqual(studio.config["aster_hud_liveliness"], "alive")
        self.assertIn("aster_hud_liveliness", config.PROFILE_TEXT_SETTINGS)
        self.assertEqual(studio.config["aster_hud_focus"], "expressive")
        self.assertFalse(studio._html_overlay_settings_save({"companion_size": "65", "companion_focus": "wandering"}))
        self.assertTrue(studio._html_overlay_option_toggle("companion_motion", False))
        self.assertFalse(studio.config["aster_hud_motion"])
        for identity in companions.IDENTITIES:
            # Set once, for every companion: no setting each of them in turn.
            look = companions.display_options({**studio.config, "companion_identity": identity})
            self.assertEqual((look["companion_size"], look["companion_liveliness"], look["companion_focus"], look["companion_motion"]),
                             (192, "alive", "expressive", False), identity)
            self.assertEqual(look["companion_accent"], "brass" if identity == "aster" else companions.display_accent({"companion_identity": identity}),
                             "colour is each companion's own")
        studio.config["companion_identity"] = "watcher"
        self.assertTrue(studio._html_overlay_settings_save({"companion_size": "72", "companion_accent": "hal", "companion_liveliness": "calm", "companion_focus": "off"}))
        self.assertEqual(studio.config["heartbeat_orb_size"], 72)
        self.assertEqual(studio.config["aster_hud_size"], 72)
        self.assertEqual(companions.display_options(studio.config)["companion_size"], 72)
        self.assertEqual(studio.config["aster_hud_liveliness"], "calm")
        self.assertEqual(studio.config["aster_hud_focus"], "off")
        self.assertEqual(studio.config["heartbeat_focus_movement"], "off")
        # Colour stays each companion's own.
        self.assertEqual((studio.config["heartbeat_eye_color"], studio.config["aster_hud_accent"]), ("hal", "brass"))
        self.assertTrue(studio._html_overlay_option_toggle("companion_motion", True))
        self.assertTrue(all(studio.config[key] for key in companions.shared_display("companion_motion", True)))
        self.assertEqual(companions.display_options(studio.config)["companion_focus"], "off")
        for setting in ("aster_hud_focus", "heartbeat_focus_movement"):
            self.assertIn(setting, config.PROFILE_TEXT_SETTINGS)

    def test_each_companion_supports_every_shared_size_and_accent(self):
        from tests.test_heartbeat_orb import _Studio
        for identity in companions.IDENTITIES:
            studio = _Studio()
            studio.config["companion_identity"] = identity
            for size in (54, 72, 96, 144, 192, 256):
                self.assertTrue(studio._html_overlay_settings_save({"companion_size": str(size)}))
                self.assertEqual(companions.display_size(studio.config), size)
            for accent in companions.accent_choices(identity):
                self.assertTrue(studio._html_overlay_settings_save({"companion_accent": accent}))
                self.assertEqual(companions.display_options(studio.config)["companion_accent"], accent)

    def test_replacement_manifest_restarts_an_already_warm_aster_engine(self):
        settings = {"companion_identity": "aster"}
        speaker = watcher_voice.WatcherSpeaker(settings=lambda: settings, player=lambda path: None)
        first, second = Mock(), Mock()
        first.poll.return_value = second.poll.return_value = None
        with patch.object(voice_assets, "installed", return_value=True), patch.object(watcher_voice.subprocess, "Popen", side_effect=[first, second]) as popen:
            self.assertIs(speaker._ensure_engine(), first)
            changed = tuple(dict(row, sha256="f" * 64) for row in voice_assets.ASTER_MODEL_FILES)
            with patch.object(voice_assets, "ASTER_MODEL_FILES", changed):
                self.assertIs(speaker._ensure_engine(), second)
            first.kill.assert_called_once()
            self.assertTrue(popen.call_args.args[0][2].endswith("en_GB-jarvis-medium.onnx"))
        speaker.close()


class SpokenCaptionTests(unittest.TestCase):
    def setUp(self):
        from voidcompass.core.application_runtime import ApplicationRuntime
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = ApplicationRuntime()
        self.addCleanup(root.close)
        patcher = patch('voidcompass.overlays.heartbeat_hud._memory_path', return_value=Path(folder.name) / 'aster_memory.json')
        patcher.start(); self.addCleanup(patcher.stop)
        self.hud = HeartbeatHUD(root, {'companion_identity': 'aster'})
        self.addCleanup(self.hud.destroy)
        self.clock = Clock()
        self.hud.mind.clock = self.clock
        self.hud.mind.voice_active = True
        self.states = {}
        self.accepted = []
        def say(words, key, **kwargs):
            self.states[key] = 'queued'; self.accepted.append(key); return True
        self.hud.voice_listener = say
        self.hud.voice_status_listener = lambda key: self.states.get(key, 'unknown')

    def utter(self, words):
        return self.hud.mind._utter('talk', words, words, self.clock())['id']

    def test_caption_waits_through_loading_playback_and_following_queued_lines(self):
        first = self.utter('First report.')
        self.assertEqual(self.hud._thought_payload()['voice_state'], 'queued')
        self.clock.now += 1000
        self.assertEqual(self.hud._thought_payload()['id'], first, 'queued speech outlives the ordinary text timeout')
        self.states[first] = 'playing'
        second = self.utter('A longer second report.')
        self.assertEqual(self.hud._thought_payload()['id'], first)
        self.assertEqual(self.accepted, [first, second])
        self.states.update({first: 'finished', second: 'preparing'})
        self.assertEqual(self.hud._thought_payload()['id'], first, 'keep the old caption through the speech pause')
        self.states[second] = 'playing'
        self.clock.now += 1000
        payload = self.hud._thought_payload()
        self.assertEqual(payload['id'], second)
        self.assertTrue(payload['voice_full'])
        self.assertEqual(self.accepted, [first, second], 'polling never queues a line twice')
        self.states[second] = 'finished'
        ended = time.monotonic()
        with patch('voidcompass.overlays.heartbeat_hud.time.monotonic', return_value=ended):
            self.assertEqual(self.hud._thought_payload()['id'], second)
        with patch('voidcompass.overlays.heartbeat_hud.time.monotonic', return_value=ended + 1000):
            self.assertIsNone(self.hud._thought_payload())

    def test_failed_or_cancelled_speech_falls_back_to_the_written_reply(self):
        key = self.utter('The written reply remains available.')
        self.hud._thought_payload()
        for state in ('failed', 'cancelled'):
            self.states[key] = state
            payload = self.hud._thought_payload()
            self.assertFalse(payload['voice'])
            self.assertEqual(payload['text'], 'The written reply remains available.')
            self.assertEqual(payload['voice_state'], state)
