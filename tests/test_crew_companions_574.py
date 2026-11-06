"""Axiom/Meridian integration, independent assets and their own persona content (5.7.4)."""
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from voidcompass.core import companions, config
from voidcompass.overlays import watcher_ship, watcher_name
from voidcompass.overlays import companion_personas
from voidcompass.overlays.crew_mind import CrewMind, TEST_LINES
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD, _memory_path
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.voice import voice_assets, watcher_voice
from tests.test_aster_companion import Clock


class CrewMindTests(unittest.TestCase):
    def mind(self, identity, path=None):
        return companions.create_mind(path, {"companion_identity":identity, f"{identity}_thoughts":"chatty"}, clock=Clock(), rng=random.Random(7))

    def test_welcomes_and_capabilities_use_active_name_and_persist_rotation(self):
        for identity in companions.NEW_IDENTITIES:
            lines = companion_personas.get(identity).lines
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/"memory.json"
                heard=[]
                for _ in range(len(lines.GREETINGS)):
                    mind=self.mind(identity,path)
                    self.assertIsInstance(mind,CrewMind)
                    self.assertTrue(mind.talk(f"Hello {companions.NAMES[identity]}"))
                    heard.append(mind.thought["text"])
                    mind.save()
                self.assertEqual(set(heard),set(lines.GREETINGS))
                self.assertEqual(len(heard),len(set(heard)))
                mind=self.mind(identity,path)
                mind.talk(f"{companions.NAMES[identity]}, what can you do?")
                self.assertIn(mind.thought["text"],lines.CAPABILITIES)

    def test_login_welcome_deduplicates_and_rotates(self):
        for identity in companions.NEW_IDENTITIES:
            events = companion_personas.get(identity).lines.EVENTS
            mind=self.mind(identity)
            login={"timestamp":"2026-11-04T10:00:00Z","Commander":"NightOwl","FID":"F1"}
            first=mind.observe("LoadGame",login)
            self.assertIn(first["text"],events["greet_new"])
            self.assertIsNone(mind.observe("LoadGame",login))
            mind.clock.now+=30
            second=mind.observe("LoadGame",dict(login,timestamp="2026-11-04T10:00:30Z"))
            self.assertIn(second["text"],events["greet_away"])
            self.assertEqual(mind.memory["sessions"],2)

    def test_own_story_name_introduction_port_and_postcards(self):
        for identity in companions.NEW_IDENTITIES:
            persona = companion_personas.get(identity)
            with self.subTest(identity=identity):
                mind=self.mind(identity)
                mind.session_start();mind.memory["hours"]=500;mind.clock.now+=7200
                story=mind.remember()
                self.assertEqual(story["text"],persona.story.passages[0][5])
                self.assertTrue(story["heading"].startswith(persona.story.unit.upper()))
                self.assertFalse(any(word in story["text"] for word in ("Aster","handover","Watcher")))
                watcher_name.observe(mind.memory,"Commander",{"Name":"NightOwl","FID":"F1"})
                asked=mind.ask("your_name")
                self.assertIn("NightOwl",asked["text"])
                self.assertEqual(mind.pending_question()["id"],"your_name")
                self.assertTrue(mind.answer("yes"))
                self.assertEqual(watcher_name.call_name(mind.memory),"NightOwl")
                mind.surroundings.docked=True;mind.surroundings.station="Jameson Memorial"
                port=mind.consider("idle_docked",{"station":"Jameson Memorial"},force=True)
                self.assertIn(port["text"].replace("NightOwl","Commander"),[line.format(station="Jameson Memorial") for line in persona.lines.EVENTS["idle_docked"]])
                note=persona.postcards.postcard_note({"title":"Sol"},rng=random.Random(3))
                self.assertTrue(note)
                self.assertEqual(persona.postcards.SIGNATURE,companions.NAMES[identity])
                self.assertTrue(mind.memories_page())

    def test_shared_actions_facts_preferred_address_and_pronunciation(self):
        for identity in companions.NEW_IDENTITIES:
            mind=self.mind(identity)
            watcher_name.set_nickname(mind.memory,"Jeff")
            watcher_name.set_call(mind.memory,"nickname")
            self.assertIn(watcher_ship.reply("unavailable",mind.random),companion_personas.get(identity).lines.COMMANDS["unavailable"])
            mind.lookup_provider=lambda text:["We are in Sol."]
            self.assertTrue(mind.talk(f"{companions.NAMES[identity]}, where are we?"))
            self.assertEqual(mind.thought["text"],"We are in Sol.")
            mind.talk(f"Hello {companions.NAMES[identity]}")
            watcher_name.set_spoken(mind.memory,"Jef")
            self.assertEqual(mind.spoken_words({"text":"Welcome, Jeff."}),"Welcome, Jef.")

    def test_profile_registration_and_independent_live_settings(self):
        for key,value in companions.new_defaults().items():
            group=config.PROFILE_BOOL_SETTINGS if isinstance(value,bool) else config.PROFILE_TEXT_SETTINGS if isinstance(value,str) else config.PROFILE_VALUE_SETTINGS
            self.assertIn(key,group)
        values={"companion_identity":"axiom","axiom_voice_volume":55,"meridian_voice_volume":85}
        self.assertEqual(companions.settings(values).get("watcher_voice_volume"),55)
        values["companion_identity"]="meridian"
        self.assertEqual(companions.settings(values).get("watcher_voice_volume"),85)

    def test_each_profile_memory_path_is_distinct(self):
        with patch.object(config,"get_profile_file",side_effect=lambda profile,filename: filename):
            self.assertEqual({_memory_path({"companion_identity":i}) for i in companions.IDENTITIES},
                             {f"{i}_memory.json" for i in companions.IDENTITIES})

    def test_studio_controls_and_size_carry_across_all_identities(self):
        from tests.test_heartbeat_orb import _Studio
        studio=_Studio()
        for identity in companions.NEW_IDENTITIES:
            studio.config["companion_identity"]=identity
            self.assertTrue(studio._html_overlay_settings_save({"companion_size":"192","companion_accent":"cyan","companion_focus":"expressive","companion_liveliness":"alive"}))
            self.assertTrue(studio._html_overlay_option_toggle("companion_motion",False))
            self.assertEqual(companions.display_options(studio.config)["companion_focus"],"expressive")
            self.assertFalse(studio.config[f"{identity}_hud_motion"])
        for identity in companions.IDENTITIES:
            self.assertEqual(companions.display_size(dict(studio.config,companion_identity=identity)),192)

    def test_download_and_test_select_correct_voice(self):
        for identity in companions.NEW_IDENTITIES:
            deck=DashboardWatcherVoiceMixin();deck.config={"companion_identity":identity}
            deck._companion_voice_installed=lambda:True
            deck._watcher_voice_boot_held=lambda:False
            speaker=deck._watcher_voice=Mock()
            download=deck._watcher_voice_downloader()
            self.assertEqual(download.model,identity)
            deck._handle_watcher_settings_command("voice_test",{})
            speaker.say.assert_called_once_with(TEST_LINES[identity],"test")
            voice=deck._html_watcher_voice({})
            self.assertEqual(voice["model_name"],f"{companions.NAMES[identity]} voice")
            self.assertTrue(voice["finding"]["found"])


class FourVoiceAssetsTests(unittest.TestCase):
    def test_shipped_pairs_match_each_exact_manifest(self):
        root=Path(__file__).resolve().parents[1]
        for identity in companions.NEW_IDENTITIES:
            folder,rows,url=voice_assets.manifest(identity)
            self.assertTrue(url.endswith(f"/models/{folder}/"))
            for row in rows:
                path=root/"models"/folder/row["name"]
                self.assertEqual(path.stat().st_size,row["size"])
                self.assertEqual(voice_assets.sha256_of(path),row["sha256"])

    def test_all_install_orders_share_engine_and_independent_removal(self):
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,"w") as bundle:bundle.writestr("piper/piper.exe",b"engine")
        contents={"piper_windows_amd64.zip":archive.getvalue()}
        manifests={}
        for identity in (i for i in companions.IDENTITIES if not companions.overlay_only(i)):
            manifests[identity]=[]
            for suffix in (".onnx",".onnx.json"):
                name=identity+suffix;data=(identity+suffix).encode();contents[name]=data
                manifests[identity].append({"name":name,"size":len(data),"sha256":hashlib.sha256(data).hexdigest()})
        engine=dict(voice_assets.ENGINE,sha256=hashlib.sha256(archive.getvalue()).hexdigest(),size=len(archive.getvalue()))
        fetched=[]
        def opener(url):
            name=url.rsplit("/",1)[-1];fetched.append(name);return io.BytesIO(contents[name])
        folders={i:voice_assets.manifest(i)[0] for i in companions.IDENTITIES if not companions.overlay_only(i)}
        def manifest(identity="watcher"):return folders[identity],manifests[identity],"https://example.test/"
        with tempfile.TemporaryDirectory() as base,patch.object(voice_assets,"ENGINE",engine),patch.object(voice_assets,"manifest",side_effect=manifest):
            for identity in ("axiom","meridian","watcher","aster"):
                job=voice_assets.VoiceDownload(base,opener=opener,model=identity);job._run(None)
                self.assertEqual(job.state()["stage"],"done",job.state())
            self.assertEqual(fetched.count("piper_windows_amd64.zip"),1)
            self.assertEqual(len({voice_assets._receipt(base,i) for i in companions.IDENTITIES if not companions.overlay_only(i)}),4)
            for identity in ("watcher","aster","meridian"):
                self.assertTrue(voice_assets.remove(base,identity))
                self.assertTrue(voice_assets.installed(base,"axiom"))
            self.assertTrue(voice_assets.remove(base,"axiom"))
            self.assertFalse(voice_assets.engine_exe(base).exists())

    def test_warm_speaker_restarts_for_each_active_pair(self):
        settings={"companion_identity":"axiom"}
        speaker=watcher_voice.WatcherSpeaker(settings=lambda:settings,player=lambda path:None)
        processes=[Mock(),Mock()]
        for process in processes:process.poll.return_value=None
        with patch.object(voice_assets,"installed",return_value=True),patch.object(watcher_voice.subprocess,"Popen",side_effect=processes) as popen:
            self.assertIs(speaker._ensure_engine(),processes[0])
            self.assertIn("data",popen.call_args.args[0][2])
            settings["companion_identity"]="meridian"
            self.assertIs(speaker._ensure_engine(),processes[1])
            self.assertIn("picard",popen.call_args.args[0][2])
        speaker.close()
