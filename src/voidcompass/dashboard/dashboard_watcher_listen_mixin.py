"""Talking to the Watcher by voice (5.7.1), for MainDashboard: the talk key
(held or tapped), the button and VOICE IN card on its MIND page, and the
mic test.

What you say goes to its mind like words typed in TALK TO IT, so its own
words must be on to answer; the mic test works without them. The hearing
itself is voice/listener.py.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time

from voidcompass.core.global_hotkeys import parse_hotkey
from voidcompass.voice import listen_assets, microphone
from voidcompass.voice.listener import WatcherListener

LISTEN_MODES = ("hold", "tap")
TEST_SECONDS = 4
# How often a held talk key is checked for being let go.
HOLD_POLL_S = 0.03
# Windows' microphone list, asked again at most this often for the page.
MICS_EVERY_S = 5.0


def _key_down(key):
    """The key (a virtual-key code) held down now, anywhere in Windows."""
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.WinDLL("user32")
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        return bool(user32.GetAsyncKeyState(int(key)) & 0x8000)
    except (OSError, ValueError):
        return False


class DashboardWatcherListenMixin:
    def _watcher_listener(self):
        listener = getattr(self, "_watcher_listen", None)
        if listener is None:
            listener = WatcherListener(settings=lambda: self.config, on_heard=self._watcher_listen_heard,
                                       on_change=self._watcher_listen_changed, prompt_provider=self._watcher_listen_words)
            self._watcher_listen = listener
        return listener

    def _watcher_listen_mode(self):
        mode = str(self.config.get("watcher_listen_mode") or "hold")
        return mode if mode in LISTEN_MODES else "hold"

    def _watcher_listen_blocked(self, test=False):
        """Why it can't listen now, or "" when it can."""
        if not self.config.get("watcher_listen_enabled"):
            return "Voice in is off: turn it on on the Watcher's MIND page."
        if not listen_assets.installed():
            return "Its hearing isn't downloaded yet: see VOICE IN on the Watcher's MIND page."
        if test:
            return ""
        if getattr(getattr(self, "heartbeat_hud", None), "mind", None) is None:
            return "The Watcher is off: turn it on in Overlay Studio to talk to it."
        if not self.config.get("watcher_llm_enabled") or not self._watcher_llm().listening():
            return "Its own words are off or still waking: it needs them to answer."
        return ""

    def _watcher_listen_words(self):
        """Where you are and what you fly, so the names come out right."""
        facts = self._watcher_llm_facts()
        return [facts.get("system"), facts.get("ship name"), facts.get("ship"), facts.get("near"),
                str(getattr(self, "current_station_name", "") or "")]

    # -- talking --------------------------------------------------------------
    def _watcher_talk_key(self):
        """The talk hotkey: held, it listens until you let go; tapped, it
        listens until the next tap."""
        listener = self._watcher_listener()
        mode = self._watcher_listen_mode()
        if mode == "tap" and listener.active():
            listener.stop()
            return
        blocked = self._watcher_listen_blocked()
        if blocked:
            # Said where you'll see it in game too.
            self._watcher_listen_tell(blocked, feed=True)
            return
        key = None
        if mode == "hold":
            try:
                parsed = parse_hotkey(self.config.get("overlay_hotkey_watcher_talk"))
            except ValueError:
                parsed = None
            key = parsed[1] if parsed else None
        self._watcher_listen_begin(key=key)

    def _watcher_listen_begin(self, key=None, test=False):
        if getattr(self, "_closing", False):
            return False
        threading.Thread(target=self._watcher_listen_run, args=(key, test), name="watcher-talk", daemon=True).start()
        return True

    def _watcher_listen_run(self, key=None, test=False):
        listener = self._watcher_listener()
        self._watcher_listen_quiet()
        if not listener.start(test=test):
            return
        if test:
            end = time.monotonic() + TEST_SECONDS
            while listener.listening() and time.monotonic() < end:
                time.sleep(0.05)
            listener.stop()
        elif key is not None:
            while listener.listening() and _key_down(key):
                time.sleep(HOLD_POLL_S)
            listener.stop()

    def _watcher_listen_quiet(self):
        """You're speaking: the Watcher stops mid-line."""
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None and speaker.live() is not None:
            self._voice_stop_reason = "stopped"
            speaker.stop()

    def _watcher_listen_heard(self, text):
        """What you said (on the hearing thread): to its mind, as talk."""
        def work():
            mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
            if mind is None or not mind.talk(text, voice=True):
                self._watcher_listen_tell(f"It heard “{text}”, but its own words aren't ready to answer.",
                                          feed=True)
                return
            self._watcher_mind_watch()
        self._ui_post(work)

    def _watcher_listen_tell(self, note, feed=False):
        listener = self._watcher_listener()
        listener.note = note
        if feed and callable(getattr(self, "add_event_feed_entry", None)):
            self.add_event_feed_entry("SYSTEM", f"The Watcher: {note}", severity="INFO")
        self._schedule_html_dashboard_publish(immediate=True)

    def _watcher_listen_changed(self):
        """Listening, hearing or done (any thread): the page and the orb follow."""
        if not getattr(self, "_closing", False):
            self._ui_post(self._watcher_listen_show, key="watcher-listen-state")

    def _watcher_listen_show(self):
        live = self._watcher_listen_live()
        hud = getattr(self, "heartbeat_hud", None)
        if hud is not None and hasattr(hud, "set_hearing"):
            hud.set_hearing(live["stage"] if live else "")
        self._schedule_html_dashboard_publish(immediate=True)

    def _watcher_listen_live(self):
        """The orb's share of /api/live: listening or working out what you said."""
        listener = getattr(self, "_watcher_listen", None)
        return listener.live() if listener is not None else None

    def _watcher_listen_close(self):
        download = getattr(self, "_watcher_listen_download", None)
        if download is not None:
            download.cancel()
        listener = getattr(self, "_watcher_listen", None)
        if listener is not None:
            listener.close()

    # -- the download ---------------------------------------------------------
    def _watcher_listen_downloader(self):
        download = getattr(self, "_watcher_listen_download", None)
        if download is None:
            download = self._watcher_listen_download = listen_assets.ListenDownload()
        return download

    def _watcher_listen_start_download(self):
        started = self._watcher_listen_downloader().start(self._watcher_listen_downloaded)
        self._watcher_listen_progress()
        return started

    def _watcher_listen_progress(self):
        download = getattr(self, "_watcher_listen_download", None)
        if download is None or getattr(self, "_closing", False):
            return
        self._schedule_html_dashboard_publish(immediate=True)
        if download.running():
            self._watcher_listen_progress_job = self.root.call_later(700, self._watcher_listen_progress)

    def _watcher_listen_downloaded(self, state):
        stage = state.get("stage")
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            if stage == "done":
                feed("SYSTEM", "The Watcher can hear you now: hold your talk key and speak", severity="INFO")
            elif stage == "failed":
                feed("SYSTEM", f"The Watcher's hearing didn't download: {state.get('error')}", severity="WARNING")
        self._ui_post(self._schedule_html_dashboard_publish, immediate=True, key="watcher-listen-download")

    # -- the page -------------------------------------------------------------
    def _watcher_mics(self):
        cached = getattr(self, "_watcher_mics_cache", None)
        now = time.monotonic()
        if cached is None or now - cached[0] > MICS_EVERY_S:
            cached = self._watcher_mics_cache = (now, microphone.devices())
        return list(cached[1])

    def _html_watcher_listen(self):
        listener = self._watcher_listener()
        download = getattr(self, "_watcher_listen_download", None)
        state = download.state() if download is not None else {"stage": "idle", "done": 0, "total": 0, "error": ""}
        live = listener.state()
        try:
            hotkey = parse_hotkey(self.config.get("overlay_hotkey_watcher_talk"))
        except ValueError:
            hotkey = None
        return {
            "enabled": bool(self.config.get("watcher_listen_enabled")),
            "installed": listen_assets.installed(),
            "download": state,
            "download_mb": round(listen_assets.download_bytes() / 1_000_000),
            "notice": listen_assets.NOTICE,
            "mics": self._watcher_mics(),
            "mic": str(self.config.get("watcher_listen_mic") or ""),
            "mode": self._watcher_listen_mode(),
            "hotkey": hotkey[2] if hotkey else "",
            "hotkeys_on": bool(self.config.get("overlay_hotkeys_enabled", True)),
            # Its loudness and seconds move too fast for the page: the meter asks /api/data/listen.
            "stage": live["stage"],
            "testing": live["testing"],
            "heard": live["heard"],
            "note": live["note"],
            "has_test": listener.last_test() is not None,
            "blocked": self._watcher_listen_blocked(),
        }

    def _watcher_listen_data(self, name):
        """/api/data/listen (the level meter) and /api/data/listen-test (the
        mic test, to hear back)."""
        listener = self._watcher_listener()
        if name == "listen":
            return self._json_answer(listener.state())
        if name == "listen-test":
            sound = listener.last_test()
            return ("audio/wav", sound) if sound else None
        return None

    def _handle_watcher_listen_command(self, operation, payload):
        """VOICE IN's controls and the talk button. None when not one of them."""
        if operation == "listen_toggle":
            self.config["watcher_listen_enabled"] = bool(payload.get("value"))
            self._persist_config()
            if self.config["watcher_listen_enabled"]:
                if not listen_assets.installed():
                    self._watcher_listen_start_download()
            else:
                listener = self._watcher_listener()
                listener.stop()
                threading.Thread(target=listener.stop_server, name="watcher-hearing-stop", daemon=True).start()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "listen_settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if "watcher_listen_mic" in values:
                mic = str(values["watcher_listen_mic"] or "")
                if mic and mic not in microphone.devices():
                    return False
                self.config["watcher_listen_mic"] = mic
            if values.get("watcher_listen_mode") in LISTEN_MODES:
                self.config["watcher_listen_mode"] = values["watcher_listen_mode"]
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "listen_download":
            return self._watcher_listen_start_download()
        if operation == "listen_cancel":
            self._watcher_listen_downloader().cancel()
            return True
        if operation == "listen_remove":
            listener = self._watcher_listener()
            listener.stop()
            listener.stop_server()
            done = listen_assets.remove()
            self._schedule_html_dashboard_publish(immediate=True)
            return done
        if operation == "listen_start":
            blocked = self._watcher_listen_blocked()
            if blocked:
                self._watcher_listen_tell(blocked)
                return False
            return self._watcher_listen_begin()
        if operation == "listen_stop":
            self._watcher_listener().stop()
            return True
        if operation == "listen_test":
            blocked = self._watcher_listen_blocked(test=True)
            if blocked:
                self._watcher_listen_tell(blocked)
                return False
            return self._watcher_listen_begin(test=True)
        return None

