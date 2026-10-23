"""The Watcher's voice and its settings page (5.5.4), for MainDashboard.

The voice is Piper with the HAL model, downloaded on first use. Its switch,
download, test and settings live on the Watcher page, with the Watcher's
thought settings (moved there from Overlay Studio).
"""
from __future__ import annotations

import logging

from voidcompass.overlays import watcher_habits, watcher_mind, watcher_voice_lore
from voidcompass.overlays.heartbeat_hud import HEARTBEAT_TEXT_SIZES, heartbeat_text_size, thought_side_setting
from voidcompass.voice import voice_assets
from voidcompass.voice.watcher_voice import LEVELS, SPEEDS, WatcherSpeaker

# The Watcher's thought settings, now on its own page: select values go
# through Overlay Studio's checks, switches through its toggles.
WATCHER_SELECTS = (
    "heartbeat_thoughts", "heartbeat_personality", "heartbeat_thought_side", "heartbeat_text_scale_percent",
    "heartbeat_thought_colour", "heartbeat_thought_size", "heartbeat_thought_hold",
)
WATCHER_SWITCHES = ("heartbeat_thought_backdrop", "heartbeat_thought_heading")
TEST_LINE = "This is my voice, Commander. I can hear you. Well. I can hear the ship."


class DashboardWatcherVoiceMixin:
    # -- the speaker ---------------------------------------------------------
    def _watcher_speaker(self):
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is None:
            speaker = WatcherSpeaker(settings=lambda: self.config)
            self._watcher_voice = speaker
        return speaker

    def _watcher_voice_on(self):
        return bool(self.config.get("watcher_voice_enabled")) and voice_assets.installed()

    def _watcher_voice_attach(self, hud):
        """A new Watcher orb: give it the voice."""
        if hud is None:
            return
        hud.voice_listener = self._watcher_voice_say
        self._watcher_voice_sync()

    def _watcher_voice_say(self, words, key=None, feel=None):
        if getattr(self, "_closing", False) or not self._watcher_voice_on():
            return False
        said = self._watcher_speaker().say(words, key, feel=feel)
        if said and hasattr(self, "_api_publish"):
            self._api_publish("voice", {"text": words, "from": "api" if str(key or "").startswith("api-") else "watcher"})
        return said

    def _watcher_voice_sync(self):
        """Voice on and downloaded: warm it and tell the orb. Otherwise hush."""
        on = self._watcher_voice_on()
        hud = getattr(self, "heartbeat_hud", None)
        if hud is not None and hasattr(hud, "set_voice_active"):
            hud.set_voice_active(on)
        speaker = getattr(self, "_watcher_voice", None)
        if on:
            self._watcher_speaker().warm()
        elif speaker is not None:
            speaker.stop()
            speaker._stop_engine()

    def _watcher_live_levels(self):
        """The orb's live feed: the Music player's levels and its own voice."""
        levels = dict(self.music_levels() or {})
        speaker = getattr(self, "_watcher_voice", None)
        levels["speech"] = speaker.live() if speaker is not None else None
        return levels

    def _watcher_voice_close(self):
        """App shutdown: silent at once, the engine stopped, any download dropped."""
        download = getattr(self, "_watcher_voice_download", None)
        if download is not None:
            download.cancel()
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            speaker.close()

    # -- the download --------------------------------------------------------
    def _watcher_voice_downloader(self):
        download = getattr(self, "_watcher_voice_download", None)
        if download is None:
            download = voice_assets.VoiceDownload()
            self._watcher_voice_download = download
        return download

    def _watcher_voice_start_download(self):
        """Start the download, and keep the Watcher page's progress moving."""
        started = self._watcher_voice_downloader().start(self._watcher_voice_downloaded)
        self._watcher_voice_progress()
        return started

    def _watcher_voice_progress(self):
        download = getattr(self, "_watcher_voice_download", None)
        if download is None or getattr(self, "_closing", False):
            return
        self._schedule_html_dashboard_publish(immediate=True)
        if download.running():
            self._watcher_voice_progress_job = self.root.call_later(700, self._watcher_voice_progress)

    def _watcher_voice_downloaded(self, state):
        stage = state.get("stage")
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            if stage == "done":
                feed("SYSTEM", "The Watcher's voice is downloaded and ready", severity="INFO")
            elif stage == "failed":
                feed("SYSTEM", f"The Watcher's voice didn't download: {state.get('error')}", severity="WARNING")
        post = getattr(self, "_ui_post", None)
        work = lambda: (self._watcher_voice_sync(), self._schedule_html_dashboard_publish(immediate=True))
        if callable(post):
            post(work, key="watcher-voice-download")
        else:
            work()

    # -- the page ------------------------------------------------------------
    def _html_watcher_settings(self):
        style = watcher_mind.thought_style(self.config)
        return {
            "heartbeat_thoughts": watcher_mind.frequency(self.config),
            "heartbeat_personality": watcher_mind.personality(self.config),
            "heartbeat_thought_side": thought_side_setting(self.config),
            "heartbeat_text_scale_percent": heartbeat_text_size(self.config.get("heartbeat_text_scale_percent")),
            "heartbeat_thought_colour": style["colour"],
            "heartbeat_thought_size": style["size"],
            "heartbeat_thought_hold": style["hold"],
            "heartbeat_thought_backdrop": style["backdrop"],
            "heartbeat_thought_heading": style["heading"],
            "text_sizes": list(HEARTBEAT_TEXT_SIZES),
        }

    def _html_watcher_voice(self, memory):
        download = getattr(self, "_watcher_voice_download", None)
        state = download.state() if download is not None else {"stage": "idle", "done": 0,
                                                                "total": voice_assets.DOWNLOAD_BYTES, "error": ""}
        speaker = getattr(self, "_watcher_voice", None)
        try:
            volume = int(float(self.config.get("watcher_voice_volume", 80)))
        except (TypeError, ValueError):
            volume = 80
        return {
            "enabled": bool(self.config.get("watcher_voice_enabled")),
            "installed": voice_assets.installed(),
            "download": state,
            "size_mb": round(voice_assets.DOWNLOAD_BYTES / 1_000_000),
            "rights": voice_assets.RIGHTS_NOTICE,
            "volume": max(0, min(100, volume)),
            "speed": str(self.config.get("watcher_voice_speed") or "standard"),
            "level": str(self.config.get("watcher_voice_level") or "every"),
            "speaking": bool(speaker is not None and speaker.live()),
            "finding": watcher_voice_lore.progress(memory),
            "orb_on": getattr(self, "heartbeat_hud", None) is not None,
        }

    def _html_watcher_extras(self, mind):
        """The Watcher page's settings, voice and what it knows of you."""
        return {"settings": self._html_watcher_settings(),
                "voice": self._html_watcher_voice(mind.memory),
                "habits": watcher_habits.summary(mind.memory, mind.bond())}

    def _handle_watcher_settings_command(self, operation, payload):
        """The Watcher page's own controls. True when handled and done."""
        if operation == "settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            selects = {key: values[key] for key in WATCHER_SELECTS if key in values}
            done = True
            if selects:
                done = bool(self._html_overlay_settings_save(selects))
            for key in WATCHER_SWITCHES:
                if key in values:
                    done = bool(self._html_overlay_option_toggle(key, bool(values[key]))) and done
            return done
        if operation == "voice_toggle":
            self.config["watcher_voice_enabled"] = bool(payload.get("value"))
            self._persist_config()
            if self.config["watcher_voice_enabled"] and not voice_assets.installed():
                self._watcher_voice_start_download()
            self._watcher_voice_sync()
            return True
        if operation == "voice_settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if "watcher_voice_volume" in values:
                try:
                    self.config["watcher_voice_volume"] = max(0, min(100, int(float(values["watcher_voice_volume"]))))
                except (TypeError, ValueError):
                    return False
            if values.get("watcher_voice_speed") in SPEEDS:
                self.config["watcher_voice_speed"] = values["watcher_voice_speed"]
            if values.get("watcher_voice_level") in LEVELS:
                self.config["watcher_voice_level"] = values["watcher_voice_level"]
            self._persist_config()
            return True
        if operation == "voice_download":
            self._watcher_voice_start_download()
            return True
        if operation == "voice_cancel":
            self._watcher_voice_downloader().cancel()
            return True
        if operation == "voice_remove":
            speaker = getattr(self, "_watcher_voice", None)
            if speaker is not None:
                speaker.stop()
                speaker._stop_engine()
            done = voice_assets.remove()
            self._watcher_voice_sync()
            return done
        if operation == "voice_test":
            if not voice_assets.installed():
                return False
            return self._watcher_speaker().say(TEST_LINE, "test")
        if operation == "voice_stop":
            speaker = getattr(self, "_watcher_voice", None)
            if speaker is not None:
                speaker.stop()
            return True
        return None
