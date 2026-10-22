"""5.5.17: the Music page, given some love. Long mixes resume where they were
left, the track list selects, sorts, drags and finds moved files, there's a
queue, and your listening (from the music diary) shows on the page, with the
system you were in."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import os
import unittest

from tests.test_music_library import make_wav
from tests import test_music_player
from tests.test_music_player import BrowserTests, Player
from voidcompass.services.music_diary import MusicDiary
from voidcompass.services.music_library import RESUME_MIN_TRACK_S, MusicLibrary

ROOT = Path(__file__).resolve().parents[1]


class Folder(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.library = MusicLibrary(self.folder / "library")
        self.addCleanup(self.library.wait_idle)
        self.files = [make_wav(self.folder / "music" / f"0{n} - Band - Track {n}.wav", seconds=1) for n in (1, 2, 3, 4)]
        self.playlist = self.library.create_playlist("Mixes")
        self.library.add_files(self.playlist, self.files)
        self.library.wait_idle()
        self.tracks = list(self.library.playlist(self.playlist)["tracks"])


class LibraryTests(Folder):
    def test_a_long_mix_remembers_where_it_was_left(self):
        key = self.tracks[0]
        self.library.set_duration(key, 3 * 3600)
        self.assertTrue(self.library.set_resume(key, 5400))
        self.assertEqual(self.library.resume_at(key), 5400)
        self.assertEqual(self.library.payload()["resume"], {key: 5400.0})
        reopened = MusicLibrary(self.folder / "library")
        self.assertEqual(reopened.resume_at(key), 5400, "kept across restarts")
        self.assertTrue(self.library.set_resume(key, 3 * 3600 - 30), "near the end: forgotten")
        self.assertEqual(self.library.resume_at(key), 0)
        self.assertFalse(self.library.set_resume(key, 10), "nothing to forget at the start")

    def test_short_tracks_are_never_resumed(self):
        self.library.set_duration(self.tracks[1], RESUME_MIN_TRACK_S - 60)
        self.assertFalse(self.library.set_resume(self.tracks[1], 300))
        self.assertTrue(self.library.set_resume(self.tracks[1], 300, duration=RESUME_MIN_TRACK_S + 1),
                        "the player's measured length counts")

    def test_several_tracks_move_together(self):
        self.assertTrue(self.library.move_tracks(self.playlist, [0, 2], 4))
        self.assertEqual(self.library.playlist(self.playlist)["tracks"],
                         [self.tracks[1], self.tracks[3], self.tracks[0], self.tracks[2]])
        self.assertTrue(self.library.move_tracks(self.playlist, [3], 0))
        self.assertEqual(self.library.playlist(self.playlist)["tracks"][0], self.tracks[2])
        self.assertFalse(self.library.move_tracks(self.playlist, [0], 0), "already there")

    def test_copy_into_another_playlist(self):
        other = self.library.create_playlist("Keepers")
        self.assertEqual(self.library.add_existing(other, [self.tracks[1], "0" * 16, self.tracks[3]]), 2)
        self.assertEqual(self.library.playlist(other)["tracks"], [self.tracks[1], self.tracks[3]])

    def test_a_moved_folder_is_found_from_one_file(self):
        moved = self.folder / "moved"
        moved.mkdir()
        for file in self.files[:3]:
            Path(file).rename(moved / Path(file).name)
        self.library.recheck_files()
        self.assertTrue(self.library.missing(self.tracks[0]))
        self.assertEqual(self.library.relink(self.tracks[0], moved / Path(self.files[0]).name), 3, "the rest of the folder too")
        self.library.wait_idle()
        self.assertFalse(any(self.library.missing(key) for key in self.tracks))
        self.assertEqual(self.library.playlist(self.playlist)["tracks"], self.tracks, "same tracks, same order")
        self.assertEqual(self.library.relink(self.tracks[0], self.folder / "nope.wav"), 0)

    def test_payload_says_when_each_was_added(self):
        payload = self.library.payload()
        self.assertTrue(all(payload["tracks"][key]["added"] > 0 for key in self.tracks))


class StatsTests(Folder):
    def player(self):
        player = Player(self.folder)
        player._music_library_instance = self.library
        diary = MusicDiary(str(self.folder / "diary.json"))
        player.music_diary = lambda: diary
        stamp = lambda moment: datetime.fromtimestamp(moment, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        now = time.time()

        class History:
            lock = __import__("threading").RLock()
            rows = [[stamp(now - 7200), "Sol", 0, 0, 0, "G", 0, ""], [stamp(now - 1800), "Colonia", 1, 2, 3, "K", 9, ""]]
        player.travel_history = History()
        for track in self.tracks:
            self.library.set_duration(track, 600)
        diary.note(now - 5000, self.tracks[0], "Track 1", "Band")
        diary.note(now - 4000, self.tracks[1], "Track 2", "Band")
        diary.note(now - 1000, self.tracks[0], "Track 1", "Band")
        return player

    def test_plays_recent_and_where_you_were(self):
        stats = self.player()._music_stats()
        self.assertEqual(stats["plays"][self.tracks[0]][0], 2)
        self.assertEqual([row["track_id"] for row in stats["recent"]], [self.tracks[0], self.tracks[1], self.tracks[0]])
        self.assertEqual([row["system"] for row in stats["recent"]], ["Colonia", "Sol", "Sol"])
        self.assertEqual(stats["listening"]["top"]["track_id"], self.tracks[0])
        self.assertEqual(stats["listening"]["week_s"], 1200, "each play lasts its track or until the next started")

    def test_cached_until_something_changes(self):
        player = self.player()
        first = player._music_stats()
        self.assertIs(player._music_stats(), first)
        player.music_diary().note(time.time(), self.tracks[2], "Track 3", "Band")
        self.assertIsNot(player._music_stats(), first)

    def test_page_commands(self):
        player = self.player()
        other = self.library.create_playlist("Keepers")
        self.assertTrue(player._handle_html_music_command({"operation": "add_tracks", "playlist_id": other, "track_ids": self.tracks[:2]}))
        self.assertTrue(player._handle_html_music_command({"operation": "move_tracks", "playlist_id": self.playlist,
                                                          "positions": [3], "to": 0}))
        self.assertEqual(self.library.playlist(self.playlist)["tracks"][0], self.tracks[3])
        self.library.set_duration(self.tracks[2], 4000)
        player._handle_html_music_command({"operation": "set_resume", "track_id": self.tracks[2], "position": 900})
        self.assertEqual(self.library.resume_at(self.tracks[2]), 900)
        self.assertIn("stats", player._html_music_snapshot())


class PageTests(unittest.TestCase):
    """The page itself, in the real deck against a real library (the music
    player tests' harness, borrowed rather than inherited)."""

    setUpClass = classmethod(BrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(BrowserTests.tearDownClass.__func__)
    setUp = test_music_player.Folder.setUp
    deck = BrowserTests.deck

    def open_music(self):
        deck = self.deck()
        deck.page.locator('.nav-item[data-page="music"]').click()
        deck.page.wait_for_selector(".music-row")
        return deck

    def test_a_double_click_plays_the_row_it_started_on(self):
        deck = self.open_music()
        deck.page.locator(".music-row").nth(1).dblclick()
        deck.page.wait_for_function("window.voidcompassMusic.state().playing")
        self.assertEqual(deck.page.evaluate("window.voidcompassMusic.state().currentId"), deck.tracks[1],
                         "the selection bar never moves the rows under the pointer")

    def test_select_then_queue_then_play_next(self):
        deck = self.open_music()
        page = deck.page
        page.locator(".music-row").nth(0).dblclick()
        page.wait_for_function("window.voidcompassMusic.state().playing")
        page.locator(".music-row").nth(2).click()
        self.assertFalse(page.locator("#music-selection").is_hidden())
        page.click('[data-sel="next"]')
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().queue"), [deck.tracks[2]])
        self.assertEqual(page.locator("#music-upnext li").first.get_attribute("data-upnext"), deck.tracks[2])
        page.click("#music-next")
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{deck.tracks[2]}'")
        page.click("#music-next")
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{deck.tracks[1]}'")

    def test_shift_selects_a_run_and_delete_removes_it(self):
        deck = self.open_music()
        page = deck.page
        page.locator(".music-row").nth(0).click()
        page.locator(".music-row").nth(2).click(modifiers=["Shift"])
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().selected"), [0, 1, 2])
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        removes = [row for row in deck.commands if row.get("operation") == "remove_tracks"]
        self.assertEqual(removes[-1]["positions"], [0, 1, 2])

    def test_drag_a_row_to_reorder(self):
        deck = self.open_music()
        page = deck.page
        page.locator(".music-row").nth(2).drag_to(page.locator(".music-row").nth(0), target_position={"x": 40, "y": 4})
        page.wait_for_timeout(200)
        moves = [row for row in deck.commands if row.get("operation") == "move_tracks"]
        self.assertTrue(moves, "a drag sends a move")
        self.assertEqual((moves[-1]["positions"], moves[-1]["to"]), ([2], 0))

    def test_sorting_is_only_a_view(self):
        deck = self.open_music()
        page = deck.page
        page.click('[data-sort="title"]')
        page.click('[data-sort="title"]')
        self.assertEqual(page.locator(".music-row .music-name b").all_inner_texts(), ["Track 3", "Track 2", "Track 1"])
        self.assertEqual(page.locator(".music-row[draggable='true']").count(), 0, "no dragging out of the playlist's order")
        self.assertFalse([row for row in deck.commands if row.get("operation") in {"move_track", "move_tracks"}])

    def test_smart_lists_and_recently_played(self):
        deck = self.open_music()
        page = deck.page
        now = time.time()
        deck.state["music"]["stats"] = {"revision": 7, "plays": {deck.tracks[0]: [3, now - 60]},
                                        "recent": [{"at": now - 60, "track_id": deck.tracks[0], "title": "Track 1", "artist": "Band 1",
                                                    "system": "Colonia"}], "listening": {"week_s": 3600, "all_s": 7200}}
        deck.server.publish(deck.state)
        page.wait_for_function("document.querySelectorAll('.music-smart').length === 6")
        page.click('[data-playlist="smart:most"]')
        self.assertEqual(page.locator(".music-row .music-name b").all_inner_texts(), ["Track 1"])
        page.click('[data-playlist="recent"]')
        self.assertEqual(page.locator(".music-where").all_inner_texts(), ["Colonia"])
        self.assertIn("1.0 h", page.locator("#music-listening").inner_text())

    def test_a_long_mix_starts_where_it_was_left(self):
        def prepare(library, tracks):
            library.set_duration(tracks[1], 3600)
            library.set_resume(tracks[1], 1800)
        deck = self.deck(prepare=prepare)
        page = deck.page
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        self.assertIn("AT 30:00", page.locator(".music-row").nth(1).inner_text())
        self.assertTrue(page.locator('.music-row >> nth=1 >> [data-from-start]').count())
        page.locator(".music-row").nth(1).dblclick()
        page.wait_for_function("window.voidcompassMusic.audio.currentTime > 1")


    def test_the_visualizer_has_looks_to_pick_from(self):
        deck = self.open_music()
        page = deck.page
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.locator(".music-row").nth(0).dblclick()
        page.wait_for_function("window.voidcompassMusic.audio.currentTime > .3")
        painted = """() => {
          const canvas = document.getElementById('music-visualizer');
          const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
          let ink = 0;
          for (let i = 3; i < data.length; i += 4) ink += data[i];
          return ink > 0;
        }"""
        self.assertEqual(page.inner_text("#music-viz span"), "BARS")
        looks = page.eval_on_selector_all("#music-viz-list [data-viz]", "nodes => nodes.map((node) => node.dataset.viz)")
        self.assertEqual(len(looks), 12)
        self.assertIn("ELITE", page.text_content("#music-viz-list"), "the Elite looks have their own heading")
        shots = os.environ.get("VOIDCOMPASS_VIZ_SHOTS")
        for look in looks:
            page.click("#music-viz")
            page.click(f'#music-viz-list [data-viz="{look}"]')
            page.wait_for_timeout(400)
            self.assertEqual(page.inner_text("#music-viz span"), look.upper())
            self.assertFalse(page.evaluate("document.getElementById('music-viz-menu').open"), "picking closes the menu")
            self.assertEqual(page.evaluate(painted), look != "off", look)
            if shots:
                page.locator(".music-bar").screenshot(path=os.path.join(shots, f"viz_{look}.png"))
        page.click("#music-viz")
        page.click('#music-viz-list [data-viz="scanner"]')
        self.assertEqual(page.evaluate("localStorage.getItem('voidcompass.music.visualizer')"), "scanner", "kept per viewer")
        self.assertEqual(errors, [])


class MarkupTests(unittest.TestCase):
    def test_the_page_has_its_new_parts(self):
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for marker in ('id="music-upnext"', 'id="music-resume-mark"', 'id="music-smart"', 'id="music-listening"',
                       'id="music-selection"', 'id="music-add-menu"', 'id="music-more-menu"'):
            self.assertIn(marker, page)
        self.assertNotIn("data-move=", (ROOT / "web" / "dashboard" / "music.js").read_text(encoding="utf-8"),
                         "the ▲ ▼ buttons gave way to dragging")



class SpotifyLayoutTests(unittest.TestCase):
    def test_library_list_now_playing_and_the_bar(self):
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        music = page.split('data-page-name="music"', 1)[1].split('data-page-name=', 1)[0]
        for marker in ('class="music-shell"', 'class="music-side"', 'id="music-hero"', 'id="music-list-play"',
                       'class="music-now-panel"', 'class="music-deck music-bar', 'data-playlist="follow"'):
            self.assertIn(marker, music)
        for control in ("music-play", "music-seek", "music-volume", "music-shuffle", "music-repeat", "music-level",
                        "music-find", "music-upnext", "music-cover", "music-title", "music-tracks"):
            self.assertEqual(music.count(f'id="{control}"'), 1, control)


if __name__ == "__main__":
    unittest.main()
