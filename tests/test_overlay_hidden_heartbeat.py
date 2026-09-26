"""Hidden overlays are not reloaded for being throttled.

Chromium runs a hidden page's timers once a second, and once a minute after
five minutes hidden. The watchdog used the visible 4 s heartbeat for every
overlay, so from the five-minute mark it reloaded each waiting overlay every
12 s, leaving it mid-reload just when it should appear.
"""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from voidcompass.overlays.html_overlay_runtime import HtmlOverlaySurface


class _Server:
    def __init__(self):
        self.visible = False
        self.seen_at = 0.0

    def window_visible(self, _overlay_id):
        return self.visible

    def last_client_seen(self, _overlay_id):
        return self.seen_at

    def is_ready(self, _overlay_id):
        return True

    def rendered_revision(self, _overlay_id):
        return 3


def _surface(server):
    surface = HtmlOverlaySurface.__new__(HtmlOverlaySurface)
    surface.overlay_id = "gravity"
    surface.root = SimpleNamespace(_voidcompass_startup_presentation_held=False)
    surface._disposed = False
    surface._visible_since = None
    surface._renderer_seen = True
    surface._renderer_lost_at = None
    surface._reload_attempts = 0
    surface._started_at = 0.0
    reloads = []
    surface.runtime = SimpleNamespace(
        server=server, is_alive=lambda: True,
        request_surface_reload=lambda surface, reason: reloads.append(reason),
        request_recovery=lambda reason: reloads.append(reason),
    )
    return surface, reloads


class HiddenHeartbeatTests(unittest.TestCase):
    def ready_at(self, surface, now):
        with patch("voidcompass.overlays.html_overlay_runtime.time.monotonic", return_value=now):
            return surface.ready

    def failed_at(self, surface, now):
        with patch("voidcompass.overlays.html_overlay_runtime.time.monotonic", return_value=now):
            return surface.startup_failed

    def test_a_throttled_hidden_overlay_stays_ready_and_is_not_reloaded(self):
        server = _Server()
        surface, reloads = _surface(server)
        server.seen_at = 1000.0
        # Silent for 30 s, as a page throttled to one poll a minute is.
        self.assertTrue(self.ready_at(surface, 1030.0))
        self.failed_at(surface, 1033.0)
        self.failed_at(surface, 1045.0)
        self.assertEqual(reloads, [])
        # Beyond even the throttled allowance the page is presumed lost.
        self.ready_at(surface, 1080.0)
        self.failed_at(surface, 1083.0)
        self.assertEqual(len(reloads), 1)

    def test_a_shown_overlay_gets_time_to_wake_then_the_visible_heartbeat(self):
        server = _Server()
        surface, reloads = _surface(server)
        server.seen_at = 1000.0
        server.visible = True
        # Just shown: its page may still be waking from throttling.
        self.assertTrue(self.ready_at(surface, 1030.0))
        self.assertTrue(self.ready_at(surface, 1034.0))
        server.seen_at = 1034.5
        self.assertTrue(self.ready_at(surface, 1036.0))
        # Settled on screen: the 4 s heartbeat applies again.
        self.assertTrue(self.ready_at(surface, 1038.0))
        self.ready_at(surface, 1039.0)
        self.failed_at(surface, 1042.0)
        self.assertEqual(len(reloads), 1)

    def test_hiding_resets_the_settle_period(self):
        server = _Server()
        surface, _reloads = _surface(server)
        server.visible = True
        server.seen_at = 1000.0
        self.ready_at(surface, 1000.0)
        server.visible = False
        self.ready_at(surface, 1010.0)
        self.assertIsNone(surface._visible_since)


if __name__ == "__main__":
    unittest.main()
