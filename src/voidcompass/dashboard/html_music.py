"""The Music page and its player, from Python's side.

The dashboard page is the player: it streams each track from the local
dashboard server (/media/music/<id>) and reports what it is doing about once
a second. Python keeps the library (services.music_library), remembers the
player for the commander so it resumes next time, hands hotkeys to the page,
and feeds the music overlay, including the visualizer's live levels.
"""

from __future__ import annotations

from datetime import datetime, timezone
import bisect
import logging
from pathlib import Path
import threading
import time

from voidcompass.services.music_library import MusicLibrary
from voidcompass.services.music_scenes import FADES, SCENES, follow_settings, scene_of

MUSIC_REPEAT = ("off", "all", "one")
MUSIC_REMOTE = ("toggle", "next", "previous")
# The playing position is saved this often at most (track, playlist and
# settings changes are saved at once), so config.json is not rewritten
# every second while music plays.
MUSIC_POSITION_SAVE_S = 20.0
# Levels older than this are silence: the page has stopped sending them.
MUSIC_LEVELS_STALE_S = 1.0
MUSIC_BANDS = 64
MUSIC_WAVE_POINTS = 64
# The Music page's RECENTLY PLAYED (5.5.17).
MUSIC_RECENT = 20
WEEK_S = 7 * 86400


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
            # Music that flies with you (5.5.3.8): the settings and what the
            # game is doing now.
            "follow": follow_settings(config),
            **scene_of(getattr(self, "current_status_flags", 0), getattr(self, "current_status_flags2", 0),
                       getattr(self, "_music_population", None)),
            "stats": self._music_stats(),
        }

    def _music_stats(self):
        """Your listening, from the music diary: plays per track, the last
        few with where you were, and roughly how long you've listened."""
        diary_of = getattr(self, "music_diary", None)
        if not callable(diary_of):
            return {"revision": 0, "plays": {}, "recent": [], "listening": {}}
        try:
            diary = diary_of()
        except Exception:
            return {"revision": 0, "plays": {}, "recent": [], "listening": {}}
        library = self.music_library()
        history = getattr(self, "travel_history", None)
        travel = len(getattr(history, "rows", None) or ())
        key = (id(diary), diary.revision, library.revision, travel)
        cached = getattr(self, "_music_stats_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        with diary.lock:
            rows = [list(row) for row in diary.rows]
        plays, listened_all, listened_week = {}, 0.0, 0.0
        week_from = time.time() - WEEK_S
        for index, row in enumerate(rows):
            started, track_id = float(row[0] or 0), str(row[1])
            count, last = plays.get(track_id, (0, 0.0))
            plays[track_id] = (count + 1, max(last, started))
            # Only starts are logged: a play lasts until the next one starts,
            # or its track's length if that's sooner.
            gap = float(rows[index + 1][0]) - started if index + 1 < len(rows) else 0.0
            length = float((library.track(track_id) or {}).get("duration") or 600.0)
            heard = max(0.0, min(gap, length)) if gap else 0.0
            listened_all += heard
            if started >= week_from:
                listened_week += heard
        recent = []
        for row in reversed(rows[-MUSIC_RECENT:]):
            recent.append({"at": float(row[0] or 0), "track_id": str(row[1]), "title": str(row[2] or ""),
                           "artist": str(row[3] or ""), "system": self._music_system_at(float(row[0] or 0))})
        top = max(plays.items(), key=lambda item: (item[1][0], item[1][1]), default=None)
        stats = {
            "revision": diary.revision,
            "plays": {track_id: [count, round(last, 1)] for track_id, (count, last) in plays.items()},
            "recent": recent,
            "listening": {"week_s": round(listened_week), "all_s": round(listened_all),
                          "top": {"track_id": top[0], "count": top[1][0],
                                  "title": next((str(row[2]) for row in reversed(rows) if str(row[1]) == top[0]), "")}
                          if top else None},
        }
        self._music_stats_cache = (key, stats)
        return stats

    def _music_system_at(self, moment):
        """The system you were in at a unix time, from the travel history."""
        history = getattr(self, "travel_history", None)
        if history is None or not moment:
            return ""
        stamp = datetime.fromtimestamp(moment, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with history.lock:
                times = getattr(self, "_music_travel_times", None)
                if times is None or times[0] != len(history.rows):
                    times = (len(history.rows), [str(row[0]) for row in history.rows])
                    self._music_travel_times = times
                index = bisect.bisect_right(times[1], stamp) - 1
                return str(history.rows[index][1]) if index >= 0 else ""
        except Exception:
            return ""

    def _music_observe(self, event, raw):
        """A jump or login: how many live in this system (deep space is
        where nobody does)."""
        if event in ("FSDJump", "Location", "CarrierJump") and isinstance(raw, dict):
            self._music_population = raw.get("Population")

    def _music_follow_set(self, key, value):
        """A Follow the game setting from the Music page."""
        if key == "music_follow_game" or key == "music_jump_duck":
            self.config[key] = value is True or str(value).casefold() in {"1", "true", "on"}
        elif key == "music_follow_fade_s":
            try:
                fade = int(float(value))
            except (TypeError, ValueError):
                return False
            if fade not in FADES:
                return False
            self.config[key] = fade
        elif key in SCENES:
            playlist = _text(value, 40)
            if playlist and self.music_library().playlist(playlist) is None:
                return False
            settings = follow_settings(self.config)
            chosen = dict(settings["playlists"])
            chosen[key] = playlist
            self.config["music_scene_playlists"] = chosen
            # A song chosen from another playlist no longer belongs.
            songs = dict(settings["tracks"])
            if songs.get(key) and songs[key] not in ((self.music_library().playlist(playlist) or {}).get("tracks") or ()):
                songs[key] = ""
                self.config["music_scene_tracks"] = songs
        elif key.startswith("track:") and key[6:] in SCENES:
            scene, track = key[6:], _text(value, 16)
            settings = follow_settings(self.config)
            playlist = self.music_library().playlist(settings["playlists"][scene])
            if track and (playlist is None or track not in (playlist.get("tracks") or ())):
                return False
            songs = dict(settings["tracks"])
            songs[scene] = track
            self.config["music_scene_tracks"] = songs
        else:
            return False
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        return True

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
        if operation == "follow_set":
            done = self._music_follow_set(_text(payload.get("key"), 40), payload.get("value"))
            self._schedule_html_dashboard_publish(immediate=True)
            return done
        if operation == "set_duration":
            library.set_duration(_text(payload.get("track_id"), 16), payload.get("duration"))
        elif operation == "set_loudness":
            library.set_loudness(_text(payload.get("track_id"), 16), payload.get("lufs"))
            return True
        elif operation == "set_resume":
            library.set_resume(_text(payload.get("track_id"), 16), payload.get("position"), payload.get("duration"))
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
        elif operation == "move_tracks":
            positions = [int(_number(value, -1)) for value in list(payload.get("positions") or [])[:5000]]
            if not library.move_tracks(playlist_id, positions, int(_number(payload.get("to"), -1))):
                return False
        elif operation == "add_tracks":
            ids = [_text(value, 16) for value in list(payload.get("track_ids") or [])[:5000]]
            added = library.add_existing(playlist_id, ids)
            if not added:
                return False
            name = (library.playlist(playlist_id) or {}).get("name") or "the playlist"
            self._music_say(f"Added {added} track{'s' if added != 1 else ''} to {name}.")
        elif operation == "relink":
            found = library.relink(_text(payload.get("track_id"), 16), _text(payload.get("path"), 2048))
            if not found:
                self._music_say("That isn't a music file Void Compass can play.", "warn")
            else:
                more = found - 1
                self._music_say("Found it." + (f" And {more} more from the same folder." if more else ""))
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
            # For the overlay (5.5.17): the next three, and the scene it plays for.
            "upcoming": [{"id": _text(item.get("id"), 16), "queued": bool(item.get("queued"))}
                         for item in (payload.get("upcoming") if isinstance(payload.get("upcoming"), list) else [])
                         if isinstance(item, dict)][:3],
            "scene": _text(payload.get("scene"), 12),
        }
        previous = getattr(self, "_music_status", None) or {}
        self._music_status = status
        self._music_remember(status)
        self._music_update_overlay()
        if (previous.get("track_id"), previous.get("playing")) == (status["track_id"], status["playing"]):
            return
        track = self.music_library().track(status["track_id"]) or {} if status["track_id"] else {}
        # The music diary (5.5.10): each track as it starts.
        if status["playing"] and status["track_id"] and hasattr(self, "_music_diary_note"):
            self._music_diary_note(status["track_id"], track)
        if hasattr(self, "_api_publish"):
            self._api_publish("music", {"playing": status["playing"], "track_id": status["track_id"],
                                        "title": track.get("title") or "", "artist": track.get("artist") or ""})

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
        if status["track_id"] and moved:
            # A long mix's place, for the next time it plays.
            self.music_library().set_resume(status["track_id"], status["position"], status["duration"])
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
        # The waveform's slice (5.6.2), for the overlay's Wave and VU looks.
        wave = payload.get("wave")
        try:
            shape = [max(0, min(255, int(value))) for value in wave[:MUSIC_WAVE_POINTS]] if isinstance(wave, list) else []
        except (TypeError, ValueError):
            shape = []
        # One assignment, read whole by the overlay server's thread.
        self._music_levels = {"bands": clean, "wave": shape, "at": time.monotonic(), "playing": bool(payload.get("playing"))}
        return True

    def music_levels(self):
        """The newest levels for the overlay; silence once they go stale."""
        levels = getattr(self, "_music_levels", None)
        if not levels or time.monotonic() - levels["at"] > MUSIC_LEVELS_STALE_S:
            return {"bands": [], "wave": [], "playing": False}
        return {"bands": levels["bands"], "wave": levels.get("wave") or [], "playing": levels["playing"]}
