"""5.6.8: a stable shared timestamp for the start of music."""

import unittest
from unittest.mock import patch

from voidcompass.dashboard.html_music import HtmlMusicMixin


class MusicStartTests(unittest.TestCase):
    def test_timestamp_changes_only_when_playback_starts_or_stops(self):
        class Deck(HtmlMusicMixin):
            def _music_remember(self, _status):
                pass

            def _music_update_overlay(self):
                pass

        deck = Deck()
        with patch("voidcompass.dashboard.html_music.time.time", side_effect=[1000, 2000]):
            deck._music_status_report({"playing": True})
            self.assertEqual(deck._hatchling_music_started_at, 1000)
            deck._music_status_report({"playing": True})
            self.assertEqual(deck._hatchling_music_started_at, 1000)
            deck._music_status_report({"playing": False})
            self.assertIsNone(deck._hatchling_music_started_at)
            deck._music_status_report({"playing": True})
            self.assertEqual(deck._hatchling_music_started_at, 2000)


if __name__ == "__main__":
    unittest.main()
