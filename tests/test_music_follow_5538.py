"""Music that flies with you (5.5.3.8): a playlist for each scene the game is
in, faded across as it changes; quieter in hyperspace."""
from __future__ import annotations

from pathlib import Path
import unittest

from tests import test_music_player as base
from voidcompass.core import config as config_module
from voidcompass.services.music_scenes import (
    BEING_INTERDICTED, DOCKED, FSD_JUMP, IN_DANGER, IN_SRV, LANDED, ON_FOOT_IN_STATION, ON_FOOT_ON_PLANET,
    SCENES, SUPERCRUISE, follow_settings, scene_of,
)

ROOT = Path(__file__).resolve().parents[1]


class SceneTests(unittest.TestCase):
    def test_what_the_game_is_doing(self):
        cases = [
            ((DOCKED, 0, 5000), "docked"),
            ((0, ON_FOOT_IN_STATION, 5000), "docked"),
            ((LANDED, 0, 0), "surface"),
            ((IN_SRV, 0, None), "surface"),
            ((0, ON_FOOT_ON_PLANET, 0), "surface"),
            ((SUPERCRUISE, 0, 120000), "space"),
            ((SUPERCRUISE, 0, 0), "deep"),
            ((1 << 24, 0, None), "space"),  # in the ship, population unknown
            ((SUPERCRUISE | IN_DANGER, 0, 0), "combat"),
            ((BEING_INTERDICTED | SUPERCRUISE, 0, 9), "combat"),
            ((DOCKED | IN_DANGER, 0, 9), "combat"),
        ]
        for (flags, flags2, population), expected in cases:
            with self.subTest(expected=expected, flags=flags):
                self.assertEqual(scene_of(flags, flags2, population)["scene"], expected)

    def test_hyperspace_and_nothing_yet(self):
        self.assertTrue(scene_of(FSD_JUMP | (1 << 24), 0, 0)["jumping"])
        self.assertEqual(scene_of(0, 0), {"scene": "", "jumping": False}, "no Status.json yet: no scene")

    def test_settings_kept_sane(self):
        self.assertEqual(follow_settings({}), {"on": False, "playlists": dict.fromkeys(SCENES, ""),
                                                 "tracks": dict.fromkeys(SCENES, ""), "fade_s": 2, "duck": True})
        odd = follow_settings({"music_follow_game": True, "music_follow_fade_s": 99, "music_scene_playlists": "nope"})
        self.assertEqual((odd["on"], odd["fade_s"], odd["playlists"]["combat"]), (True, 2, ""))


class CommandTests(base.Folder):
    def test_set_from_the_music_page(self):
        player = base.Player(self.folder)
        library = player.music_library()
        playlist = library.create_playlist("Battle")
        command = player._handle_html_music_command
        self.assertTrue(command({"operation": "follow_set", "key": "music_follow_game", "value": True}))
        self.assertTrue(command({"operation": "follow_set", "key": "combat", "value": playlist}))
        self.assertFalse(command({"operation": "follow_set", "key": "combat", "value": "no-such-list"}))
        self.assertTrue(command({"operation": "follow_set", "key": "docked", "value": ""}), "back to Keep playing")
        self.assertTrue(command({"operation": "follow_set", "key": "music_follow_fade_s", "value": "4"}))
        self.assertFalse(command({"operation": "follow_set", "key": "music_follow_fade_s", "value": "3"}))
        self.assertFalse(command({"operation": "follow_set", "key": "volume", "value": 5}))
        follow = player._html_music_snapshot()["follow"]
        self.assertEqual((follow["on"], follow["playlists"]["combat"], follow["fade_s"]), (True, playlist, 4))

    def test_a_song_of_its_own_for_a_scene(self):
        player = base.Player(self.folder)
        library = player.music_library()
        battle = library.create_playlist("Battle")
        files = [base.make_wav(self.folder / "music" / f"Battle {n}.wav", seconds=2) for n in (1, 2)]
        library.add_files(battle, files)
        library.wait_idle()
        theme = library.playlist(battle)["tracks"][1]
        command = player._handle_html_music_command
        self.assertFalse(command({"operation": "follow_set", "key": "track:combat", "value": theme}), "no playlist chosen yet")
        command({"operation": "follow_set", "key": "combat", "value": battle})
        self.assertTrue(command({"operation": "follow_set", "key": "track:combat", "value": theme}))
        self.assertFalse(command({"operation": "follow_set", "key": "track:combat", "value": "0123456789abcdef"}), "not in its playlist")
        self.assertFalse(command({"operation": "follow_set", "key": "track:nowhere", "value": theme}))
        self.assertEqual(player._html_music_snapshot()["follow"]["tracks"]["combat"], theme)
        other = library.create_playlist("Calm")
        command({"operation": "follow_set", "key": "combat", "value": other})
        self.assertEqual(player._html_music_snapshot()["follow"]["tracks"]["combat"], "", "another playlist: the song goes")
        self.assertIn("music_scene_tracks", config_module.PROFILE_SETTINGS)

    def test_the_snapshot_carries_the_scene(self):
        player = base.Player(self.folder)
        player.current_status_flags, player.current_status_flags2 = SUPERCRUISE, 0
        player._music_observe("FSDJump", {"event": "FSDJump", "StarSystem": "Far", "Population": 0})
        snapshot = player._html_music_snapshot()
        self.assertEqual((snapshot["scene"], snapshot["jumping"]), ("deep", False))
        player._music_observe("FSDJump", {"event": "FSDJump", "StarSystem": "Sol", "Population": 22780919531})
        self.assertEqual(player._html_music_snapshot()["scene"], "space")

    def test_every_setting_follows_the_commander(self):
        for key in ("music_follow_game", "music_jump_duck", "music_scene_playlists", "music_follow_fade_s"):
            self.assertIn(key, config_module.PROFILE_SETTINGS)


class FollowBrowserTests(base.BrowserTests):
    """The real page: switching playlists with the game, fading, ducking."""

    def two_lists(self, settings=None):
        def prepare(library, _tracks):
            battle = library.create_playlist("Battle")
            files = [base.make_wav(self.folder / "music" / f"Battle {n}.wav", seconds=6) for n in (1, 2)]
            library.add_files(battle, files)
            library.wait_idle()
            self.battle = battle
        return self.deck(settings=settings, prepare=prepare)

    def publish(self, deck, scene, jumping=False, on=True, fade_s=1, tracks=None):
        deck.state["music"].update(follow={"on": on, "playlists": {"combat": self.battle, "docked": deck.playlist},
                                           "tracks": tracks or {}, "fade_s": fade_s, "duck": True}, scene=scene, jumping=jumping)
        deck.server.publish(deck.state)

    def test_combat_switches_playlists_and_back(self):
        deck = self.two_lists()
        page = deck.page
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        page.locator(".music-row").nth(1).dblclick()
        page.wait_for_function("window.voidcompassMusic.state().playing")
        self.publish(deck, "space")
        page.wait_for_timeout(500)
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().playlistId"), deck.playlist, "space: keep playing")
        self.publish(deck, "combat")
        page.wait_for_function(f"window.voidcompassMusic.state().playlistId === '{self.battle}'", timeout=8000)
        page.wait_for_function("!window.voidcompassMusic.state().switching && window.voidcompassMusic.state().playing", timeout=8000)
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().fadeMix"), 1, "faded back up")
        # Docking again: the first playlist, back on the track it was playing.
        self.publish(deck, "docked")
        page.wait_for_function(f"window.voidcompassMusic.state().playlistId === '{deck.playlist}'", timeout=12000)
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().currentId"), deck.tracks[1])
        self.assertIn("NOW: DOCKED", page.locator("#music-follow header b").inner_text())

    def test_it_never_starts_by_itself_and_ducks_for_hyperspace(self):
        deck = self.two_lists()
        page = deck.page
        page.wait_for_function("window.voidcompassMusic.state().revision >= 0")
        self.publish(deck, "combat")
        page.wait_for_timeout(800)
        state = page.evaluate("window.voidcompassMusic.state()")
        self.assertFalse(state["playing"], "paused stays paused")
        self.publish(deck, "space", jumping=True)
        page.wait_for_function("window.voidcompassMusic.state().duckMix < .35", timeout=10000)
        self.publish(deck, "space", jumping=False)
        page.wait_for_function("window.voidcompassMusic.state().duckMix > .99", timeout=10000)

    def test_a_scenes_song_starts_from_the_top(self):
        deck = self.two_lists()
        page = deck.page
        theme = deck.library.playlist(self.battle)["tracks"][1]
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        page.locator(".music-row").first.dblclick()
        page.wait_for_function("window.voidcompassMusic.state().playing")
        self.publish(deck, "combat", tracks={"combat": theme})
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{theme}'", timeout=8000)
        page.wait_for_function("!window.voidcompassMusic.state().switching", timeout=8000)
        self.assertLess(page.evaluate("window.voidcompassMusic.audio.currentTime"), 2.5, "from the top")
        self.assertEqual(page.locator('#music-follow select[data-follow="track:combat"]').input_value(), theme)
        # Docked: back to the first playlist; combat again: the song again.
        self.publish(deck, "docked", tracks={"combat": theme})
        page.wait_for_function(f"window.voidcompassMusic.state().playlistId === '{deck.playlist}'", timeout=12000)
        page.wait_for_function("!window.voidcompassMusic.state().switching", timeout=8000)
        self.publish(deck, "combat", tracks={"combat": theme})
        page.wait_for_function(f"window.voidcompassMusic.state().currentId === '{theme}'", timeout=8000)

    def test_off_means_off(self):
        deck = self.two_lists()
        page = deck.page
        page.locator('.nav-item[data-page="music"]').click()
        page.wait_for_selector(".music-row")
        page.locator(".music-row").first.dblclick()
        page.wait_for_function("window.voidcompassMusic.state().playing")
        self.publish(deck, "combat", on=False)
        page.wait_for_timeout(1200)
        self.assertEqual(page.evaluate("window.voidcompassMusic.state().playlistId"), deck.playlist)
        self.assertIn("OFF", page.locator("#music-follow header b").inner_text())


# The inherited browser tests already run in test_music_player.
for _name in [name for name in dir(base.BrowserTests) if name.startswith("test_")]:
    if _name in FollowBrowserTests.__dict__:
        continue
    setattr(FollowBrowserTests, _name, None)


if __name__ == "__main__":
    unittest.main()
