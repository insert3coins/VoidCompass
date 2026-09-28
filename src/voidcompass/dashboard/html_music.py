"""The Music page and its player, from Python's side.

The dashboard page is the player: it streams each track from the local
dashboard server (/media/music/<id>) and reports what it is doing about once
a second. Python keeps the library (services.music_library), remembers the
player for the commander so it resumes next time, hands hotkeys to the page,
and feeds the music overlay, including the visualizer's live levels.
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time

from voidcompass.services.music_library import MusicLibrary

MUSIC_REPEAT = ("off", "all", "one")
MUSIC_REMOTE = ("toggle", "next", "previous")
# The playing position is saved this often at most (track, playlist and
# settings changes are saved at once), so config.json is not rewritten
# every second while music plays.
MUSIC_POSITION_SAVE_S = 20.0
# Levels older than this are silence: the page has stopped sending them.
MUSIC_LEVELS_STALE_S = 1.0
MUSIC_BANDS = 64


def _text(value, limit=240):
    return str(value if value is not None else "").strip()[:limit]


def _number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and abs(number) != float("inf") else default


class HtmlMusicMixin:
    """The library, the player's memory, hotkeys and the overlay's feed."""

    # Tests point this at a temporary folder; the app keeps music/ beside
    # its other data.
    _music_root = None

    def music_library(self):
        library = getattr(self, "_music_library_instance", None)
        if library is None:
            library = MusicLibrary(Path(self._music_root or "music"), on_change=self._music_library_touched)
            self._music_library_instance = library
        return library

    def _attach_music_library(self, runtime):
        server = getattr(runtime, "server", None)
        if server is not None:
            server.music = self.music_library()

    def _music_library_touched(self):
        # Tags are read on the library's worker thread; publish on the app's.
        post = getattr(self, "_ui_post", None)
        if callable(post):
            post(self._music_library_changed, key="music-library")

    def _music_library_changed(self):
        self._music_update_overlay()
        self._schedule_html_dashboard_publish(immediate=True)

    # -- what the page is told --------------------------------------------------
    def _html_music_snapshot(self):
        config = self.config
        repeat = config.get("music_repeat")
        return {
            "library_revision": self.music_library().revision,
            "settings": {
                "volume": max(0, min(100, int(_number(config.get("music_volume"), 80)))),
                "shuffle": bool(config.get("music_shuffle", False)),
                "repeat": repeat if repeat in MUSIC_REPEAT else "all",
                "normalise": bool(config.get("music_normalise", True)),
                "playlist_id": _text(config.get("music_playlist_id"), 40),
                "track_id": _text(config.get("music_track_id"), 16),
                "position": max(0.0, _number(config.get("music_position"))),
            },
            "remote": dict(getattr(self, "_music_remote", None) or {"seq": 0, "op": ""}),
            "focus": dict(getattr(self, "_music_focus", None) or {"seq": 0, "playlist_id": ""}),
            "notice": dict(getattr(self, "_music_notice", None) or {"seq": 0, "text": "", "tone": ""}),
            "working": bool(getattr(self, "_music_working", False)),
            "overlay": bool(config.get("music_player_overlay_enabled", False)),
        }

    def _music_say(self, text, tone="ok"):
        previous = getattr(self, "_music_notice", None) or {"seq": 0}
        self._music_notice = {"seq": int(previous["seq"]) + 1, "text": _text(text, 300), "tone": tone}

    def _music_show_playlist(self, playlist_id):
        previous = getattr(self, "_music_focus", None) or {"seq": 0}
        self._music_focus = {"seq": int(previous["seq"]) + 1, "playlist_id": _text(playlist_id, 40)}

    # -- hotkeys ------------------------------------------------------------------
    def music_remote(self, operation):
        """Play/pause, next or previous from a hotkey; the page carries it out."""
        if operation not in MUSIC_REMOTE:
            return False
        previous = getattr(self, "_music_remote", None) or {"seq": 0}
        self._music_remote = {"seq": int(previous["seq"]) + 1, "op": operation}
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    # -- commands from the page ---------------------------------------------------
    def _handle_html_music_command(self, payload):
        operation = _text(payload.get("operation"), 40).casefold()
        library = self.music_library()
        playlist_id = _text(payload.get("playlist_id"), 40)
        if operation == "status":
            self._music_status_report(payload)
            return True
        if operation == "set_duration":
            library.set_duration(_text(payload.get("track_id"), 16), payload.get("duration"))
        elif operation == "set_loudness":
            library.set_loudness(_text(payload.get("track_id"), 16), payload.get("lufs"))
            return True
        if operation == "recheck":
            library.recheck_files()
        elif operation == "create_playlist":
            self._music_show_playlist(library.create_playlist(_text(payload.get("name"), 80) or "New playlist"))
        elif operation == "rename_playlist":
            if not library.rename_playlist(playlist_id, _text(payload.get("name"), 80)):
                return False
        elif operation == "delete_playlist":
            if not library.delete_playlist(playlist_id):
                return False
        elif operation == "remove_tracks":
            if not library.remove_tracks(playlist_id, list(payload.get("positions") or [])[:5000]):
                return False
        elif operation == "move_track":
            if not library.move_track(playlist_id, int(_number(payload.get("from"), -1)),
                                      int(_number(payload.get("to"), -1))):
                return False
        elif operation in {"add_paths", "import_m3u", "export_m3u"}:
            return self._music_file_job(operation, payload)
        else:
            return False
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _music_file_job(self, operation, payload):
        """Scanning folders and reading playlists takes a while: off the app loop."""
        library = self.music_library()
        playlist_id = _text(payload.get("playlist_id"), 40)
        paths = [path for path in (_text(item, 2048) for item in list(payload.get("paths") or [])[:4000]) if path]
        target = _text(payload.get("path"), 2048)
        if operation == "add_paths" and (not paths or library.playlist(playlist_id) is None):
            return False
        if operation in {"import_m3u", "export_m3u"} and not target:
            return False
        if operation == "export_m3u" and library.playlist(playlist_id) is None:
            return False

        def work():
            focus = ""
            try:
                if operation == "add_paths":
                    added = library.add_files(playlist_id, library.expand(paths))
                    if added:
                        message, tone = f"Added {added} track{'s' if added != 1 else ''}.", "ok"
                    else:
                        message, tone = "No music there that Void Compass can play (MP3, FLAC, M4A, AAC, OGG, Opus, WAV).", "warn"
                    focus = playlist_id
                elif operation == "import_m3u":
                    result = library.import_m3u(target, playlist_id or None)
                    left_out = [f"{count} {label}" for label, count in (
                        ("missing", result["missing"]), ("web streams skipped", result["streams"]),
                        ("in formats it cannot play", result["unsupported"])) if count]
                    message = f"Imported {result['added']} track{'s' if result['added'] != 1 else ''}"
                    message += f" ({', '.join(left_out)})." if left_out else "."
                    tone, focus = ("ok" if result["added"] else "warn"), result["playlist_id"]
                else:
                    written = library.export_m3u(playlist_id, target)
                    message, tone = f"Exported {written} tracks to {Path(target).name}.", "ok"
            except Exception as exc:
                logging.exception("Music %s failed", operation)
                message, tone = f"That did not work: {exc}", "error"
            self._ui_post(self._music_file_job_done, message, tone, focus, key=f"music-job:{operation}")

        self._music_working = True
        self._schedule_html_dashboard_publish(immediate=True)
        threading.Thread(target=work, name=f"music-{operation}", daemon=True).start()
        return True

    def _music_file_job_done(self, message, tone, focus):
        self._music_working = False
        self._music_say(message, tone)
        if focus:
            self._music_show_playlist(focus)
        self._schedule_html_dashboard_publish(immediate=True)

    # -- what the page is doing -------------------------------------------------------
    def _music_status_report(self, payload):
        repeat = _text(payload.get("repeat"), 8)
        status = {
            "track_id": _text(payload.get("track_id"), 16),
            "next_id": _text(payload.get("next_id"), 16),
            "playlist_id": _text(payload.get("playlist_id"), 40),
            "position": max(0.0, _number(payload.get("position"))),
            "duration": max(0.0, _number(payload.get("duration"))),
            "playing": bool(payload.get("playing")),
            "blocked": bool(payload.get("blocked")),
            "volume": max(0, min(100, int(_number(payload.get("volume"), 80)))),
            "shuffle": bool(payload.get("shuffle")),
            "repeat": repeat if repeat in MUSIC_REPEAT else "all",
            "normalise": bool(payload.get("normalise", True)),
            "reported_at": _number(payload.get("reported_at")),
        }
        self._music_status = status
        self._music_remember(status)
        self._music_update_overlay()

    def _music_remember(self, status):
        """Keep the player's state for the commander, to resume from next time."""
        config = self.config
        lasting = {
            "music_volume": status["volume"], "music_shuffle": status["shuffle"],
            "music_repeat": status["repeat"], "music_normalise": status["normalise"],
            "music_playlist_id": status["playlist_id"],
            "music_track_id": status["track_id"],
        }
        changed = any(config.get(key) != value for key, value in lasting.items())
        now = time.monotonic()
        moved = abs(_number(config.get("music_position")) - status["position"]) > 1
        due = not status["playing"] or now - getattr(self, "_music_saved_at", 0.0) >= MUSIC_POSITION_SAVE_S
        if not changed and not (moved and due):
            return False
        config.update(lasting)
        config["music_position"] = round(status["position"], 1)
        self._music_saved_at = now
        self._persist_config()
        return True

    def _music_update_overlay(self):
        hud = getattr(self, "music_player_hud", None)
        if hud is not None:
            hud.update(getattr(self, "_music_status", None) or {}, self.music_library())

    # -- the visualizer's live levels -------------------------------------------------
    def receive_music_levels(self, payload):
        """Levels from the playing page, on the dashboard server's own thread."""
        bands = (payload or {}).get("bands")
        if not isinstance(bands, list) or not bands or len(bands) > MUSIC_BANDS:
            return False
        try:
            clean = [max(0, min(255, int(value))) for value in bands]
        except (TypeError, ValueError):
            return False
        # One assignment, read whole by the overlay server's thread.
        self._music_levels = {"bands": clean, "at": time.monotonic(), "playing": bool(payload.get("playing"))}
        return True

    def music_levels(self):
        """The newest levels for the overlay; silence once they go stale."""
        levels = getattr(self, "_music_levels", None)
        if not levels or time.monotonic() - levels["at"] > MUSIC_LEVELS_STALE_S:
            return {"bands": [], "playing": False}
        return {"bands": levels["bands"], "playing": levels["playing"]}
