import pathlib
import sys
import tempfile
import unittest
import wave
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import voice_callouts  # noqa: E402


class VoiceCalloutTests(unittest.TestCase):
    def test_voice_catalog_uses_pinned_artifacts(self):
        self.assertIn(voice_callouts.DEFAULT_VOICE, voice_callouts.VOICES)
        self.assertEqual(len(voice_callouts.VOICES), 18)
        for name, item in voice_callouts.VOICES.items():
            self.assertEqual(voice_callouts.canonical_voice(name), name)
            self.assertEqual(len(item["onnx_sha"]), 64)
            self.assertEqual(len(item["config_sha"]), 64)
            int(item["onnx_sha"], 16)
            int(item["config_sha"], 16)

    def test_regional_vctk_choices_share_one_pinned_model(self):
        regional = (
            "en_AU-vctk-p326-medium", "en_NZ-vctk-p335-medium",
            "en_IE-vctk-p245-medium", "en_IE-vctk-p283-medium",
        )
        paths = {voice_callouts.model_path(voice) for voice in regional}
        configs = {voice_callouts.model_config_path(voice) for voice in regional}
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(configs), 1)
        self.assertEqual(
            {voice_callouts.VOICES[voice]["speaker_id"] for voice in regional},
            {71, 42, 97, 8},
        )
        payload = voice_callouts._synthesis_payload("Test", pathlib.Path("test.wav"), regional[0])
        self.assertEqual(payload["speaker_id"], 71)

    def test_unknown_voice_is_rejected_before_download(self):
        with self.assertRaisesRegex(voice_callouts.VoiceError, "Unknown voice"):
            voice_callouts.start_download("../../not-a-voice")

    def test_status_reports_only_complete_voice_install(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(
            voice_callouts, "TTS_DIR", pathlib.Path(folder)
        ):
            voice = voice_callouts.DEFAULT_VOICE
            voice_callouts.model_path(voice).write_bytes(b"model")
            self.assertFalse(voice_callouts.voice_installed(voice))
            voice_callouts.model_config_path(voice).write_text("{}", encoding="utf-8")
            self.assertTrue(voice_callouts.voice_installed(voice))
            self.assertFalse(voice_callouts.ready(voice))

    def test_manager_honours_enable_category_and_cooldown(self):
        config = {
            "voice_callouts_enabled": False,
            "voice_safety_enabled": True,
            "voice_name": voice_callouts.DEFAULT_VOICE,
            "voice_volume": 0.7,
        }
        manager = voice_callouts.VoiceCalloutManager(config)
        queued = []
        try:
            with mock.patch.object(voice_callouts, "ready", return_value=True), mock.patch.object(
                manager, "_enqueue", side_effect=lambda *item: queued.append(item) or True
            ):
                self.assertFalse(manager.say("Low fuel", key="low-fuel"))
                config["voice_callouts_enabled"] = True
                self.assertTrue(manager.say("Low fuel", key="low-fuel"))
                self.assertFalse(manager.say("Low fuel", key="low-fuel"))
                config["voice_safety_enabled"] = False
                self.assertFalse(manager.say("Hull critical", key="hull"))
                self.assertEqual(queued, [("Low fuel", voice_callouts.DEFAULT_VOICE, 0.7)])
        finally:
            manager.stop()

    def test_volume_scaling_creates_quieter_wav(self):
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / "source.wav"
            samples = (10000).to_bytes(2, "little", signed=True) * 20
            with wave.open(str(source), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(22050)
                writer.writeframes(samples)

            scaled = voice_callouts._scaled_wav(source, 0.5)
            with wave.open(str(scaled), "rb") as reader:
                first = int.from_bytes(reader.readframes(1), "little", signed=True)
            self.assertNotEqual(scaled, source)
            self.assertEqual(first, 5000)

    def test_cache_status_and_clear(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(
            voice_callouts, "CACHE_DIR", pathlib.Path(folder)
        ):
            (pathlib.Path(folder) / "one.wav").write_bytes(b"a" * 100)
            (pathlib.Path(folder) / "two.wav").write_bytes(b"b" * 200)
            status = voice_callouts.cache_status()
            self.assertEqual(status["files"], 2)
            self.assertEqual(status["bytes"], 300)
            cleared = voice_callouts.clear_cache()
            self.assertEqual(cleared, {"files": 2, "bytes": 300})
            self.assertEqual(voice_callouts.cache_status()["files"], 0)

    def test_no_cache_playback_removes_temporary_audio(self):
        config = {"voice_cache_enabled": False, "voice_name": voice_callouts.DEFAULT_VOICE}
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / "temporary.wav"
            scaled = pathlib.Path(folder) / "temporary-v050.wav"
            source.write_bytes(b"source")
            scaled.write_bytes(b"scaled")
            manager = voice_callouts.VoiceCalloutManager(config)
            try:
                with mock.patch.object(voice_callouts, "ready", return_value=True), \
                        mock.patch.object(voice_callouts, "synthesize", return_value=source), \
                        mock.patch.object(voice_callouts, "_scaled_wav", return_value=scaled), \
                        mock.patch.object(voice_callouts, "_play_wav"):
                    manager._enqueue("Test", voice_callouts.DEFAULT_VOICE, 0.5, False)
                    manager._queue.join()
                self.assertFalse(source.exists())
                self.assertFalse(scaled.exists())
            finally:
                manager.stop()


if __name__ == "__main__":
    unittest.main()
