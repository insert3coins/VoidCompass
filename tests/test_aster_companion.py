"""5.7.4: Aster's independent persona, paced story, profile settings and shared voice assets."""
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from voidcompass.core import companions, config
from voidcompass.overlays import aster_lines, aster_lore, watcher_copilot, watcher_ship
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
        for row in aster_lore.PASSAGES:
            thought = self.mind.remember()
            self.assertEqual(thought["text"], row[5])
            self.assertTrue(thought["heading"].startswith("MANIFEST"))
            self.assertIsNone(self.mind.remember(), "not twice in one quiet period")
            self.clock.now += aster_lore.GAP_S + 1
        self.assertIsNone(self.mind.remember())
        self.assertTrue(aster_lore.page(self.mind.memory, 500)["complete"])
        self.assertEqual(len(aster_lore.PASSAGES), 48)
        fresh = AsterMind(None, self.config, clock=self.clock)
        fresh.session_start(); fresh.memory["hours"] = 500
        self.clock.now += aster_lore.SETTLE_S + 1
        fresh._in_danger = True
        self.assertIsNone(fresh.remember())

    def test_story_gates_have_event_and_time_alternatives_and_no_spoilers(self):
        page = aster_lore.page({}, 0)
        self.assertTrue(all(row["title"] == "Unopened report" and not row["told"] and not row["account"] for row in page["chapters"]))
        for gate, (count, fallback, _label, field) in aster_lore.GATES.items():
            self.assertFalse(aster_lore.gate_ready({}, gate, 0))
            self.assertTrue(aster_lore.gate_ready({"aster_marks": {field: count}}, gate, 0))
            self.assertTrue(aster_lore.gate_ready({}, gate, fallback))
        self.mind.observe("FSDJump", {"StarSystem": "Sol"})
        self.mind.observe("FSDJump", {"StarSystem": "Achenar"})
        self.mind.observe("FSDJump", {"StarSystem": "Sol"})
        self.mind.observe("Docked", {"StationName": "Galileo"})
        self.mind.observe("MarketSell", {})
        self.assertEqual(self.mind.memory["aster_marks"], {"jumps": 3, "returns": 1, "arrivals": 1, "deliveries": 1})
        self.mind.observe("Shutdown", {})
        self.assertFalse(self.mind.memory.get("echoes"))
        self.assertFalse(self.mind.memory.get("dreams"))
        self.assertIsNone(self.mind.find_voice())
        self.assertIsNone(self.mind.pending_question())

    def test_restraint_and_frequency_are_independent(self):
        self.config.update(heartbeat_thoughts="off", aster_thoughts="chatty", aster_humour="off")
        self.assertIsNotNone(self.mind.consider("quiet", force=True))
        self.assertEqual(self.mind.thought["text"], aster_lines.EVENTS["quiet"][0])
        self.config["aster_thoughts"] = "off"
        self.assertIsNone(self.mind.consider("quiet", force=True))
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
        hud.apply_settings()
        self.assertEqual(frequency(hud.mind.config), "rare")
        self.assertIsNone(hud.mind.consider("quiet"))

    def test_preferred_address_is_used_sparingly_and_pronounced(self):
        self.mind._session_start = self.clock.now
        self.mind.memory["name"] = {"known": "J_F", "call": "name", "spoken": "Jeff"}
        first = self.mind._utter("greet_away", "a", "Welcome back, Commander.", self.clock.now)
        self.assertEqual(first["text"], "Welcome back, J_F.")
        self.assertEqual(self.mind.spoken_words(first), "Welcome back, Jeff.")
        second = self.mind._utter("greet_away", "b", "Welcome back, Commander.", self.clock.now)
        self.assertEqual(second["text"], "Welcome back, Commander.")

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
        folder = self.base / "models/jarvis"; folder.mkdir(parents=True)
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
        for path in ("/assets/aster-companion.js", "/assets/aster-3d.js", "/galactic_map/vendor/three.module.min.js", "/galactic_map/vendor/three.core.min.js"):
            with self.subTest(path=path), urlopen(server.origin + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("javascript", response.headers["Content-Type"])
                self.assertGreater(len(response.read()), 100)
