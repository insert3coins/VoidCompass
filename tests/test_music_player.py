"""The music player: the Music page plays, the overlay shows what plays.

The command deck's Music page is the player. It streams each track by id
from the local dashboard server (files play from wherever they are; nothing
is copied), reports what it is doing, and carries out hotkeys. The music
overlay only shows the music, with a visualizer fed live levels from the
playing page. These tests hold the streaming (tokens, byte ranges for
seeking, never a path), the commands and what is remembered for the
commander, the overlay's model and Overlay Studio options, its
registration and hotkeys (media keys included), and both pages running in
a browser against a real library.
"""

import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

from tests.test_music_library import make_flac, make_wav
from voidcompass.core import config as config_module
from voidcompass.core.global_hotkeys import normalize_hotkey
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPEC_BY_ATTR
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.dashboard.html_music import HtmlMusicMixin
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays.html_music_overlay import HtmlMusicPlayerBridge
from voidcompass.overlays.html_overlay_host import _OverlayHost
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer
from voidcompass.overlays.music_player_hud import (
    MUSIC_AUTO_HIDE, MUSIC_COLOURS, MUSIC_LAYOUTS, MUSIC_VISUALIZERS, MusicPlayerHUD, music_overlay_options,
    music_overlay_size,
)
from voidcompass.services.music_library import MusicLibrary

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class Player(HtmlMusicMixin):
    """The dashboard's music side, without the dashboard."""

    def __init__(self, root):
        self._music_root = root
        self.config = {}
        self.persisted = 0
        self.published = 0

    def _persist_config(self):
        self.persisted += 1

    def _schedule_html_dashboard_publish(self, **_kwargs):
        self.published += 1

    def _ui_post(self, callback, *args, key=None, **kwargs):
        callback(*args, **kwargs)


class Folder(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)


class StreamingTests(Folder):
    def setUp(self):
        super().setUp()
        self.library = MusicLibrary(self.folder / "library")
        self.addCleanup(self.library.wait_idle)
        self.song = make_wav(self.folder / "far" / "song.wav", seconds=2, title="Song", cover=True)
        playlist = self.library.create_playlist("P")
        self.library.add_files(playlist, [self.song])
        self.library.wait_idle()
        self.key = self.library.payload()["playlists"][0]["tracks"][0]
        self.server = HtmlDashboardServer(WEB / "dashboard")
        self.addCleanup(self.server.stop)
        self.server.music = self.library

    def get(self, path, headers=None, token=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=5)
        self.addCleanup(connection.close)
        suffix = f"{'&' if '?' in path else '?'}token={self.server.token}" if token else ""
        connection.request("GET", path + suffix, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()

    def test_tracks_stream_whole_or_by_the_range_a_seek_asks_for(self):
        whole = self.song.read_bytes()
        status, headers, body = self.get(f"/media/music/{self.key}")
        self.assertEqual((status, headers["Content-Type"], headers["Accept-Ranges"]), (200, "audio/wav", "bytes"))
        self.assertEqual(body, whole)
        status, headers, body = self.get(f"/media/music/{self.key}", {"Range": "bytes=100-199"})
        self.assertEqual((status, headers["Content-Range"], body), (206, f"bytes 100-199/{len(whole)}", whole[100:200]))
        status, _, body = self.get(f"/media/music/{self.key}", {"Range": "bytes=-50"})
        self.assertEqual((status, body), (206, whole[-50:]))
        status, headers, _ = self.get(f"/media/music/{self.key}", {"Range": f"bytes={len(whole) + 10}-"})
        self.assertEqual((status, headers["Content-Range"]), (416, f"bytes */{len(whole)}"))

    def test_only_library_tracks_by_id_and_only_with_the_token(self):
        self.assertEqual(self.get(f"/media/music/{self.key}", token=False)[0], 403)
        self.assertEqual(self.get("/api/music/library", token=False)[0], 403)
        self.assertEqual(self.get("/media/music/" + "0" * 16)[0], 404)
        for probe in ("/media/music/..%2F..%2Fconfig.json", "/media/music/C:%5CWindows%5Cwin.ini", "/media/art/../x"):
            with self.subTest(probe=probe):
                self.assertEqual(self.get(probe)[0], 404)
        status, headers, body = self.get(f"/media/art/{self.key}.jpg")
        self.assertEqual((status, headers["Content-Type"], body[:2]), (200, "image/jpeg", b"\xff\xd8"))
        status, _, body = self.get("/api/music/library")
        payload = json.loads(body)
        self.assertEqual(payload["tracks"][self.key]["title"], "Song")
        self.assertNotIn(str(self.song), body.decode("utf-8"), "the page never learns file paths")
        self.song.unlink()
        self.assertEqual(self.get(f"/media/music/{self.key}")[0], 404, "a vanished file is simply not found")


class CommandTests(Folder):
    def setUp(self):
        super().setUp()
        self.player = Player(self.folder / "library")
        self.library = self.player.music_library()
        self.addCleanup(self.library.wait_idle)

    def command(self, operation, **payload):
        return self.player._handle_html_music_command({"operation": operation, **payload})

    def wait_for_job(self):
        deadline = time.monotonic() + 5
        while getattr(self.player, "_music_working", False) and time.monotonic() < deadline:
            time.sleep(.02)
        self.library.wait_idle()

    def test_playlists_are_managed_from_the_page(self):
        self.assertTrue(self.command("create_playlist", name="Deep Space"))
        playlist = self.player._html_music_snapshot()["focus"]["playlist_id"]
        self.assertTrue(playlist, "a new playlist is shown to the commander")
        songs = [make_wav(self.folder / "tunes" / f"{n} - Band - Song {n}.wav") for n in (1, 2, 3)]
        self.assertTrue(self.command("add_paths", playlist_id=playlist, paths=[str(self.folder / "tunes")]))
        self.wait_for_job()
        self.assertIn("Added 3 tracks", self.player._html_music_snapshot()["notice"]["text"])
        self.assertTrue(self.command("move_track", playlist_id=playlist, **{"from": 0, "to": 2}))
        self.assertTrue(self.command("remove_tracks", playlist_id=playlist, positions=[0]))
        titles = [self.library.payload()["tracks"][key]["title"] for key in self.library.playlist(playlist)["tracks"]]
        self.assertEqual(titles, ["Song 3", "Song 1"])
        export = self.folder / "out.m3u8"
        self.assertTrue(self.command("export_m3u", playlist_id=playlist, path=str(export)))
        self.wait_for_job()
        self.assertIn(str(songs[2]), export.read_text(encoding="utf-8"))
        self.assertTrue(self.command("import_m3u", path=str(export)))
        self.wait_for_job()
        self.assertEqual([item["name"] for item in self.library.payload()["playlists"]], ["Deep Space", "out"])
        self.assertTrue(self.command("rename_playlist", playlist_id=playlist, name="Drift"))
        self.assertTrue(self.command("delete_playlist", playlist_id=playlist))
        self.assertFalse(self.command("delete_playlist", playlist_id=playlist))
        self.assertFalse(self.command("add_paths", playlist_id="nope", paths=["x"]))
        self.assertFalse(self.command("format_drive"))

    def test_the_player_is_remembered_for_the_commander(self):
        report = {"track_id": "a" * 16, "playlist_id": "p1", "position": 30, "duration": 200, "playing": True,
                  "volume": 55, "shuffle": True, "repeat": "one", "reported_at": 1}
        self.command("status", **report)
        self.assertEqual({key: self.player.config[key] for key in ("music_volume", "music_shuffle", "music_repeat",
                                                                    "music_playlist_id", "music_track_id")},
                         {"music_volume": 55, "music_shuffle": True, "music_repeat": "one",
                          "music_playlist_id": "p1", "music_track_id": "a" * 16})
        saves = self.player.persisted
        # Playing on, the position is not written to disk every second...
        self.command("status", **{**report, "position": 31})
        self.command("status", **{**report, "position": 45})
        self.assertEqual(self.player.persisted, saves)
        # ...but a pause saves exactly where it stopped.
        self.command("status", **{**report, "position": 47, "playing": False})
        self.assertEqual((self.player.persisted, self.player.config["music_position"]), (saves + 1, 47))
        settings = self.player._html_music_snapshot()["settings"]
        self.assertEqual((settings["volume"], settings["repeat"], settings["position"]), (55, "one", 47))
        self.command("status", **{**report, "repeat": "sideways", "volume": 900})
        self.assertEqual((self.player.config["music_repeat"], self.player.config["music_volume"]), ("all", 100))
        # Levelling is on unless the commander turns it off.
        self.assertTrue(self.player._html_music_snapshot()["settings"]["normalise"])
        self.command("status", **{**report, "normalise": False})
        self.assertFalse(self.player.config["music_normalise"])
        self.assertFalse(self.player._html_music_snapshot()["settings"]["normalise"])

    def test_measured_loudness_is_kept_in_the_library(self):
        playlist = self.library.create_playlist("P")
        self.library.add_files(playlist, [make_wav(self.folder / "a.wav", title="A")])
        self.library.wait_idle()
        key = self.library.playlist(playlist)["tracks"][0]
        self.assertTrue(self.command("set_loudness", track_id=key, lufs=-7.5))
        self.assertEqual(self.library.payload()["tracks"][key]["loudness"], -7.5)

    def test_hotkeys_reach_the_page_in_order(self):
        self.assertTrue(self.player.music_remote("toggle"))
        self.assertTrue(self.player.music_remote("next"))
        self.assertFalse(self.player.music_remote("eject"))
        self.assertEqual(self.player._html_music_snapshot()["remote"], {"seq": 2, "op": "next"})
        app = MainDashboard.__new__(MainDashboard)
        app.is_running = True
        app.music_remote = Mock()
        app._handle_overlay_hotkey("music_play_pause")
        app._handle_overlay_hotkey("music_previous")
        self.assertEqual([call.args[0] for call in app.music_remote.call_args_list], ["toggle", "previous"])

    def test_visualizer_levels_are_kept_briefly_for_the_overlay(self):
        self.assertTrue(self.player.receive_music_levels({"bands": [0, 300, -5, 128], "playing": True}))
        self.assertEqual(self.player.music_levels(), {"bands": [0, 255, 0, 128], "playing": True})
        self.assertFalse(self.player.receive_music_levels({"bands": list(range(100))}))
        self.assertFalse(self.player.receive_music_levels({"bands": ["loud"]}))
        self.player._music_levels["at"] -= 5
        self.assertEqual(self.player.music_levels(), {"bands": [], "playing": False}, "stale levels are silence")


class OverlayTests(Folder):
    def test_options_stay_within_their_choices(self):
        self.assertEqual(music_overlay_options({}), {
            "layout": "card", "visualizer": "bars", "colour": "theme", "show_art": True, "show_details": True,
            "show_next": True, "auto_hide": 0, "text_scale_percent": 0})
        wild = music_overlay_options({"music_player_layout": "hologram", "music_player_visualizer": "lasers",
                                      "music_player_colour": "plaid", "music_player_auto_hide": 7,
                                      "music_player_text_scale_percent": 999})
        self.assertEqual((wild["layout"], wild["visualizer"], wild["colour"], wild["auto_hide"],
                          wild["text_scale_percent"]), ("card", "bars", "theme", 0, 200))
        self.assertEqual(music_overlay_size({}), (460, 154))
        self.assertEqual(music_overlay_size({"music_player_show_next": False}), (460, 136))
        self.assertEqual(music_overlay_size({"music_player_layout": "strip"}), (580, 44))
        self.assertEqual(music_overlay_size({"music_player_text_scale_percent": 150}), (690, 231))
        self.assertEqual(music_overlay_size({"overlay_text_scale_percent": 125, "music_player_layout": "strip"}),
                         (725, 55))

    def test_the_model_shows_the_track_its_tags_and_what_is_next(self):
        from voidcompass.core.application_runtime import ApplicationRuntime
        runtime = ApplicationRuntime()
        self.addCleanup(runtime.close)
        library = MusicLibrary(self.folder / "library")
        self.addCleanup(library.wait_idle)
        playlist = library.create_playlist("Deep Space Radio")
        library.add_files(playlist, [make_flac(self.folder / "a.flac", title="Aurora", artist="Solar Fields",
                                               album="Movements", date="2009", cover=True),
                                     make_wav(self.folder / "Vangelis - Rachel's Song.wav")])
        library.wait_idle()
        first, second = library.playlist(playlist)["tracks"]
        hud = MusicPlayerHUD(runtime, {"music_player_auto_hide": 10})
        self.addCleanup(hud.destroy)
        self.assertEqual(hud._html_render_model["state"], "idle")
        hud.update({"track_id": first, "next_id": second, "playlist_id": playlist, "playing": True,
                    "position": 12, "reported_at": 5}, library)
        model = hud._html_render_model
        self.assertEqual((model["state"], model["track"]["title"], model["track"]["album"], model["track"]["year"]),
                         ("playing", "Aurora", "Movements", "2009"))
        self.assertEqual((model["next"], model["playlist"]), ({"title": "Rachel's Song", "artist": "Vangelis"},
                                                              "Deep Space Radio"))
        self.assertTrue(model["art"].startswith("data:image/jpeg;base64,"))
        self.assertFalse(hud.hidden_while_idle())
        hud.update({"track_id": first, "playing": False}, library)
        self.assertEqual(hud._html_render_model["state"], "paused")
        hud._idle_since -= 11
        self.assertTrue(hud.hidden_while_idle(), "paused past its auto-hide")
        hud.config["music_player_show_art"] = False
        hud.config["music_player_show_next"] = False
        hud.apply_settings()
        self.assertEqual((hud._html_render_model["art"], hud._html_render_model["next"]), ("", None))
        hud.update({"track_id": first, "blocked": True}, library)
        self.assertEqual(hud._html_render_model["state"], "blocked")

    def test_the_bridge_sizes_hides_and_serves_live_levels(self):
        bridge = HtmlMusicPlayerBridge.__new__(HtmlMusicPlayerBridge)
        bridge.config = {"music_player_layout": "strip"}
        self.assertEqual(bridge._dimensions(), (580, 44))
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        server.register("music-player", "music_player", "Music")
        server.set_live_provider("music-player", lambda: {"bands": [9, 8], "playing": True})
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        self.addCleanup(connection.close)
        connection.request("GET", f"/api/live?token={server.token}&overlay=music-player")
        self.assertEqual(json.loads(connection.getresponse().read()), {"bands": [9, 8], "playing": True})
        connection.request("GET", "/api/live?overlay=music-player")
        self.assertEqual(connection.getresponse().status, 403)


class RegistrationTests(unittest.TestCase):
    def test_it_is_a_managed_overlay_with_player_hotkeys(self):
        spec = OVERLAY_SPEC_BY_ATTR["music_player_hud"]
        self.assertEqual((spec.enabled_key, spec.default_enabled), ("music_player_overlay_enabled", False))
        actions = {action: key for action, key, _label, _attr in OVERLAY_HOTKEY_SPECS}
        for action in ("music_player", "music_play_pause", "music_next", "music_previous"):
            self.assertIn(action, actions)
            self.assertIn(actions[action], config_module.PROFILE_TEXT_SETTINGS)
        host = _OverlayHost.__new__(_OverlayHost)
        host.token, host.origin = "t", "http://127.0.0.1:1"
        self.assertIn("/music_player/index.html", host.page_url("music-player", "music_player"))

    def test_media_keys_work_alone_other_keys_still_need_a_modifier(self):
        self.assertEqual(normalize_hotkey("MediaPlayPause"), "MediaPlayPause")
        self.assertEqual(normalize_hotkey("media next"), "MediaNext")
        self.assertEqual(normalize_hotkey("Ctrl+Alt+MediaPrevious"), "Ctrl+Alt+MediaPrevious")
        with self.assertRaises(ValueError):
            normalize_hotkey("P")

    def test_every_setting_follows_the_commander_profile(self):
        for key in ("music_player_overlay_enabled", "music_player_show_art", "music_player_show_details",
                    "music_player_show_next", "music_shuffle", "music_normalise"):
            self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS)
        for key in ("music_repeat", "music_playlist_id", "music_track_id", "music_player_layout",
                    "music_player_visualizer", "music_player_colour"):
            self.assertIn(key, config_module.PROFILE_TEXT_SETTINGS)
        for key in ("music_player_hud_x", "music_player_hud_y", "music_player_text_scale_percent",
                    "music_player_auto_hide", "music_volume", "music_position"):
            self.assertIn(key, config_module.PROFILE_VALUE_SETTINGS)

    def test_studio_saves_and_validates_the_overlay_options(self):
        class Studio(HtmlOverlayStudioMixin):
            def __init__(self):
                self.config = {}
                self.music_player_hud = SimpleNamespace(apply_settings=Mock())

            def _persist_config(self):
                pass

            def update_hud(self):
                pass

            def _schedule_html_dashboard_publish(self, **kwargs):
                pass

        studio = Studio()
        studio._html_overlay_settings_save({"music_player_layout": "STRIP", "music_player_visualizer": "wave",
                                            "music_player_colour": "spectrum", "music_player_auto_hide": "30",
                                            "music_player_text_scale_percent": "140"})
        self.assertEqual({key: studio.config[key] for key in studio.config}, {
            "music_player_layout": "strip", "music_player_visualizer": "wave", "music_player_colour": "spectrum",
            "music_player_auto_hide": 30, "music_player_text_scale_percent": 140})
        studio._html_overlay_settings_save({"music_player_layout": "cube", "music_player_auto_hide": "45",
                                            "music_player_text_scale_percent": "0"})
        self.assertEqual((studio.config["music_player_layout"], studio.config["music_player_auto_hide"],
                          studio.config["music_player_text_scale_percent"]), ("card", 0, 0))
        for key in ("music_player_show_art", "music_player_show_details", "music_player_show_next"):
            self.assertTrue(studio._html_overlay_option_toggle(key, False))
            self.assertFalse(studio.config[key])
        self.assertGreaterEqual(studio.music_player_hud.apply_settings.call_count, 5)

    def test_studio_offers_exactly_the_supported_choices(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="music_player_hud">(.*?)</section>', html, re.S).group(1)
        choices = lambda key: re.findall(r'value="([^"]+)"',  # noqa: E731
                                         re.search(rf'data-studio-setting="{key}">(.*?)</select>', section, re.S).group(1))
        self.assertEqual(tuple(choices("music_player_layout")), tuple(MUSIC_LAYOUTS))
        self.assertEqual(tuple(choices("music_player_visualizer")), MUSIC_VISUALIZERS)
        self.assertEqual(tuple(choices("music_player_colour")), MUSIC_COLOURS)
        self.assertEqual(tuple(int(value) for value in choices("music_player_auto_hide")), MUSIC_AUTO_HIDE)
        for option in ("music_player_show_art", "music_player_show_details", "music_player_show_next"):
            self.assertIn(f'data-overlay-option="{option}"', section)
        self.assertIn('data-studio-setting="music_player_text_scale_percent"', section)


class BrowserTests(Folder):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(
                headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def deck(self, settings=None, prepare=None):
        """The real dashboard server and page, with a real library behind it.

        `settings(playlist, tracks)` gives the saved player state to resume;
        `prepare(library, tracks)` changes the library before the page loads.
        """
        from tests.test_dashboard_overview_visuals import overview_state
        library = MusicLibrary(self.folder / "library")
        self.addCleanup(library.wait_idle)
        playlist = library.create_playlist("Deep Space Radio")
        files = [make_wav(self.folder / "music" / f"0{n} - Band {n} - Track {n}.wav", seconds=6) for n in (1, 2, 3)]
        library.add_files(playlist, files)
        library.wait_idle()
        tracks = library.playlist(playlist)["tracks"]
        if prepare:
            prepare(library, tracks)
        commands = []
        server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images",
                                     command_callback=lambda payload: commands.append(payload) or True)
        self.addCleanup(server.stop)
        server.music = library
        state = overview_state()
        state["music"] = {
            "library_revision": library.revision,
            "settings": {"volume": 70, "shuffle": False, "repeat": "all", "playlist_id": "", "track_id": "",
                         "position": 0, **(settings(playlist, tracks) if settings else {})},
            "remote": {"seq": 0, "op": ""}, "focus": {"seq": 0, "playlist_id": ""},
            "notice": {"seq": 0, "text": "", "tone": ""}, "working": False, "overlay": True,
        }
        server.publish(state)
        context = self.browser.new_context(viewport={"width": 1600, "height": 900}, bypass_csp=True)
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        page.goto(server.url)
        page.wait_for_function("document.body.classList.contains('ready') && window.voidcompassMusic", timeout=15000)
        return SimpleNamespace(page=page, server=server, library=library, playlist=playlist, state=state,
                               commands=commands, tracks=tracks)

    def test_the_music_page_lists_plays_and_reports(self):
        deck = self.deck()
        page = deck.page
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        self.assertEqual(page.locator(".music-playlist").count(), 1)
        self.assertEqual(page.locator(".music-row .music-name b").all_inner_texts(), ["Track 1", "Track 2", "Track 3"])
        page.locator(".music-row").nth(1).dblclick()
        page.wait_for_function("window.voidcompassMusic.state().playing")
        state = page.evaluate("window.voidcompassMusic.state()")
        self.assertEqual((state["currentId"], state["index"]), (deck.tracks[1], 1))
        self.assertTrue(state["src"].startswith(f"/media/music/{deck.tracks[1]}?token="))
        self.assertEqual(page.locator("#music-title").inner_text(), "Track 2")
        page.wait_for_timeout(1300)
        statuses = [command for command in deck.commands if command.get("operation") == "status"]
        self.assertTrue(statuses and statuses[-1]["track_id"] == deck.tracks[1] and statuses[-1]["playing"])
        self.assertEqual(statuses[-1]["next_id"], deck.tracks[2])
        self.assertTrue(any(command.get("action") == "music_levels" for command in deck.commands),
                        "the overlay is fed while it is on")
        page.locator("#music-next").click()
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{deck.tracks[2]}'")
        # Repeat all wraps round to the first track.
        page.locator("#music-next").click()
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{deck.tracks[0]}'")
        page.locator("#music-play").click()
        page.wait_for_function("!window.voidcompassMusic.state().playing")

    def test_hotkeys_arrive_in_the_snapshot_and_are_not_replayed(self):
        deck = self.deck()
        page = deck.page
        page.wait_for_function("window.voidcompassMusic.state().revision >= 0")
        deck.state["music"]["remote"] = {"seq": 1, "op": "toggle"}
        deck.server.publish(deck.state)
        page.wait_for_function("window.voidcompassMusic.state().playing", timeout=6000)
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().currentId"), deck.tracks[0])
        deck.state["music"]["remote"] = {"seq": 2, "op": "next"}
        deck.server.publish(deck.state)
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{deck.tracks[1]}'", timeout=6000)
        # A reloaded page doesn't replay the hotkeys that came before it (a
        # replayed "next" would move it on to track 3). Reloaded mid-song, as
        # when WebView2 loses its renderer, the music carries on.
        page.wait_for_timeout(1300)
        mark = len(deck.commands)
        page.reload()
        page.wait_for_function("document.body.classList.contains('ready') && window.voidcompassMusic")
        page.wait_for_function("window.voidcompassMusic.state().playing", timeout=6000)
        # The reloaded page's reports: it carried on with track 2 from where it
        # was (these tracks are short, so it may have moved on since).
        reports = [command for command in deck.commands[mark + 1:]
                   if command.get("operation") == "status" and command.get("playing")]
        self.assertEqual(reports[0]["track_id"], deck.tracks[1])
        self.assertGreater(reports[0]["position"], 1.0)

    def test_a_fresh_start_resumes_paused_even_after_playing_last_time(self):
        # Paused before the reload: it comes back paused, as on any fresh start.
        deck = self.deck()
        page = deck.page
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        page.locator(".music-row").nth(0).dblclick()
        page.wait_for_function("window.voidcompassMusic.state().playing")
        page.locator("#music-play").click()
        page.wait_for_function("!window.voidcompassMusic.state().playing")
        page.wait_for_timeout(300)
        page.reload()
        page.wait_for_function("document.body.classList.contains('ready') && window.voidcompassMusic")
        page.wait_for_timeout(1200)
        self.assertFalse(page.evaluate("window.voidcompassMusic.state().playing"))

    def test_repeat_all_goes_round_to_the_first_track_after_the_last(self):
        deck = self.deck(settings=lambda playlist, tracks: {"repeat": "all"})
        page, tracks = deck.page, deck.tracks
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        page.locator(".music-row").nth(2).dblclick()
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{tracks[2]}' && window.voidcompassMusic.state().playing")
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().repeat"), "all")
        page.wait_for_function("Number.isFinite(window.voidcompassMusic.audio.duration)")
        page.evaluate("() => { const a = window.voidcompassMusic.audio; a.currentTime = Math.max(0, a.duration - .4); }")
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{tracks[0]}'", timeout=8000)
        page.wait_for_function("window.voidcompassMusic.state().playing", timeout=4000)

    def test_it_resumes_paused_where_the_commander_left_off(self):
        deck = self.deck(settings=lambda playlist, tracks: {
            "playlist_id": playlist, "track_id": tracks[2], "position": 4.0,
            "shuffle": True, "repeat": "one", "volume": 35},
            prepare=lambda library, tracks: library.set_loudness(tracks[2], -14))
        page, tracks = deck.page, deck.tracks
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{tracks[2]}'", timeout=8000)
        state = page.evaluate("window.voidcompassMusic.state()")
        self.assertEqual((state["playing"], state["shuffle"], state["repeat"], state["volume"]), (False, True, "one", 35))
        # 35% is 26 dB under full volume, and this -14 LUFS track is levelled
        # 6 dB down to the -20 LUFS target.
        self.assertAlmostEqual(page.evaluate("window.voidcompassMusic.audio.volume"), 10 ** (-32 / 20))
        page.locator('.nav-item[data-page="music"]').click()
        page.locator("#music-level").click()
        # Levelling off: every track 11 dB down, as mastered.
        self.assertAlmostEqual(page.evaluate("window.voidcompassMusic.audio.volume"), 10 ** (-37 / 20))
        self.assertEqual(page.locator("#music-level").get_attribute("aria-pressed"), "false")
        self.assertEqual(state["order"][0], tracks[2], "a shuffle starts from the remembered track")
        page.wait_for_function("Math.abs(window.voidcompassMusic.audio.currentTime - 4) < .6", timeout=8000)

    def test_volume_slider_is_an_even_taper_in_decibels(self):
        # Full volume puts an unmeasured track 11 dB down; every step below is
        # 0.4 dB, so the whole slider is usable instead of its bottom few steps.
        deck = self.deck()
        page = deck.page
        page.locator('.nav-item[data-page="music"]').click()
        for setting, output in ((0, 0.0), (50, 10 ** (-31 / 20)), (75, 10 ** (-21 / 20)), (100, 10 ** (-11 / 20))):
            page.evaluate("""value => {
                const slider = document.querySelector('#music-volume');
                slider.value = String(value);
                slider.dispatchEvent(new Event('input', {bubbles: true}));
            }""", setting)
            self.assertEqual(page.evaluate("window.voidcompassMusic.state().volume"), setting)
            self.assertEqual(page.locator("#music-volume-value").inner_text(), str(setting))
            self.assertAlmostEqual(page.evaluate("window.voidcompassMusic.audio.volume"), output)


class OverlayBrowserTests(unittest.TestCase):
    STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
            " window.renderMusic = options.render; return {rerender() {}}; }};")

    @classmethod
    def setUpClass(cls):
        BrowserTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open(self, width=460, height=154):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors, polls = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/live":
                polls.append(time.monotonic())
                route.fulfill(content_type="application/json", body=json.dumps({"bands": [200] * 32, "playing": True}))
                return
            file = WEB / path.lstrip("/")
            if not file.is_file():
                route.fulfill(status=404, body="")
            elif file.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + self.STUB)
            else:
                route.fulfill(path=str(file))

        page.route("http://music.test/**", serve)
        page.goto("http://music.test/music_player/index.html")
        page.wait_for_function("Boolean(window.renderMusic)")
        return page, polls

    @staticmethod
    def snapshot(state="playing", reduced=False, **options):
        return {"theme": {}, "effects": {"crt": True, "reduced_motion": reduced, "text_scale": 1},
                "music": {"state": state, "track": {"id": "a" * 16, "title": "Aurora", "artist": "Solar Fields",
                                                      "album": "Movements", "year": "2009", "format": "FLAC",
                                                      "duration": 300},
                          "next": {"title": "Rachel's Song", "artist": "Vangelis"}, "playlist": "Deep Space",
                          "position": 60, "reported_at": time.time() * 1000, "shuffle": False, "repeat": "all",
                          "art": "", "options": {"layout": "card", "visualizer": "bars", "colour": "theme",
                                                 "show_art": True, "show_details": True, "show_next": True,
                                                 **options}}}

    def test_the_strip_scrolls_its_whole_line_title_and_artist(self):
        page, _ = self.open(width=580, height=44)
        snapshot = self.snapshot(layout="strip")
        snapshot["music"]["track"].update(title="Hyperspace Is A Long Way Down, And It Keeps Going",
                                          artist="Erasmus Kodiak and the Witch-space Orchestra")
        page.evaluate("s => renderMusic(s)", snapshot)
        page.wait_for_timeout(300)
        self.assertIn("Erasmus Kodiak", page.inner_text("#title"), "the artist rides in the title's window")
        self.assertTrue(page.evaluate("musicPlayerOverlay.state().scrolling"))
        # A line that fits stays still.
        snapshot["music"]["track"].update(id="b" * 16, title="Aurora", artist="Solar Fields")
        page.evaluate("s => renderMusic(s)", snapshot)
        page.wait_for_timeout(300)
        self.assertFalse(page.evaluate("musicPlayerOverlay.state().scrolling"))

    def test_it_shows_the_track_and_runs_the_clock_on(self):
        page, _ = self.open()
        page.evaluate("s => renderMusic(s)", self.snapshot())
        self.assertEqual(page.inner_text("#title"), "Aurora")
        self.assertIn("Movements", page.inner_text("#details"))
        self.assertIn("Rachel's Song", page.inner_text("#next-title"))
        first = page.inner_text("#elapsed")
        page.wait_for_timeout(1200)
        self.assertNotEqual(page.inner_text("#elapsed"), first, "the position runs on between reports")

    def test_the_visualizer_listens_only_while_music_plays(self):
        page, polls = self.open()
        page.evaluate("s => renderMusic(s)", self.snapshot())
        page.wait_for_timeout(700)
        self.assertGreater(len(polls), 4)
        self.assertGreater(page.evaluate("musicPlayerOverlay.state().level"), .2)
        page.evaluate("s => renderMusic(s)", self.snapshot(state="paused"))
        count = len(polls)
        page.wait_for_timeout(500)
        self.assertLessEqual(len(polls) - count, 1, "paused, it stops asking")
        page.evaluate("s => renderMusic(s)", self.snapshot(visualizer="off"))
        page.wait_for_timeout(300)
        self.assertEqual(page.evaluate("musicPlayerOverlay.state().visualizer"), "off")
        page.evaluate("s => renderMusic(s)", self.snapshot(reduced=True))
        self.assertEqual(page.evaluate("musicPlayerOverlay.state().visualizer"), "off", "reduced motion keeps it still")

    def test_the_strip_is_one_slim_line(self):
        page, _ = self.open(580, 44)
        page.evaluate("s => renderMusic(s)", self.snapshot(layout="strip"))
        state = page.evaluate("musicPlayerOverlay.state()")
        self.assertEqual((state["layout"], state["next"]), ("strip", ""))
        box = page.locator("#player").bounding_box()
        self.assertLessEqual(box["height"], 44)


if __name__ == "__main__":
    unittest.main()
